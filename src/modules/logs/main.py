import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from modules.ai.agent_factory import create_agent
from modules.logs.models import ChunkAnalysisResult, LogChunk
from modules.logs.promps import (
    COORDINATOR_AGENT_PROMPT,
    TRIAGE_PROMPT,
    WORKER_AGENT_PROMPT,
)
from modules.logs.tools import register_error_for_fix
from settings import MAX_CHUNKS_TO_PROCESS, Models

logger = logging.getLogger(__name__)

logs_client = boto3.client("logs")

MAX_RESULTS_PER_QUERY = 10000

CHUNK_SIZE = 2000
MAX_PARALLEL_WORKERS = 5
WORKER_TIMEOUT_SECONDS = 300
DEFAULT_CW_SQL = "fields @timestamp, @message | sort @timestamp asc"

def to_unix_seconds(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def explain_query_status(status: str) -> str:
    """
    Provide human-readable explanation for CloudWatch Insights query status.

    Args:
        status: Query status from AWS (Complete, Failed, Cancelled, Timeout, Unknown)

    Returns:
        Explanation of what the status means and suggested actions
    """
    status_explanations = {
        "Failed": "Query execution failed due to an internal error or invalid query",
        "Cancelled": "Query was cancelled before completion (possibly by another process)",
        "Timeout": "Query exceeded the maximum execution time limit (15 minutes)",
        "Unknown": "Query is in an unknown state (possibly due to service issues)",
    }

    explanation = status_explanations.get(
        status,
        f"Query ended with unexpected status: {status}"
    )

    return f"{explanation}. Check CloudWatch Logs console for more details."


def insights_query(log_group: str, start: datetime, end: datetime, query: str, limit: int = 10000):
    resp = logs_client.start_query(
        logGroupName=log_group,
        startTime=to_unix_seconds(start),
        endTime=to_unix_seconds(end),
        queryString=query,
        limit=limit,
    )
    qid = resp["queryId"]

    while True:
        r = logs_client.get_query_results(queryId=qid)
        if r["status"] in ["Complete", "Failed", "Cancelled", "Timeout", "Unknown"]:
            return r["status"], r.get("results", [])
        time.sleep(1)


def calculate_payload_size(data: dict) -> tuple[int, float, float]:
    """
    Calculate size of JSON payload in bytes, KB, and MB.

    Args:
        data: Dictionary to be serialized to JSON

    Returns:
        Tuple of (bytes, kilobytes, megabytes)
    """
    json_str = json.dumps(data)
    size_bytes = len(json_str.encode("utf-8"))
    size_kb = size_bytes / 1024
    size_mb = size_kb / 1024
    return size_bytes, size_kb, size_mb


def create_empty_result_metadata() -> tuple[str, dict]:
    """
    Create standard response for empty query results.

    Returns:
        Tuple of (message, metadata_dict)
    """
    return (
        "No logs found to analyze.",
        {
            "chunks_processed": 0,
            "records_analyzed": 0,
            "processing_time_seconds": 0.0,
            "chunks_failed": 0,
        },
    )


def parse_log_entry(row: list[dict]) -> dict[str, str]:
    """Parse a single log entry, excluding internal fields."""
    return {field["field"]: field["value"] for field in row if field["field"] != "@ptr"}


def query_chunk_recursively(log_group: str, start: datetime, end: datetime, query: str, depth: int = 0) -> list[list[dict]]:
    """
    Queries a time chunk and subdivides it recursively if it hits the result limit.
    Returns all log entries for the given time range.
    """
    indent = "  " * depth
    logger.info(f"{indent}Querying: {start} to {end}")

    try:
        status, rows = insights_query(
            log_group,
            start=start,
            end=end,
            query=query,
            limit=MAX_RESULTS_PER_QUERY
        )
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))

        if error_code == 'MalformedQueryException':
            logger.error(
                f"{indent}Query syntax error: CloudWatch Insights query is malformed. "
                f"Check query syntax: '{query}'"
            )
            return []

        logger.error(
            f"{indent}AWS API error [{error_code}]: {error_message}"
        )
        return []

    if status != "Complete":
        explanation = explain_query_status(status)
        logger.error(f"{indent}Query failed with status '{status}': {explanation}")
        return []

    records_count = len(rows)
    logger.info(f"{indent}Retrieved {records_count} records")

    if records_count >= MAX_RESULTS_PER_QUERY:
        logger.warning(f"{indent}Hit limit of {MAX_RESULTS_PER_QUERY}. Subdividing chunk...")

        # Subdivide in half
        midpoint = start + (end - start) / 2

        logger.info(f"{indent}Subdividing into 2 chunks:")
        first_half = query_chunk_recursively(log_group, start, midpoint, query, depth + 1)
        second_half = query_chunk_recursively(log_group, midpoint, end, query, depth + 1)

        return first_half + second_half

    return rows


def create_log_chunks(all_records: list[dict], chunk_size: int = CHUNK_SIZE) -> list[LogChunk]:
    """
    Split parsed log records into chunks for parallel processing.

    Args:
        all_records: List of parsed log dictionaries
        chunk_size: Number of logs per chunk

    Returns:
        List of LogChunk objects with metadata
    """
    if not all_records:
        return []

    chunks = []
    total_chunks = (len(all_records) + chunk_size - 1) // chunk_size

    for i in range(0, len(all_records), chunk_size):
        chunk_logs = all_records[i : i + chunk_size]

        start_ts = chunk_logs[0].get("@timestamp")
        end_ts = chunk_logs[-1].get("@timestamp")

        chunk = LogChunk(
            chunk_index=len(chunks),
            total_chunks=total_chunks,
            chunk_size=len(chunk_logs),
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            logs=chunk_logs,
        )
        chunks.append(chunk)

    logger.info(f"Created {len(chunks)} chunks from {len(all_records)} records")
    for chunk in chunks:
        logger.info(
            f"  Chunk {chunk.chunk_index + 1}/{chunk.total_chunks}: "
            f"{chunk.chunk_size} records ({chunk.get_time_range_description()})"
        )

    return chunks


def analyze_chunk_with_worker(
    chunk: LogChunk, question: str, log_group: str, global_metadata: dict
) -> ChunkAnalysisResult:
    """
    Analyze a single chunk of logs using a worker agent.

    Args:
        chunk: LogChunk object with logs and metadata
        question: User's question about the logs
        log_group: CloudWatch log group name
        global_metadata: Overall context (total records, time range, etc.)

    Returns:
        ChunkAnalysisResult with analysis or error details
    """
    start_time = time.time()
    chunk_id = f"Chunk {chunk.chunk_index + 1}/{chunk.total_chunks}"

    logger.info(f"[{chunk_id}] Starting worker analysis...")

    try:
        worker_prompt = WORKER_AGENT_PROMPT.format(
            chunk_index=chunk.chunk_index + 1,
            total_chunks=chunk.total_chunks,
            chunk_size=chunk.chunk_size,
            time_range=chunk.get_time_range_description(),
            question=question,
        )

        worker_agent = create_agent(
            system_prompt=worker_prompt,
            model=Models.CLAUDE_45,
            temperature=0.3,
            read_timeout=WORKER_TIMEOUT_SECONDS,
        )

        chunk_context = {
            "metadata": {
                "log_group": log_group,
                "chunk_index": chunk.chunk_index + 1,
                "total_chunks": chunk.total_chunks,
                "chunk_time_range": chunk.get_time_range_description(),
                "chunk_size": chunk.chunk_size,
                "global_time_range": global_metadata["period"],
                "total_records_in_dataset": global_metadata["total_records"],
            },
            "logs": chunk.logs,
        }

        context_json = json.dumps(chunk_context)
        context_bytes, context_size_kb, _ = calculate_payload_size(chunk_context)
        logger.info(f"[{chunk_id}] Payload size: {context_size_kb:.2f} KB ({context_bytes:,} bytes)")

        prompt = [
            {"text": f"Question: {question}"},
            {"text": f"Log context: {context_json}"},
            {"text": "Analyze this chunk of logs according to the guidelines in your system prompt."},
        ]

        result = worker_agent(prompt=prompt)
        analysis = str(result)  # Convert AgentResult to string

        processing_time = time.time() - start_time
        logger.info(f"[{chunk_id}] Completed in {processing_time:.2f}s")

        return ChunkAnalysisResult(
            chunk_index=chunk.chunk_index,
            chunk_time_range=chunk.get_time_range_description(),
            chunk_size=chunk.chunk_size,
            analysis=analysis,
            success=True,
            processing_time_seconds=processing_time,
        )

    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"[{chunk_id}] Failed after {processing_time:.2f}s: {error_msg}")

        return ChunkAnalysisResult(
            chunk_index=chunk.chunk_index,
            chunk_time_range=chunk.get_time_range_description(),
            chunk_size=chunk.chunk_size,
            analysis="",
            success=False,
            error_message=error_msg,
            processing_time_seconds=processing_time,
        )


def consolidate_with_coordinator(
    chunk_results: list[ChunkAnalysisResult],
    question: str,
    log_group: str,
    start: datetime,
    end: datetime,
    total_records: int,
) -> str:
    """
    Use coordinator agent to synthesize chunk analyses into final answer.

    Args:
        chunk_results: List of ChunkAnalysisResult from workers
        question: User's original question
        log_group: CloudWatch log group name
        start: Start datetime of query
        end: End datetime of query
        total_records: Total number of log records

    Returns:
        Final consolidated analysis as string
    """
    logger.info("Starting coordinator consolidation...")

    successful_results = [r for r in chunk_results if r.success]
    failed_results = [r for r in chunk_results if not r.success]

    if not successful_results:
        error_summary = "\n".join(
            [f"- Chunk {r.chunk_index + 1}: {r.error_message}" for r in failed_results]
        )
        return f"ERROR: All chunks failed to process.\n\nFailures:\n{error_summary}"

    coordinator_prompt = COORDINATOR_AGENT_PROMPT.format(
        chunks_processed=len(successful_results),
        total_records=total_records,
        time_range=f"{start.isoformat()} to {end.isoformat()}",
        total_chunks=len(chunk_results),
    )

    coordinator = create_agent(
        system_prompt=coordinator_prompt,
        model=Models.CLAUDE_45,
        temperature=0.3,
        read_timeout=WORKER_TIMEOUT_SECONDS,
    )

    coordinator_context = {
        "metadata": {
            "log_group": log_group,
            "time_range": f"{start.isoformat()} to {end.isoformat()}",
            "total_records": total_records,
            "total_chunks": len(chunk_results),
            "successful_chunks": len(successful_results),
            "failed_chunks": len(failed_results),
        },
        "chunk_analyses": [
            {
                "chunk_index": r.chunk_index + 1,
                "time_range": r.chunk_time_range,
                "size": r.chunk_size,
                "analysis": r.analysis,
                "processing_time": f"{r.processing_time_seconds:.2f}s",
            }
            for r in successful_results
        ],
    }

    if failed_results:
        coordinator_context["failed_chunks"] = [
            {"chunk_index": r.chunk_index + 1, "error": r.error_message} for r in failed_results
        ]

    context_json = json.dumps(coordinator_context)
    context_bytes, context_size_kb, _ = calculate_payload_size(coordinator_context)
    logger.info(f"Coordinator payload size: {context_size_kb:.2f} KB ({context_bytes:,} bytes)")

    prompt = [
        {"text": f"Original Question: {question}"},
        {"text": f"Chunk Analyses: {context_json}"},
        {"text": "Synthesize these chunk analyses to answer the user's question."},
    ]

    result = coordinator(prompt=prompt)
    logger.info("Coordinator consolidation completed")

    return str(result)  # Convert AgentResult to string


def ask_to_log_parallel(
    log_group: str,
    question: str,
    start: datetime,
    end: datetime,
    cloudwatch_sql: str = DEFAULT_CW_SQL,
    chunk_size: int = CHUNK_SIZE,
    max_workers: int = MAX_PARALLEL_WORKERS,
) -> tuple[str, dict]:
    """
    Parallel version of ask_to_log using chunked processing with worker-coordinator pattern.

    Args:
        log_group: CloudWatch log group name
        question: User's question about the logs
        start: Start datetime for query
        end: End datetime for query
        cloudwatch_sql: CloudWatch Insights query string (default: DEFAULT_CW_SQL)
        chunk_size: Number of logs per chunk (default: 5000)
        max_workers: Maximum parallel workers (default: 5)

    Returns:
        tuple: (analysis_text, metadata_dict)
    """
    overall_start = time.time()

    logger.info(f"Logging from group: {log_group}. Period: {start} to {end}")
    logger.info(f"Using parallel processing: chunk_size={chunk_size}, max_workers={max_workers}")

    all_records = query_chunk_recursively(
        log_group, start, end, query=cloudwatch_sql
    )

    total_count = len(all_records)
    logger.info(f"Total records retrieved: {total_count}")

    if total_count == 0:
        logger.warning("No records found for the specified time range")
        return create_empty_result_metadata()

    if total_count > 10000:
        logger.warning(
            f"Analyzing {total_count} records using parallel processing. "
            f"This will create ~{(total_count + chunk_size - 1) // chunk_size} chunks."
        )

    all_logs = [parse_log_entry(r) for r in all_records]

    global_metadata = {
        "log_group": log_group,
        "period": f"{start.isoformat()} to {end.isoformat()}",
        "total_records": total_count,
    }

    chunks = create_log_chunks(all_logs, chunk_size=chunk_size)

    # Check if exceeds maximum chunks limit
    if len(chunks) > MAX_CHUNKS_TO_PROCESS:
        error_msg = (
            f"Dataset would generate {len(chunks)} chunks, which exceeds the maximum limit "
            f"of {MAX_CHUNKS_TO_PROCESS} chunks.\n\n"
            f"Options:\n"
            f"  1. Reduce time range to analyze fewer logs\n"
            f"  2. Increase MAX_CHUNKS_TO_PROCESS in settings or via environment variable\n"
            f"  3. Use more specific CloudWatch Insights filters\n\n"
            f"Current dataset: {total_count} records, chunk size: {chunk_size}"
        )
        logger.error(error_msg)
        return (
            f"ERROR: {error_msg}",
            {
                "chunks_processed": 0,
                "records_analyzed": total_count,
                "processing_time_seconds": 0.0,
                "chunks_failed": 0,
                "error": "MAX_CHUNKS_TO_PROCESS exceeded",
            },
        )

    if len(chunks) == 1:
        logger.info("Only one chunk - using single-agent processing instead")
        return ask_to_log(log_group, question, start, end, cloudwatch_sql=cloudwatch_sql)

    logger.info(f"Processing {len(chunks)} chunks with up to {max_workers} parallel workers...")
    chunk_results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_chunk = {
            executor.submit(analyze_chunk_with_worker, chunk, question, log_group, global_metadata): chunk
            for chunk in chunks
        }

        for future in as_completed(future_to_chunk):
            chunk = future_to_chunk[future]
            try:
                result = future.result()
                chunk_results.append(result)
            except Exception as e:
                logger.error(f"Unexpected error processing chunk {chunk.chunk_index + 1}: {e}")
                chunk_results.append(
                    ChunkAnalysisResult(
                        chunk_index=chunk.chunk_index,
                        chunk_time_range=chunk.get_time_range_description(),
                        chunk_size=chunk.chunk_size,
                        analysis="",
                        success=False,
                        error_message=f"Unexpected error: {str(e)}",
                        processing_time_seconds=0.0,
                    )
                )

    chunk_results.sort(key=lambda r: r.chunk_index)

    logger.info("All chunks processed. Starting consolidation...")
    final_analysis = consolidate_with_coordinator(
        chunk_results, question, log_group, start, end, total_count
    )

    total_time = time.time() - overall_start
    successful = sum(1 for r in chunk_results if r.success)
    failed = sum(1 for r in chunk_results if not r.success)

    logger.info(f"\n=== Processing Summary ===")
    logger.info(f"Total records: {total_count}")
    logger.info(f"Chunks processed: {successful}/{len(chunks)}")
    if failed > 0:
        logger.warning(f"Chunks failed: {failed}")
    logger.info(f"Total processing time: {total_time:.2f}s")
    logger.info(
        f"Average time per chunk: {sum(r.processing_time_seconds for r in chunk_results) / len(chunk_results):.2f}s"
    )

    logger.info(f"\n=== AI Analysis ===")

    metadata = {
        "chunks_processed": successful,
        "records_analyzed": total_count,
        "processing_time_seconds": total_time,
        "chunks_failed": failed,
    }

    return final_analysis, metadata


def ask_to_log(
    log_group: str,
    question: str,
    start: datetime,
    end: datetime,
    cloudwatch_sql: str = DEFAULT_CW_SQL,
) -> tuple[str, dict]:
    """
    Main entry point for log analysis. Automatically routes to parallel processing
    for large datasets (> CHUNK_SIZE records).

    Args:
        log_group: CloudWatch log group name
        question: User's question about the logs
        start: Start datetime for query
        end: End datetime for query
        cloudwatch_sql: CloudWatch Insights query string (default: DEFAULT_CW_SQL)

    Returns:
        tuple: (analysis_text, metadata_dict)
    """
    logger.info(f"Logging from group: {log_group}. Period: {start} to {end}")

    all_records = query_chunk_recursively(
        log_group,
        start,
        end,
        query=cloudwatch_sql
    )

    total_count = len(all_records)
    logger.info(f"Total records retrieved: {total_count}")

    if total_count == 0:
        logger.warning("No records found for the specified time range")
        return create_empty_result_metadata()

    # Smart routing: use parallel processing for large datasets
    if total_count > CHUNK_SIZE:
        estimated_chunks = (total_count + CHUNK_SIZE - 1) // CHUNK_SIZE

        if estimated_chunks > MAX_CHUNKS_TO_PROCESS:
            error_msg = (
                f"Dataset too large ({total_count} records would create {estimated_chunks} chunks).\n"
                f"Maximum allowed: {MAX_CHUNKS_TO_PROCESS} chunks.\n\n"
                f"Suggestions:\n"
                f"  - Reduce time range\n"
                f"  - Increase MAX_CHUNKS_TO_PROCESS (currently {MAX_CHUNKS_TO_PROCESS})\n"
                f"  - Current chunk size: {CHUNK_SIZE} records"
            )
            logger.error(f"Dataset would generate {estimated_chunks} chunks, exceeding limit of {MAX_CHUNKS_TO_PROCESS}")
            return (
                f"ERROR: {error_msg}",
                {
                    "chunks_processed": 0,
                    "records_analyzed": total_count,
                    "processing_time_seconds": 0.0,
                    "chunks_failed": 0,
                    "error": "MAX_CHUNKS_TO_PROCESS exceeded",
                },
            )

        logger.info(
            f"Large dataset ({total_count} records > {CHUNK_SIZE}), routing to parallel processing"
        )
        return ask_to_log_parallel(log_group, question, start, end, cloudwatch_sql=cloudwatch_sql)

    logger.info(f"Small dataset ({total_count} records <= {CHUNK_SIZE}), using single agent")

    # Warning for large datasets
    if total_count > 1000:
        logger.warning(f"Analyzing {total_count} records. This may be expensive and slow.")

    # Parse all records for analysis
    all_logs = [parse_log_entry(r) for r in all_records]

    context = {
        "metadata": {
            "log_group": log_group,
            "period": f"{start.isoformat()} to {end.isoformat()}",
            "total_records": total_count
        },
        "logs": all_logs
    }

    # Calculate payload size
    context_json = json.dumps(context)
    context_bytes, context_size_kb, context_size_mb = calculate_payload_size(context)

    if context_size_mb >= 1:
        logger.info(f"Payload size to Claude: {context_size_mb:.2f} MB ({context_bytes:,} bytes)")
    else:
        logger.info(f"Payload size to Claude: {context_size_kb:.2f} KB ({context_bytes:,} bytes)")

    agent = create_agent(
        system_prompt=TRIAGE_PROMPT,
        model=Models.CLAUDE_45,
        tools=[register_error_for_fix]
    )

    prompt = [
        {"text": f"Question: {question}"},
        {"text": f"Log context: {context_json}"},
        {"text": "Answer the question based on the log data provided."}
    ]
    result = agent(prompt=prompt)
    logger.info(f"\n=== AI Analysis ===")

    analysis = str(result)  # Convert AgentResult to string

    metadata = {
        "chunks_processed": 1,
        "records_analyzed": total_count,
        "processing_time_seconds": 0.0,  # Could track this if needed
        "chunks_failed": 0,
    }

    return analysis, metadata




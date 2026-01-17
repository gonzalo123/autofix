import click
from datetime import datetime, timezone
from modules.logs.main import ask_to_log, DEFAULT_CW_SQL


@click.command()
@click.option("--group", type=str, required=True, help='Specify CloudWatch log group')
@click.option("--question", type=str, required=True, help='Question to ask about the logs')
@click.option("--start", type=click.DateTime(formats=["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]), required=True, help='Start datetime (YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD)')
@click.option("--end", type=click.DateTime(formats=["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]), default=None, help='End datetime (YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD). Defaults to now')
@click.option("--query", type=str, default=None, help='CloudWatch Insights query (default: "fields @timestamp, @message | sort @timestamp asc")')

def run(group: str, question: str, start: datetime, end: datetime | None, query: str | None):
    start_dt = start.replace(tzinfo=timezone.utc)
    end_dt = end.replace(tzinfo=timezone.utc) if end else datetime.now(timezone.utc)

    cloudwatch_sql = query if query else DEFAULT_CW_SQL
    analysis, metadata = ask_to_log(group, question, start_dt, end_dt, cloudwatch_sql)

    # Print analysis for CLI users
    print(analysis)

    # Print metadata summary
    print(
        f"\n[Metadata: {metadata['records_analyzed']} records, "
        f"{metadata['chunks_processed']} chunks, "
        f"{metadata['processing_time_seconds']:.1f}s]"
    )


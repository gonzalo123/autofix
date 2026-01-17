from datetime import datetime

from pydantic import BaseModel, Field


class PrTitleModel(BaseModel):
    """
    Model for generating GitHub pull request title and description.
    """
    pr_title: str = Field(..., description="Concise and descriptive title for the GitHub pull request.")
    pr_description: str = Field(..., description="Detailed description for the GitHub pull request.")


class LogEntry(BaseModel):
    """
    Model representing a log entry.
    """
    timestamp: datetime
    level: str
    fix_short_name: str = Field(...,
                                description="Short name for the git branch for fixing. It should be concise and valid as a branch name.")
    message: str

class LogChunk(BaseModel):
    """Represents a chunk of logs for parallel processing"""

    chunk_index: int
    total_chunks: int
    chunk_size: int
    start_timestamp: str | None = None
    end_timestamp: str | None = None
    logs: list[dict]

    def get_time_range_description(self) -> str:
        """Human-readable time range for this chunk"""
        if self.start_timestamp and self.end_timestamp:
            return f"{self.start_timestamp} to {self.end_timestamp}"
        return f"Chunk {self.chunk_index + 1} of {self.total_chunks}"


class ChunkAnalysisResult(BaseModel):
    """Result from a single worker agent analyzing a chunk"""

    chunk_index: int
    chunk_time_range: str
    chunk_size: int
    analysis: str
    success: bool
    error_message: str | None = None
    processing_time_seconds: float



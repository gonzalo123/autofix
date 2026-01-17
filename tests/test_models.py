"""Tests for Pydantic models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from modules.logs.models import ChunkAnalysisResult, LogChunk, LogEntry, PrTitleModel


class TestLogEntry:
    """Tests for LogEntry model."""

    def test_valid_log_entry(self) -> None:
        """Test creating a valid LogEntry."""
        entry = LogEntry(
            timestamp=datetime(2025, 1, 15, 10, 0, 0),
            level="ERROR",
            fix_short_name="fix-auth-bug",
            message="Authentication failed for user",
        )

        assert entry.timestamp == datetime(2025, 1, 15, 10, 0, 0)
        assert entry.level == "ERROR"
        assert entry.fix_short_name == "fix-auth-bug"
        assert entry.message == "Authentication failed for user"

    def test_missing_required_field_raises_error(self) -> None:
        """Test that missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            LogEntry(
                timestamp=datetime(2025, 1, 15),
                level="ERROR",
                # missing fix_short_name and message
            )

    def test_timestamp_from_string(self) -> None:
        """Test that timestamp can be parsed from ISO string."""
        entry = LogEntry(
            timestamp="2025-01-15T10:00:00",
            level="INFO",
            fix_short_name="fix-test",
            message="Test message",
        )

        assert entry.timestamp == datetime(2025, 1, 15, 10, 0, 0)


class TestPrTitleModel:
    """Tests for PrTitleModel."""

    def test_valid_pr_model(self) -> None:
        """Test creating a valid PrTitleModel."""
        model = PrTitleModel(
            pr_title="fix(auth): resolve login timeout issue",
            pr_description="This PR fixes the authentication timeout that occurred when...",
        )

        assert model.pr_title == "fix(auth): resolve login timeout issue"
        assert "authentication timeout" in model.pr_description

    def test_missing_title_raises_error(self) -> None:
        """Test that missing pr_title raises ValidationError."""
        with pytest.raises(ValidationError):
            PrTitleModel(pr_description="Some description")

    def test_missing_description_raises_error(self) -> None:
        """Test that missing pr_description raises ValidationError."""
        with pytest.raises(ValidationError):
            PrTitleModel(pr_title="Some title")


class TestLogChunk:
    """Tests for LogChunk model."""

    def test_valid_log_chunk(self) -> None:
        """Test creating a valid LogChunk."""
        chunk = LogChunk(
            chunk_index=0,
            total_chunks=3,
            chunk_size=100,
            start_timestamp="2025-01-15T10:00:00",
            end_timestamp="2025-01-15T10:30:00",
            logs=[{"@message": "test"}],
        )

        assert chunk.chunk_index == 0
        assert chunk.total_chunks == 3
        assert chunk.chunk_size == 100
        assert len(chunk.logs) == 1

    def test_get_time_range_description_with_timestamps(self) -> None:
        """Test time range description when timestamps are present."""
        chunk = LogChunk(
            chunk_index=0,
            total_chunks=1,
            chunk_size=10,
            start_timestamp="2025-01-15T10:00:00",
            end_timestamp="2025-01-15T10:30:00",
            logs=[],
        )

        description = chunk.get_time_range_description()

        assert description == "2025-01-15T10:00:00 to 2025-01-15T10:30:00"

    def test_get_time_range_description_without_timestamps(self) -> None:
        """Test time range description when timestamps are None."""
        chunk = LogChunk(
            chunk_index=2,
            total_chunks=5,
            chunk_size=10,
            logs=[],
        )

        description = chunk.get_time_range_description()

        assert description == "Chunk 3 of 5"

    def test_optional_timestamps(self) -> None:
        """Test that timestamps are optional."""
        chunk = LogChunk(
            chunk_index=0,
            total_chunks=1,
            chunk_size=0,
            logs=[],
        )

        assert chunk.start_timestamp is None
        assert chunk.end_timestamp is None


class TestChunkAnalysisResult:
    """Tests for ChunkAnalysisResult model."""

    def test_successful_result(self) -> None:
        """Test creating a successful analysis result."""
        result = ChunkAnalysisResult(
            chunk_index=0,
            chunk_time_range="2025-01-15T10:00:00 to 2025-01-15T10:30:00",
            chunk_size=100,
            analysis="Found 3 errors related to authentication.",
            success=True,
            processing_time_seconds=5.5,
        )

        assert result.success is True
        assert result.error_message is None
        assert "authentication" in result.analysis

    def test_failed_result(self) -> None:
        """Test creating a failed analysis result."""
        result = ChunkAnalysisResult(
            chunk_index=1,
            chunk_time_range="2025-01-15T10:30:00 to 2025-01-15T11:00:00",
            chunk_size=100,
            analysis="",
            success=False,
            error_message="Timeout exceeded",
            processing_time_seconds=300.0,
        )

        assert result.success is False
        assert result.error_message == "Timeout exceeded"
        assert result.analysis == ""

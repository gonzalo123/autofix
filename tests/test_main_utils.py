"""Tests for utility functions in main module."""

from datetime import datetime, timezone

import pytest

from modules.logs.main import (
    calculate_payload_size,
    create_log_chunks,
    explain_query_status,
    parse_log_entry,
    to_unix_seconds,
)


class TestToUnixSeconds:
    """Tests for to_unix_seconds function."""

    def test_utc_datetime(self) -> None:
        """Test conversion of UTC datetime."""
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        result = to_unix_seconds(dt)

        assert result == 1736942400

    def test_naive_datetime_treated_as_utc(self) -> None:
        """Test that naive datetime is treated as UTC."""
        dt_naive = datetime(2025, 1, 15, 12, 0, 0)
        dt_utc = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        result_naive = to_unix_seconds(dt_naive)
        result_utc = to_unix_seconds(dt_utc)

        assert result_naive == result_utc

    def test_returns_integer(self) -> None:
        """Test that result is an integer."""
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        result = to_unix_seconds(dt)

        assert isinstance(result, int)


class TestExplainQueryStatus:
    """Tests for explain_query_status function."""

    def test_failed_status(self) -> None:
        """Test explanation for Failed status."""
        result = explain_query_status("Failed")

        assert "failed" in result.lower()
        assert "CloudWatch Logs console" in result

    def test_cancelled_status(self) -> None:
        """Test explanation for Cancelled status."""
        result = explain_query_status("Cancelled")

        assert "cancelled" in result.lower()

    def test_timeout_status(self) -> None:
        """Test explanation for Timeout status."""
        result = explain_query_status("Timeout")

        assert "exceeded" in result.lower() or "timeout" in result.lower()

    def test_unknown_status(self) -> None:
        """Test explanation for Unknown status."""
        result = explain_query_status("Unknown")

        assert "unknown" in result.lower()

    def test_unexpected_status(self) -> None:
        """Test explanation for unexpected status values."""
        result = explain_query_status("SomeNewStatus")

        assert "SomeNewStatus" in result
        assert "unexpected" in result.lower()


class TestCalculatePayloadSize:
    """Tests for calculate_payload_size function."""

    def test_empty_dict(self) -> None:
        """Test size calculation for empty dict."""
        bytes_size, kb_size, mb_size = calculate_payload_size({})

        assert bytes_size == 2  # "{}"
        assert kb_size == 2 / 1024
        assert mb_size == 2 / 1024 / 1024

    def test_simple_dict(self) -> None:
        """Test size calculation for simple dict."""
        data = {"key": "value"}

        bytes_size, kb_size, mb_size = calculate_payload_size(data)

        expected_bytes = len('{"key": "value"}'.encode("utf-8"))
        assert bytes_size == expected_bytes
        assert kb_size == expected_bytes / 1024
        assert mb_size == expected_bytes / 1024 / 1024

    def test_nested_structure(self) -> None:
        """Test size calculation for nested structure."""
        data = {"logs": [{"msg": "test"}, {"msg": "test2"}], "count": 2}

        bytes_size, kb_size, mb_size = calculate_payload_size(data)

        assert bytes_size > 0
        assert kb_size == bytes_size / 1024
        assert mb_size == kb_size / 1024

    def test_returns_tuple_of_three(self) -> None:
        """Test that function returns tuple of three values."""
        result = calculate_payload_size({"test": 1})

        assert isinstance(result, tuple)
        assert len(result) == 3


class TestParseLogEntry:
    """Tests for parse_log_entry function."""

    def test_excludes_ptr_field(self) -> None:
        """Test that @ptr field is excluded from result."""
        row = [
            {"field": "@timestamp", "value": "2025-01-15T10:00:00"},
            {"field": "@message", "value": "Test message"},
            {"field": "@ptr", "value": "internal-pointer-value"},
        ]

        result = parse_log_entry(row)

        assert "@ptr" not in result
        assert "@timestamp" in result
        assert "@message" in result

    def test_includes_all_other_fields(self) -> None:
        """Test that all non-ptr fields are included."""
        row = [
            {"field": "@timestamp", "value": "2025-01-15T10:00:00"},
            {"field": "@message", "value": "Test message"},
            {"field": "level", "value": "ERROR"},
            {"field": "custom_field", "value": "custom_value"},
        ]

        result = parse_log_entry(row)

        assert result["@timestamp"] == "2025-01-15T10:00:00"
        assert result["@message"] == "Test message"
        assert result["level"] == "ERROR"
        assert result["custom_field"] == "custom_value"

    def test_empty_row(self) -> None:
        """Test parsing empty row."""
        result = parse_log_entry([])

        assert result == {}

    def test_only_ptr_field(self) -> None:
        """Test row with only @ptr field."""
        row = [{"field": "@ptr", "value": "pointer"}]

        result = parse_log_entry(row)

        assert result == {}


class TestCreateLogChunks:
    """Tests for create_log_chunks function."""

    def test_empty_records(self) -> None:
        """Test with empty records list."""
        result = create_log_chunks([])

        assert result == []

    def test_single_chunk(self) -> None:
        """Test when all records fit in one chunk."""
        records = [{"@timestamp": f"2025-01-15T10:{i:02d}:00"} for i in range(5)]

        result = create_log_chunks(records, chunk_size=10)

        assert len(result) == 1
        assert result[0].chunk_index == 0
        assert result[0].total_chunks == 1
        assert result[0].chunk_size == 5

    def test_multiple_chunks(self) -> None:
        """Test chunking into multiple chunks."""
        records = [{"@timestamp": f"2025-01-15T10:{i:02d}:00"} for i in range(25)]

        result = create_log_chunks(records, chunk_size=10)

        assert len(result) == 3
        assert result[0].chunk_size == 10
        assert result[1].chunk_size == 10
        assert result[2].chunk_size == 5
        for i, chunk in enumerate(result):
            assert chunk.chunk_index == i
            assert chunk.total_chunks == 3

    def test_exact_chunk_size(self) -> None:
        """Test when records divide evenly into chunks."""
        records = [{"@timestamp": f"2025-01-15T10:{i:02d}:00"} for i in range(20)]

        result = create_log_chunks(records, chunk_size=10)

        assert len(result) == 2
        assert result[0].chunk_size == 10
        assert result[1].chunk_size == 10

    def test_timestamps_captured(self) -> None:
        """Test that start and end timestamps are captured."""
        records = [
            {"@timestamp": "2025-01-15T10:00:00"},
            {"@timestamp": "2025-01-15T10:05:00"},
            {"@timestamp": "2025-01-15T10:10:00"},
        ]

        result = create_log_chunks(records, chunk_size=10)

        assert result[0].start_timestamp == "2025-01-15T10:00:00"
        assert result[0].end_timestamp == "2025-01-15T10:10:00"

    def test_logs_preserved(self) -> None:
        """Test that logs are preserved in chunks."""
        records = [{"@message": f"msg{i}"} for i in range(5)]

        result = create_log_chunks(records, chunk_size=3)

        assert result[0].logs == records[:3]
        assert result[1].logs == records[3:]

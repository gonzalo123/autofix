"""Tests for time_parser module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from modules.logs.time_parser import _parse_single_datetime, parse_time_range


class TestParseTimeRange:
    """Tests for parse_time_range function."""

    def test_last_n_hours(self) -> None:
        """Test parsing 'last N hours' format."""
        with patch("modules.logs.time_parser.datetime") as mock_dt:
            fixed_now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = fixed_now
            mock_dt.strptime = datetime.strptime

            start, end = parse_time_range("last 2 hours")

            assert end == fixed_now
            assert start == fixed_now - timedelta(hours=2)

    def test_last_n_days(self) -> None:
        """Test parsing 'last N days' format."""
        with patch("modules.logs.time_parser.datetime") as mock_dt:
            fixed_now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = fixed_now
            mock_dt.strptime = datetime.strptime

            start, end = parse_time_range("last 7 days")

            assert end == fixed_now
            assert start == fixed_now - timedelta(days=7)

    def test_last_n_minutes(self) -> None:
        """Test parsing 'last N minutes' format."""
        with patch("modules.logs.time_parser.datetime") as mock_dt:
            fixed_now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = fixed_now
            mock_dt.strptime = datetime.strptime

            start, end = parse_time_range("last 30 minutes")

            assert end == fixed_now
            assert start == fixed_now - timedelta(minutes=30)

    def test_last_n_weeks(self) -> None:
        """Test parsing 'last N weeks' format."""
        with patch("modules.logs.time_parser.datetime") as mock_dt:
            fixed_now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = fixed_now
            mock_dt.strptime = datetime.strptime

            start, end = parse_time_range("last 2 weeks")

            assert end == fixed_now
            assert start == fixed_now - timedelta(weeks=2)

    def test_since_yesterday(self) -> None:
        """Test parsing 'since yesterday' format."""
        with patch("modules.logs.time_parser.datetime") as mock_dt:
            fixed_now = datetime(2025, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
            mock_dt.now.return_value = fixed_now
            mock_dt.strptime = datetime.strptime

            start, end = parse_time_range("since yesterday")

            assert end == fixed_now
            expected_start = datetime(2025, 1, 14, 0, 0, 0, tzinfo=timezone.utc)
            assert start == expected_start

    def test_since_today(self) -> None:
        """Test parsing 'since today' format."""
        with patch("modules.logs.time_parser.datetime") as mock_dt:
            fixed_now = datetime(2025, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
            mock_dt.now.return_value = fixed_now
            mock_dt.strptime = datetime.strptime

            start, end = parse_time_range("since today")

            assert end == fixed_now
            expected_start = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
            assert start == expected_start

    def test_date_range_format(self) -> None:
        """Test parsing 'YYYY-MM-DD to YYYY-MM-DD' format."""
        start, end = parse_time_range("2025-01-01 to 2025-01-10")

        assert start == datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert end == datetime(2025, 1, 10, 0, 0, 0, tzinfo=timezone.utc)

    def test_datetime_range_format(self) -> None:
        """Test parsing ISO datetime range format."""
        start, end = parse_time_range("2025-01-01t10:00:00 to 2025-01-01t18:00:00")

        assert start == datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        assert end == datetime(2025, 1, 1, 18, 0, 0, tzinfo=timezone.utc)

    def test_invalid_format_raises_value_error(self) -> None:
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_time_range("invalid time string")

        assert "Cannot parse time range" in str(exc_info.value)

    def test_case_insensitive(self) -> None:
        """Test that parsing is case insensitive."""
        with patch("modules.logs.time_parser.datetime") as mock_dt:
            fixed_now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = fixed_now
            mock_dt.strptime = datetime.strptime

            start1, _ = parse_time_range("LAST 2 HOURS")
            start2, _ = parse_time_range("Last 2 Hours")

            assert start1 == start2


class TestParseSingleDatetime:
    """Tests for _parse_single_datetime function."""

    def test_iso_format_with_t(self) -> None:
        """Test parsing ISO format with T separator."""
        result = _parse_single_datetime("2025-01-15t10:30:00")

        assert result == datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

    def test_datetime_with_space(self) -> None:
        """Test parsing datetime with space separator."""
        result = _parse_single_datetime("2025-01-15 10:30:00")

        assert result == datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

    def test_date_only(self) -> None:
        """Test parsing date-only format."""
        result = _parse_single_datetime("2025-01-15")

        assert result == datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    def test_invalid_format_raises_value_error(self) -> None:
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _parse_single_datetime("invalid")

        assert "Cannot parse datetime" in str(exc_info.value)

    def test_result_has_utc_timezone(self) -> None:
        """Test that all results have UTC timezone."""
        result = _parse_single_datetime("2025-01-15")

        assert result.tzinfo == timezone.utc

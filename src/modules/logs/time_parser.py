"""Natural language time range parsing for CloudWatch Logs queries."""

import re
from datetime import datetime, timedelta, timezone
from typing import Tuple


def parse_time_range(time_str: str) -> Tuple[datetime, datetime]:
    """
    Parse natural language or structured time ranges into start/end datetimes.

    Supported formats:
    - "last N hours/days/weeks/minutes" - e.g., "last 2 hours", "last 7 days"
    - "since yesterday/today" - e.g., "since yesterday"
    - "YYYY-MM-DD to YYYY-MM-DD" - e.g., "2025-12-10 to 2025-12-12"
    - "YYYY-MM-DDTHH:MM:SS to YYYY-MM-DDTHH:MM:SS" - ISO format ranges

    Args:
        time_str: Natural language or structured time range

    Returns:
        Tuple of (start_datetime, end_datetime) both with UTC timezone

    Raises:
        ValueError: If time string cannot be parsed
    """
    time_str = time_str.strip().lower()
    now = datetime.now(timezone.utc)

    # Pattern: "last N hours/days/weeks/minutes"
    match = re.match(r"last\s+(\d+)\s+(hour|day|week|minute)s?", time_str)
    if match:
        value = int(match.group(1))
        unit = match.group(2)

        delta_map = {
            "minute": timedelta(minutes=value),
            "hour": timedelta(hours=value),
            "day": timedelta(days=value),
            "week": timedelta(weeks=value),
        }

        return now - delta_map[unit], now

    # Pattern: "since yesterday"
    if "since yesterday" in time_str:
        yesterday_start = (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return yesterday_start, now

    # Pattern: "since today"
    if "since today" in time_str:
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return today_start, now

    # Pattern: "YYYY-MM-DD to YYYY-MM-DD" or "ISO to ISO"
    if " to " in time_str:
        parts = time_str.split(" to ")
        if len(parts) == 2:
            start_str, end_str = parts
            start_dt = _parse_single_datetime(start_str.strip())
            end_dt = _parse_single_datetime(end_str.strip())
            return start_dt, end_dt

    raise ValueError(
        f"Cannot parse time range: '{time_str}'. "
        f"Supported formats: 'last N hours/days/minutes/weeks', 'since yesterday', "
        f"'YYYY-MM-DD to YYYY-MM-DD', or ISO datetime ranges."
    )


def _parse_single_datetime(dt_str: str) -> datetime:
    """
    Parse a single datetime string (used internally by parse_time_range).

    Args:
        dt_str: Datetime string in ISO format or date format

    Returns:
        datetime object with UTC timezone

    Raises:
        ValueError: If datetime string cannot be parsed
    """
    # Try ISO format with time (both with and without 'T' separator)
    for fmt in [
        "%Y-%m-%dt%H:%M:%S",  # 2025-12-14t10:00:00
        "%Y-%m-%d %H:%M:%S",  # 2025-12-14 10:00:00
        "%Y-%m-%d",  # 2025-12-14
    ]:
        try:
            dt = datetime.strptime(dt_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    raise ValueError(f"Cannot parse datetime: '{dt_str}'")

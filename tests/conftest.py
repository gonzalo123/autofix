"""Shared pytest fixtures for the test suite."""

import sys
from pathlib import Path

import pytest

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def sample_log_entry() -> dict[str, str]:
    """Sample parsed log entry for testing."""
    return {
        "@timestamp": "2025-01-15T10:30:00.000Z",
        "@message": "Test log message",
        "level": "INFO",
    }


@pytest.fixture
def sample_log_entries() -> list[dict[str, str]]:
    """Multiple sample log entries for chunk testing."""
    return [
        {"@timestamp": f"2025-01-15T10:{i:02d}:00.000Z", "@message": f"Message {i}"}
        for i in range(10)
    ]

"""CloudWatch Logs analysis module."""

from modules.logs.main import ask_to_log, ask_to_log_parallel
from modules.logs.time_parser import parse_time_range

__all__ = [
    "ask_to_log",
    "ask_to_log_parallel",
    "parse_time_range",
]

import logging
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Literal, Union

from pythonjsonlogger.json import JsonFormatter


def uncaught_exception_handler(exc_type, exc_value, exc_traceback):
    """Handle uncaught exceptions by logging them."""
    logging.exception("Uncaught exception: %s", exc_value)


class CloudWatchJsonFormatter(JsonFormatter):
    """JSON formatter for CloudWatch logs with custom metadata fields."""

    def __init__(self, app: str, process: str, *args, **kwargs):
        self.app = app
        self.process = process
        super().__init__(*args, **kwargs)

    def add_fields(self, log_record, record, message_dict):
        """Add CloudWatch-specific fields to log record."""
        log_record['@timestamp'] = datetime.fromtimestamp(record.created).isoformat()
        log_record['level'] = record.levelname
        log_record['app'] = self.app
        log_record['logger'] = record.name
        log_record['process'] = self.process
        super(CloudWatchJsonFormatter, self).add_fields(log_record, record, message_dict)


class ConsoleFormatter(logging.Formatter):
    """Console formatter that includes extra fields."""

    # Standard log record attributes to exclude from extras
    RESERVED_ATTRS = {
        'name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname',
        'levelno', 'lineno', 'module', 'msecs', 'message', 'pathname', 'process',
        'processName', 'relativeCreated', 'thread', 'threadName', 'exc_info',
        'exc_text', 'stack_info', 'asctime'
    }

    def format(self, record):
        # Format basic message
        base_message = super().format(record)

        # Extract extra fields (anything not in standard attributes)
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in self.RESERVED_ATTRS
        }

        # Append extras to message if any exist
        if extras:
            extras_str = ' '.join(f'{k}={v}' for k, v in extras.items())
            return f'{base_message} | {extras_str}'

        return base_message


def setup_logging(
    env: Literal['local', 'production'],
    app: str,
    log_path: Union[Path, str],
    process: str = 'main',
    log_level: str = logging.INFO,
) -> None:
    """Configure logging with environment-specific settings.

    Args:
        env: Environment mode ('local' for human-readable, 'production' for JSON)
        app: Application name for log metadata
        log_path: Path to log file (used in production mode)
        process: Process identifier for log metadata
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    if env == 'local':
        logging.basicConfig(
            format='%(asctime)s [%(levelname)s] %(message)s',
            level=log_level,
            datefmt='%d/%m/%Y %X'
        )
    else:
        # Console handler with human-readable format for docker compose logs
        console_handler = logging.StreamHandler()
        console_formatter = ConsoleFormatter(
            fmt='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)

        # JSON formatter for file (CloudWatch)
        json_formatter = CloudWatchJsonFormatter(
            app=app,
            process=process,
            fmt='%(levelname)s %(name)s %(message)s'
        )

        # File handler with hourly rotation (CloudWatch auto_removal deletes rotated files)
        file_handler = TimedRotatingFileHandler(
            log_path,
            when='H',
            interval=1,
            backupCount=2,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(json_formatter)

        logging.basicConfig(
            level=log_level,
            handlers=[console_handler, file_handler]
        )

    # Install global exception handler
    sys.excepthook = uncaught_exception_handler
import os
from enum import StrEnum
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENVIRONMENT = os.getenv('ENVIRONMENT', 'local')

DEBUG = os.getenv('DEBUG', 'False') == 'True'
load_dotenv(dotenv_path=Path(BASE_DIR).resolve().joinpath('env', ENVIRONMENT, '.env'))

APP_ID = 'cw'
APP = 'cw_demo'
PROCESS = 'cw_demo'
LOG_PATH = BASE_DIR / 'logs' / 'app.log'

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", False)
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", False)
AWS_PROFILE_NAME = os.getenv("AWS_PROFILE_NAME", False)
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
AWS_ASSUME_ROLE = os.getenv("AWS_ASSUME_ROLE", False)

CLAUDE_CODE_OAUTH_TOKEN = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

GITHUB_REPO = "gonzalo123/autofix"
WORK_DIR = Path(BASE_DIR) / "tmp"

# Parallel processing limits
MAX_CHUNKS_TO_PROCESS = int(os.getenv("MAX_CHUNKS_TO_PROCESS", "5"))


class Models(StrEnum):
    CLAUDE_45_HAIKU = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    CLAUDE_45 = "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"

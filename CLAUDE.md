# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A multi-agent log analysis system with automatic bug-fix capabilities. The application integrates with AWS CloudWatch to analyze logs using AI agents powered by AWS Bedrock (Claude models), performs intelligent error triage, and can automatically create GitHub pull requests to fix detected issues using the Claude Code SDK.

**Key Features:**
- CloudWatch Logs Insights integration for log retrieval
- Multi-agent architecture with worker-coordinator pattern for parallel log analysis
- Automatic chunking for large log datasets
- AI-powered error triage and analysis
- Automatic bug-fix PR creation via Claude Code SDK

## Commands

### Development

```bash
# Install dependencies (uses Poetry)
poetry install

# Run CLI for log analysis
python src/cli.py log --group <log-group> --question "What errors occurred?" --start 2024-01-01

# Run Flask demo app locally
python src/app.py

# Run with gunicorn (production mode)
gunicorn -w 1 app:app -b 0.0.0.0:5000 --timeout 180
```

### CLI Usage

```bash
# Analyze CloudWatch logs with a question
python src/cli.py log \
  --group /aws/lambda/my-function \
  --question "What are the main errors and their root causes?" \
  --start 2024-01-01T00:00:00 \
  --end 2024-01-02T00:00:00

# With custom CloudWatch Insights query
python src/cli.py log \
  --group /aws/lambda/my-function \
  --question "Analyze authentication failures" \
  --start 2024-01-01 \
  --query "fields @timestamp, @message | filter @message like /error/i | sort @timestamp asc"
```

**CLI Options:**
- `--group` (required): CloudWatch log group name
- `--question` (required): Question to ask about the logs
- `--start` (required): Start datetime (YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD)
- `--end` (optional): End datetime, defaults to now
- `--query` (optional): Custom CloudWatch Insights query

### Testing & Linting

```bash
# Run tests
make test

# Run tests with coverage
make test-cov

# Run linter (ruff)
make lint
```

### Docker

```bash
# Build and run with Docker Compose
docker compose up --build

# Run only the API service
docker compose up api --build
```

## Architecture

```
src/
├── cli.py                    # CLI entry point
├── app.py                    # Flask demo application
├── settings.py               # Configuration from environment variables
├── lib/
│   ├── cli.py                # Click CLI group definition
│   └── logger.py             # Dual-mode logging (local/production)
├── commands/
│   ├── __init__.py           # Command registration
│   └── log.py                # Log analysis CLI command
└── modules/
    ├── ai/
    │   ├── agent_factory.py  # Strands Agent creation with Bedrock
    │   └── bedrock_model.py  # AWS Bedrock model configuration
    └── logs/
        ├── main.py           # Log analysis engine (parallel processing)
        ├── models.py         # Pydantic models (LogEntry, LogChunk, etc.)
        ├── promps.py         # Agent prompts (triage, worker, coordinator)
        ├── tools.py          # Agent tools (register_error_for_fix)
        └── time_parser.py    # Time parsing utilities

tests/
├── conftest.py               # Pytest fixtures
├── test_main_utils.py        # Log analysis utility tests
├── test_models.py            # Model tests
└── test_time_parser.py       # Time parser tests

.docker/cw/
├── Dockerfile                # CloudWatch agent sidecar
├── cwagent-config.json       # CloudWatch agent configuration
├── entrypoint.sh             # Container entrypoint
└── credentials.dist          # AWS credentials template
```

### Core Components

**Multi-Agent System:**
- **Triage Agent**: Analyzes small datasets, identifies errors, can invoke auto-fix tool
- **Worker Agents**: Process log chunks in parallel for large datasets
- **Coordinator Agent**: Synthesizes worker analyses into final answer

**Auto-Fix Pipeline:**
1. Agent identifies fixable errors in logs
2. Clones target repository
3. Creates fix branch
4. Invokes Claude Code SDK to fix the error
5. Commits changes and creates GitHub PR

### Logging System

The logging system (`src/lib/logger.py`) operates in two modes based on `ENVIRONMENT`:
- **local**: Simple console output with human-readable format
- **production**: Dual output:
  - Console: Human-readable for `docker compose logs`
  - File: JSON format with CloudWatch-specific fields (`@timestamp`, `app`, `process`, `level`)

Log files rotate hourly via `TimedRotatingFileHandler` and are picked up by a CloudWatch agent sidecar container.

## Environment Variables

### Core Settings
- `ENVIRONMENT`: `local` or `production` (affects logging behavior)
- `DEBUG`: Enable debug mode (`True`/`False`)

### AWS Configuration
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `AWS_PROFILE_NAME`: AWS profile name (alternative to access keys)
- `AWS_REGION`: AWS region (default: `eu-central-1`)
- `AWS_ASSUME_ROLE`: IAM role ARN to assume

### API Tokens
- `CLAUDE_CODE_OAUTH_TOKEN`: OAuth token for Claude Code SDK
- `GITHUB_TOKEN`: GitHub personal access token for PR creation

### Processing Limits
- `MAX_CHUNKS_TO_PROCESS`: Maximum chunks for parallel processing (default: `5`)

## Dependencies

Key libraries:
- **strands-agents**: Multi-agent framework for AI agents
- **claude-code-sdk**: Claude Code SDK for automatic bug fixes
- **boto3**: AWS SDK (CloudWatch Logs, Bedrock)
- **click**: CLI framework
- **gitpython** / **pygithub**: Git operations and GitHub API
- **pydantic**: Data validation and models
- **flask**: Demo web application

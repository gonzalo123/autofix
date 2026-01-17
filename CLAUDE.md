# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Flask-based API with structured JSON logging for AWS CloudWatch integration. The application demonstrates a production-ready logging setup with dual output: human-readable console logs and JSON-formatted file logs for CloudWatch ingestion.

## Commands

### Development

```bash
# Install dependencies (uses Poetry)
poetry install

# Run locally
python src/app.py

# Run with gunicorn (production mode)
gunicorn -w 1 app:app -b 0.0.0.0:5000 --timeout 180
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
├── app.py           # Flask application with routes
├── settings.py      # Configuration from environment variables
└── lib/
    └── logger.py    # Dual-mode logging (local/production)
```

### Logging System

The logging system (`src/lib/logger.py`) operates in two modes based on `ENVIRONMENT`:
- **local**: Simple console output with human-readable format
- **production**: Dual output:
  - Console: Human-readable for `docker compose logs`
  - File: JSON format with CloudWatch-specific fields (`@timestamp`, `app`, `process`, `level`)

Log files rotate hourly via `TimedRotatingFileHandler` and are picked up by a CloudWatch agent sidecar container.

### Environment Variables

- `ENVIRONMENT`: `local` or `production` (affects logging behavior)
- `PROCESS_ID`: Process identifier for log metadata

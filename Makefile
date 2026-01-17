.PHONY: test test-cov lint

test:
	poetry run pytest tests/ -v

test-cov:
	poetry run pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	poetry run ruff check src/ tests/

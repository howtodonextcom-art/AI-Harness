.PHONY: setup lint format typecheck test test-integration test-all coverage check

setup:
	uv sync --extra ml

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy

test:
	uv run pytest -m "not integration and not mt5"

test-integration:
	uv run pytest -m integration

test-all:
	uv run pytest -m "not mt5"

coverage:
	uv run pytest -m "not mt5" --cov --cov-report=term-missing

# Full quality gate used before declaring work done.
check: lint typecheck test-all

# Later sprints (placeholders so the command surface is stable):
#   backtest, api, dashboard, research

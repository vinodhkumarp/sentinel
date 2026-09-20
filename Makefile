.PHONY: help setup migrate explain triage test lint typecheck check

help:            ## Show this help
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

setup:           ## Create .venv from uv.lock and install dev dependencies
	uv sync --extra dev

migrate:         ## Create the sentinel schema
	sentinel migrate

explain:         ## Explain one run: make explain RUN=123
	sentinel explain $(RUN)

triage:          ## Classify the most recent run
	sentinel triage

test:            ## Run tests
	pytest --cov=sentinel --cov-report=term-missing

lint:            ## Lint and format check
	ruff check src tests && ruff format --check src tests

typecheck:       ## Static types
	mypy src

check: lint typecheck test  ## Everything CI runs

.PHONY: install install-dev test lint clean

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	pytest -v

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	rm -rf .pytest_cache/ __pycache__/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

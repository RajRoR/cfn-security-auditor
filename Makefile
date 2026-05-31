.PHONY: help install lint fmt typecheck test test-cov run api dashboard clean

help:
	@echo "Targets:"
	@echo "  install     uv sync --all-extras"
	@echo "  lint        ruff + black --check + mypy"
	@echo "  fmt         apply black + ruff --fix"
	@echo "  typecheck   mypy ."
	@echo "  test        pytest"
	@echo "  test-cov    pytest with 85% coverage floor (CI parity)"
	@echo "  api         uvicorn dev server"
	@echo "  dashboard   streamlit dev server"
	@echo "  clean       remove caches and build artefacts"

install:
	uv sync --all-extras

lint:
	uv run ruff check .
	uv run black --check .
	uv run mypy .

fmt:
	uv run ruff check . --fix
	uv run black .

typecheck:
	uv run mypy .

test:
	uv run pytest

test-cov:
	uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=85

api:
	uv run uvicorn cfn_auditor.api.app:app --reload

dashboard:
	uv run streamlit run src/cfn_auditor/dashboard/app.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
.PHONY: help install lint fmt typecheck test test-cov api dashboard openapi docker-build compose-up compose-down clean

help:
	@echo "Targets:"
	@echo "  install       uv sync --all-extras"
	@echo "  lint          ruff + black --check + mypy"
	@echo "  fmt           apply black + ruff --fix"
	@echo "  typecheck     mypy ."
	@echo "  test          pytest"
	@echo "  test-cov      pytest with 85% coverage floor (CI parity)"
	@echo "  api           uvicorn dev server"
	@echo "  dashboard     streamlit dev server"
	@echo "  openapi       regenerate docs/openapi.json from the live app"
	@echo "  docker-build  build the API/dashboard image (cfn-security-auditor:dev)"
	@echo "  compose-up    docker compose up --build (API on :8000, dashboard on :8501)"
	@echo "  compose-down  docker compose down"
	@echo "  clean         remove caches and build artefacts"

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

openapi:
	uv run python scripts/export_openapi.py

docker-build:
	docker build -t cfn-security-auditor:dev .

compose-up:
	docker compose up --build

compose-down:
	docker compose down

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

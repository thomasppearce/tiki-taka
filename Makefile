SCHEMA := docs/schema/contracts.schema.json
TS_TYPES := frontend/lib/contracts.generated.ts
BANNER := /* Generated from backend/app/models by `make types`. Do not edit by hand. */

.PHONY: install types check-types test lint format dev-backend dev-frontend

install: ## Install backend and frontend dependencies
	cd backend && uv sync
	cd frontend && npm install

types: ## Regenerate the JSON Schema and TypeScript types from the Pydantic contracts
	cd backend && uv run python -m app.models.schema ../$(SCHEMA)
	cd frontend && npx json2ts -i ../$(SCHEMA) -o ../$(TS_TYPES) \
		--unreachableDefinitions --additionalProperties false --bannerComment '$(BANNER)'

check-types: types ## Fail if the committed types are out of date with the contracts
	git diff --exit-code -- $(SCHEMA) $(TS_TYPES)

test: ## Run backend tests
	cd backend && uv run pytest

lint: ## Lint and format-check both halves
	cd backend && uv run ruff check . && uv run black --check .
	cd frontend && npm run lint && npm run typecheck && npm run format:check

format: ## Auto-format both halves
	cd backend && uv run ruff check --fix . && uv run black .
	cd frontend && npm run format

dev-backend: ## Run the API on :8001 with reload
	cd backend && uv run uvicorn app.main:app --reload --port 8001 --timeout-graceful-shutdown 3

dev-frontend: ## Run the control room on :3000
	cd frontend && npm run dev

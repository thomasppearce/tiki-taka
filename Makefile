SCHEMA := docs/schema/contracts.schema.json
TS_TYPES := frontend/lib/contracts.generated.ts
BANNER := /* Generated from backend/app/models by `make types`. Do not edit by hand. */

.PHONY: install types check-types test lint format evals register-agents dev-backend dev-frontend \
	deploy-infra deploy-backend deploy-frontend deploy warm cold

# Azure (infra/README.md). The image tag is the commit, so a deploy names exactly what it ran.
RG := rg-matchdesk
REGISTRY = $(shell az deployment group show -g $(RG) -n hosting --query properties.outputs.registryName.value -o tsv)
API_URL = $(shell az deployment group show -g $(RG) -n hosting --query properties.outputs.apiUrl.value -o tsv)
TAG = $(shell git rev-parse --short HEAD)$(shell git diff --quiet || echo -dirty)

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

evals: ## The graphics team vs a single agent on every featured-match moment, judged on Foundry (~$2): docs/evals/graphics.md
	cd backend && MATCHDAY_CACHE_DIR=.cache/matchday uv run python -m app.evals.graphics

register-agents: ## List the agent team in the Foundry project (Build > Agents), matched to its traces
	cd backend && uv run python -m app.agents.register

dev-backend: ## Run the API on :8001 with reload (the simulated matchday is kept in backend/.cache)
	cd backend && MATCHDAY_CACHE_DIR=.cache/matchday uv run uvicorn app.main:app --reload --port 8001 --timeout-graceful-shutdown 3

dev-frontend: ## Run the control room on :3000
	cd frontend && npm run dev

deploy-infra: ## Create or update the hosting resources (keeps the running image and replica setting)
	az deployment group create -g $(RG) -n hosting --template-file infra/hosting.bicep \
		--parameters backendImage=$$(az containerapp show -g $(RG) -n tikitaka-api --query 'properties.template.containers[0].image' -o tsv 2>/dev/null || echo mcr.microsoft.com/k8se/quickstart:latest) \
		minReplicas=$$(az containerapp show -g $(RG) -n tikitaka-api --query 'properties.template.scale.minReplicas' -o tsv 2>/dev/null | grep -E '^[01]$$' || echo 0) \
		--query properties.provisioningState -o tsv

deploy-backend: ## Build the backend image in Azure (matchday baked in) and roll it out
	az acr build --registry $(REGISTRY) --image tikitaka-api:$(TAG) --file backend/Dockerfile backend
	az containerapp update -g $(RG) -n tikitaka-api --image $(REGISTRY).azurecr.io/tikitaka-api:$(TAG) --query properties.provisioningState -o tsv

deploy-frontend: ## Build the static site against the deployed API and publish it
	cd frontend && NEXT_PUBLIC_API_URL=$(API_URL) npx next build
	cd frontend && npx -y @azure/static-web-apps-cli@2.0.10 deploy ./out --env production \
		--deployment-token $$(az staticwebapp secrets list -g $(RG) -n tikitaka-web --query properties.apiKey -o tsv)

deploy: deploy-backend deploy-frontend ## Both halves

warm: ## Keep one backend replica running now (the tikitaka-warm job does this for judging): ~$0.78 a day
	az containerapp update -g $(RG) -n tikitaka-api --min-replicas 1 --query properties.template.scale -o json

cold: ## Back to scaling to zero when nobody is watching (the tikitaka-cold job does this after judging)
	az containerapp update -g $(RG) -n tikitaka-api --min-replicas 0 --query properties.template.scale -o json

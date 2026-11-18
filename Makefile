.PHONY: install test lint format sdk-models sdk-models-check contract build

# uv runs with UV_NO_CONFIG=1, as in ai-portal-data: the global uv config would write a local index and exclude-newer
# into the lock.
export UV_NO_CONFIG := 1
UV ?= uv
SERVICE_REPO ?= ../ai-portal-data

install: ## Create the dev environment with every extra
	$(UV) sync --all-extras

test: ## Run the tests
	$(UV) run --frozen pytest

lint: ## Lint and check formatting
	$(UV) run ruff check
	$(UV) run ruff format --check

format: ## Format the code
	$(UV) run ruff check --fix
	$(UV) run ruff format

contract: ## Refresh contract/openapi-v1.json from an ai-portal-data checkout (SERVICE_REPO=../ai-portal-data)
	scripts/update-contract.sh $(SERVICE_REPO)

sdk-models: ## Regenerate _models.py and _operations.py from contract/openapi-v1.json
	$(UV) run python scripts/sdk_models.py

sdk-models-check: ## Fail when _models.py or _operations.py is stale
	$(UV) run python scripts/sdk_models.py --check

build: ## Build the sdist and wheel into dist/
	$(UV) build

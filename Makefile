# CivicForest developer commands. Onboarding is: `make certs && make up && make migrate && make seed`.
.DEFAULT_GOAL := help
.PHONY: help certs up down logs migrate makemigrations seed test lint fmt shell createsuperuser reindex

COMPOSE := docker compose

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

certs: ## Generate mkcert certs for the local hostnames (run `mkcert -install` once first)
	@command -v mkcert >/dev/null || { echo "Install mkcert first: https://github.com/FiloSottile/mkcert"; exit 1; }
	mkcert -install
	cd caddy/certs && \
		mkcert civicforest.local && \
		mkcert api.civicforest.local
	@echo "Add to /etc/hosts:  127.0.0.1 civicforest.local api.civicforest.local"

up: ## Start the full stack
	$(COMPOSE) up -d --build

down: ## Stop the stack
	$(COMPOSE) down

logs: ## Tail all logs
	$(COMPOSE) logs -f

migrate: ## Apply database migrations
	$(COMPOSE) run --rm backend python manage.py migrate

makemigrations: ## Create new migrations
	$(COMPOSE) run --rm backend python manage.py makemigrations

seed: ## Seed categories + demo catalog
	$(COMPOSE) run --rm backend python manage.py seed_catalog

reindex: ## Rebuild the Meilisearch index from Postgres
	$(COMPOSE) run --rm backend python manage.py reindex_search

createsuperuser: ## Create a Django admin superuser
	$(COMPOSE) run --rm backend python manage.py createsuperuser

shell: ## Django shell
	$(COMPOSE) run --rm backend python manage.py shell

test: ## Run backend tests
	$(COMPOSE) run --rm backend pytest

lint: ## Lint backend (ruff) and frontend (eslint)
	$(COMPOSE) run --rm backend ruff check .
	$(COMPOSE) run --rm frontend npm run lint

fmt: ## Auto-format backend
	$(COMPOSE) run --rm backend ruff format .

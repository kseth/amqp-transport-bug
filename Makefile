IMAGE := servicebus-test

# ── Native ──────────────────────────────────────────────────
.PHONY: native
native: ## Run reproduce.py locally (requires CONNECTION_STRING + QUEUE_NAME)
	uv run reproduce.py

# ── Docker ──────────────────────────────────────────────────
.PHONY: docker-build docker
docker-build:
	docker build -t $(IMAGE):latest .

docker: docker-build ## Build & run in Docker
	docker run --rm \
		-e CONNECTION_STRING \
		-e QUEUE_NAME \
		$(IMAGE):latest

# ── Cleanup ─────────────────────────────────────────────────
.PHONY: clean
clean: ## Remove Docker image
	-docker rmi $(IMAGE):latest

# ── Help ────────────────────────────────────────────────────
.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

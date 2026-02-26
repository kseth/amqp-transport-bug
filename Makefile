IMAGE := servicebus-test

# ── Native ──────────────────────────────────────────────────
.PHONY: native
native: ## Run reproduce.py locally (requires CONNECTION_STRING + QUEUE_NAME)
	uv run reproduce.py

# ── Docker ──────────────────────────────────────────────────
.PHONY: docker-build docker-run
docker-build: ## Build the Docker image
	docker build -t $(IMAGE):latest .

docker-run: ## Run the Docker image (requires CONNECTION_STRING + QUEUE_NAME)
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

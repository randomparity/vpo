.PHONY: help test lint format clean install hooks hooks-run hooks-update \
        docker-ffmpeg-build docker-ffmpeg-shell docker-ffmpeg-version

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

test:  ## Run test suite
	pytest

lint:  ## Run linter (Python + Rust)
	ruff check .
	cargo clippy --manifest-path crates/vpo-core/Cargo.toml --all-targets -- -D warnings

format:  ## Format code (Python + Rust)
	ruff format .
	ruff check --fix .
	cargo fmt --manifest-path crates/vpo-core/Cargo.toml

clean:  ## Remove build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf src/*.egg-info/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

install:  ## Install package in development mode
	pip install -e ".[dev]"

hooks:  ## Install pre-commit hooks
	pre-commit install
	pre-commit install --hook-type pre-push
	@echo "Git hooks installed successfully!"

hooks-run:  ## Run all pre-commit hooks manually
	pre-commit run --all-files

hooks-update:  ## Update pre-commit hook versions
	pre-commit autoupdate

# =============================================================================
# Docker/Container targets for ffmpeg
# =============================================================================

# Container runtime detection (prefer podman over docker)
CONTAINER_RT := $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null)
FFMPEG_IMAGE := ffmpeg-full

docker-ffmpeg-build:  ## Build ffmpeg container image
	$(CONTAINER_RT) build -t $(FFMPEG_IMAGE) docker/ffmpeg/

docker-ffmpeg-shell:  ## Run interactive shell in ffmpeg container
	$(CONTAINER_RT) run --rm -it -v $(PWD):/workspace -w /workspace $(FFMPEG_IMAGE) /bin/bash

docker-ffmpeg-version:  ## Show ffmpeg version from container
	$(CONTAINER_RT) run --rm $(FFMPEG_IMAGE)

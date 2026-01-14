.PHONY: help test lint format clean setup hooks-run hooks-update \
        docker-ffmpeg-build docker-ffmpeg-shell docker-ffmpeg-version check-deps

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

PYTHON_VERSION := 3.13

setup:  ## Setup complete dev environment (venv, install, hooks)
	@if command -v uv >/dev/null 2>&1; then \
		echo "==> Creating virtual environment with Python $(PYTHON_VERSION) (uv)..."; \
		uv venv --python $(PYTHON_VERSION); \
		echo "==> Installing package in development mode..."; \
		uv pip install -e ".[dev]"; \
		echo "==> Building Rust extension..."; \
		uv run maturin develop; \
		echo "==> Installing pre-commit hooks..."; \
		uv run pre-commit install; \
		uv run pre-commit install --hook-type pre-push; \
	elif command -v pyenv >/dev/null 2>&1; then \
		echo "==> Creating virtual environment with Python $(PYTHON_VERSION) (pyenv)..."; \
		pyenv install -s $(PYTHON_VERSION); \
		pyenv local $(PYTHON_VERSION); \
		pyenv exec python -m venv .venv; \
		echo "==> Installing package in development mode..."; \
		.venv/bin/pip install -e ".[dev]"; \
		echo "==> Building Rust extension..."; \
		.venv/bin/maturin develop; \
		echo "==> Installing pre-commit hooks..."; \
		.venv/bin/pre-commit install; \
		.venv/bin/pre-commit install --hook-type pre-push; \
	else \
		echo "Error: uv or pyenv required (system Python may be incompatible)"; \
		echo "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		echo "Install pyenv: https://github.com/pyenv/pyenv#installation"; \
		exit 1; \
	fi
	@echo ""
	@echo "Setup complete! Run 'source .venv/bin/activate' to activate the environment."

hooks-run:  ## Run all pre-commit hooks manually
	pre-commit run --all-files

hooks-update:  ## Update pre-commit hook versions
	pre-commit autoupdate

# =============================================================================
# Dependency checking
# =============================================================================

check-deps:  ## Check for required external tools and show install instructions
	@echo "Checking for required external tools..."
	@echo ""
	@missing=""; \
	check_tool() { \
		tool=$$1; flag=$$2; \
		if command -v $$tool >/dev/null 2>&1; then \
			version=$$($$tool $$flag 2>&1 | head -1); \
			printf "  \033[32m✓\033[0m %-15s %s\n" "$$tool" "$$version"; \
		else \
			printf "  \033[31m✗\033[0m %-15s \033[31mnot found\033[0m\n" "$$tool"; \
			missing="$$missing $$tool"; \
		fi; \
	}; \
	check_tool ffmpeg -version; \
	check_tool ffprobe -version; \
	check_tool mkvmerge --version; \
	check_tool mkvpropedit --version; \
	echo ""; \
	if [ -n "$$missing" ]; then \
		printf "\033[33mMissing tools:$$missing\033[0m\n"; \
		echo ""; \
		echo "Install instructions:"; \
		echo ""; \
		printf "  \033[36mDebian/Ubuntu (apt):\033[0m\n"; \
		echo "    sudo apt update && sudo apt install ffmpeg mkvtoolnix"; \
		echo ""; \
		printf "  \033[36mFedora (dnf):\033[0m\n"; \
		echo "    sudo dnf install ffmpeg mkvtoolnix"; \
		echo "    # Note: ffmpeg may require RPM Fusion repository"; \
		echo "    # sudo dnf install https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-\$$(rpm -E %fedora).noarch.rpm"; \
		echo ""; \
		printf "  \033[36mmacOS (Homebrew):\033[0m\n"; \
		echo "    brew install ffmpeg mkvtoolnix"; \
		echo ""; \
		printf "  \033[36mArch Linux (pacman):\033[0m\n"; \
		echo "    sudo pacman -S ffmpeg mkvtoolnix-cli"; \
		echo ""; \
		exit 1; \
	else \
		printf "\033[32mAll required tools are installed.\033[0m\n"; \
	fi

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

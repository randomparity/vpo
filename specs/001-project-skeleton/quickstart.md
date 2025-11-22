# Quickstart: Project Skeleton Setup

**Feature**: 001-project-skeleton
**Date**: 2025-11-21

## Prerequisites

- Python 3.10 or higher
- pip (Python package installer)
- Git
- make (optional, for convenience commands)

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd vpo
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Package in Development Mode

```bash
pip install -e ".[dev]"
```

This installs:
- The `video-policy-orchestrator` package in editable mode
- Development dependencies: ruff, pytest

### 4. Verify Installation

```bash
# Run tests
pytest

# Run linter
ruff check .

# Or use Makefile shortcuts
make test
make lint
```

## Development Workflow

### Running Tests

```bash
# All tests
pytest

# With coverage (when pytest-cov is added)
pytest --cov=video_policy_orchestrator

# Specific test file
pytest tests/test_package.py
```

### Running Linter

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### Common Make Targets

```bash
make help      # Show available targets
make test      # Run test suite
make lint      # Run linter
make format    # Format code
make clean     # Remove build artifacts
```

## Project Structure

```text
vpo/
├── src/
│   └── video_policy_orchestrator/
│       └── __init__.py      # Package entry point
├── tests/
│   └── test_package.py      # Package tests
├── docs/
│   ├── PRD.md               # Product requirements
│   └── ARCHITECTURE.md      # System design
├── pyproject.toml           # Project configuration
├── Makefile                 # Dev command shortcuts
├── README.md                # Project overview
├── CONTRIBUTING.md          # Contribution guide
└── CLAUDE.md                # AI assistant context
```

## Verification Checklist

After setup, verify these work:

- [ ] `pip install -e ".[dev]"` completes without errors
- [ ] `pytest` runs and passes
- [ ] `ruff check .` reports no errors
- [ ] `python -c "import video_policy_orchestrator"` succeeds

## Troubleshooting

### "No module named video_policy_orchestrator"

Ensure you installed in editable mode:
```bash
pip install -e ".[dev]"
```

### Tests not discovered

Ensure pytest is installed and tests are in `tests/` directory:
```bash
pip install pytest
pytest --collect-only
```

### Ruff not found

Install development dependencies:
```bash
pip install -e ".[dev]"
# or directly
pip install ruff
```

## Next Steps

After completing this quickstart:

1. Read `docs/PRD.md` for project goals
2. Read `docs/ARCHITECTURE.md` for system design
3. Check `CONTRIBUTING.md` for contribution guidelines
4. Review `README.md` for full project overview

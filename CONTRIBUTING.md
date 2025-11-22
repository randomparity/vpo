# Contributing to Video Policy Orchestrator

Thank you for your interest in contributing to VPO! This document provides guidelines for contributing to the project.

## Getting Started

### Prerequisites

Before you begin, ensure you have:
- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Git

### Checking Your Python Version

```bash
python --version  # Should be 3.10+
```

## Development Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd vpo
```

### 2. Create Virtual Environment and Install Dependencies

```bash
uv venv
uv pip install -e ".[dev]"
```

### 3. Verify Installation

```bash
# Run tests
uv run pytest

# Run linter
uv run ruff check .

# Or use Makefile shortcuts
source .venv/bin/activate
make test
make lint
```

## Code Style

This project uses **ruff** for both linting and formatting. Configuration is defined in `pyproject.toml`:

- **Target Python version**: 3.10
- **Line length**: 88 characters
- **Enabled checks**: pycodestyle (E, W), Pyflakes (F), isort (I), pyupgrade (UP)

### Running the Linter

```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

### Before Committing

Always run linting and tests before committing:

```bash
uv run ruff check .
uv run pytest
```

## Pull Request Process

### Branch Naming

Use descriptive branch names following this pattern:
- `feature/<description>` - New features
- `fix/<description>` - Bug fixes
- `docs/<description>` - Documentation updates
- `refactor/<description>` - Code refactoring

Examples:
- `feature/add-mkv-support`
- `fix/track-ordering-bug`
- `docs/update-architecture`

### Commit Conventions

Write clear, concise commit messages:
- Use imperative mood ("Add feature" not "Added feature")
- Keep the first line under 72 characters
- Reference issues when applicable

Examples:
```
Add MKV container parsing support

Implement ffprobe wrapper for track enumeration. Adds support for
extracting audio and subtitle track metadata from MKV files.

Fixes #42
```

### Creating a Pull Request

1. **Ensure your branch is up to date**:
   ```bash
   git fetch origin
   git rebase origin/main
   ```

2. **Run all checks**:
   ```bash
   uv run ruff check .
   uv run pytest
   ```

3. **Push your branch**:
   ```bash
   git push -u origin your-branch-name
   ```

4. **Create the PR on GitHub** with:
   - Clear title describing the change
   - Description of what and why (not just how)
   - Reference to related issues
   - Test plan or verification steps

### PR Template

```markdown
## Summary
Brief description of the changes.

## Changes
- Change 1
- Change 2

## Test Plan
How to verify these changes work correctly.

## Related Issues
Fixes #XX
```

## Code Review

### Review Criteria

Pull requests are reviewed for:
- **Correctness**: Does the code do what it's supposed to?
- **Tests**: Are there adequate tests for new functionality?
- **Style**: Does the code follow project conventions?
- **Documentation**: Are changes documented where needed?
- **Spec alignment**: Do changes match the relevant specs?

### Approval Requirements

- At least one approving review required
- All CI checks must pass
- No unresolved review comments

### Responding to Feedback

- Address all comments (resolve or discuss)
- Push fixes as new commits (don't force-push during review)
- Re-request review after making changes

## Spec-Driven Development

This project follows spec-driven development:

1. **Specs first**: New features start as specs in `docs/` or `spec/`
2. **Review specs**: Get feedback on the approach before implementing
3. **Implement**: Write code that matches the approved spec
4. **Test**: Include tests that verify spec requirements

When making changes:
- Check if relevant specs exist in `docs/` or `spec/`
- Update specs if behavior is changing
- Reference specs in PR descriptions

## Getting Help

- Open an issue for questions or feature ideas
- Check existing issues before creating new ones
- Join discussions on open PRs and issues

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

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

### Troubleshooting Setup

**Rust extension fails to build:**

```bash
# Ensure Rust toolchain is installed
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Rebuild extension
uv run maturin develop
```

**ffprobe/mkvtoolnix not found:**

```bash
# Ubuntu/Debian
sudo apt install ffmpeg mkvtoolnix

# macOS
brew install ffmpeg mkvtoolnix
```

**Database errors:**

```bash
# Reset database (development only)
rm ~/.vpo/library.db

# Check database location
vpo doctor
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

## Testing

### Running Tests

```bash
# All tests
uv run pytest

# Unit tests only
uv run pytest tests/unit/

# Single test file
uv run pytest tests/path/to_file.py

# Single test by name
uv run pytest -k test_name

# With coverage
uv run pytest --cov=video_policy_orchestrator
```

### Test Organization

- **Unit tests**: `tests/unit/` - Mirror source structure
- **Integration tests**: `tests/integration/` - End-to-end scenarios
- **Fixtures**: `tests/conftest.py` - Shared fixtures

### Writing Tests

- Name test files `test_*.py`
- Name test functions `test_<what_is_being_tested>`
- Use pytest fixtures for setup/teardown
- Aim for focused tests that verify one behavior
- Use descriptive assertion messages

### Test Coverage

While we don't enforce coverage thresholds, aim to:
- Test all public functions
- Cover error paths and edge cases
- Include integration tests for CLI commands

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

## Release Process

VPO uses automated releases via GitHub Actions. Here's how releases work:

### Version Numbering

VPO follows [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes to CLI or plugin API
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes and minor improvements

### Creating a Release

1. **Update version** in `pyproject.toml`:
   ```toml
   [project]
   version = "X.Y.Z"
   ```

2. **Create and push a version tag**:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

3. **Automated workflows** (triggered by tag push):
   - `release.yml`: Builds wheels for Linux/macOS and publishes to PyPI
   - `docker.yml`: Builds and pushes container image to GHCR

### PyPI Trusted Publishing

VPO uses [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) for secure releases:
- No API tokens needed in repository secrets
- GitHub Actions authenticates directly with PyPI
- Configured via PyPI project settings (requires maintainer access)

### Pre-release Testing

Before creating a release tag:

1. **Run full test suite**:
   ```bash
   uv run pytest
   uv run ruff check .
   ```

2. **Test wheel build locally**:
   ```bash
   uv run maturin build --release
   ```

3. **For major releases**, consider a release candidate:
   ```bash
   git tag vX.Y.Z-rc1
   git push origin vX.Y.Z-rc1
   # Test installation from TestPyPI
   ```

### Container Images

Container images are published to GitHub Container Registry (ghcr.io):
- `ghcr.io/randomparity/vpo:latest` - Latest stable release
- `ghcr.io/randomparity/vpo:vX.Y.Z` - Specific version
- `ghcr.io/randomparity/vpo:main` - Latest main branch (may be unstable)

## Security

### Reporting Vulnerabilities

If you discover a security vulnerability, please:

1. **Do not** open a public issue
2. Email the maintainers directly with details
3. Include steps to reproduce if possible
4. Allow reasonable time for a fix before disclosure

We take security seriously and will respond promptly to reports.

### Security Considerations

When contributing code:

- Avoid hardcoded credentials or secrets
- Validate all user input
- Use parameterized queries for database operations
- Follow the principle of least privilege
- Be cautious with subprocess calls and shell commands

## Getting Help

- Open an issue for questions or feature ideas
- Check existing issues before creating new ones
- Join discussions on open PRs and issues

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

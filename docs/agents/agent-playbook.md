# Agent Playbook

**Purpose:**
Step-by-step instructions for LLM agents working on the VPO codebase. Follow these guidelines to maintain consistency and avoid common pitfalls.

---

## Before Starting Work

### 1. Read CLAUDE.md

Always start by reading `/CLAUDE.md` for:
- Project overview and current state
- Development guidelines and patterns
- Active technologies and recent changes

### 2. Understand the Task

Before writing code:
- Clarify requirements if ambiguous
- Check if similar functionality exists
- Review relevant spec files in `specs/`

### 3. Find Existing Patterns

Look for patterns in existing code:
- CLI commands: `src/vpo/cli/`
- Database operations: `src/vpo/db/models.py`
- Introspection: `src/vpo/introspector/`

---

## Code Standards

### Python Style

- Follow ruff linting rules (configured in `pyproject.toml`)
- Use type hints for all function signatures
- Prefer dataclasses over dicts for structured data
- Use `from __future__ import annotations` for forward references

### Time Handling

Always use UTC:
```python
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
```

Never use naive datetimes or `datetime.now()` without timezone.

### Database Operations

- Use parameterized queries (never string concatenation)
- Implement upsert patterns for idempotence
- Store timestamps as ISO 8601 TEXT
- Store booleans as INTEGER (0/1)

### Error Handling

- Use custom exceptions for domain errors
- Collect errors during batch operations, don't fail fast
- Provide user-friendly error messages with hints
- Use appropriate exit codes for CLI commands

---

## Testing Requirements

### Before Submitting

1. Run tests: `uv run pytest`
2. Run linter: `uv run ruff check .`
3. Run formatter: `uv run ruff format .`

### Test Structure

- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- Fixtures: `tests/conftest.py`

### Writing Tests

- Test happy path and error cases
- Mock external dependencies (subprocess, file system)
- Use fixtures for database connections

---

## Documentation Updates

### When to Update Docs

- New CLI commands → Update `docs/usage/cli-usage.md`
- New configuration options → Update `docs/usage/configuration.md`
- New design patterns → Update relevant design doc
- New terms → Update `docs/glossary.md`

### Documentation Rules

1. All docs go in `/docs/` subdirectories
2. Add new docs to `docs/INDEX.md`
3. Include "Related docs" section at bottom
4. Keep docs focused and concise

---

## Checklist Before Finalizing

### Code Quality

- [ ] All tests pass (`uv run pytest`)
- [ ] Linter passes (`uv run ruff check .`)
- [ ] Code is formatted (`uv run ruff format .`)
- [ ] Type hints are complete
- [ ] Docstrings explain non-obvious behavior

### Consistency

- [ ] Follows existing patterns in codebase
- [ ] Uses UTC for all timestamps
- [ ] Error messages are user-friendly
- [ ] Exit codes follow conventions

### Documentation

- [ ] New features are documented
- [ ] INDEX.md updated if new docs added
- [ ] CLAUDE.md updated if new patterns introduced

### Testing

- [ ] Unit tests for new functions
- [ ] Integration tests for CLI commands
- [ ] Edge cases covered

---

## Common Pitfalls to Avoid

### Don't

- Use `datetime.now()` without timezone
- Store local time in database
- Hardcode file paths
- Use inline SQL in business logic
- Catch bare `Exception` without re-raising

### Do

- Use `datetime.now(timezone.utc)`
- Store UTC timestamps in ISO 8601 format
- Use Path objects and configurable paths
- Keep SQL in database layer (models.py)
- Handle specific exceptions appropriately

---

## Getting Help

If stuck:
1. Search existing code for similar patterns
2. Read spec files in `specs/` for design intent
3. Check test files for usage examples
4. Review recent commits for context

---

## Related docs

- [Documentation Index](../INDEX.md)
- [Agent Prompts](agent-prompts.md)
- [Error Handling](../internals/error-handling.md)
- [Time and Timezones](../internals/time-and-timezones.md)

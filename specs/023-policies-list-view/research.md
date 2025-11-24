# Research: Policies List View

**Feature**: 023-policies-list-view
**Date**: 2025-11-24

## Overview

This document captures research findings for implementing the Policies list view feature. The feature reads policy YAML files from disk and displays them in a web UI, following established patterns from the Jobs and Library dashboards.

## Research Topics

### 1. Policy File Discovery Pattern

**Decision**: Create a `discover_policies()` function in a new `policy/discovery.py` module

**Rationale**:
- Policy files are YAML files stored in `~/.vpo/policies/`
- Need to list files, read metadata, and handle parse errors gracefully
- Separate from `policy/loader.py` which does full validation; discovery needs partial parsing
- Encapsulates filesystem access per Constitution Principle VI (IO Separation)

**Implementation Notes**:
```python
def discover_policies(
    policies_dir: Path | None = None,
    default_policy_path: Path | None = None
) -> list[PolicySummary]:
    """Discover all policy files and extract metadata.

    Args:
        policies_dir: Directory to scan (default: ~/.vpo/policies/)
        default_policy_path: Path from profile's default_policy setting

    Returns:
        List of PolicySummary, sorted: default first, then alphabetically
    """
```

**Alternatives Considered**:
- Add to `policy/loader.py`: Rejected - loader does full validation; discovery needs lightweight parsing
- Inline in route handler: Rejected - violates IO separation principle

### 2. Lightweight Policy Parsing Strategy

**Decision**: Parse YAML but catch errors; extract only display-relevant fields

**Rationale**:
- Full `load_policy()` validation is expensive and fails on invalid files
- We need to show invalid files with error indicators, not skip them
- Only need: schema_version, audio_language_preference, subtitle_language_preference, transcode/transcription presence

**Implementation**:
```python
def _parse_policy_summary(path: Path) -> PolicySummary:
    """Parse policy file for display metadata.

    Returns PolicySummary with parse_error set if YAML invalid.
    """
    try:
        with open(path) as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            return PolicySummary(
                name=path.stem,
                filename=path.name,
                parse_error="Invalid format: expected YAML mapping"
            )

        return PolicySummary(
            name=path.stem,
            filename=path.name,
            last_modified=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
            schema_version=data.get("schema_version"),
            audio_languages=data.get("audio_language_preference", []),
            subtitle_languages=data.get("subtitle_language_preference", []),
            has_transcode=data.get("transcode") is not None,
            has_transcription=data.get("transcription", {}).get("enabled", False),
        )
    except yaml.YAMLError as e:
        return PolicySummary(
            name=path.stem,
            filename=path.name,
            parse_error=f"YAML error: {e}"
        )
    except OSError as e:
        return PolicySummary(
            name=path.stem,
            filename=path.name,
            parse_error=f"Read error: {e}"
        )
```

**Alternatives Considered**:
- Use existing `load_policy()` with try/catch: Rejected - too strict; fails on any validation error
- Parse only first N lines: Rejected - YAML requires full parse for structure

### 3. Default Policy Detection

**Decision**: Compare resolved paths to determine if a policy is the default

**Rationale**:
- Profile's `default_policy` may be an absolute path or relative path with `~`
- Policy files in the list have their own paths
- Must resolve both to canonical form for comparison

**Implementation**:
```python
def _is_default_policy(policy_path: Path, default_policy_path: Path | None) -> bool:
    """Check if policy_path matches the profile's default_policy."""
    if default_policy_path is None:
        return False
    try:
        return policy_path.resolve() == default_policy_path.expanduser().resolve()
    except (OSError, ValueError):
        return False
```

**Edge Cases**:
- `default_policy` points to file outside `~/.vpo/policies/`: Still match if paths resolve equal
- `default_policy` file doesn't exist: Flag as missing_default in response metadata

### 4. Language Preference Display Format

**Decision**: Display as comma-separated list, show first 3 with overflow indicator

**Rationale**:
- Consistent with Library page's audio language display pattern
- Most policies have 2-3 language preferences
- Keep display compact but informative

**Implementation**:
```python
def format_language_preferences(languages: list[str]) -> str:
    """Format language preference list for display."""
    if not languages:
        return "—"
    if len(languages) <= 3:
        return ", ".join(languages)
    return f"{', '.join(languages[:3])} +{len(languages) - 3} more"
```

### 5. File Modification Time Handling

**Decision**: Use file system mtime, convert to UTC ISO-8601

**Rationale**:
- Constitution Principle I requires UTC datetime handling
- `stat().st_mtime` returns Unix timestamp; convert to timezone-aware datetime
- Display as relative time on client (consistent with Jobs/Library)

**Implementation**:
```python
from datetime import datetime, timezone

mtime = path.stat().st_mtime
last_modified = datetime.fromtimestamp(mtime, tz=timezone.utc)
# Serialize as ISO-8601: last_modified.isoformat()
```

### 6. API Response Structure

**Decision**: Follow existing `JobListResponse` pattern with items list and metadata

**Rationale**:
- Consistency with existing API patterns
- Includes count for UI display ("Showing N policies")
- Includes metadata for missing default warning

**Response Shape**:
```python
@dataclass
class PolicyListResponse:
    """API response for policies list."""
    policies: list[PolicyListItem]
    total: int
    default_policy_path: str | None  # From profile config
    default_policy_missing: bool     # True if configured but file not found
```

### 7. Empty State and Error Handling

**Decision**: Three distinct states with appropriate messaging

**States**:
1. **Directory doesn't exist**: "No policies directory found. Create ~/.vpo/policies/ and add policy files."
2. **Directory empty**: "No policy files found. Add .yaml files to ~/.vpo/policies/ to get started."
3. **Has policies**: Show list with badges for invalid ones

**Implementation**:
- Check `policies_dir.exists()` first
- Then `list(policies_dir.glob("*.yaml")) + list(policies_dir.glob("*.yml"))`
- Return appropriate empty state message in response

### 8. Sorting Strategy

**Decision**: Default policy first, then alphabetically by filename (case-insensitive)

**Rationale**:
- Per spec clarification: "Default policy first, then alphabetically"
- Case-insensitive sort is more user-friendly
- Stable sort order for predictable UI

**Implementation**:
```python
def _sort_policies(policies: list[PolicySummary]) -> list[PolicySummary]:
    """Sort: default first, then alphabetically by name."""
    return sorted(
        policies,
        key=lambda p: (not p.is_default, p.name.lower())
    )
```

## Summary of Decisions

| Topic | Decision |
|-------|----------|
| Discovery pattern | New `policy/discovery.py` module with `discover_policies()` |
| Parsing strategy | Lightweight YAML parse; capture errors without failing |
| Default detection | Compare resolved paths from profile config |
| Language display | First 3 + "+N more" overflow (existing pattern) |
| Timestamps | UTC ISO-8601 (Constitution Principle I) |
| API structure | Follow `JobListResponse` pattern |
| Empty states | Three distinct messages based on directory/file state |
| Sorting | Default first, then alphabetical (case-insensitive) |

## Dependencies Identified

1. **New**: `policy/discovery.py` - Policy file discovery and summary extraction
2. **Existing**: `server/ui/models.py` - Add `PolicyListItem`, `PolicyListResponse`
3. **Existing**: `server/ui/routes.py` - Add `policies_handler()`, `policies_api_handler()`
4. **Existing**: `server/ui/templates/sections/policies.html` - Update placeholder template
5. **Existing**: `server/static/css/main.css` - Add badge styles for transcode/transcription indicators
6. **New**: `tests/unit/policy/test_discovery.py` - Unit tests
7. **New**: `tests/fixtures/policies/` - Test policy files (valid, invalid, various configs)

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Policies directory permissions | Low | Medium | Catch OSError, display appropriate message |
| Large policy files slow parsing | Low | Low | YAML parse is fast; no mitigation needed for <50 files |
| Profile default_policy config missing | Medium | Low | Handle None gracefully; no default badge shown |
| Unicode filenames | Low | Low | Python 3 + pathlib handle Unicode natively |

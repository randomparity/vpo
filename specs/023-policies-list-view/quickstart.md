# Quickstart: Policies List View Implementation

**Feature**: 023-policies-list-view
**Date**: 2025-11-24

## Overview

This guide provides a quick reference for implementing the Policies list view feature. The implementation follows established patterns from the Jobs and Library dashboards.

## Implementation Order

1. **Policy discovery module** (`policy/discovery.py`) - NEW
2. **View models** (`server/ui/models.py`)
3. **Route handlers** (`server/ui/routes.py`)
4. **HTML template** (`server/ui/templates/sections/policies.html`)
5. **CSS styles** (`server/static/css/main.css`)
6. **Tests**

Note: No JavaScript file needed - server-rendered page with no dynamic updates.

## 1. Policy Discovery Module

**File**: `src/vpo/policy/discovery.py` (NEW FILE)

```python
"""Policy file discovery and metadata extraction."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

DEFAULT_POLICIES_DIR = Path.home() / ".vpo" / "policies"


@dataclass
class PolicySummary:
    """Summary of a policy file for list display."""

    name: str
    filename: str
    file_path: str = ""
    last_modified: str = ""
    schema_version: int | None = None
    audio_languages: list[str] = field(default_factory=list)
    subtitle_languages: list[str] = field(default_factory=list)
    has_transcode: bool = False
    has_transcription: bool = False
    is_default: bool = False
    parse_error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "filename": self.filename,
            "file_path": self.file_path,
            "last_modified": self.last_modified,
            "schema_version": self.schema_version,
            "audio_languages": self.audio_languages,
            "subtitle_languages": self.subtitle_languages,
            "has_transcode": self.has_transcode,
            "has_transcription": self.has_transcription,
            "is_default": self.is_default,
            "parse_error": self.parse_error,
        }


def _parse_policy_file(path: Path) -> PolicySummary:
    """Parse a policy file and extract display metadata.

    Args:
        path: Path to the policy YAML file.

    Returns:
        PolicySummary with extracted metadata or parse_error if invalid.
    """
    try:
        mtime = path.stat().st_mtime
        last_modified = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    except OSError:
        last_modified = ""

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            return PolicySummary(
                name=path.stem,
                filename=path.name,
                file_path=str(path.resolve()),
                last_modified=last_modified,
                parse_error="Invalid format: expected YAML mapping",
            )

        # Extract transcription enabled status
        transcription = data.get("transcription")
        has_transcription = (
            isinstance(transcription, dict) and transcription.get("enabled", False)
        )

        return PolicySummary(
            name=path.stem,
            filename=path.name,
            file_path=str(path.resolve()),
            last_modified=last_modified,
            schema_version=data.get("schema_version"),
            audio_languages=data.get("audio_language_preference", []),
            subtitle_languages=data.get("subtitle_language_preference", []),
            has_transcode=data.get("transcode") is not None,
            has_transcription=has_transcription,
        )
    except yaml.YAMLError as e:
        return PolicySummary(
            name=path.stem,
            filename=path.name,
            file_path=str(path.resolve()),
            last_modified=last_modified,
            parse_error=f"YAML error: {e}",
        )
    except OSError as e:
        return PolicySummary(
            name=path.stem,
            filename=path.name,
            file_path=str(path.resolve()),
            last_modified=last_modified,
            parse_error=f"Read error: {e}",
        )


def _is_default_policy(policy_path: Path, default_policy_path: Path | None) -> bool:
    """Check if policy_path matches the profile's default_policy."""
    if default_policy_path is None:
        return False
    try:
        return policy_path.resolve() == default_policy_path.expanduser().resolve()
    except (OSError, ValueError):
        return False


def discover_policies(
    policies_dir: Path | None = None,
    default_policy_path: Path | None = None,
) -> tuple[list[PolicySummary], bool]:
    """Discover all policy files in the policies directory.

    Args:
        policies_dir: Directory to scan (default: ~/.vpo/policies/).
        default_policy_path: Path from profile's default_policy setting.

    Returns:
        Tuple of:
        - List of PolicySummary sorted (default first, then alphabetically)
        - bool indicating if default_policy_path was set but file not found
    """
    if policies_dir is None:
        policies_dir = DEFAULT_POLICIES_DIR

    policies_dir = policies_dir.expanduser()

    if not policies_dir.exists():
        logger.debug("Policies directory does not exist: %s", policies_dir)
        return [], default_policy_path is not None

    # Find all .yaml and .yml files
    policy_files = list(policies_dir.glob("*.yaml")) + list(policies_dir.glob("*.yml"))

    policies = []
    default_found = False

    for path in policy_files:
        summary = _parse_policy_file(path)
        summary.is_default = _is_default_policy(path, default_policy_path)
        if summary.is_default:
            default_found = True
        policies.append(summary)

    # Sort: default first, then alphabetically by name
    policies.sort(key=lambda p: (not p.is_default, p.name.lower()))

    # Check if default policy is missing
    default_missing = default_policy_path is not None and not default_found

    return policies, default_missing
```

## 2. View Models

**File**: `src/vpo/server/ui/models.py`

Add these classes and helper functions:

```python
def format_language_preferences(languages: list[str]) -> str:
    """Format language preference list for display."""
    if not languages:
        return "—"
    if len(languages) <= 3:
        return ", ".join(languages)
    return f"{', '.join(languages[:3])} +{len(languages) - 3} more"


@dataclass
class PolicyListItem:
    """Policy data for Policies API response."""

    name: str
    filename: str
    file_path: str
    last_modified: str
    schema_version: int | None
    audio_languages: str
    subtitle_languages: str
    has_transcode: bool
    has_transcription: bool
    is_default: bool
    parse_error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "filename": self.filename,
            "file_path": self.file_path,
            "last_modified": self.last_modified,
            "schema_version": self.schema_version,
            "audio_languages": self.audio_languages,
            "subtitle_languages": self.subtitle_languages,
            "has_transcode": self.has_transcode,
            "has_transcription": self.has_transcription,
            "is_default": self.is_default,
            "parse_error": self.parse_error,
        }


@dataclass
class PolicyListResponse:
    """API response wrapper for /api/policies."""

    policies: list[PolicyListItem]
    total: int
    policies_directory: str
    default_policy_path: str | None
    default_policy_missing: bool
    directory_exists: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "policies": [p.to_dict() for p in self.policies],
            "total": self.total,
            "policies_directory": self.policies_directory,
            "default_policy_path": self.default_policy_path,
            "default_policy_missing": self.default_policy_missing,
            "directory_exists": self.directory_exists,
        }


@dataclass
class PoliciesContext:
    """Template context for policies.html."""

    policies_directory: str

    @classmethod
    def default(cls) -> PoliciesContext:
        """Create default context."""
        return cls(
            policies_directory=str(Path.home() / ".vpo" / "policies"),
        )
```

## 3. Route Handlers

**File**: `src/vpo/server/ui/routes.py`

Add handlers:

```python
from vpo.policy.discovery import (
    DEFAULT_POLICIES_DIR,
    discover_policies,
)


@aiohttp_jinja2.template("sections/policies.html")
async def policies_handler(request: web.Request) -> dict:
    """Render the Policies page."""
    # Get default policy from active profile
    default_policy_path = None
    try:
        from vpo.config.profiles import get_active_profile
        profile = get_active_profile()
        if profile and profile.default_policy:
            default_policy_path = profile.default_policy
    except Exception:
        pass

    # Discover policies
    policies_dir = DEFAULT_POLICIES_DIR
    summaries, default_missing = await asyncio.to_thread(
        discover_policies,
        policies_dir,
        default_policy_path,
    )

    # Convert to PolicyListItem
    policies = [
        PolicyListItem(
            name=s.name,
            filename=s.filename,
            file_path=s.file_path,
            last_modified=s.last_modified,
            schema_version=s.schema_version,
            audio_languages=format_language_preferences(s.audio_languages),
            subtitle_languages=format_language_preferences(s.subtitle_languages),
            has_transcode=s.has_transcode,
            has_transcription=s.has_transcription,
            is_default=s.is_default,
            parse_error=s.parse_error,
        )
        for s in summaries
    ]

    response = PolicyListResponse(
        policies=policies,
        total=len(policies),
        policies_directory=str(policies_dir),
        default_policy_path=str(default_policy_path) if default_policy_path else None,
        default_policy_missing=default_missing,
        directory_exists=policies_dir.exists(),
    )

    return _create_template_context(
        active_id="policies",
        section_title="Policies",
        policies_context=PoliciesContext.default(),
        policies_response=response,
    )


async def policies_api_handler(request: web.Request) -> web.Response:
    """GET /api/policies - List policy files."""
    default_policy_path = None
    try:
        from vpo.config.profiles import get_active_profile
        profile = get_active_profile()
        if profile and profile.default_policy:
            default_policy_path = profile.default_policy
    except Exception:
        pass

    policies_dir = DEFAULT_POLICIES_DIR
    summaries, default_missing = await asyncio.to_thread(
        discover_policies,
        policies_dir,
        default_policy_path,
    )

    policies = [
        PolicyListItem(
            name=s.name,
            filename=s.filename,
            file_path=s.file_path,
            last_modified=s.last_modified,
            schema_version=s.schema_version,
            audio_languages=format_language_preferences(s.audio_languages),
            subtitle_languages=format_language_preferences(s.subtitle_languages),
            has_transcode=s.has_transcode,
            has_transcription=s.has_transcription,
            is_default=s.is_default,
            parse_error=s.parse_error,
        )
        for s in summaries
    ]

    response = PolicyListResponse(
        policies=policies,
        total=len(policies),
        policies_directory=str(policies_dir),
        default_policy_path=str(default_policy_path) if default_policy_path else None,
        default_policy_missing=default_missing,
        directory_exists=policies_dir.exists(),
    )

    return web.json_response(response.to_dict())
```

Register routes in `setup_ui_routes()`:

```python
app.router.add_get("/policies", policies_handler)
app.router.add_get("/api/policies", policies_api_handler)
```

## 4. HTML Template

**File**: `src/vpo/server/ui/templates/sections/policies.html`

Replace placeholder content. Key elements:
- Info banner showing policies directory path
- Warning banner if default policy missing
- Table with columns: Name, Version, Audio Langs, Subtitle Langs, Features, Modified
- "Default" badge for default policy
- "Error" badge for policies with parse errors
- "Transcode" / "Transcription" badges for feature indicators
- Empty state messages for missing directory or empty directory

## 5. CSS

**File**: `src/vpo/server/static/css/main.css`

Add policy-specific styles:

```css
/* Policy badges */
.badge-default {
    background-color: var(--color-success);
    color: white;
}

.badge-error {
    background-color: var(--color-error);
    color: white;
}

.badge-transcode {
    background-color: var(--color-info);
    color: white;
}

.badge-transcription {
    background-color: var(--color-warning);
    color: black;
}

/* Policies table */
.policies-table { /* same as .jobs-table */ }
.policies-empty { /* same as .jobs-empty */ }
.policies-info { /* info banner styles */ }
.policies-warning { /* warning banner styles */ }
```

## Testing Checklist

- [ ] Unit tests for `_parse_policy_file()` with valid YAML
- [ ] Unit tests for `_parse_policy_file()` with invalid YAML
- [ ] Unit tests for `_parse_policy_file()` with missing file
- [ ] Unit tests for `_is_default_policy()` path comparison
- [ ] Unit tests for `discover_policies()` with various scenarios
- [ ] Unit tests for `format_language_preferences()` edge cases
- [ ] Integration test for `/api/policies` endpoint
- [ ] Integration test for `/policies` HTML page
- [ ] Manual test with empty policies directory
- [ ] Manual test with missing policies directory
- [ ] Manual test with invalid policy files
- [ ] Manual test with configured default policy

## Test Fixtures

Create test policy files in `tests/fixtures/policies/`:

```yaml
# valid-basic.yaml
schema_version: 2
audio_language_preference: [eng]
subtitle_language_preference: [eng]

# valid-full.yaml
schema_version: 2
audio_language_preference: [eng, jpn, spa]
subtitle_language_preference: [eng, spa]
transcode:
  target_video_codec: hevc
transcription:
  enabled: true

# invalid-syntax.yaml
schema_version: 2
audio_language_preference: [eng
  # missing closing bracket

# invalid-format.yaml
- this
- is
- a list
- not a mapping
```

## Reference Files

| Pattern | Reference File |
|---------|---------------|
| Discovery pattern | `policy/loader.py` → `load_policy()` |
| View models | `server/ui/models.py` → `JobListItem`, `FileListItem` |
| Route handler | `server/ui/routes.py` → `library_api_handler()` |
| HTML template | `server/ui/templates/sections/library.html` |

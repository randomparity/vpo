# Data Model: Policies List View

**Feature**: 023-policies-list-view
**Date**: 2025-11-24

## Overview

This document defines the data models for the Policies list view feature. Unlike the Library feature, this feature reads from the filesystem (YAML policy files) rather than the database. New view models are added for API responses and template rendering.

## Source Data: Policy YAML Files

Policy files are stored in `~/.vpo/policies/` with `.yaml` or `.yml` extensions. The existing `PolicySchema` dataclass defines the validated policy structure, but for the list view we extract only display-relevant metadata.

### PolicySchema Fields Used for Display

From `policy/models.py`:

| Field | Type | Description |
|-------|------|-------------|
| schema_version | int | Policy format version (1 or 2) |
| audio_language_preference | tuple[str, ...] | Preferred audio languages |
| subtitle_language_preference | tuple[str, ...] | Preferred subtitle languages |
| transcode | TranscodePolicyConfig \| None | Transcode settings (presence indicates transcode policy) |
| transcription | TranscriptionPolicyOptions \| None | Transcription settings (.enabled indicates active) |

### File System Metadata

| Attribute | Source | Description |
|-----------|--------|-------------|
| filename | `path.name` | Full filename with extension |
| name | `path.stem` | Filename without extension (display name) |
| last_modified | `path.stat().st_mtime` | File modification timestamp |
| file_path | `path.resolve()` | Absolute path to file |

## New Module: policy/discovery.py

### PolicySummary

Lightweight representation of policy metadata for display.

```python
@dataclass
class PolicySummary:
    """Summary of a policy file for list display.

    Attributes:
        name: Policy name (filename without extension).
        filename: Full filename including extension.
        file_path: Absolute path to the policy file.
        last_modified: File modification time (UTC ISO-8601).
        schema_version: Policy schema version if parseable.
        audio_languages: Audio language preferences list.
        subtitle_languages: Subtitle language preferences list.
        has_transcode: True if policy includes transcode settings.
        has_transcription: True if policy has transcription.enabled=True.
        is_default: True if this is the profile's default policy.
        parse_error: Error message if YAML parsing failed, else None.
    """

    name: str
    filename: str
    file_path: str = ""
    last_modified: str = ""  # ISO-8601 UTC
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
```

### discover_policies()

Main discovery function.

```python
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
```

## New View Models (server/ui/models.py)

### PolicyListItem

Policy data for API response and template rendering.

```python
@dataclass
class PolicyListItem:
    """Policy data for Policies API response.

    Attributes:
        name: Policy name (filename without extension).
        filename: Full filename with extension.
        file_path: Absolute path to the policy file.
        last_modified: ISO-8601 UTC timestamp.
        schema_version: Policy schema version (null if parse error).
        audio_languages: Formatted audio language preferences.
        subtitle_languages: Formatted subtitle language preferences.
        has_transcode: True if policy includes transcode settings.
        has_transcription: True if transcription enabled.
        is_default: True if this is the profile's default policy.
        parse_error: Error message if YAML invalid, else None.
    """

    name: str
    filename: str
    file_path: str
    last_modified: str
    schema_version: int | None
    audio_languages: str  # Formatted string
    subtitle_languages: str  # Formatted string
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
```

### PolicyListResponse

API response wrapper.

```python
@dataclass
class PolicyListResponse:
    """API response wrapper for /api/policies.

    Attributes:
        policies: List of policy items.
        total: Total number of policies found.
        policies_directory: Path to policies directory.
        default_policy_path: Configured default policy path (may be None).
        default_policy_missing: True if configured default doesn't exist.
        directory_exists: True if policies directory exists.
    """

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
```

### PoliciesContext

Template context for policies.html.

```python
@dataclass
class PoliciesContext:
    """Template context for policies.html.

    Attributes:
        policies_directory: Path to policies directory for display.
    """

    policies_directory: str

    @classmethod
    def default(cls) -> PoliciesContext:
        """Create default context."""
        return cls(
            policies_directory=str(Path.home() / ".vpo" / "policies"),
        )
```

## Helper Functions (server/ui/models.py)

### format_language_preferences()

```python
def format_language_preferences(languages: list[str]) -> str:
    """Format language preference list for display.

    Args:
        languages: List of ISO 639-2 language codes.

    Returns:
        Formatted string (e.g., "eng, jpn" or "eng, jpn +2 more") or "—".
    """
    if not languages:
        return "—"

    if len(languages) <= 3:
        return ", ".join(languages)

    return f"{', '.join(languages[:3])} +{len(languages) - 3} more"
```

## Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  GET /api/      │     │  discover_       │     │  ~/.vpo/        │
│  policies       │────▶│  policies()      │────▶│  policies/*.yaml│
│                 │     │  (policy/        │     │  (filesystem)   │
└────────┬────────┘     │  discovery.py)   │     └─────────────────┘
         │              └────────┬─────────┘
         │                       │
         │                       ▼
         │              ┌──────────────────┐
         │              │  PolicySummary   │
         │              │  list (raw       │
         │              │  metadata)       │
         │              └────────┬─────────┘
         │                       │
         │                       ▼
         │              ┌──────────────────┐
         │              │  PolicyListItem  │
         │              │  (formatted      │
         │              │  for display)    │
         │              └────────┬─────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌──────────────────┐
│  PolicyList     │◀────│  Transform &     │
│  Response       │     │  format          │
│  (JSON)         │     │  (view models)   │
└─────────────────┘     └──────────────────┘
```

## Profile Integration

The default policy is read from the active profile configuration:

```python
# In routes.py
from video_policy_orchestrator.config.profiles import get_active_profile

profile = get_active_profile()
default_policy_path = profile.default_policy if profile else None
```

## Validation Rules

| Field | Rule | Error Handling |
|-------|------|----------------|
| YAML content | Valid YAML mapping | Set parse_error, leave other fields empty |
| schema_version | Integer >= 1 | Show as None if missing/invalid |
| audio_languages | List of strings | Show "—" if empty |
| subtitle_languages | List of strings | Show "—" if empty |
| has_transcode | Check transcode key exists | Default False |
| has_transcription | Check transcription.enabled | Default False |
| last_modified | Valid file stat | Use epoch if unavailable |

## Sorting Rules

Policies are sorted with a two-level key:
1. Default policy first (`is_default=True`)
2. Alphabetically by name (case-insensitive)

```python
def _sort_policies(policies: list[PolicySummary]) -> list[PolicySummary]:
    """Sort policies: default first, then alphabetically."""
    return sorted(
        policies,
        key=lambda p: (not p.is_default, p.name.lower())
    )
```

## Empty States

| Condition | directory_exists | total | Message |
|-----------|-----------------|-------|---------|
| Directory doesn't exist | False | 0 | "Create ~/.vpo/policies/ and add policy files" |
| Directory empty | True | 0 | "No policy files found" |
| Has policies | True | N | Show list |

## No Database Changes

This feature does not modify the database schema. All data is read from:
1. Filesystem (policy YAML files)
2. Configuration (active profile's default_policy setting)

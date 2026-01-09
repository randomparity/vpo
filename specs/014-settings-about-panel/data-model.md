# Data Model: Settings/About Panel

**Feature**: 014-settings-about-panel
**Date**: 2025-11-23

## Overview

This feature is primarily a read-only display layer with no persistent data. The data model consists of view models for template rendering.

## Entities

### AboutInfo (View Model)

Represents the configuration information displayed on the About page.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | `str` | Yes | Application version (e.g., "0.1.0") |
| `git_hash` | `str \| None` | No | Git commit hash if available |
| `profile_name` | `str` | Yes | Current profile name or "Default" |
| `api_url` | `str` | Yes | Base URL for API access |
| `docs_url` | `str` | Yes | URL to documentation |
| `is_read_only` | `bool` | Yes | Always `True` for this version |

### NavigationItem (Existing)

Extended usage - add new item for "About" section.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | `"about"` |
| `label` | `str` | `"About"` |
| `path` | `str` | `"/about"` |
| `icon` | `str \| None` | `None` (optional future use) |

## Relationships

```
AboutInfo
    └── displayed on → About Page
    └── populated from → Application Context, Request, Package

NavigationItem (about)
    └── member of → NAVIGATION_ITEMS list
    └── rendered in → base.html sidebar
```

## State Transitions

N/A - No mutable state. All data is read-only at display time.

## Validation Rules

| Rule | Constraint |
|------|------------|
| `version` | Non-empty string |
| `api_url` | Valid URL format |
| `docs_url` | Valid URL format |
| `profile_name` | Non-empty string (fallback to "Default") |

## Data Sources

| Field | Source | Access Method |
|-------|--------|---------------|
| `version` | Package metadata | `from vpo import __version__` |
| `git_hash` | Environment variable | `os.environ.get("VPO_GIT_HASH")` |
| `profile_name` | App context | `request.app.get("profile_name", "Default")` |
| `api_url` | Request URL | `str(request.url.origin())` |
| `docs_url` | Constant | `"https://github.com/randomparity/vpo/tree/main/docs"` |

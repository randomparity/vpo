# Data Model: Web UI Shell with Global Navigation

**Feature**: 013-web-ui-shell
**Date**: 2025-11-23

## Overview

The Web UI Shell is a presentation-layer feature with minimal data modeling requirements. The shell itself is stateless - it renders navigation and placeholder content without persisting any data. The data model focuses on the navigation configuration and template context structures.

## Entities

### NavigationItem

Represents a single navigation link in the sidebar.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique identifier, matches route path (e.g., "jobs") |
| `label` | `str` | Yes | Display text shown in navigation (e.g., "Jobs") |
| `path` | `str` | Yes | URL path (e.g., "/jobs") |
| `icon` | `str` | No | Optional icon identifier for future use |

**Validation Rules**:
- `id` must be lowercase alphanumeric with hyphens
- `label` must be non-empty, max 30 characters
- `path` must start with `/`

**Example**:
```python
NavigationItem(
    id="jobs",
    label="Jobs",
    path="/jobs",
    icon="briefcase"
)
```

### NavigationState

Tracks which navigation item is currently active.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `items` | `list[NavigationItem]` | Yes | Ordered list of all navigation items |
| `active_id` | `str` | Yes | ID of the currently active section |

**Derivation**: `active_id` is determined by matching the current request path to navigation item paths.

### TemplateContext

Context passed to Jinja2 templates for rendering.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `nav` | `NavigationState` | Yes | Navigation configuration and state |
| `section_title` | `str` | Yes | Title for the current section |
| `section_content` | `str` | No | Optional HTML content for section body |

## Relationships

```
NavigationState
    └── contains many → NavigationItem (ordered)

TemplateContext
    └── contains one → NavigationState
```

## State Transitions

N/A - The UI shell is stateless. Each request receives a fresh context based on the requested path.

## Data Volume / Scale

- **Navigation Items**: Fixed at 5 (Jobs, Library, Transcriptions, Policies, Approvals)
- **Concurrent Users**: Single operator assumption (spec constraint)
- **Template Rendering**: In-memory, no persistence

## Default Navigation Configuration

```python
NAVIGATION_ITEMS = [
    NavigationItem(id="jobs", label="Jobs", path="/jobs"),
    NavigationItem(id="library", label="Library", path="/library"),
    NavigationItem(id="transcriptions", label="Transcriptions", path="/transcriptions"),
    NavigationItem(id="policies", label="Policies", path="/policies"),
    NavigationItem(id="approvals", label="Approvals", path="/approvals"),
]

DEFAULT_SECTION = "jobs"
```

## No Database Changes

This feature does not modify the SQLite schema. All data is:
- Configuration (navigation items) - defined in code
- Runtime state (active section) - derived from request path
- Templates - static files on disk

# Data Model: Plugin Architecture & Extension Model

**Feature**: 005-plugin-architecture
**Date**: 2025-11-22

## Entities

### PluginManifest

Metadata describing a plugin. Immutable after loading.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | str | Yes | Unique plugin identifier (kebab-case) |
| version | str | Yes | Plugin version (semver format) |
| description | str | No | Human-readable description |
| author | str | No | Plugin author name/email |
| plugin_type | PluginType | Yes | `analyzer`, `mutator`, or `both` |
| min_api_version | str | Yes | Minimum supported API version |
| max_api_version | str | Yes | Maximum supported API version |
| events | list[str] | Yes | Events this plugin handles |
| source | PluginSource | Yes | `entry_point` or `directory` |
| source_path | Path | No | File path for directory plugins |

**Validation Rules**:
- `name` must be unique across all loaded plugins
- `name` must match pattern `^[a-z][a-z0-9-]*[a-z0-9]$` (2+ chars)
- `version` must be valid semver (e.g., `1.0.0`, `2.1.3-beta`)
- `min_api_version` <= `max_api_version`
- `events` must contain at least one valid event name

### PluginType (Enum)

```python
class PluginType(Enum):
    ANALYZER = "analyzer"
    MUTATOR = "mutator"
    BOTH = "both"
```

### PluginSource (Enum)

```python
class PluginSource(Enum):
    ENTRY_POINT = "entry_point"
    DIRECTORY = "directory"
    BUILTIN = "builtin"
```

### LoadedPlugin

Runtime representation of a loaded plugin instance.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| manifest | PluginManifest | Yes | Plugin metadata |
| instance | AnalyzerPlugin \| MutatorPlugin | Yes | Plugin instance |
| enabled | bool | Yes | Whether plugin is active |
| load_error | str \| None | No | Error message if loading failed |
| loaded_at | datetime | Yes | UTC timestamp of load |

### PluginRegistry

Central catalog of discovered and loaded plugins.

| Field | Type | Description |
|-------|------|-------------|
| plugins | dict[str, LoadedPlugin] | Map of plugin name to loaded plugin |
| api_version | str | Current core API version |
| plugin_dirs | list[Path] | Configured plugin directories |
| entry_point_group | str | Entry point group name |

**Operations**:
- `discover()` → list[PluginManifest]: Find all available plugins
- `load(name: str)` → LoadedPlugin: Load a specific plugin
- `load_all()` → list[LoadedPlugin]: Load all discovered plugins
- `get(name: str)` → LoadedPlugin | None: Get loaded plugin by name
- `get_by_event(event: str)` → list[LoadedPlugin]: Get plugins for event
- `enable(name: str)` → bool: Enable a plugin
- `disable(name: str)` → bool: Disable a plugin

### PluginAcknowledgment

Database record for directory plugin user acknowledgments.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | Yes | Primary key (auto) |
| plugin_name | str | Yes | Plugin identifier |
| plugin_hash | str | Yes | SHA-256 hash of plugin file(s) |
| acknowledged_at | datetime | Yes | UTC timestamp |
| acknowledged_by | str | No | User identifier (hostname) |

**Constraints**:
- Unique constraint on `(plugin_name, plugin_hash)`
- Index on `plugin_name` for lookup

### APIVersion

Version information for compatibility checking.

| Field | Type | Description |
|-------|------|-------------|
| major | int | Breaking changes |
| minor | int | New features (backward compatible) |
| patch | int | Bug fixes |

**Operations**:
- `parse(version_str: str)` → APIVersion: Parse semver string
- `is_compatible(plugin_min: APIVersion, plugin_max: APIVersion)` → bool: Check compatibility
- `__str__()` → str: Format as semver string

## Plugin Events

Events that plugins can subscribe to.

| Event Name | Trigger | Data Passed | Plugin Type |
|------------|---------|-------------|-------------|
| `file.scanned` | After ffprobe introspection | FileInfo, list[TrackInfo] | Analyzer |
| `file.metadata_enriched` | After analyzer plugins run | FileInfo (enriched) | Analyzer |
| `policy.before_evaluate` | Before policy evaluation | FileInfo, PolicySchema | Analyzer |
| `policy.after_evaluate` | After policy evaluation | FileInfo, Plan | Analyzer |
| `plan.before_execute` | Before plan execution | Plan | Mutator |
| `plan.after_execute` | After successful execution | Plan, ExecutorResult | Analyzer |
| `plan.execution_failed` | After execution failure | Plan, Exception | Analyzer |

## State Transitions

### Plugin Lifecycle

```
[Discovered] → [Loading] → [Loaded] → [Enabled]
                  ↓            ↓          ↓
              [Load Failed] [Disabled] [Error]
```

| State | Description |
|-------|-------------|
| Discovered | Plugin found by discovery mechanism |
| Loading | Plugin being imported and validated |
| Load Failed | Import or validation error |
| Loaded | Plugin instance created, not yet active |
| Enabled | Plugin active and receiving events |
| Disabled | Plugin loaded but not receiving events |
| Error | Runtime error during event handling |

### Acknowledgment Flow (Directory Plugins)

```
[New Plugin] → [Prompt User] → [Acknowledged] → [Loaded]
                    ↓
               [Rejected] → [Not Loaded]
```

## Database Schema Extension

```sql
-- New table for plugin acknowledgments
CREATE TABLE IF NOT EXISTS plugin_acknowledgments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_name TEXT NOT NULL,
    plugin_hash TEXT NOT NULL,
    acknowledged_at TEXT NOT NULL,  -- ISO-8601 UTC
    acknowledged_by TEXT,
    UNIQUE(plugin_name, plugin_hash)
);

CREATE INDEX IF NOT EXISTS idx_plugin_ack_name
    ON plugin_acknowledgments(plugin_name);
```

## Relationships

```
PluginRegistry 1──* LoadedPlugin
LoadedPlugin 1──1 PluginManifest
LoadedPlugin 1──1 (AnalyzerPlugin | MutatorPlugin)
PluginAcknowledgment *──1 (directory plugin)
```

## Data Volume Estimates

| Entity | Expected Count | Growth |
|--------|----------------|--------|
| LoadedPlugin | 5-20 typical, 50 max | Per user installation |
| PluginAcknowledgment | 1-10 | One per directory plugin |
| Events per operation | 2-5 | Per file processed |

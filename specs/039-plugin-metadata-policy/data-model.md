# Data Model: Plugin Metadata Access in Policies

**Feature**: 039-plugin-metadata-policy
**Date**: 2025-12-01

## New Types

### PluginMetadataOperator (Enum)

Operators for plugin metadata comparisons.

| Value | Description |
|-------|-------------|
| `EQ` | Equals comparison (`value == expected`) |
| `NEQ` | Not equals comparison (`value != expected`) |
| `CONTAINS` | Substring match for strings (`expected in value`) |
| `EXISTS` | Check if field is present and not None |

### PluginMetadataCondition (Dataclass)

Condition checking plugin-provided metadata.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `plugin_name` | `str` | Yes | Plugin identifier (e.g., "radarr", "sonarr") |
| `field_name` | `str` | Yes | Field within plugin data (e.g., "original_language") |
| `operator` | `PluginMetadataOperator` | Yes | Comparison operator |
| `value` | `str \| int \| None` | No | Expected value (required except for EXISTS) |

**Validation Rules**:
- `plugin_name` must be non-empty
- `field_name` must be non-empty
- `value` required when operator is EQ, NEQ, or CONTAINS
- `value` must be None when operator is EXISTS

**Evaluation Rules**:
- Missing plugin data → `(False, "no plugin metadata")`
- Missing plugin name in data → `(False, "plugin not in metadata")`
- Missing field in plugin data → `(False, "field not found")`
- For EXISTS: returns `(True, "exists")` if field present and not None

### PluginMetadataConditionModel (Pydantic)

Pydantic model for YAML parsing.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `plugin_metadata` | `str` | Yes | - | Reference in "plugin:field" format |
| `operator` | `Literal["eq", "neq", "contains", "exists"]` | No | `"eq"` | Comparison operator |
| `value` | `str \| int \| None` | No | `None` | Expected value |

**Validation**:
- `plugin_metadata` must contain exactly one colon
- Both plugin and field parts must be non-empty
- `value` required for operators other than "exists"

## Modified Types

### FileRecord (db/types.py)

Add field:

| Field | Type | Description |
|-------|------|-------------|
| `plugin_metadata` | `str \| None` | JSON string of plugin enrichment data |

### FileInfo (db/types.py)

Add field:

| Field | Type | Description |
|-------|------|-------------|
| `plugin_metadata` | `dict[str, dict[str, Any]] \| None` | Parsed plugin enrichment data |

### Condition (policy/models.py)

Update type union to include `PluginMetadataCondition`:

```python
Condition = (
    ExistsCondition
    | CountCondition
    | AndCondition
    | OrCondition
    | NotCondition
    | AudioIsMultiLanguageCondition
    | PluginMetadataCondition  # NEW
)
```

## Database Schema

### Migration v16 → v17

Add column to `files` table:

```sql
ALTER TABLE files ADD COLUMN plugin_metadata TEXT;
```

### Plugin Metadata JSON Schema

```json
{
  "type": "object",
  "additionalProperties": {
    "type": ["object", "null"],
    "description": "Plugin enrichment data keyed by field name"
  },
  "example": {
    "radarr": {
      "original_language": "jpn",
      "external_source": "radarr",
      "external_id": 12345,
      "external_title": "My Neighbor Totoro",
      "external_year": 1988,
      "imdb_id": "tt0096283",
      "tmdb_id": 8392
    },
    "sonarr": null
  }
}
```

## Known Plugin Fields Registry

Hard-coded registry for validation warnings.

### radarr

| Field | Type | Description |
|-------|------|-------------|
| `original_language` | `str` | ISO 639-2/B language code |
| `external_source` | `str` | Always "radarr" |
| `external_id` | `int` | Radarr movie ID |
| `external_title` | `str` | Movie title from Radarr |
| `external_year` | `int \| None` | Release year |
| `imdb_id` | `str \| None` | IMDB identifier |
| `tmdb_id` | `int \| None` | TMDB identifier |

### sonarr

All fields from radarr plus:

| Field | Type | Description |
|-------|------|-------------|
| `series_title` | `str \| None` | TV series title |
| `season_number` | `int \| None` | Season number |
| `episode_number` | `int \| None` | Episode number |
| `episode_title` | `str \| None` | Episode title |
| `tvdb_id` | `int \| None` | TVDB identifier |

## Relationships

```
FileRecord 1──1 plugin_metadata (JSON)
     │
     └── Contains multiple plugin namespaces
         │
         ├── radarr: { original_language, tmdb_id, ... }
         └── sonarr: { series_title, season_number, ... }

PolicySchema 1──* ConditionalRule
                      │
                      └── when: Condition
                               │
                               └── PluginMetadataCondition
                                        │
                                        └── References plugin_metadata via plugin_name:field_name
```

## State Transitions

N/A - This feature adds read-only condition evaluation. Plugin metadata is written by the scanner and read by the policy evaluator. No state machine.

## Validation Summary

| Context | Validation | Severity | Behavior |
|---------|------------|----------|----------|
| Policy load | Syntax valid (`plugin:field`) | Error | Fail policy load |
| Policy load | Plugin name in registry | Warning | Log and continue |
| Policy load | Field name in registry for plugin | Warning | Log and continue |
| Policy load | Value provided for non-exists operator | Error | Fail policy load |
| Evaluation | Plugin has data for file | N/A | Condition → false |
| Evaluation | Field exists in plugin data | N/A | Condition → false |

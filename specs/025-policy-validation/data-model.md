# Data Model: Policy Validation and Error Reporting

**Feature**: 025-policy-validation
**Date**: 2025-11-25

## New Entities

### ValidationError

Represents a single validation error with field context.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| field | string | Yes | Dot-notation field path (e.g., `audio_language_preference[0]`) |
| message | string | Yes | Human-readable error message |
| code | string | No | Machine-readable error type code |

**Validation Rules**:
- `field` must be non-empty string
- `message` must be non-empty string
- `code` is optional; if present, must match Pydantic error type pattern

**Example**:
```json
{
  "field": "audio_language_preference[2]",
  "message": "Invalid language code 'english'. Use ISO 639-2 codes (e.g., 'eng', 'jpn').",
  "code": "string_pattern_mismatch"
}
```

### ValidationResult

Represents the complete validation outcome.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| success | boolean | Yes | True if validation passed |
| errors | ValidationError[] | No | List of errors if validation failed |
| policy | object | No | Validated policy data if successful |

**State Transitions**:
- Initial: Validation requested
- Terminal (success): `success=true`, `policy` populated, `errors` empty/absent
- Terminal (failure): `success=false`, `errors` populated, `policy` absent

**Validation Rules**:
- If `success=false`, `errors` must be non-empty
- If `success=true`, `errors` must be empty or absent

### FieldChange

Represents a single field change in the diff summary.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| field | string | Yes | Field name that changed |
| change_type | string (enum) | Yes | Type of change |
| details | string | No | Human-readable change details |

**Enum Values for change_type**:
- `added`: New value where none existed
- `removed`: Value deleted
- `modified`: Value changed (for scalar/object fields)
- `reordered`: List items reordered (order changed but items same)
- `items_added`: Items added to a list
- `items_removed`: Items removed from a list

### DiffSummary

Represents all changes between original and updated policy.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| changes | FieldChange[] | Yes | List of field changes |

**Derived Properties**:
- `to_summary_text()`: Human-readable summary string

**Example**:
```json
{
  "changes": [
    {"field": "audio_language_preference", "change_type": "reordered", "details": "eng, jpn → jpn, eng"},
    {"field": "default_flags.clear_other_defaults", "change_type": "modified", "details": "true → false"},
    {"field": "commentary_patterns", "change_type": "items_added", "details": "added 1 pattern"}
  ]
}
```

## Modified Entities

### PolicyEditorRequest (existing in models.py)

No structural changes; already contains all policy fields.

### PolicyEditorContext (existing in models.py)

No structural changes; response already includes full policy data.

## API Response Models

### ValidationErrorResponse

HTTP 400 response for validation failures.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| error | string | Yes | Always "Validation failed" |
| errors | ValidationError[] | Yes | List of field-level errors |
| details | string | No | Optional general error message |

### PolicySaveSuccessResponse

HTTP 200 response for successful save.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| success | boolean | Yes | Always true |
| changed_fields | string[] | Yes | List of field names that changed |
| policy | PolicyEditorContext | Yes | Updated policy data |

### PolicyValidateResponse

HTTP 200 response for validation-only request (Test Policy).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| valid | boolean | Yes | True if validation passed |
| errors | ValidationError[] | No | List of errors if invalid |
| message | string | No | "Policy configuration is valid" if valid |

## Relationships

```
PolicyEditorRequest ──(validates to)──> ValidationResult
                                              │
                                    ┌─────────┴─────────┐
                                    │                   │
                              (success)            (failure)
                                    │                   │
                                    ▼                   ▼
                           DiffSummary          ValidationError[]
```

## Database Changes

None. This feature operates on filesystem (YAML policy files) only.

## Indexes/Constraints

N/A - No database involvement.

## Migration

N/A - No schema changes required.

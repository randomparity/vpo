# Research: Policy Validation and Error Reporting

**Feature**: 025-policy-validation
**Date**: 2025-11-25

## Research Tasks

### 1. Pydantic Validation Error Structure

**Task**: Understand Pydantic error format for field-level extraction

**Findings**:
- Pydantic `ValidationError.errors()` returns a list of dicts with keys: `loc`, `msg`, `type`, `input`
- `loc` is a tuple of field path segments (e.g., `('audio_language_preference', 0)`)
- `msg` is a human-readable error message
- `type` is the error type code (e.g., `string_pattern_mismatch`)

**Decision**: Map Pydantic errors to ValidationError dataclass with:
- `field`: Join `loc` tuple with dots/brackets (e.g., `audio_language_preference[0]`)
- `message`: Use Pydantic `msg` directly
- `code`: Optional, use Pydantic `type` if useful for programmatic handling

**Rationale**: Direct mapping preserves Pydantic's detailed error information while normalizing format for frontend consumption.

### 2. Existing Error Handling in PolicyRoundTripEditor

**Task**: Review current error handling in editor.py and loader.py

**Findings**:
- `PolicyValidationError` class in `loader.py` has `message` and optional `field` attributes
- `_format_validation_error()` in `loader.py` extracts first Pydantic error only
- Current implementation returns single error message, not all errors

**Decision**: Enhance to return all validation errors, not just first one
- Modify `_format_validation_error()` to return list of structured errors
- Update `PolicyValidationError` to optionally hold multiple errors

**Rationale**: Users need to see all errors at once to efficiently fix multiple issues (spec edge case: "Display all errors, not just the first one").

**Alternatives Considered**:
- Keep single error (simpler) - Rejected: Poor UX, requires multiple save attempts
- Return raw Pydantic errors - Rejected: Exposes internal structure

### 3. Existing API Response Patterns

**Task**: Review existing API response patterns in routes.py

**Findings**:
- Success responses use `web.json_response(data.to_dict())`
- Error responses use `web.json_response({"error": message}, status=400)`
- Existing `api_policy_update_handler` returns 400 with `{"error": "...", "details": "..."}` for validation failures
- Concurrent modification returns 409

**Decision**: Extend existing pattern for structured errors:
```json
// Validation error response (400)
{
  "error": "Validation failed",
  "errors": [
    {"field": "audio_language_preference[0]", "message": "Invalid language code..."},
    {"field": "commentary_patterns[2]", "message": "Invalid regex pattern..."}
  ]
}

// Success response (200)
{
  "success": true,
  "changed_fields": ["audio_language_preference", "default_flags"],
  "policy": { ... }
}
```

**Rationale**: Backward-compatible extension of existing error format; `errors` array is additive.

### 4. JavaScript Error Display Patterns

**Task**: Review existing error display in policy-editor.js

**Findings**:
- `showError(message)` displays single error in `validationErrors` element
- Already scrolls to top and adds role="alert" for accessibility
- Already has close button functionality
- Does not support multiple errors or field association

**Decision**: Extend to support multiple field-level errors:
- Create `showErrors(errors)` function for array of errors
- Each error displays field name and message
- Clicking field name scrolls to and focuses that form section
- Keep existing `showError()` for single general errors

**Rationale**: Leverages existing infrastructure while adding field-level capability.

### 5. Diff Summary Implementation

**Task**: Design approach for change summary

**Findings**:
- `PolicyRoundTripEditor.save()` already tracks `changed_fields` list
- Changes are detected by comparing before/after values
- Need to differentiate change types: added, removed, modified, reordered

**Decision**: Implement `DiffSummary` helper that compares:
- List fields: detect add/remove/reorder
- Dict fields (default_flags): detect changed keys
- Scalar fields: detect value change

Return format:
```python
@dataclass
class FieldChange:
    field: str           # Field name
    change_type: str     # "added", "removed", "modified", "reordered"
    details: str | None  # Optional human-readable details

@dataclass
class DiffSummary:
    changes: list[FieldChange]

    def to_summary_text(self) -> str:
        """Generate human-readable summary."""
```

**Rationale**: Server-side diff keeps UI simple; provides both structured data and human-readable text.

### 6. Test Policy Endpoint Design

**Task**: Design validate-only endpoint

**Findings**:
- Need CSRF protection (POST method)
- Should accept same payload as PUT /api/policies/{name}
- Must not modify policy file
- Should return same error format as save

**Decision**:
- Endpoint: `POST /api/policies/{name}/validate`
- Request body: Same as PUT (policy fields + last_modified_timestamp)
- Response: Same structure as PUT errors/success, minus actual save
- Does not check last_modified (no concurrent modification concern)

**Rationale**: Consistent contract with save endpoint; POST ensures CSRF token validation.

**Alternatives Considered**:
- GET with query params - Rejected: Complex for nested data; no CSRF
- PUT with ?dry_run=true - Rejected: Muddles REST semantics

## Summary

All research tasks completed. Key decisions:

1. **Error format**: Map Pydantic errors to `{field, message}` structure
2. **Multiple errors**: Return all validation errors, not just first
3. **API response**: Extend existing pattern with `errors` array
4. **UI display**: Extend `showError` to handle multiple field-level errors
5. **Diff summary**: Server-side `DiffSummary` class with change type tracking
6. **Test endpoint**: `POST /api/policies/{name}/validate`

No unresolved clarifications. Ready for Phase 1 design.

# Quickstart: Policy Validation and Error Reporting

**Feature**: 025-policy-validation
**Date**: 2025-11-25

## Overview

This feature enhances the policy editor with:
1. **Structured validation errors** - Field-level error messages from backend
2. **Test Policy** - Validate without saving
3. **Diff summary** - Show what changed on successful save
4. **Enhanced real-time validation** - Immediate feedback while typing

## Getting Started

### Prerequisites

- VPO daemon running (`uv run vpo serve`)
- At least one policy file in `~/.vpo/policies/`
- Browser with JavaScript enabled

### Quick Test

1. Start the daemon:
   ```bash
   uv run vpo serve --port 8080
   ```

2. Open policy editor:
   ```
   http://localhost:8080/policies/default/edit
   ```

3. Test validation error:
   - Add an invalid language code (e.g., "english" instead of "eng")
   - Click "Save Changes"
   - Observe field-level error message

4. Test "Test Policy" feature:
   - Make some changes
   - Click "Test Policy"
   - See validation result without saving

## Key Files

### Backend (Python)

| File | Purpose |
|------|---------|
| `src/vpo/policy/validation.py` | ValidationResult, DiffSummary helpers (NEW) |
| `src/vpo/policy/loader.py` | PolicyModel validation (MODIFY) |
| `src/vpo/server/ui/routes.py` | API endpoints (MODIFY) |
| `src/vpo/server/ui/models.py` | Response models (MODIFY) |

### Frontend (JavaScript)

| File | Purpose |
|------|---------|
| `src/vpo/server/static/js/policy-editor/policy-editor.js` | Form handling, error display (MODIFY) |

### Tests

| File | Purpose |
|------|---------|
| `tests/unit/policy/test_validation.py` | ValidationResult, DiffSummary tests (NEW) |
| `tests/integration/test_policy_editor_flow.py` | End-to-end validation tests (MODIFY) |

## Development Workflow

### 1. Run Tests

```bash
# All tests
uv run pytest

# Unit tests for validation
uv run pytest tests/unit/policy/test_validation.py -v

# Integration tests for policy editor
uv run pytest tests/integration/test_policy_editor_flow.py -v
```

### 2. Manual Testing

```bash
# Start daemon in development mode
uv run vpo serve --port 8080 --log-level debug

# Open browser to policy editor
open http://localhost:8080/policies/default/edit
```

### 3. API Testing (curl)

```bash
# Test validation endpoint
curl -X POST http://localhost:8080/api/policies/default/validate \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: <token>" \
  -d '{
    "track_order": ["video", "audio_main"],
    "audio_language_preference": ["invalid"],
    "subtitle_language_preference": ["eng"],
    "default_flags": {}
  }'

# Save with validation
curl -X PUT http://localhost:8080/api/policies/default \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: <token>" \
  -d '{
    "track_order": ["video", "audio_main"],
    "audio_language_preference": ["eng", "jpn"],
    "subtitle_language_preference": ["eng"],
    "default_flags": {"set_first_video_default": true},
    "last_modified_timestamp": "2025-11-25T12:00:00Z"
  }'
```

## API Response Examples

### Validation Error (400)

```json
{
  "error": "Validation failed",
  "errors": [
    {
      "field": "audio_language_preference[0]",
      "message": "Invalid language code 'english'. Use ISO 639-2 codes (e.g., 'eng', 'jpn')."
    },
    {
      "field": "commentary_patterns[1]",
      "message": "Invalid regex pattern: unclosed bracket"
    }
  ]
}
```

### Save Success (200)

```json
{
  "success": true,
  "changed_fields": ["audio_language_preference", "default_flags"],
  "policy": {
    "name": "default",
    "schema_version": 2,
    "track_order": ["video", "audio_main", "subtitle_main"],
    "audio_language_preference": ["jpn", "eng"],
    ...
  }
}
```

### Test Policy Valid (200)

```json
{
  "valid": true,
  "message": "Policy configuration is valid"
}
```

### Test Policy Invalid (200)

```json
{
  "valid": false,
  "errors": [
    {
      "field": "track_order",
      "message": "track_order cannot be empty"
    }
  ]
}
```

## Common Issues

### CSRF Token Missing

**Symptom**: 403 Forbidden on POST/PUT
**Solution**: Include `X-CSRF-Token` header from page's `window.CSRF_TOKEN`

### Concurrent Modification

**Symptom**: 409 Conflict
**Solution**: Reload page to get latest `last_modified_timestamp`

### Real-time vs Server Validation Mismatch

**Note**: Browser validation is advisory. Server validation is authoritative.
If server returns errors browser didn't catch, server errors take precedence.

## Related Documentation

- [Policy Editor Usage Guide](../../docs/usage/policy-editor.md)
- [Feature Spec](./spec.md)
- [API Contract](./contracts/api.yaml)

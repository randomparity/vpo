# Data Model: Visual Policy Editor

**Feature**: 024-policy-editor
**Date**: 2025-11-24

This document defines the data structures, validation rules, and flow for the Visual Policy Editor feature.

---

## Overview

The policy editor follows a **load → edit → validate → save** cycle with field preservation. Data flows through three representations:

1. **YAML File** (storage): Raw policy file with comments and unknown fields
2. **Form State** (frontend): JavaScript object representing editable fields
3. **Validated Schema** (backend): Pydantic PolicySchema for validation

---

## Entity Definitions

### 1. PolicyEditorRequest (Frontend → Backend)

The data structure sent when saving policy changes.

```typescript
interface PolicyEditorRequest {
  // Core fields (editable)
  track_order: TrackType[];
  audio_language_preference: string[];
  subtitle_language_preference: string[];
  commentary_patterns: string[];
  default_flags: DefaultFlagsConfig;

  // Optional sections
  transcode?: TranscodePolicyConfig;
  transcription?: TranscriptionPolicyConfig;

  // Metadata for optimistic concurrency
  last_modified_timestamp: string;  // ISO-8601 UTC
}
```

**Validation Rules**:
- `track_order`: Non-empty array of valid TrackType enum values
- `audio_language_preference`: Non-empty array of ISO 639-2 codes (regex: `/^[a-z]{2,3}$/`)
- `subtitle_language_preference`: Non-empty array of ISO 639-2 codes
- `commentary_patterns`: Array of strings (valid regex patterns)
- `default_flags`: All boolean fields, no special validation
- `last_modified_timestamp`: Must match current file mtime (concurrency check)

**Field Constraints**:
- Language codes: 2-3 lowercase letters, no duplicates within array
- Track order: No duplicate track types, must include VIDEO
- Commentary patterns: Must compile as valid regular expressions
- Transcode/transcription: If present, must pass nested validation

---

### 2. PolicyEditorResponse (Backend → Frontend)

The data structure returned when loading a policy for editing.

```typescript
interface PolicyEditorResponse {
  // Policy identity
  name: string;              // Filename without extension
  filename: string;          // Full filename (e.g., "default.yaml")
  file_path: string;         // Absolute path

  // Editable fields (populated from parsed YAML)
  track_order: TrackType[];
  audio_language_preference: string[];
  subtitle_language_preference: string[];
  commentary_patterns: string[];
  default_flags: DefaultFlagsConfig;
  transcode: TranscodePolicyConfig | null;
  transcription: TranscriptionPolicyConfig | null;

  // Metadata
  schema_version: number;    // Read-only, displayed but not editable
  last_modified: string;     // ISO-8601 UTC, for concurrency check

  // Raw YAML (for preservation)
  raw_yaml: string;          // Original YAML content

  // Validation status
  parse_error: string | null;
}
```

**Field Sources**:
- Editable fields: Parsed from YAML using `PolicyModel.model_validate()`
- `raw_yaml`: Raw file contents for YAML preview
- `last_modified`: File mtime for optimistic concurrency
- `parse_error`: Set if YAML parsing fails

---

### 3. FormState (Frontend JavaScript)

The reactive state object managed by the Proxy-based state manager.

```javascript
const formState = {
  // Policy identity (read-only)
  name: "default",
  filename: "default.yaml",
  last_modified: "2025-11-24T12:00:00Z",

  // Editable fields
  track_order: ["video", "audio_main", "audio_alternate", ...],
  audio_language_preference: ["eng", "und"],
  subtitle_language_preference: ["eng", "und"],
  commentary_patterns: ["commentary", "director"],
  default_flags: {
    set_first_video_default: true,
    set_preferred_audio_default: true,
    set_preferred_subtitle_default: false,
    clear_other_defaults: true
  },

  // Optional sections (null if not present)
  transcode: null,
  transcription: null,

  // UI state
  isDirty: false,           // Has unsaved changes
  isSaving: false,          // Save in progress
  validationErrors: {},     // Field-level errors
  lastSaveError: null       // Last save error message
};
```

**Reactivity**: Changes to any field automatically trigger:
1. Form UI updates
2. YAML preview refresh
3. Client-side validation
4. `isDirty` flag update

---

### 4. DefaultFlagsConfig

Configuration for default flag behavior (subset of PolicySchema).

```typescript
interface DefaultFlagsConfig {
  set_first_video_default: boolean;      // Set first video track as default
  set_preferred_audio_default: boolean;  // Set preferred audio as default
  set_preferred_subtitle_default: boolean; // Set preferred subtitle as default
  clear_other_defaults: boolean;         // Clear other default flags
}
```

**Validation**: All fields are booleans, no cross-field rules.

---

### 5. TranscodePolicyConfig

Transcode settings (optional section, subset of PolicySchema).

```typescript
interface TranscodePolicyConfig {
  // Video settings
  target_video_codec: string | null;   // "hevc" | "h264" | "vp9" | "av1"
  target_crf: number | null;           // 0-51
  target_bitrate: string | null;       // e.g., "5M", "2500k"
  max_resolution: string | null;       // "1080p" | "720p" | "4k" | etc.
  max_width: number | null;            // Pixels
  max_height: number | null;           // Pixels

  // Audio settings
  audio_preserve_codecs: string[];     // Codecs to stream copy
  audio_transcode_to: string;          // Target codec (default: "aac")
  audio_transcode_bitrate: string;     // Bitrate (default: "192k")
  audio_downmix: string | null;        // "stereo" | "5.1" | null

  // Destination
  destination: string | null;          // Template string
  destination_fallback: string;        // Fallback value
}
```

**Validation Rules**:
- `target_video_codec`: Must be in VALID_VIDEO_CODECS if not null
- `target_crf`: 0-51 if not null
- `max_resolution`: Must be in VALID_RESOLUTIONS if not null
- `audio_transcode_to`: Must be in VALID_AUDIO_CODECS
- `audio_downmix`: Must be "stereo" or "5.1" if not null

---

### 6. TranscriptionPolicyConfig

Transcription settings (optional section, subset of PolicySchema).

```typescript
interface TranscriptionPolicyConfig {
  enabled: boolean;                          // Enable transcription analysis
  update_language_from_transcription: boolean; // Update language tags
  confidence_threshold: number;              // 0.0-1.0
  detect_commentary: boolean;                // Enable commentary detection
  reorder_commentary: boolean;               // Move commentary to end
}
```

**Validation Rules**:
- `confidence_threshold`: Must be 0.0-1.0
- `reorder_commentary`: Can only be true if `detect_commentary` is true

---

## Data Flow

### Load Flow (GET /api/policies/{name})

```
1. Client requests policy
   ↓
2. Server loads YAML file
   ↓
3. Server parses with ruamel.yaml (preserves structure)
   ↓
4. Server validates with PolicyModel (Pydantic)
   ↓
5. Server returns PolicyEditorResponse
   - Editable fields
   - Raw YAML string
   - Metadata (mtime, schema_version)
   ↓
6. Client initializes FormState with response data
   ↓
7. Client renders form sections
   ↓
8. Client displays YAML preview (read-only)
```

### Save Flow (PUT /api/policies/{name})

```
1. User clicks Save
   ↓
2. Client validates FormState (JSON Schema + custom validators)
   ↓
3. If invalid: Display errors, abort save
   ↓
4. Client sends PolicyEditorRequest to server
   ↓
5. Server checks last_modified_timestamp (concurrency check)
   ↓
6. If stale: Return 409 Conflict error
   ↓
7. Server loads original YAML with ruamel.yaml
   ↓
8. Server updates only edited fields in-place
   ↓
9. Server validates merged result with PolicyModel
   ↓
10. If invalid: Return 400 Bad Request with field errors
    ↓
11. Server writes YAML with ruamel.yaml (preserves comments)
    ↓
12. Server returns updated PolicyEditorResponse
    ↓
13. Client updates FormState and resets isDirty
```

---

## Round-Trip Field Preservation

### Preserved Elements

**Always Preserved**:
- Unknown top-level fields (e.g., custom `x-my-field`)
- YAML comments on preserved fields
- Key ordering (ruamel.yaml maintains insertion order)
- YAML formatting (indentation, line breaks)

**Best-Effort Preservation**:
- Comments on edited fields (may shift if array reordered)
- Comments on deleted fields (lost)

### Merge Strategy

```python
# Load with preservation
yaml = YAML()
yaml.preserve_quotes = True
data = yaml.load(policy_file)

# Update only changed fields
for field in edited_fields:
    data[field] = request_data[field]

# Unknown fields remain untouched
# Comments on unchanged fields preserved

# Validate merged result
validated = PolicyModel.model_validate(dict(data))

# Save with preservation
yaml.dump(data, policy_file)
```

---

## Validation Rules

### Track Order

- **Rule**: Must be non-empty array of valid TrackType values
- **Error**: "track_order cannot be empty"
- **Error**: "Unknown track type '{type}' at index {idx}"
- **Frontend**: Enum validation, duplicate detection
- **Backend**: Pydantic field validator

### Language Preferences

- **Rule**: Must be non-empty array of ISO 639-2 codes (2-3 lowercase letters)
- **Error**: "Language preference cannot be empty"
- **Error**: "Invalid language code '{code}' at index {idx}. Use ISO 639-2 codes (e.g., 'eng', 'jpn')"
- **Frontend**: Regex `/^[a-z]{2,3}$/`, duplicate detection
- **Backend**: Pydantic field validator with regex

### Commentary Patterns

- **Rule**: Must be array of valid regex patterns
- **Error**: "Invalid regex pattern '{pattern}': {error}"
- **Frontend**: Try `new RegExp(pattern)`, catch syntax errors
- **Backend**: `validate_regex_patterns()` helper

### Default Flags

- **Rule**: All fields must be booleans
- **Error**: "Expected boolean for '{field}', got {type}"
- **Frontend**: Checkbox inputs enforce boolean type
- **Backend**: Pydantic type validation

### Cross-Field Rules

- **Rule**: `transcription.reorder_commentary` requires `transcription.detect_commentary`
- **Error**: "reorder_commentary requires detect_commentary to be true"
- **Frontend**: Custom validator, disable checkbox if detect_commentary false
- **Backend**: Pydantic field validator

---

## Error Handling

### Client-Side Errors

**Display Strategy**:
- Field-level errors: Inline below input, red border on field
- Form-level errors: Banner at top of form
- ARIA live region announces errors for screen readers

**Error Structure**:
```javascript
validationErrors: {
  "audio_language_preference.1": "Invalid language code 'xx'",
  "transcription.confidence_threshold": "Must be between 0.0 and 1.0"
}
```

### Server-Side Errors

**HTTP Status Codes**:
- `400 Bad Request`: Validation error (field-specific errors in response)
- `404 Not Found`: Policy file not found
- `409 Conflict`: Concurrent modification detected
- `500 Internal Server Error`: Unexpected error

**Error Response Format**:
```json
{
  "error": "Validation failed",
  "details": {
    "audio_language_preference": ["Invalid language code 'xx' at index 1"],
    "track_order": ["track_order cannot be empty"]
  }
}
```

---

## State Transitions

### Form States

```
Initial → Loading → Loaded → Editing → Validating → Saving → Saved
                                                    ↓ (error)
                                                  Error → Editing
```

**State Definitions**:
- **Initial**: Page load, no data
- **Loading**: Fetching policy from server
- **Loaded**: Policy loaded, form rendered, no edits
- **Editing**: User has made changes, `isDirty = true`
- **Validating**: Running client-side validation
- **Saving**: Submitting to server
- **Saved**: Save successful, `isDirty = false`
- **Error**: Validation or save failed, display errors

### Dirty State Management

```javascript
// Track original state
const originalState = JSON.stringify(formState);

// On any form change
function checkDirty() {
  const currentState = JSON.stringify(formState);
  formState.isDirty = (currentState !== originalState);
}

// Warn on navigation if dirty
window.addEventListener('beforeunload', (e) => {
  if (formState.isDirty) {
    e.preventDefault();
    e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
  }
});
```

---

## Performance Considerations

### YAML Preview Debouncing

```javascript
let previewTimeout;
function updateYAMLPreview() {
  clearTimeout(previewTimeout);
  previewTimeout = setTimeout(() => {
    // Generate YAML from formState
    const yaml = generateYAML(formState);
    document.getElementById('yaml-preview').textContent = yaml;
  }, 300); // 300ms debounce
}
```

### Validation Throttling

```javascript
// Validate on blur, not on every keystroke
inputElement.addEventListener('blur', () => {
  validateField(inputElement.name);
});

// Validate all fields before save
saveButton.addEventListener('click', async () => {
  const errors = validateAllFields();
  if (Object.keys(errors).length === 0) {
    await savePolicy();
  }
});
```

---

## Testing Strategy

### Unit Tests

**Backend (Python)**:
- `test_policy_roundtrip.py`: Load → modify → save preserves unknown fields
- `test_policy_validation.py`: All validation rules enforce constraints
- `test_editor_routes.py`: API endpoints return correct responses

**Frontend (JavaScript)**:
- `test_form_state.js`: Proxy reactivity triggers updates
- `test_validation.js`: Client-side validators match backend
- `test_yaml_generation.js`: FormState correctly serializes to YAML

### Integration Tests

**E2E Flow** (`test_policy_editor_flow.py`):
1. Load policy with unknown fields and comments
2. Edit track order via UI
3. Save policy
4. Verify unknown fields preserved
5. Verify comments preserved (best-effort)
6. Verify edited fields updated

**Concurrency Test**:
1. Load policy in two browser tabs
2. Save from tab 1
3. Attempt save from tab 2
4. Verify 409 Conflict error returned

---

## Summary

The data model supports:
- ✅ Round-trip preservation of unknown fields and comments
- ✅ Reactive form state with automatic YAML preview
- ✅ Client and server validation with consistent error messages
- ✅ Optimistic concurrency detection
- ✅ Clear error handling and user feedback
- ✅ Performance optimization (debouncing, throttling)

**Next**: Define API contracts in `contracts/api.yaml`

# Quickstart: V9 Policy Editor GUI Implementation

**Phase 1 Output** | **Date**: 2025-11-30

## Prerequisites

Before starting implementation:

1. **Branch**: Ensure you're on `036-v9-policy-editor` branch
2. **Dependencies**: Run `uv pip install -e ".[dev]"` to install dependencies
3. **Server**: Run `uv run vpo serve --port 8080` to test changes

## Quick Reference

### Key Files to Modify

| File | Changes |
|------|---------|
| `server/ui/routes.py` | Extend `api_policy_get`, `api_policy_put`, `api_policy_validate` |
| `server/ui/templates/sections/policy_editor.html` | Add accordion sections for V3-V10 |
| `server/static/css/policy-editor.css` | Add accordion styles |
| `server/static/js/policy-editor/policy-editor.js` | Import and initialize new section modules |

### New Files to Create

| File | Purpose |
|------|---------|
| `server/static/js/policy-editor/accordion.js` | Accordion component |
| `server/static/js/policy-editor/section-transcode.js` | V6 transcode section |
| `server/static/js/policy-editor/section-filters.js` | V3 filtering section |
| `server/static/js/policy-editor/section-synthesis.js` | V5 synthesis section |
| `server/static/js/policy-editor/section-conditional.js` | V4 conditional rules |
| `server/static/js/policy-editor/section-container.js` | V3 container section |
| `server/static/js/policy-editor/section-workflow.js` | V9 workflow section |

## Implementation Order

### Phase 1: Foundation (Blocking)

1. **Accordion Component** (`accordion.js`)
   - Implement using HTML5 `<details>` elements
   - Add CSS for styling and animation

2. **Template Structure** (`policy_editor.html`)
   - Add placeholder sections with `<details class="accordion-section">`
   - Keep existing form fields, wrap in accordion

### Phase 2: V3 Features (Highest Value)

3. **Track Filters Section** (`section-filters.js`)
   - Audio filter: languages list, fallback mode, minimum
   - Subtitle filter: languages list, preserve_forced, remove_all
   - Attachment filter: remove_all checkbox

4. **Container Section** (`section-container.js`)
   - Target format dropdown (mkv/mp4)
   - On incompatible codec dropdown

### Phase 3: V6 Transcode (High Complexity)

5. **Transcode Section** (`section-transcode.js`)
   - Video: target_codec, skip_if, quality, scaling, hardware_acceleration
   - Audio: preserve_codecs list, transcode_to, transcode_bitrate

### Phase 4: V4 Conditional Rules (Complex UI)

6. **Conditional Section** (`section-conditional.js`)
   - Rule list with add/remove
   - Condition builder (2-level nesting max)
   - Action editor

### Phase 5: V5 Audio Synthesis

7. **Synthesis Section** (`section-synthesis.js`)
   - Track list with add/remove
   - Source preference editor
   - Skip if exists criteria (V8)

### Phase 6: V9 Workflow

8. **Workflow Section** (`section-workflow.js`)
   - Phase selector (checkboxes)
   - Auto process toggle
   - On error dropdown

## Testing Checklist

### Unit Tests

```bash
# Run policy editor tests
uv run pytest tests/unit/policy/test_editor_v6_v10.py -v

# Run API tests
uv run pytest tests/integration/server/test_policy_editor_api.py -v
```

### Manual Testing

1. **Load Policy**: Open `http://localhost:8080/policies/default/edit`
2. **Accordion**: Verify sections expand/collapse
3. **Form Fields**: Test each field type (text, dropdown, list, checkbox)
4. **Validation**: Enter invalid data, verify error messages
5. **YAML Preview**: Verify real-time updates
6. **Save**: Verify successful save and reload
7. **Conflict Detection**: Modify file externally, try to save

### Test Policies

Create test policy files in `~/.vpo/policies/`:

**test-v6.yaml** (V6 transcode):
```yaml
schema_version: 6
track_order: [video, audio_main]
audio_language_preference: [eng]
subtitle_language_preference: [eng]
transcode:
  video:
    target_codec: hevc
    skip_if:
      codec_matches: [hevc]
    quality:
      mode: crf
      crf: 20
```

**test-v10.yaml** (Full V10):
```yaml
schema_version: 10
track_order: [video, audio_main, subtitle_main]
audio_language_preference: [eng, jpn]
subtitle_language_preference: [eng]
audio_filter:
  languages: [eng, jpn]
  keep_music_tracks: true
conditional:
  - name: Test rule
    when:
      exists:
        track_type: audio
        language: jpn
    then:
      - warn: "Found Japanese audio"
workflow:
  phases: [apply]
  on_error: continue
```

## Common Patterns

### Adding a New Field

1. Add field to template HTML in accordion section
2. Add field binding in JavaScript section module
3. Add validation in both client (JS) and server (Pydantic)
4. Add to data-model.md if not already present

### JavaScript Section Module Template

```javascript
// section-example.js
export function initExampleSection(container, state) {
  const section = container.querySelector('#example-section');
  if (!section) return;

  // Get form elements
  const field1 = section.querySelector('#field1');

  // Bind change handlers
  field1.addEventListener('change', () => {
    state.policy.example = { field1: field1.value };
    state.isDirty = true;
    triggerYamlPreview();
  });

  // Populate from state
  populateExampleSection(section, state);
}

export function populateExampleSection(section, state) {
  const example = state.policy.example || {};
  section.querySelector('#field1').value = example.field1 || '';
}

export function validateExampleSection(state) {
  const errors = [];
  const example = state.policy.example;

  if (example && !example.field1) {
    errors.push({ field: 'example.field1', message: 'Required' });
  }

  return errors;
}
```

### Validation Pattern

```javascript
// Client-side validation on blur
field.addEventListener('blur', () => {
  const error = validateField(field.value);
  showFieldError(field, error);
});

// Server-side validation on save
const response = await fetch(`/api/policies/${name}/validate`, {
  method: 'POST',
  body: JSON.stringify(state.policy)
});
const result = await response.json();
if (!result.valid) {
  showValidationErrors(result.errors);
}
```

## Debugging

### Browser DevTools

1. Open Network tab to monitor API calls
2. Check Console for JavaScript errors
3. Use Elements tab to inspect generated HTML

### Server Logs

```bash
# Run server with debug logging
VPO_LOG_LEVEL=DEBUG uv run vpo serve --port 8080
```

### YAML Preview Issues

If YAML preview doesn't update:
1. Check browser console for errors
2. Verify debounce timer is working
3. Check API response for `yaml_preview` field

## Resources

- [Spec](./spec.md) - Feature specification
- [Data Model](./data-model.md) - Entity definitions
- [API Contract](./contracts/api.md) - REST API specification
- [Research](./research.md) - Technical decisions
- [Policy Editor Docs](../../docs/usage/policy-editor.md) - User documentation

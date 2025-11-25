# Quickstart: Visual Policy Editor Development

**Feature**: 024-policy-editor
**Date**: 2025-11-24

This guide helps developers quickly get started with the Visual Policy Editor codebase.

---

## Table of Contents

1. [Running the Editor Locally](#running-the-editor-locally)
2. [Project Structure](#project-structure)
3. [Adding a New Form Field](#adding-a-new-form-field)
4. [Testing Policy Round-Trip](#testing-policy-round-trip)
5. [Debugging Validation Errors](#debugging-validation-errors)
6. [Common Tasks](#common-tasks)

---

## Running the Editor Locally

### Prerequisites

```bash
# Install dependencies (including ruamel.yaml)
uv pip install -e ".[dev]"

# Build Rust extension (if needed)
uv run maturin develop

# Create test policy directory
mkdir -p ~/.vpo/policies/
```

### Start the Server

```bash
# Start VPO daemon with web UI
uv run vpo serve --port 8080

# Server will be available at http://localhost:8080
```

### Access the Editor

1. Open browser to `http://localhost:8080/policies`
2. Click on a policy name to view details
3. Click "Edit" button to open editor at `/policies/{name}/edit`

### Create a Test Policy

```bash
# Create a minimal test policy
cat > ~/.vpo/policies/test.yaml << 'EOF'
schema_version: 2
track_order:
  - video
  - audio_main
  - audio_alternate
  - subtitle_main
  - subtitle_forced
  - audio_commentary
  - subtitle_commentary
  - attachment
audio_language_preference:
  - eng
  - und
subtitle_language_preference:
  - eng
  - und
commentary_patterns:
  - commentary
  - director
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
EOF
```

---

## Project Structure

### Backend (Python)

```
src/video_policy_orchestrator/
├── policy/
│   ├── loader.py          # Policy loading/validation (existing)
│   ├── discovery.py       # Policy file discovery (existing)
│   ├── models.py          # PolicySchema definitions (existing)
│   └── editor.py          # NEW: Round-trip editor logic
├── server/
│   └── ui/
│       ├── routes.py      # MODIFY: Add editor routes
│       ├── models.py      # MODIFY: Add editor models
│       └── templates/
│           ├── policies.html          # Existing list view
│           └── policy_editor.html     # NEW: Editor page
```

### Frontend (JavaScript/CSS)

```
src/video_policy_orchestrator/server/static/
├── css/
│   └── policy-editor.css  # NEW: Editor styles
└── js/
    ├── state-manager.js        # NEW: Reactive state with Proxy
    ├── form-bindings.js        # NEW: Form ↔ state sync
    ├── yaml-preview.js         # NEW: Real-time YAML generation
    └── policy-editor.js        # NEW: Main editor module
```

### Tests

```
tests/
├── unit/
│   ├── policy/
│   │   └── test_policy_editor.py          # NEW: Editor logic tests
│   │   └── test_policy_roundtrip.py       # NEW: Field preservation
│   └── server/
│       └── test_policy_editor_routes.py   # NEW: API endpoint tests
└── integration/
    └── test_policy_editor_flow.py         # NEW: E2E editor tests
```

---

## Adding a New Form Field

### Example: Add "description" field to policies

#### Step 1: Update Backend Schema (if needed)

```python
# src/video_policy_orchestrator/policy/models.py
@dataclass(frozen=True)
class PolicySchema:
    schema_version: int
    description: str = ""  # NEW FIELD
    track_order: tuple[TrackType, ...] = DEFAULT_TRACK_ORDER
    # ... rest of fields
```

#### Step 2: Update Pydantic Validator

```python
# src/video_policy_orchestrator/policy/loader.py
class PolicyModel(BaseModel):
    schema_version: int = Field(ge=1, le=MAX_SCHEMA_VERSION)
    description: str = Field(default="")  # NEW FIELD
    track_order: list[str] = Field(...)
    # ... rest of fields
```

#### Step 3: Add to Editor Response Model

```python
# src/video_policy_orchestrator/server/ui/models.py
@dataclass
class PolicyEditorContext:
    name: str
    filename: str
    description: str  # NEW FIELD
    track_order: list[str]
    # ... rest of fields
```

#### Step 4: Add Form Input (HTML)

```html
<!-- src/video_policy_orchestrator/server/ui/templates/policy_editor.html -->
<section class="editor-section">
  <h2>Description</h2>
  <label for="description">Policy Description</label>
  <input type="text" id="description" name="description"
         placeholder="Brief description of this policy">
</section>
```

#### Step 5: Wire Up JavaScript

```javascript
// src/video_policy_orchestrator/server/static/js/policy-editor.js
function initializeFormState(policyData) {
  return {
    name: policyData.name,
    description: policyData.description,  // NEW FIELD
    track_order: policyData.track_order,
    // ... rest of fields
  };
}

function createFormBindings(state) {
  // Two-way binding for description
  bindTextInput('description', state);
  // ... rest of bindings
}
```

#### Step 6: Add to YAML Preview

```javascript
// src/video_policy_orchestrator/server/static/js/yaml-preview.js
function generateYAML(state) {
  return `schema_version: ${state.schema_version}
description: ${state.description}
track_order:
${state.track_order.map(t => `  - ${t}`).join('\n')}
...`;
}
```

#### Step 7: Add Tests

```python
# tests/unit/policy/test_policy_roundtrip.py
def test_description_preserved():
    """Test that description field is preserved."""
    policy = {
        "schema_version": 2,
        "description": "Test policy",
        "track_order": ["video", "audio_main"],
        # ... rest of fields
    }

    # Save and reload
    editor = PolicyRoundTripEditor(policy_path)
    editor.update(policy)

    reloaded = editor.load()
    assert reloaded["description"] == "Test policy"
```

---

## Testing Policy Round-Trip

### Manual Test

```bash
# 1. Create a policy with unknown fields and comments
cat > ~/.vpo/policies/roundtrip-test.yaml << 'EOF'
schema_version: 2
# This comment should be preserved
track_order:
  - video
  - audio_main
audio_language_preference:
  - eng
subtitle_language_preference:
  - eng
commentary_patterns:
  - commentary
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true

# Unknown field - should be preserved
x_custom_field: my_value
EOF

# 2. Edit via UI: Change audio_language_preference to [jpn, eng]

# 3. Verify preservation
cat ~/.vpo/policies/roundtrip-test.yaml
# Should show:
# - Comments preserved
# - x_custom_field still present
# - audio_language_preference updated to [jpn, eng]
```

### Automated Test

```python
# tests/unit/policy/test_policy_roundtrip.py
import pytest
from pathlib import Path
from video_policy_orchestrator.policy.editor import PolicyRoundTripEditor

def test_unknown_field_preservation(tmp_path):
    """Test that unknown fields are preserved during round-trip."""
    policy_file = tmp_path / "test.yaml"

    # Create policy with unknown field
    policy_file.write_text("""
schema_version: 2
track_order:
  - video
  - audio_main
audio_language_preference:
  - eng
subtitle_language_preference:
  - eng
commentary_patterns:
  - commentary
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
x_custom_field: preserved_value
""")

    # Load, modify, save
    editor = PolicyRoundTripEditor(policy_file)
    data = editor.load()
    data['audio_language_preference'] = ['jpn', 'eng']
    editor.save(data)

    # Reload and verify
    reloaded = editor.load()
    assert reloaded['x_custom_field'] == 'preserved_value'
    assert reloaded['audio_language_preference'] == ['jpn', 'eng']
```

### Run Tests

```bash
# Run all policy editor tests
uv run pytest tests/unit/policy/test_policy_editor.py -v

# Run round-trip tests only
uv run pytest tests/unit/policy/test_policy_roundtrip.py -v

# Run integration tests
uv run pytest tests/integration/test_policy_editor_flow.py -v
```

---

## Debugging Validation Errors

### Backend Validation Errors

```bash
# Enable debug logging
export VPO_LOG_LEVEL=DEBUG
uv run vpo serve --port 8080

# Watch server logs in another terminal
tail -f ~/.vpo/vpo.log
```

**Common Issues**:

1. **Invalid language code**
   ```
   Error: "Invalid language code 'xx' at index 1"
   Fix: Use ISO 639-2 codes (eng, jpn, fra, etc.)
   ```

2. **Empty track_order**
   ```
   Error: "track_order cannot be empty"
   Fix: Ensure at least one track type is selected
   ```

3. **Regex pattern error**
   ```
   Error: "Invalid regex pattern 'commentary(': missing )"
   Fix: Check commentary_patterns for valid regex syntax
   ```

### Frontend Validation Errors

Open browser DevTools console:

```javascript
// Check form state
console.log(window.policyEditor.getState());

// Check validation errors
console.log(window.policyEditor.getValidationErrors());

// Test individual validator
const result = validators.validateLanguageCode('eng');
console.log(result);  // {valid: true}

// Test full form validation
const errors = validators.validateAll(formState);
console.log(errors);
```

### Validation Mismatch (Client vs Server)

If client-side validation passes but server-side fails:

```bash
# 1. Check JSON Schema endpoint
curl http://localhost:8080/api/policies/schema | jq

# 2. Compare with client-side validators
# Open: src/video_policy_orchestrator/server/static/js/policy-editor.js
# Look for validators object

# 3. Update client validators to match server schema
```

---

## Common Tasks

### Task 1: Clear Policy Cache

```python
from video_policy_orchestrator.policy.discovery import clear_policy_cache

clear_policy_cache()
```

Or restart the server:
```bash
# Kill server (Ctrl+C)
uv run vpo serve --port 8080
```

### Task 2: Validate Policy File

```bash
# Using Python API
python -c "
from pathlib import Path
from video_policy_orchestrator.policy.loader import load_policy

policy = load_policy(Path('~/.vpo/policies/test.yaml').expanduser())
print(f'Valid policy: schema_version={policy.schema_version}')
"
```

### Task 3: Generate JSON Schema

```bash
# Get JSON Schema for validation
curl http://localhost:8080/api/policies/schema | jq > policy-schema.json

# Use for offline validation
ajv validate -s policy-schema.json -d my-policy.json
```

### Task 4: Test Editor API Directly

```bash
# GET policy for editing
curl http://localhost:8080/api/policies/test | jq

# PUT policy changes
curl -X PUT http://localhost:8080/api/policies/test \
  -H "Content-Type: application/json" \
  -d @updated-policy.json | jq
```

### Task 5: Add Test Policy Fixtures

```python
# tests/fixtures/policies.py
import pytest
from pathlib import Path

@pytest.fixture
def minimal_policy(tmp_path):
    """Minimal valid policy for testing."""
    policy_file = tmp_path / "minimal.yaml"
    policy_file.write_text("""
schema_version: 2
track_order: [video, audio_main]
audio_language_preference: [eng]
subtitle_language_preference: [eng]
commentary_patterns: [commentary]
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
""")
    return policy_file

@pytest.fixture
def policy_with_unknown_fields(tmp_path):
    """Policy with unknown fields for round-trip testing."""
    policy_file = tmp_path / "unknown.yaml"
    policy_file.write_text("""
schema_version: 2
track_order: [video]
audio_language_preference: [eng]
subtitle_language_preference: [eng]
commentary_patterns: [commentary]
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
x_custom: preserved
""")
    return policy_file
```

---

## Troubleshooting

### Issue: YAML comments lost after save

**Cause**: Comments on edited fields may shift or be lost.

**Solution**: This is expected "best-effort" behavior. Comments on unchanged fields are preserved.

### Issue: "Concurrent modification detected" error

**Cause**: Policy file was modified between load and save.

**Solution**:
1. Reload the page to get latest version
2. Reapply your changes
3. Save again

**Prevention**: Single-user editing, avoid editing same policy in multiple tabs

### Issue: Changes not appearing in YAML preview

**Cause**: Preview debouncing delay (300ms) or JavaScript error.

**Check**:
1. Open browser DevTools console for errors
2. Verify state is updating: `console.log(window.policyEditor.getState())`
3. Check debounce timer: Wait 300ms after last change

### Issue: Form field not syncing with state

**Cause**: Form binding not initialized or event listener missing.

**Fix**:
```javascript
// Check bindings are initialized
console.log(window.policyEditor.bindings);

// Re-initialize if needed
window.policyEditor.initializeFormBindings();
```

---

## Next Steps

- **Read**: [data-model.md](./data-model.md) for detailed data structures
- **Review**: [contracts/api.yaml](./contracts/api.yaml) for API specifications
- **Study**: [research.md](./research.md) for technical decision rationale

---

## Additional Resources

- **VPO Documentation**: `/docs/`
- **Existing UI Code**: `src/video_policy_orchestrator/server/static/js/library.js` (similar patterns)
- **Policy Loader**: `src/video_policy_orchestrator/policy/loader.py` (validation logic)
- **ruamel.yaml Docs**: https://yaml.readthedocs.io/en/latest/

---

**Questions?** Check `specs/024-policy-editor/` for complete feature documentation.

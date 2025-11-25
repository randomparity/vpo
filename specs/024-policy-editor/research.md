# Research: Visual Policy Editor Technical Decisions

**Feature**: 024-policy-editor
**Date**: 2025-11-24
**Status**: Complete

This document consolidates research findings for the four key technical decisions needed for the Visual Policy Editor implementation.

---

## 1. YAML Preservation Strategy

### Decision

Use **ruamel.yaml** with round-trip mode (`typ="rt"`) combined with selective field updates and Pydantic validation.

### Rationale

- **Meets all spec requirements**: Preserves unknown fields (FR-011) and comments (User Story 7, best-effort)
- **Simple to implement**: ~50 lines of core logic, integrates cleanly with existing PolicySchema
- **Excellent UX**: Users' comments and formatting preserved through edit cycles
- **Low risk**: Stable dependency (500k+ downloads/day), pure Python fallback available
- **Backward compatible**: Existing PolicySchema and validation unchanged

### Alternatives Considered

| Approach | Unknown Fields | Comments | Complexity | Rejected Because |
|----------|---------------|----------|------------|------------------|
| PyYAML + Manual Merge | ✅ | ❌ | Medium | Fails comment preservation requirement |
| ruamel.yaml Round-Trip | ✅ | ✅ | Low | **CHOSEN** |
| Hybrid (both libraries) | ✅ | ✅ | High | Unnecessary complexity |
| Database Storage | ✅ | ❌ | High | Contradicts VPO's filesystem architecture |

### Implementation Notes

**Core Pattern**:
```python
from ruamel.yaml import YAML

yaml = YAML()
yaml.preserve_quotes = True
data = yaml.load(policy_file)

# Update only edited fields
data['track_order'] = updated_values
data['audio_language_preference'] = updated_values

# Validate merged result
validated = load_policy_from_dict(dict(data))

# Save with preservation
yaml.dump(data, policy_file)
```

**New Dependency**:
```toml
dependencies = ["ruamel.yaml>=0.18.0"]
```

**Performance**: ~20% slower than PyYAML but <10ms difference for typical policies (<10KB)

**Comment Preservation**: Best-effort; may be lost if keys are deleted, but preserved for untouched sections

**Testing**: Add fixtures testing comment preservation, unknown field preservation, and validation error handling

---

## 2. Form State Management Pattern

### Decision

Use **Proxy-based Reactive State Management** with vanilla JavaScript (no frameworks).

### Rationale

- **Native browser support**: Uses JavaScript's built-in `Proxy` API, zero dependencies
- **Automatic synchronization**: Changes to state automatically trigger form and YAML preview updates
- **Minimal code**: ~150 lines for core state manager, total ~330 lines including bindings
- **Scalable**: Handles complex nested state (lists, objects, arrays)
- **Debuggable**: Easy to log and trace state changes
- **Consistent with VPO**: Extends existing IIFE module pattern used in library.js

### Alternatives Considered

| Approach | Reactivity | Dependencies | Code Size | Rejected Because |
|----------|-----------|--------------|-----------|------------------|
| Plain Object (current pattern) | Manual | None | Small | Too manual for complex multi-section forms |
| Lightweight Library (VanJS/ArrowJS) | Automatic | +1-2KB | Small | Adds dependency, not needed with Proxy |
| Observer Pattern | Semi-auto | None | Medium | More verbose than Proxy |
| Pub/Sub | Manual | None | Large | Overcomplicated for this use case |
| Proxy-based | Automatic | None | Small | **CHOSEN** |

### Implementation Notes

**Architecture** (3 modules, ~330 lines total):

1. **state-manager.js** (~150 lines): Reactive state store using Proxy
2. **form-bindings.js** (~100 lines): Two-way form synchronization
3. **yaml-preview.js** (~80 lines): Real-time YAML generation

**Core Pattern**:
```javascript
const state = new Proxy(initialState, {
    set(target, property, value) {
        target[property] = value;
        // Automatically triggers:
        // 1. Form field updates
        // 2. YAML preview refresh
        // 3. Validation
        return true;
    }
});
```

**YAML Preview Options**:
- **js-yaml library** (10kB via CDN): Full-featured YAML serialization
- **Manual generation** (~80 lines): No dependencies, sufficient for PolicySchema

**Integration with existing patterns**:
- IIFE modules for encapsulation ✓
- Event delegation for dynamic content ✓
- URL synchronization via history.replaceState ✓
- 300ms debouncing for preview updates ✓

---

## 3. Validation Strategy

### Decision

Use **Hybrid Validation Architecture** combining:
1. JSON Schema-based validation (Ajv) for structural rules
2. Lightweight JavaScript validators for domain-specific logic
3. Always validate on backend as authoritative source

### Rationale

- **Optimal UX**: Client-side validation provides <10ms feedback vs 100-500ms for API calls
- **Maintainable**: JSON Schema auto-generated from Pydantic reduces duplication
- **Pragmatic**: Some duplication acceptable given vanilla JS architecture (no TypeScript/build step)
- **Industry consensus**: "Always implement both validations" for production apps
- **Safe**: Backend always validates; client-side is progressive enhancement

### Alternatives Considered

| Approach | UX Latency | Code Duplication | Complexity | Rejected Because |
|----------|-----------|------------------|------------|------------------|
| Pure server-side | High (500ms) | None | Low | Poor UX, every error requires network round-trip |
| API validation endpoint | Medium (200ms) | Low | Medium | Still has latency, increases server load |
| Pydantic → TypeScript | Low (<10ms) | None | Very High | Requires TypeScript, VPO uses vanilla JS |
| WebAssembly shared | Low (<10ms) | None | Extreme | Massive complexity for limited benefit |
| Hybrid (JSON Schema + JS) | Low (<10ms) | Minimal | Low | **CHOSEN** |

### Implementation Notes

**MVP Implementation**:

1. **Backend**: Add `/api/policies/schema` endpoint
   ```python
   @routes.get("/api/policies/schema")
   async def get_policy_schema(request):
       schema = PolicyModel.model_json_schema()
       return web.json_response(schema)
   ```

2. **Frontend**: Integrate Ajv for JSON Schema validation
   ```html
   <script src="https://cdn.jsdelivr.net/npm/ajv@8/dist/ajv7.min.js"></script>
   ```

3. **Custom Validators**:
   - ISO 639-2 language codes (regex: `/^[a-z]{2,3}$/`)
   - Track type enums validation
   - Cross-field rules (e.g., reorder_commentary requires detect_commentary)

**Validation Flow**:
```
User Input → Client Validation → Error Display (if invalid)
                                → Server Validation (if valid) → Save or Error
```

**Error Display**:
- Field-level errors: Show inline below input
- Form-level errors: Show summary banner
- Preserve server validation as authoritative

**Dependencies**:
- Ajv (<100KB, fast, actively maintained)
- Optional: iso-639-1 package for language name lookups

---

## 4. Language Code Input UX

### Decision

Use **Accessible Autocomplete Combobox** for single language input + **Button-Based Reordering** for preference lists.

### Rationale

- **User research backed**: GOV.UK testing shows autocomplete preferred over closed dropdowns
- **Accessibility**: W3C ARIA Combobox pattern, WCAG 2.1 AA compliant
- **Usability**: Users search by language name ("English") or code ("eng"), not memorize codes
- **Reordering research**: Darin Senneff user testing shows button-based reordering "picked up fastest"
- **Flexibility**: Supports typos, case-insensitive, partial matches on name/code/endonym
- **Correctness**: Validates against ISO 639-2 standard (490 languages)

### Alternatives Considered

| Approach | Discoverability | Validation | Accessibility | Rejected Because |
|----------|----------------|-----------|---------------|------------------|
| Free text only | Low | Manual | Good | No discoverability, allows invalid codes |
| Closed dropdown | Low | Automatic | Good | Can't search 490 languages, poor mobile UX |
| Drag-drop only | N/A | N/A | Poor | Not keyboard-accessible without complex ARIA |
| Numeric ordering | N/A | N/A | Good | User testing showed confusion and errors |
| Autocomplete + Buttons | High | Automatic | Excellent | **CHOSEN** |

### Implementation Notes

**Component 1: Language Autocomplete**

HTML Structure:
```html
<div class="language-input">
  <label for="lang-input">Language</label>
  <input type="text" id="lang-input" role="combobox"
         aria-expanded="false" aria-autocomplete="list"
         aria-controls="lang-listbox" placeholder="Search languages...">
  <ul id="lang-listbox" role="listbox" hidden></ul>
  <div role="status" aria-live="polite" class="sr-only"></div>
</div>
```

Features:
- Minimum 3 characters before showing suggestions (GOV.UK user testing)
- Case-insensitive partial matching on code, name, endonym
- Live region announces result count: "13 results available"
- Keyboard navigation: Arrow keys, Enter to select, Escape to close
- Touch targets 48×48px minimum (accessibility requirement)

**Component 2: Preference List with Button Reordering**

HTML Structure:
```html
<ul class="language-list" role="list">
  <li>
    <span>English (eng)</span>
    <div class="reorder-buttons">
      <button aria-label="Move English up" title="Move up">↑</button>
      <button aria-label="Move English down" title="Move down">↓</button>
      <button aria-label="Remove English" title="Remove">×</button>
    </div>
  </li>
</ul>
<div role="status" aria-live="polite"></div>
```

Features:
- 48×48px minimum button size
- Live announcements: "Moved English down 1 position"
- Optional drag handles for power users (progressive enhancement)
- Fully keyboard-accessible (Tab, Arrow keys, Enter, Delete)
- Disable ↑ for first item, ↓ for last item

**Data Source**:
- ISO 639-2 Language List from Library of Congress (490 languages)
- Format: `[{code: "eng", name: "English", endonym: "English"}, ...]`
- Bundle in JS module or fetch from API endpoint

**Accessibility Checklist**:
- ✅ Keyboard-only navigation
- ✅ Screen reader support (ARIA roles, live regions)
- ✅ High contrast mode support
- ✅ Touch targets 48×48px minimum
- ✅ Clear focus indicators (2-4px outline)
- ✅ Respects `prefers-reduced-motion`
- ✅ Dark mode support
- ✅ Zoom support up to 200%

**Implementation Classes**:
- `LanguageAutocomplete` - autocomplete with validation (~150 lines)
- `LanguagePreferenceList` - reorderable list with drag-drop (~200 lines)

**Estimated Effort**: 3-4.5 days for foundation, polish, testing, and integration

---

## Research Sources

### YAML Preservation
- [ruamel.yaml PyPI](https://pypi.org/project/ruamel.yaml/)
- [Why ruamel.yaml Should Be Your Python YAML Library](https://medium.com/top-python-libraries/why-ruamel-yaml-should-be-your-python-yaml-library-of-choice-81bc17891147)
- [Tips that may save you from the hell of PyYAML](https://reorx.com/blog/python-yaml-tips/)

### State Management
- [State Management in Vanilla JS: 2026 Trends](https://medium.com/@chirag.dave/state-management-in-vanilla-js-2026-trends-f9baed7599de)
- [Reactive State Management using Proxy and Reflect](https://medium.com/@rahul.jindal57/reactive-state-management-using-proxy-and-reflect-in-javascript-1cbdcb79d017)
- [Build a state management system with vanilla JavaScript](https://css-tricks.com/build-a-state-management-system-with-vanilla-javascript/)

### Validation
- [Ajv JSON Schema Validator](https://ajv.js.org/)
- [Pydantic JSON Schema Documentation](https://docs.pydantic.dev/latest/concepts/json_schema/)
- [Stack Overflow: Best Practice in Synchronized Form Data Validations](https://softwareengineering.stackexchange.com/questions/398837/best-practice-in-synchronized-form-data-validations-web-apps-client-server)

### Language Input UX
- [W3C ARIA Combobox Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/)
- [GOV.UK Accessible Autocomplete](https://alphagov.github.io/accessible-autocomplete/)
- [Darin Senneff: Reorderable List Design Research](https://www.darins.page/articles/designing-a-reorderable-list-component)

---

## Phase 0 Gate Check

- [x] All research questions answered
- [x] YAML preservation strategy chosen (ruamel.yaml)
- [x] Form state management pattern documented (Proxy-based)
- [x] Validation approach defined (Hybrid with JSON Schema)
- [x] Language code input UX specified (Autocomplete + Buttons)

**Status**: ✅ Ready to proceed to Phase 1 (Design & Contracts)

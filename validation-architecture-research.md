# Frontend Validation Architecture Research Report

**Date:** 2025-11-24
**Project:** Video Policy Orchestrator (VPO)
**Context:** Policy Editor UI Development

## Executive Summary

This report evaluates validation architecture strategies for mirroring backend Pydantic validation rules in the frontend JavaScript layer. The goal is to provide fast user feedback while maintaining consistency with backend validation logic and minimizing code duplication.

---

## Decision: Hybrid Validation Architecture

**Recommended approach:** Implement a **hybrid validation strategy** combining:

1. **JSON Schema-based validation** for structural rules
2. **Lightweight JavaScript validators** for common patterns (language codes, regex)
3. **Progressive enhancement** with optional API-based validation for complex rules
4. **Always validate on backend** as the authoritative source of truth

---

## Rationale

### 1. User Experience Benefits (Primary Goal)

**Fast feedback is critical for good UX:**
- Policy editing involves multiple fields with interdependencies
- Users expect immediate feedback when entering invalid data
- Waiting for server round-trips on every field creates frustration
- Client-side validation provides sub-100ms feedback vs 100-500ms+ for API calls

**Hybrid approach provides best UX:**
- Instant feedback for common validation errors (empty fields, invalid formats)
- Progressive validation for complex rules (regex patterns, cross-field dependencies)
- Clear, field-specific error messages before save attempt

### 2. Maintainability & DRY Principles (Secondary Goal)

**Pure duplication is acceptable for this use case:**
- The VPO web UI has no framework dependencies (vanilla JS)
- The validation rules are relatively stable (policy schema v2 is current)
- The complexity cost of perfect DRY exceeds the maintenance cost of some duplication
- Critical insight: "In practice, full duplication (option 1) is generally less of a pain point than maintaining the extra code and complexity required for other approaches" ([Stack Overflow](https://softwareengineering.stackexchange.com/questions/398837/best-practice-in-synchronized-form-data-validations-web-apps-client-server))

**JSON Schema provides partial DRY:**
- Pydantic can export JSON Schema via `model_json_schema()`
- JavaScript validators like Ajv can consume this schema
- Reduces duplication for structural validation (types, required fields, ranges)
- Does NOT eliminate all duplication (custom validators, cross-field logic)

### 3. Technical Architecture Alignment

**Backend (Python/Pydantic):**
- `PolicyModel` in `/home/dave/src/vpo/src/video_policy_orchestrator/policy/loader.py`
- Validation includes:
  - Schema version (1-2)
  - Track order (valid TrackType values)
  - Language preferences (ISO 639-2 codes: 2-3 letter, lowercase)
  - Commentary patterns (valid regex)
  - Numeric ranges (CRF 0-51, confidence 0.0-1.0)
  - Codec/resolution enums
  - Cross-field rules (e.g., `reorder_commentary` requires `detect_commentary`)

**Frontend (Vanilla JavaScript):**
- No build step, no TypeScript, no frameworks
- Current architecture uses server-rendered HTML + progressive enhancement
- Existing patterns: fetch API for AJAX, vanilla DOM manipulation
- Security: CSP headers restrict inline scripts

**Alignment considerations:**
- TypeScript code generation tools (pydantic-to-typescript) not applicable (no TypeScript)
- Build-time validation not applicable (no build step)
- Must use runtime JavaScript validation libraries
- Should leverage existing patterns (no framework dependencies)

---

## Implementation Strategy

### Phase 1: JSON Schema Export (Backend)

**Add schema export endpoint:**

```python
# In src/video_policy_orchestrator/server/ui/routes.py
async def api_policy_schema_handler(request: web.Request) -> web.Response:
    """Handle GET /api/policies/schema - JSON Schema for policy validation.

    Returns JSON Schema generated from PolicyModel for client-side validation.
    """
    from video_policy_orchestrator.policy.loader import PolicyModel

    schema = PolicyModel.model_json_schema()

    # Add custom formats and patterns for better client validation
    # Pydantic's schema export handles most constraints automatically

    return web.json_response(schema)
```

**What this provides:**
- Structural validation (types, required fields)
- Range constraints (ge, le from Field definitions)
- Enum values (for track_order, codecs, resolutions)
- Pattern matching (for language codes via field_validator regex)

**What this does NOT provide:**
- Custom Python logic (e.g., regex compilation tests)
- Cross-field validation (e.g., `reorder_commentary` depends on `detect_commentary`)
- Domain-specific validation (e.g., checking if language code is in ISO 639-2 registry)

### Phase 2: Client-Side Validation Library

**Use Ajv for JSON Schema validation:**

```javascript
// In src/video_policy_orchestrator/server/static/js/policy-validator.js

import Ajv from 'ajv'; // Via CDN or bundled as standalone
import addFormats from 'ajv-formats';

class PolicyValidator {
    constructor() {
        this.ajv = new Ajv({ allErrors: true });
        addFormats(this.ajv);
        this.schema = null;
        this.validate = null;
    }

    async init() {
        // Fetch schema from backend
        const response = await fetch('/api/policies/schema');
        this.schema = await response.json();
        this.validate = this.ajv.compile(this.schema);
    }

    validatePolicy(policyData) {
        const valid = this.validate(policyData);
        if (!valid) {
            return this.formatErrors(this.validate.errors);
        }
        return null; // No errors
    }

    formatErrors(errors) {
        // Transform Ajv errors into user-friendly messages
        return errors.map(err => ({
            field: err.instancePath.replace(/^\//, '').replace(/\//g, '.'),
            message: err.message,
            constraint: err.keyword
        }));
    }
}
```

**Why Ajv:**
- Fastest JSON Schema validator (50% faster than alternatives) ([Ajv website](https://ajv.js.org/))
- Supports JSON Schema draft-07/2019-09/2020-12 (Pydantic v2 uses draft-07 compatible)
- Active maintenance (commits through December 2024)
- Wide adoption across JavaScript ecosystem
- Works in browsers without build step (CDN available)

### Phase 3: Specialized Validators for Domain Logic

**Language code validation:**

```javascript
// Option A: Use iso-639-1 library (for ISO 639-1 codes)
import ISO6391 from 'iso-639-1';

function validateLanguageCode(code) {
    // VPO uses ISO 639-2 (3-letter codes), but many are also ISO 639-1 (2-letter)
    // Pattern match from Pydantic: r"^[a-z]{2,3}$"
    if (!/^[a-z]{2,3}$/.test(code)) {
        return { valid: false, error: 'Invalid format. Use 2-3 lowercase letters.' };
    }

    // Optional: Check against known codes (requires ISO 639-2 list)
    // For MVP, pattern matching may be sufficient
    return { valid: true };
}
```

**Library choice for language codes:**
- Use **iso-639-1** npm package for ISO 639-1 validation ([npm package](https://www.npmjs.com/package/iso-639-1))
- For ISO 639-2 (3-letter codes used in VPO), use **iso-639-3** or pattern matching
- Consider embedded static list of valid codes to avoid external dependency

**Regex pattern validation:**

```javascript
function validateRegexPattern(pattern) {
    try {
        new RegExp(pattern);
        return { valid: true };
    } catch (e) {
        return { valid: false, error: `Invalid regex: ${e.message}` };
    }
}
```

**Cross-field validation:**

```javascript
function validateCrossFieldRules(policyData) {
    const errors = [];

    // Example: reorder_commentary requires detect_commentary
    if (policyData.transcription?.reorder_commentary &&
        !policyData.transcription?.detect_commentary) {
        errors.push({
            field: 'transcription.reorder_commentary',
            message: 'Requires detect_commentary to be enabled'
        });
    }

    return errors;
}
```

### Phase 4: Integration with Policy Editor UI

**Validation on field blur:**

```javascript
// In policy editor form
document.getElementById('audio_language_preference').addEventListener('blur', async (e) => {
    const value = e.target.value.split(',').map(s => s.trim());
    const errors = [];

    for (const code of value) {
        const result = validateLanguageCode(code);
        if (!result.valid) {
            errors.push(result.error);
        }
    }

    if (errors.length > 0) {
        showFieldError(e.target, errors[0]);
    } else {
        clearFieldError(e.target);
    }
});
```

**Validation on form submit:**

```javascript
async function submitPolicy(policyData) {
    // 1. Validate with JSON Schema
    const schemaErrors = validator.validatePolicy(policyData);
    if (schemaErrors) {
        showValidationErrors(schemaErrors);
        return;
    }

    // 2. Validate cross-field rules
    const crossFieldErrors = validateCrossFieldRules(policyData);
    if (crossFieldErrors.length > 0) {
        showValidationErrors(crossFieldErrors);
        return;
    }

    // 3. Submit to backend
    try {
        const response = await fetch('/api/policies', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(policyData)
        });

        if (!response.ok) {
            const error = await response.json();
            // Server validation caught something client missed
            showValidationErrors(error.errors);
        } else {
            // Success
        }
    } catch (e) {
        // Network error
    }
}
```

---

## Alternatives Considered

### Alternative 1: Pure Server-Side Validation

**Approach:** No client-side validation, only validate on backend

**Pros:**
- Zero duplication
- Single source of truth
- No JavaScript dependencies
- Simpler to maintain

**Cons:**
- Poor UX: requires round-trip for every error
- Network latency (100-500ms+) for each validation attempt
- Increased server load from validation requests
- Users must wait for save attempt to see errors

**Verdict:** ❌ Rejected due to poor UX

### Alternative 2: API-Based Validation Endpoint

**Approach:** Create `/api/policies/validate` endpoint, call on field blur

**Pros:**
- Zero duplication in validation logic
- Backend remains single source of truth
- Can validate complex rules easily

**Cons:**
- Still requires network round-trip (100-500ms latency)
- Increased server load (validation on every field change)
- Poor UX for fast typers (lag between input and feedback)
- Requires debouncing/throttling (adds complexity)
- "Can increase client to server traffic immensely" ([Stack Overflow](https://stackoverflow.com/questions/778726/how-do-you-avoid-duplication-of-validation-on-the-server-and-client-side))

**Verdict:** ❌ Rejected as primary strategy (could be used for optional enhanced validation)

### Alternative 3: Pydantic to TypeScript Code Generation

**Approach:** Use pydantic-to-typescript to generate TypeScript interfaces + validation

**Tools:**
- [pydantic-to-typescript](https://github.com/phillipdupuis/pydantic-to-typescript) - CLI tool for conversion
- [FastUI](https://docs.pydantic.dev/fastui/) - Pydantic + React framework

**Pros:**
- Near-perfect DRY (single definition, generated code)
- Type safety in frontend (if using TypeScript)
- Automated updates when backend changes

**Cons:**
- VPO uses vanilla JavaScript (no TypeScript, no build step)
- Would require major architectural change (add TypeScript, build tools)
- Complexity increase (CI/CD pipeline for regeneration)
- Doesn't eliminate all duplication (custom validators, cross-field logic)
- "Requires json2ts CLI utility to be installed" ([PyPI](https://pypi.org/project/pydantic-to-typescript/))

**Verdict:** ❌ Rejected due to architectural mismatch (no TypeScript/build step)

### Alternative 4: Shared Validation via WebAssembly

**Approach:** Compile Python validation logic to WASM, run in browser

**Pros:**
- True code sharing (exact same validation logic)
- Zero duplication

**Cons:**
- Extremely complex (requires Pyodide or similar)
- Large bundle size (Python runtime in browser)
- Significant performance overhead
- Maintenance nightmare
- Overkill for this use case

**Verdict:** ❌ Rejected due to excessive complexity

### Alternative 5: OpenAPI + Code Generation

**Approach:** Generate OpenAPI schema from Pydantic, use OpenAPI validators

**Tools:**
- Pydantic → OpenAPI (via FastAPI or manual generation)
- openapi-schema-validation JavaScript libraries

**Pros:**
- Standard format (OpenAPI)
- Tooling ecosystem (Swagger, etc.)

**Cons:**
- VPO doesn't use FastAPI (uses aiohttp)
- OpenAPI is designed for API documentation, not form validation
- Adds extra conversion layer (Pydantic → OpenAPI → JS validator)
- More complex than direct JSON Schema approach

**Verdict:** ❌ Rejected due to unnecessary complexity (JSON Schema is more direct)

---

## Implementation Notes

### 1. Dependency Management

**For JSON Schema validation (Ajv):**
- **Option A:** CDN import (simplest, no build step)
  ```html
  <script src="https://cdn.jsdelivr.net/npm/ajv@8/dist/2020.bundle.js"></script>
  ```
- **Option B:** Vendored copy (better security/reliability)
  - Download ajv.bundle.js to `/server/static/js/vendor/`
  - Commit to repo
  - Reference as static file

**For language code validation:**
- **Recommended:** Embed static list of ISO 639-2 codes
- Extract from iso-639-2 npm package, create `iso639-codes.js` constant
- Avoid runtime dependency on external library

### 2. Error Message Consistency

**Challenge:** Pydantic error messages vs client-side messages

**Solution:** Create error message mapping

```javascript
const ERROR_MESSAGES = {
    'schema_version.ge': 'Schema version must be at least 1',
    'schema_version.le': 'Schema version must be at most 2',
    'track_order.min_length': 'Track order cannot be empty',
    'track_order.invalid_type': 'Unknown track type. Valid types: video, audio_main, ...',
    'language_preference.pattern': 'Invalid language code. Use ISO 639-2 codes (e.g., eng, jpn)',
    'confidence_threshold.ge': 'Confidence threshold must be between 0.0 and 1.0',
    'target_crf.ge': 'CRF must be between 0 and 51'
};
```

Match these to backend error messages in `loader.py` to ensure consistency.

### 3. Schema Versioning

**Problem:** What if backend schema changes?

**Solutions:**
- Cache schema in sessionStorage with TTL
- Add schema version to schema endpoint response
- Invalidate cache on version mismatch
- Show warning if client schema is stale

```javascript
async function fetchSchema() {
    const cached = sessionStorage.getItem('policy_schema');
    const cachedVersion = sessionStorage.getItem('policy_schema_version');

    if (cached && cachedVersion === EXPECTED_VERSION) {
        return JSON.parse(cached);
    }

    const response = await fetch('/api/policies/schema');
    const schema = await response.json();

    sessionStorage.setItem('policy_schema', JSON.stringify(schema));
    sessionStorage.setItem('policy_schema_version', schema.version);

    return schema;
}
```

### 4. Testing Strategy

**Client-side validation tests:**
- Unit tests for validator functions (Jest or similar)
- Integration tests for form validation flow
- Test error message display

**Backend validation tests:**
- Existing tests in `/tests/unit/policy/` already cover PolicyModel
- Add tests for schema export endpoint
- Ensure client and server validation produce similar error messages

**Cross-validation tests:**
- Test cases that should pass client but fail server (edge cases)
- Test cases that should fail both (common errors)
- Verify error messages match expectations

### 5. Progressive Enhancement

**Ensure form works without JavaScript:**
- Use native HTML5 validation attributes as fallback
  ```html
  <input type="text" pattern="[a-z]{2,3}" required>
  ```
- Server-side validation always runs (regardless of client validation)
- Show server validation errors if client validation bypassed

### 6. Performance Considerations

**Schema size:**
- PolicyModel JSON Schema is ~2-4KB (small)
- Ajv bundle is ~50KB minified (acceptable)
- Total overhead: <100KB (negligible)

**Validation speed:**
- JSON Schema validation: <1ms for typical policy
- Regex validation: <1ms per pattern
- Language code lookup: <1ms
- Total client validation: <10ms (instant feedback)

**Memory:**
- Compiled Ajv validators are efficient
- Cache compiled validators (don't recompile on each validation)

---

## Risks and Mitigations

### Risk 1: Schema Divergence

**Risk:** Client and server validation get out of sync

**Mitigation:**
- Backend is always authoritative (always validate on save)
- Schema endpoint auto-generated from Pydantic model (can't drift)
- CI/CD test that compares client validation results to server
- Document that client validation is UX enhancement, not security

### Risk 2: Complex Validation Logic Duplication

**Risk:** Custom validators (e.g., regex compilation) must be duplicated

**Mitigation:**
- Accept some duplication for complex rules
- Document which validations are duplicated and why
- Consider API-based validation for very complex rules (optional enhancement)
- Keep custom validators simple and well-tested

### Risk 3: Maintenance Burden

**Risk:** Every schema change requires updating client and server

**Mitigation:**
- JSON Schema auto-generation reduces burden (structural changes handled)
- Only custom validators need manual updates
- Schema changes are infrequent (current version: 2, stable)
- Document validation rules in ADR for reference

### Risk 4: JavaScript Dependency Management

**Risk:** Ajv or other libraries become outdated/unmaintained

**Mitigation:**
- Vendor dependencies (commit to repo) for stability
- Ajv is widely adopted and actively maintained (commits through 2024)
- Could replace with alternative JSON Schema validator if needed (standard format)
- Fallback to server-side validation if client library fails

---

## Recommendations

### Immediate Actions (MVP)

1. **Implement JSON Schema export endpoint** (`/api/policies/schema`)
   - Use Pydantic's `model_json_schema()` method
   - Add to routes.py

2. **Add Ajv validation to policy editor**
   - Vendor Ajv standalone bundle
   - Create `policy-validator.js` module
   - Integrate with form submit

3. **Add specialized validators**
   - Language code pattern matching
   - Regex compilation test
   - Cross-field rules (detect_commentary → reorder_commentary)

4. **Show validation errors in UI**
   - Field-level errors on blur
   - Form-level errors on submit
   - Clear, actionable error messages

### Future Enhancements (Post-MVP)

1. **API-based validation endpoint** (optional)
   - `/api/policies/validate` for complex rule checking
   - Use for progressive enhancement (not required)
   - Debounced to avoid excessive requests

2. **Validation on field input** (optional)
   - Real-time validation as user types
   - Debounced (300-500ms) to avoid flicker
   - Show inline suggestions (e.g., autocomplete language codes)

3. **Schema versioning and caching**
   - Detect schema version mismatches
   - Show warning if client needs refresh
   - Invalidate cache on backend deployment

4. **Validation analytics**
   - Track which validation errors are most common
   - Improve error messages based on user confusion
   - Identify fields that need better UX (autocomplete, dropdowns)

---

## Conclusion

The **hybrid validation architecture** provides the best balance for VPO's needs:

- **User Experience:** Fast, immediate feedback (sub-10ms validation)
- **Maintainability:** Acceptable duplication given stable schema and simple validation rules
- **Architecture Alignment:** Works with vanilla JS, no build step, fits existing patterns
- **Risk Management:** Backend always authoritative, client validation is enhancement

This approach follows industry best practices: "Always implement both validations... In practice, full duplication is generally less of a pain point than maintaining the extra code and complexity required for other approaches" ([Stack Overflow - Best Practices](https://softwareengineering.stackexchange.com/questions/398837/best-practice-in-synchronized-form-data-validations-web-apps-client-server)).

The recommended implementation strategy provides incremental value:
1. **MVP:** JSON Schema + Ajv for structural validation (immediate UX win)
2. **Phase 2:** Specialized validators for domain logic (language codes, regex)
3. **Phase 3:** Optional API-based validation for complex rules (progressive enhancement)

This allows shipping fast feedback early while keeping the door open for future enhancements.

---

## Sources

1. [Ajv JSON Schema Validator](https://ajv.js.org/) - Fastest JSON Schema validator
2. [Pydantic JSON Schema Documentation](https://docs.pydantic.dev/latest/concepts/json_schema/) - Schema generation from models
3. [pydantic-to-typescript on GitHub](https://github.com/phillipdupuis/pydantic-to-typescript) - TypeScript code generation tool
4. [Stack Overflow: Best Practice in Synchronized Form Data Validations](https://softwareengineering.stackexchange.com/questions/398837/best-practice-in-synchronized-form-data-validations-web-apps-client-server) - Validation architecture patterns
5. [Stack Overflow: Avoiding Server-Side and Client-Side Validation Duplication](https://stackoverflow.com/questions/37024363/avoiding-server-side-and-client-side-validation-code-duplication-in-enterprise-w) - DRY strategies
6. [DEV Community: Reusable Form Validation Architecture](https://dev.to/vkrepkiy/reusable-form-validation-architecture-for-restful-systems-4103) - JSON Schema approach
7. [DevZery: API Schema Validation Guide](https://www.devzery.com/post/api-schema-validation) - Runtime vs build-time validation
8. [Matt's Blog: TypeScript Runtime Validation](https://www.thegalah.com/solving-typescript-runtime-validation-without-changing-your-code) - Build-time validation tools
9. [iso-639-1 npm package](https://www.npmjs.com/package/iso-639-1) - Language code validation library
10. [Stack Overflow: Client-side vs Server-side Validation](https://stackoverflow.com/questions/162159/javascript-client-side-vs-server-side-validation) - Security and UX tradeoffs

---

**Report prepared by:** Claude (Anthropic)
**Review status:** Draft for team discussion
**Next steps:** Discuss recommendations with team, prioritize MVP features, create implementation tickets

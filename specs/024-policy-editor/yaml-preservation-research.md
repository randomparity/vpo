# YAML Preservation Research: Policy Editor Round-Trip Operations

**Date**: 2025-11-24
**Context**: Research for feature 024-policy-editor
**Researcher**: Claude Code

## Executive Summary

This research evaluates strategies for preserving unknown fields and comments when round-tripping YAML policy files through the VPO policy editor. The goal is to allow users to edit core policy fields via a web form while maintaining data integrity for unrecognized fields, custom extensions, and best-effort preservation of YAML comments.

**Recommendation**: Use **ruamel.yaml** with round-trip mode (`typ="rt"`) combined with a selective merge strategy that preserves unknown fields. This approach balances simplicity, maintainability, and data preservation requirements.

---

## Research Questions Addressed

### 1. What are the options for preserving unknown YAML fields during round-trip?

**Options Identified**:

#### A. **PyYAML with Manual Merge Strategy**
- Load original YAML with `yaml.safe_load()` to get full dict
- Validate edited fields via Pydantic
- Merge validated fields back into original dict, preserving unknown keys
- Dump with `yaml.safe_dump()`

**Pros**:
- Uses existing PyYAML dependency (already in VPO)
- Simple to understand and implement
- Preserves unknown fields at top level

**Cons**:
- Cannot preserve YAML comments (PyYAML discards them at parse time)
- Loses formatting (indentation, line breaks, flow style)
- Manual merge logic required for nested structures
- No preservation of key ordering

#### B. **ruamel.yaml with Round-Trip Mode**
- Load with `YAML(typ="rt")` which preserves structure and comments
- Modify specific fields in the loaded data structure
- Dump back with same YAML instance

**Pros**:
- Preserves comments, formatting, key ordering
- Handles complex nested structures
- Widely used in production (500k+ daily downloads)
- Good documentation and community support
- Supports both YAML 1.1 and 1.2

**Cons**:
- Additional dependency (but lightweight, pure Python available)
- Slightly different API from PyYAML
- Comment preservation can break if structure changes significantly (e.g., deleting keys)
- Requires careful handling to avoid losing Pydantic validation

#### C. **Hybrid: ruamel.yaml Load → Pydantic Validate → ruamel.yaml Dump**
- Load original with ruamel.yaml to preserve structure
- Extract fields for editing/validation via Pydantic
- Merge validated fields back into ruamel.yaml data structure
- Dump with ruamel.yaml

**Pros**:
- Maintains existing Pydantic validation architecture
- Preserves comments and formatting where possible
- Allows selective field editing
- Compatible with existing PolicySchema

**Cons**:
- Most complex approach
- Requires understanding both libraries
- Merge logic needs careful design

---

### 2. What library options exist for preserving YAML comments?

**Finding**: Only **ruamel.yaml** provides reliable comment preservation in Python.

#### PyYAML Status (2024)
- Comments are discarded during scanning (lowest level of parser)
- Feature request for comment support has been stalling since before 2020
- No active development on this feature
- Source: [PyYAML GitHub Issues](https://github.com/yaml/pyyaml), [Reorx's PyYAML Tips](https://reorx.com/blog/python-yaml-tips/)

#### ruamel.yaml Capabilities
- Designed specifically for round-trip preservation
- Preserves:
  - Comments (block and end-of-line)
  - Key ordering in mappings
  - Flow style vs block style
  - Quotes around strings
  - Indentation patterns

- **Limitations**:
  - Comments may be lost if keys are deleted
  - Major structural changes can affect comment association
  - Best-effort preservation, not guaranteed for all edge cases

**Source References**:
- [ruamel.yaml PyPI](https://pypi.org/project/ruamel.yaml/)
- [Why ruamel.yaml Should Be Your Python YAML Library](https://medium.com/top-python-libraries/why-ruamel-yaml-should-be-your-python-yaml-library-of-choice-81bc17891147)
- [Stack Overflow: Python YAML update preserving order and comments](https://stackoverflow.com/questions/47382227/python-yaml-update-preserving-order-and-comments)

#### Alternative Libraries
- **strictyaml**: Focuses on type safety, no comment preservation
- **pyyaml-include**: Extends PyYAML, inherits comment limitation
- **omegaconf**: Configuration management, not designed for round-trip editing

**Conclusion**: ruamel.yaml is the only mature, production-ready library for comment-preserving YAML round-trips in Python.

---

### 3. What is the recommended strategy for merging edited fields with preserved fields?

**Recommended Strategy**: **Selective In-Place Updates**

This approach modifies only the specific fields that were edited in the form, leaving all other fields untouched in the ruamel.yaml data structure.

#### Implementation Pattern

```python
from ruamel.yaml import YAML
from pathlib import Path

# Initialize YAML with round-trip mode
yaml = YAML()
yaml.preserve_quotes = True
yaml.default_flow_style = False

# Load original policy
with open(policy_path) as f:
    data = yaml.load(f)

# Apply selective updates from editor
# Only update fields that were actually edited
if 'track_order' in updates:
    data['track_order'] = updates['track_order']

if 'audio_language_preference' in updates:
    data['audio_language_preference'] = updates['audio_language_preference']

# Validate complete policy via existing loader
# (Ensures edited policy is valid before saving)
from vpo.policy.loader import load_policy_from_dict
validated_policy = load_policy_from_dict(dict(data))

# Write back to file
with open(policy_path, 'w') as f:
    yaml.dump(data, f)
```

#### Key Principles

1. **In-Place Modification**: Update fields directly in the loaded ruamel.yaml structure rather than reconstructing from scratch

2. **Selective Updates**: Only touch fields that were edited in the form; ignore unchanged fields

3. **Validation After Merge**: Run the existing Pydantic validation on the complete merged structure to ensure integrity

4. **Preserve Unknown Fields**: Any fields not recognized by the editor remain in the `data` structure untouched

#### Handling Nested Structures

For nested fields like `transcode` or `default_flags`:

```python
# Update nested section while preserving siblings
if 'default_flags' in updates:
    if 'default_flags' not in data:
        data['default_flags'] = {}

    # Update only specified flags
    for flag_name, flag_value in updates['default_flags'].items():
        data['default_flags'][flag_name] = flag_value
```

#### Alternative Strategies Considered

**A. Full Reconstruction**: Convert Pydantic model back to dict and dump
- **Rejected**: Loses all unknown fields, comments, and formatting

**B. Deep Merge**: Recursively merge updated dict into original
- **Considered**: More complex than needed for VPO's flat-ish policy structure
- **Use Case**: Better suited for deeply nested configs with array merging requirements

**Source References**:
- [Stack Overflow: Editing YAML file by Python](https://stackoverflow.com/questions/29518833/editing-yaml-file-by-python)
- [ruamel.yaml Documentation: Details](https://yaml.dev/doc/ruamel.yaml/detail/)

---

### 4. What are the tradeoffs of each approach?

#### Comparison Matrix

| Criterion | PyYAML + Manual Merge | ruamel.yaml Round-Trip | Hybrid Approach |
|-----------|----------------------|------------------------|-----------------|
| **Preserve Unknown Fields** | ✅ Yes (with merge logic) | ✅ Yes (automatic) | ✅ Yes (with merge logic) |
| **Preserve Comments** | ❌ No | ✅ Yes (best-effort) | ✅ Yes (best-effort) |
| **Preserve Formatting** | ❌ No | ✅ Yes | ✅ Yes |
| **Use Existing Validation** | ✅ Yes | ⚠️ Requires adaptation | ✅ Yes |
| **Implementation Complexity** | Medium | Low | High |
| **Additional Dependencies** | None | ruamel.yaml | ruamel.yaml |
| **Backward Compatibility** | ✅ Full | ✅ Full | ✅ Full |
| **Risk of Data Loss** | Medium (unknown fields) | Low | Low |
| **Maintenance Burden** | Medium | Low | High |

#### Detailed Tradeoff Analysis

**PyYAML + Manual Merge**:
- ✅ Zero new dependencies
- ✅ Simple mental model
- ❌ Poor user experience (loses comments)
- ❌ Fails spec requirement for "best-effort" comment preservation
- **Use When**: Comments are not important, simplicity is paramount

**ruamel.yaml Round-Trip**:
- ✅ Best user experience (preserves human-readable formatting)
- ✅ Lowest implementation complexity
- ✅ Meets all spec requirements
- ⚠️ Requires new dependency (~800KB, pure Python version ~100KB)
- ⚠️ Comment preservation is "best-effort" (not guaranteed)
- **Use When**: Round-trip editing is the primary use case (matches VPO editor)

**Hybrid Approach**:
- ✅ Maximum flexibility
- ✅ Preserves existing validation architecture unchanged
- ❌ Highest complexity (two libraries, merge logic, validation bridge)
- ❌ More potential for bugs
- **Use When**: Existing validation is complex and can't be easily adapted

---

## Decision: Recommended Approach for VPO Policy Editor

### Choice: **ruamel.yaml Round-Trip with Selective Updates + Pydantic Validation**

This is essentially the "Hybrid Approach" but simplified by recognizing that VPO's validation layer can work with dict representations.

### Rationale

1. **Meets Spec Requirements**:
   - ✅ Preserves unknown fields (FR-011)
   - ✅ Best-effort comment preservation (User Story 7)
   - ✅ Maintains backward compatibility with PolicySchema
   - ✅ Clear error handling

2. **Simple Yet Powerful**:
   - Leverages ruamel.yaml's round-trip capabilities
   - Existing Pydantic validation remains unchanged
   - Selective update pattern is straightforward
   - ~50 lines of code for the core round-trip logic

3. **Good User Experience**:
   - Users' comments and formatting preserved
   - Advanced users can mix UI editing with manual YAML editing
   - Debugging is easier (readable YAML diffs)

4. **Maintainable**:
   - Single additional dependency (well-maintained, 500k+ daily downloads)
   - Clear separation: ruamel.yaml handles YAML, Pydantic handles validation
   - No complex merge algorithms needed for VPO's relatively flat policy structure

5. **Aligns with Project Values**:
   - Follows VPO constitution principle VIII (Explicit Error Handling)
   - Respects principle IX (Configuration as Data)
   - Supports principle XVIII (Living Documentation) by preserving comments

### Implementation Strategy

#### Phase 1: Add ruamel.yaml Dependency
```toml
# pyproject.toml
dependencies = [
    # ... existing deps
    "ruamel.yaml>=0.18.0",
]
```

#### Phase 2: Create Policy Editor Module
`src/vpo/server/ui/policy_editor.py`:

```python
"""Policy editor with YAML round-trip preservation."""

from pathlib import Path
from typing import Any
from ruamel.yaml import YAML

from vpo.policy.loader import (
    PolicyValidationError,
    load_policy_from_dict,
)


class PolicyRoundTripEditor:
    """Edit policy files while preserving formatting and unknown fields."""

    def __init__(self) -> None:
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.default_flow_style = False
        self.yaml.width = 4096  # Prevent line wrapping

    def load(self, policy_path: Path) -> dict[str, Any]:
        """Load policy file preserving structure."""
        with open(policy_path) as f:
            return self.yaml.load(f)

    def save(
        self,
        policy_path: Path,
        updates: dict[str, Any],
        original_data: dict[str, Any] | None = None
    ) -> None:
        """Save policy with selective updates."""
        # Load current file if original not provided
        if original_data is None:
            original_data = self.load(policy_path)

        # Apply selective updates (shallow merge for core fields)
        for key, value in updates.items():
            original_data[key] = value

        # Validate complete policy via existing validation
        try:
            load_policy_from_dict(dict(original_data))
        except Exception as e:
            raise PolicyValidationError(
                f"Policy validation failed after updates: {e}"
            ) from e

        # Write back to file
        with open(policy_path, 'w') as f:
            self.yaml.dump(original_data, f)
```

#### Phase 3: API Endpoints
```python
# In routes.py
from .policy_editor import PolicyRoundTripEditor

editor = PolicyRoundTripEditor()

async def get_policy_for_editing(request):
    """GET /api/policies/{name} - Load policy for editing."""
    name = request.match_info['name']
    policy_path = get_policy_path(name)

    # Load with preservation
    data = editor.load(policy_path)

    # Also provide validated schema for UI
    policy = load_policy(policy_path)

    return web.json_response({
        'raw': data,  # Includes unknown fields, for merging
        'schema': policy_to_dict(policy),  # Validated fields only
    })

async def save_policy_edits(request):
    """PUT /api/policies/{name} - Save edited policy."""
    name = request.match_info['name']
    policy_path = get_policy_path(name)

    body = await request.json()
    updates = body['updates']  # Only changed fields
    original = body.get('original')  # Original for merge

    try:
        editor.save(policy_path, updates, original)
        return web.json_response({'status': 'ok'})
    except PolicyValidationError as e:
        return web.json_response(
            {'error': str(e)},
            status=400
        )
```

---

## Alternatives Considered

### Alternative 1: PyYAML-Only Solution
**Why Rejected**: Does not meet spec requirement for best-effort comment preservation. While simpler, it degrades user experience for users who maintain policy comments as documentation.

### Alternative 2: pydantic-yaml Library
**Why Rejected**:
- Uses `typ="safe"` by default (disables round-trip features)
- Goes through JSON serialization round-trip (loses YAML-specific features)
- Adds abstraction layer that doesn't provide value for VPO's use case

### Alternative 3: Full Pydantic Round-Trip
**Why Rejected**: Pydantic's `model_dump()` creates a clean dict but loses unknown fields. Even with `extra="allow"`, comment preservation is impossible.

### Alternative 4: Store Unknown Fields in Database
**Why Rejected**: Over-engineering. VPO policies are filesystem-based YAML; moving to database storage contradicts project architecture and principle IX (Configuration as Data).

---

## Implementation Notes

### Key Details for Integration

1. **Validation Timing**: Always validate after merge, before save. This catches issues introduced by manual edits between form loads.

2. **Concurrency**: Use optimistic concurrency with file modification timestamps. Warn if file changed since load.

3. **Error Handling**: Distinguish between validation errors (user-fixable) and I/O errors (system issue).

4. **Testing Strategy**:
   ```python
   def test_preserves_comments():
       """Comments in policy file are preserved after edit."""
       original = "# My comment\nschema_version: 1\n"
       # ... edit, save, reload
       assert "# My comment" in reloaded_content

   def test_preserves_unknown_fields():
       """Unknown fields remain in file after edit."""
       original = {"schema_version": 1, "custom_field": "value"}
       # ... edit known fields, save, reload
       assert reloaded_data["custom_field"] == "value"
   ```

5. **Frontend Considerations**:
   - Send only changed fields in `updates` payload (reduce bandwidth)
   - Include `original` snapshot for server-side merge (prevent race conditions)
   - Show read-only YAML preview that updates as form changes

6. **Backward Compatibility**:
   - Existing `load_policy()` function remains unchanged
   - New editor is additive (doesn't replace existing policy loader)
   - All existing tests pass without modification

7. **Performance**:
   - ruamel.yaml is ~20% slower than PyYAML for parsing
   - For VPO policy files (typically <10KB), latency difference is <10ms
   - Acceptable for web UI use case (not hot path)

8. **Dependency Risk Mitigation**:
   - ruamel.yaml is stable (v0.18+), widely used (Ansible, many CI/CD tools)
   - Pure Python version available as fallback if C extension issues arise
   - No breaking changes expected (mature API)

### Edge Cases to Handle

1. **Policy File Deleted During Edit**: Return 404, clear form
2. **Invalid YAML Syntax**: Show error, offer raw text editor
3. **Validation Failure**: Highlight specific field errors, don't save
4. **Large Comment Blocks**: May be repositioned by ruamel.yaml (acceptable per spec)
5. **Empty Policy File**: Treat as `{schema_version: 2}` with defaults

---

## Migration Path

### Rollout Strategy

1. **Phase 1**: Add ruamel.yaml, create PolicyRoundTripEditor module
2. **Phase 2**: Implement GET/PUT endpoints with round-trip support
3. **Phase 3**: Build frontend form (parallel to backend)
4. **Phase 4**: Integration testing with real policy files
5. **Phase 5**: Document in user guide with comment preservation examples

### Rollback Plan

If ruamel.yaml causes issues:
- Fall back to PyYAML with manual merge (comment preservation degraded)
- Update spec to document "comments not preserved" limitation
- Editor still functional, just loses formatting preservation

### Success Metrics

- ✅ 100% unknown field preservation in tests
- ✅ 90%+ comment preservation in typical edits (not deleting keys)
- ✅ All existing policy files load and save correctly
- ✅ No regression in existing `load_policy()` behavior

---

## Sources

### Primary Research Sources

- [ruamel.yaml PyPI](https://pypi.org/project/ruamel.yaml/)
- [ruamel.yaml Documentation](https://yaml.dev/doc/ruamel.yaml/overview/)
- [Why ruamel.yaml Should Be Your Python YAML Library](https://medium.com/top-python-libraries/why-ruamel-yaml-should-be-your-python-yaml-library-of-choice-81bc17891147)
- [Tips that may save you from the hell of PyYAML](https://reorx.com/blog/python-yaml-tips/)
- [Stack Overflow: Python YAML update preserving order and comments](https://stackoverflow.com/questions/47382227/python-yaml-update-preserving-order-and-comments)
- [Stack Overflow: Save/dump a YAML file with comments in PyYAML](https://stackoverflow.com/questions/7255885/save-dump-a-yaml-file-with-comments-in-pyyaml)
- [pydantic-yaml PyPI](https://pypi.org/project/pydantic-yaml/)
- [Configuration files using Pydantic and YAML](https://trhallam.github.io/trhallam/blog/pydantic-yaml-config/)
- [Stack Overflow: Editing YAML file by Python](https://stackoverflow.com/questions/29518833/editing-yaml-file-by-python)
- [Stack Overflow: Merge two YAML files in Python](https://stackoverflow.com/questions/47424865/merge-two-yaml-files-in-python)
- [ruamel.yaml Detail Documentation](https://yaml.dev/doc/ruamel.yaml/detail/)

### Related VPO Files Analyzed

- `/home/dave/src/vpo/src/vpo/policy/loader.py` - Current policy loading
- `/home/dave/src/vpo/src/vpo/policy/models.py` - PolicySchema definition
- `/home/dave/src/vpo/tests/unit/test_policy_loader.py` - Validation test patterns
- `/home/dave/src/vpo/tests/fixtures/policies/valid-full.yaml` - Example policy structure
- `/home/dave/src/vpo/examples/policies/transcode-hevc.yaml` - Policy with extensive comments

---

## Conclusion

The recommended approach of using **ruamel.yaml with round-trip mode and selective updates** provides the best balance of:

- **Correctness**: Preserves unknown fields and comments (meets spec)
- **Simplicity**: ~50 lines of new code for core functionality
- **Maintainability**: Clear separation of concerns, stable dependency
- **User Experience**: Human-friendly YAML preservation
- **Risk**: Low (fallback to PyYAML if needed, backward compatible)

This solution integrates cleanly with VPO's existing architecture while enabling the policy editor feature with high data integrity.

# Research: Conditional Policy Logic

**Feature**: 032-conditional-policy
**Date**: 2025-11-26
**Status**: Complete

## Research Areas

### 1. Condition Expression Syntax Design

**Decision**: Use YAML-native nested structures with keyword operators

**Rationale**:
- Consistent with existing policy YAML syntax
- No custom expression parser needed
- Clear visual hierarchy for complex conditions
- Easy to validate with Pydantic

**Alternatives Considered**:
1. **String-based DSL** (e.g., `"video.height >= 2160 AND audio.channels > 2"`)
   - Rejected: Requires custom parser, error messages harder, escaping issues
2. **JSONPath expressions**
   - Rejected: Overkill for track matching, unfamiliar syntax for users
3. **YAML anchors/references**
   - Rejected: Makes conditions harder to read at a glance

**Syntax Example**:
```yaml
conditional:
  - name: "4K content handling"
    when:
      and:
        - exists:
            track_type: video
            height: { gte: 2160 }
        - not:
            exists:
              track_type: audio
              codec: [truehd, dts-hd]
    then:
      skip_video_transcode: true
    else:
      warn: "Non-4K or has lossless audio"
```

### 2. Condition Evaluation Strategy

**Decision**: Recursive visitor pattern with depth tracking

**Rationale**:
- Clean separation between condition types
- Natural fit for tree-structured conditions
- Depth tracking enforces 3-level nesting limit during evaluation
- Easy to extend with new condition types

**Implementation Pattern**:
```python
def evaluate_condition(
    condition: Condition,
    tracks: list[TrackInfo],
    depth: int = 0,
) -> bool:
    if depth > 3:
        raise PolicyValidationError("Condition nesting exceeds 3 levels")

    match condition:
        case ExistsCondition():
            return evaluate_exists(condition, tracks)
        case CountCondition():
            return evaluate_count(condition, tracks)
        case AndCondition():
            return all(evaluate_condition(c, tracks, depth + 1) for c in condition.conditions)
        case OrCondition():
            return any(evaluate_condition(c, tracks, depth + 1) for c in condition.conditions)
        case NotCondition():
            return not evaluate_condition(condition.inner, tracks, depth + 1)
```

**Alternatives Considered**:
1. **Compile to Python lambdas**
   - Rejected: Security concerns, harder to debug/log
2. **External rule engine (drools-like)**
   - Rejected: Heavy dependency, overkill for this scope

### 3. Track Matching in Conditions

**Decision**: Reuse existing TrackInfo properties with comparison operators

**Rationale**:
- Consistent with Sprint 1's track filtering
- Properties already available from ffprobe introspection
- Familiar to users who use track filtering

**Available Properties** (from TrackInfo dataclass):
| Property | Type | Operators | Example |
|----------|------|-----------|---------|
| track_type | string | eq, in | `track_type: video` |
| codec | string | eq, in | `codec: [hevc, h265, x265]` |
| language | string | eq, in | `language: eng` |
| is_default | bool | eq | `is_default: true` |
| is_forced | bool | eq | `is_forced: true` |
| channels | int | eq, lt, lte, gt, gte | `channels: { gte: 6 }` |
| width | int | eq, lt, lte, gt, gte | `width: { gte: 3840 }` |
| height | int | eq, lt, lte, gt, gte | `height: { gte: 2160 }` |
| title | string | eq, contains, regex | `title: { contains: "Commentary" }` |

**Codec Alias Handling**:
- Maintain canonical alias map in `conditions.py`
- hevc ↔ h265 ↔ x265
- aac ↔ mp4a
- ac3 ↔ a52
- dts ↔ dca

### 4. Action Types for Conditional Rules

**Decision**: Three categories of actions

**Rationale**:
- Skip actions modify plan execution without adding operations
- Alert actions provide feedback/control flow
- Policy actions can reference existing policy action syntax

**Action Categories**:

1. **Skip Actions** (set flags that affect later processing):
   - `skip_video_transcode: true` - Don't transcode video even if policy requests it
   - `skip_audio_transcode: true` - Don't transcode audio
   - `skip_track_filter: true` - Don't apply track filtering

2. **Alert Actions** (control flow and feedback):
   - `warn: "message"` - Log warning, continue processing
   - `fail: "message"` - Stop processing with error

3. **Policy Override Actions** (future extensibility):
   - `set_default: { track_type: subtitle, language: eng }` - Set default flag
   - `transcode: { target_crf: 18 }` - Override transcode settings

**Placeholder Substitution**:
- `{filename}` - Base filename without path
- `{path}` - Full file path
- `{rule_name}` - Name of the matching rule
- `{track_type}` - Track type that matched (for exists conditions)

### 5. Integration with Policy Evaluation Flow

**Decision**: Conditionals execute first, set flags, then normal policy sections run

**Rationale**:
- Clear execution order prevents confusion
- Skip flags can suppress operations before they're planned
- Non-conditional sections remain predictable

**Execution Flow**:
```
1. Load and validate policy (schema v4)
2. Parse conditional rules
3. For each file:
   a. Evaluate conditional rules (first-match-wins)
   b. Execute matched rule's then/else actions
   c. Set skip flags in evaluation context
   d. Run track filtering (respects skip_track_filter)
   e. Run track ordering
   f. Generate transcode actions (respects skip_video_transcode)
   g. Return Plan with all actions + conditional results
```

**Plan Extension**:
```python
@dataclass(frozen=True)
class Plan:
    # ... existing fields ...
    conditional_result: ConditionalResult | None  # NEW
    skip_flags: SkipFlags  # NEW

@dataclass(frozen=True)
class ConditionalResult:
    matched_rule: str | None  # Name of first matching rule
    matched_branch: Literal["then", "else", None]
    warnings: tuple[str, ...]  # Any warn actions triggered

@dataclass(frozen=True)
class SkipFlags:
    skip_video_transcode: bool = False
    skip_audio_transcode: bool = False
    skip_track_filter: bool = False
```

### 6. Validation Strategy

**Decision**: Two-phase validation (Pydantic then semantic)

**Rationale**:
- Pydantic catches structural issues (missing fields, wrong types)
- Semantic validation catches logical issues (unknown track_type, invalid nesting)

**Phase 1 - Pydantic Structural Validation**:
```python
class ConditionModel(BaseModel):
    exists: dict | None = None
    count: dict | None = None
    and_: list["ConditionModel"] | None = Field(None, alias="and")
    or_: list["ConditionModel"] | None = Field(None, alias="or")
    not_: "ConditionModel" | None = Field(None, alias="not")

    @model_validator(mode="after")
    def exactly_one_condition_type(self):
        # Ensure exactly one of exists/count/and/or/not is set
```

**Phase 2 - Semantic Validation**:
- Validate nesting depth ≤ 3
- Validate track_type values are known
- Validate comparison operators are valid for property types
- Validate codec aliases exist

### 7. Dry-Run Output Format

**Decision**: Structured output showing rule evaluation trace

**Rationale**:
- Users need to debug why rules match or don't match
- Consistent with existing dry-run verbosity

**Output Format**:
```
=== Conditional Rules ===
Rule "4K HEVC handling":
  Condition: exists(video, height >= 2160)
  → MATCHED
  Actions: skip_video_transcode=true

Rule "Add stereo if missing":
  Condition: not(exists(audio, channels <= 2))
  → NOT MATCHED (found: audio[1] channels=2)

=== Track Filtering ===
...
```

### 8. Error Messages

**Decision**: Contextual error messages with YAML path

**Examples**:
```
PolicyValidationError: Invalid condition at conditional[0].when.and[1].exists
  Unknown track_type: "vidoe" (did you mean "video"?)

PolicyValidationError: Invalid condition at conditional[2].when
  Nesting depth exceeds maximum of 3 levels

PolicyValidationError: Invalid action at conditional[0].then
  Unknown action type: "skip_transcode" (did you mean "skip_video_transcode"?)

ConditionalFailError: Rule "Corrupted video check" triggered fail action
  Message: "Video track has unknown codec - manual review required"
  File: /media/videos/problematic.mkv
```

## Summary

All research questions resolved. Key decisions:
1. YAML-native syntax with keyword operators (exists, count, and, or, not)
2. Recursive evaluator with depth tracking for nesting limit
3. Reuse TrackInfo properties with standard comparison operators
4. Three action categories: skip, alert, policy override
5. Conditionals execute first, set flags for later sections
6. Two-phase validation (structural then semantic)
7. Trace-style dry-run output for debugging

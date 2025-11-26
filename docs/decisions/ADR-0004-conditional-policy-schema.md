# ADR-0004: Conditional Policy Schema

**Status:** Accepted
**Date:** 2025-11-26
**Decision Makers:** Project maintainers

---

## Context

VPO policies define rules for organizing and transforming video libraries. As users manage increasingly diverse libraries, they need to apply different settings based on file properties without maintaining multiple policy files.

Common scenarios requiring conditional logic:
- Skip video transcoding when file is already in target codec
- Apply different quality settings for 4K vs HD content
- Warn when files lack expected tracks (e.g., missing English subtitles)
- Handle anime differently from Western content based on audio/subtitle presence

The existing policy schema (v3) lacks the ability to make decisions based on file analysis.

---

## Decision

Introduce schema version 4 with a `conditional` section supporting if/then/else rules with first-match-wins semantics.

### Schema Structure

```yaml
schema_version: 4

conditional:
  - name: "Rule name"
    when: <condition>
    then: <actions>
    else: <actions>  # optional
```

### Condition Types

1. **exists** - Check if tracks matching criteria exist
2. **count** - Count tracks matching criteria with comparison
3. **and** - All sub-conditions must be true
4. **or** - At least one sub-condition must be true
5. **not** - Negate a condition

### Track Filters

Conditions can filter tracks by:
- `track_type`: video, audio, subtitle, attachment
- `language`: ISO 639-2/B code or list
- `codec`: Codec name or list
- `is_default`, `is_forced`: Boolean flags
- `channels`, `width`, `height`: Numeric with comparison operators
- `title`: Substring or regex match

### Comparison Operators

Numeric properties support: `eq`, `lt`, `lte`, `gt`, `gte`

### Actions

- `skip_video_transcode`, `skip_audio_transcode`, `skip_track_filter`: Boolean
- `warn`: String message (logged, processing continues)
- `fail`: String message (halts processing)

Messages support placeholders: `{filename}`, `{path}`, `{rule_name}`

### Evaluation Order

1. Conditional rules are evaluated before non-conditional sections
2. Rules are evaluated in document order
3. First matching rule wins (stops evaluation)
4. Skip flags from matched rule affect subsequent processing
5. Non-conditional sections always execute after conditionals

---

## Options Considered

### Option A: Per-Section Conditions

Add conditions to each existing policy section:

```yaml
audio_filter:
  when: { exists: { track_type: audio, language: eng } }
  languages: [eng]
```

**Pros:** Localized, no new top-level section
**Cons:** Repetitive, can't share conditions, unclear evaluation order

### Option B: Rule-Based System (Chosen)

Dedicated `conditional` section with named rules:

```yaml
conditional:
  - name: "Skip HEVC"
    when: { exists: { track_type: video, codec: hevc } }
    then: [skip_video_transcode: true]
```

**Pros:** Clear semantics, named rules for debugging, first-match-wins is intuitive
**Cons:** New top-level section, slightly more verbose

### Option C: Expression Language

Use a DSL for conditions:

```yaml
conditional:
  - when: "video.codec == 'hevc' && video.height >= 2160"
    then: ...
```

**Pros:** Very expressive, familiar to programmers
**Cons:** New syntax to learn, harder to validate, parser complexity

---

## Consequences

### Positive

- Single policy handles multiple scenarios
- Clear debugging with named rules and dry-run output
- Extensible design for future condition types
- Backward compatible (v3 policies unchanged)

### Negative

- Increased schema complexity
- Users must understand evaluation order
- Nesting limit (3 levels) may frustrate power users

### Neutral

- Schema version bump to v4
- New exception type (ConditionalFailError)
- Additional validation at policy load time

---

## Implementation Notes

### Data Models

Core models in `policy/models.py`:
- `Condition` union type with variants (Exists, Count, And, Or, Not)
- `ConditionalAction` union type (Skip, Warn, Fail)
- `ConditionalRule` with name, when, then, else_actions
- `SkipFlags` for controlling subsequent processing
- `ConditionalResult` for evaluation outcome

### Evaluation Flow

1. `evaluate_conditional_rules()` iterates rules
2. `evaluate_condition()` dispatches to type-specific evaluators
3. `execute_actions()` processes matched rule's actions
4. Result includes matched rule, branch, skip flags, warnings, trace

### Validation

- Schema version check at load time
- Track type validation
- Comparison operator validation
- Nesting depth check (max 3 levels)
- Regex syntax validation for title patterns

---

## Related docs

- [Conditional Policy Guide](../usage/conditional-policies.md)
- [Policy Configuration Guide](../usage/policies.md)
- [ADR-0002: Policy Schema Versioning](ADR-0002-policy-schema-versioning.md)

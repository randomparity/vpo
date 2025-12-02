# Research: Plugin Metadata Access in Policies

**Feature**: 039-plugin-metadata-policy
**Date**: 2025-12-01

## Research Summary

This feature extends the existing policy condition system to support plugin-provided metadata. All design decisions leverage existing VPO patterns, so no significant technical unknowns required resolution.

## Decision 1: Condition Type Design

**Decision**: Create a new `PluginMetadataCondition` dataclass following the `AudioIsMultiLanguageCondition` pattern.

**Rationale**:
- Existing conditions (`ExistsCondition`, `CountCondition`) operate on track-level data
- Plugin metadata operates on file-level data - different domain, warrants separate type
- New type makes YAML syntax explicit and self-documenting
- Enables isolated unit testing of plugin metadata evaluation

**Alternatives Considered**:
- Extend `TrackFilters` with plugin references: Rejected because it conflates track-level and file-level concerns
- Generic "metadata" condition for all sources: Rejected because plugin namespacing (radarr vs sonarr) is essential

## Decision 2: YAML Syntax

**Decision**: Use explicit operator syntax with `plugin_metadata`, `operator`, and `value` fields.

**Rationale**:
- Consistent with VPO's explicit-over-implicit design philosophy
- Clear separation of reference, comparison type, and expected value
- Supports future operator additions without syntax changes
- Self-documenting in policy files

**Syntax Example**:
```yaml
conditional:
  - name: japanese-content
    when:
      plugin_metadata:
        plugin_metadata: "radarr:original_language"
        operator: eq
        value: "jpn"
    then:
      - skip_audio_transcode: true
```

**Alternatives Considered**:
- Concise nested (`plugin_field: { plugin: "...", equals: "..." }`): Rejected as less consistent
- Flat reference (`radarr:original_language: { eq: "jpn" }`): Rejected due to parsing complexity

## Decision 3: Fallback Handling

**Decision**: Use condition-based fallback - missing data evaluates to false, users use `exists` checks and `else` branches.

**Rationale**:
- Leverages existing conditional rule pattern (no new syntax to learn)
- Follows VPO's explicit error handling principle (Constitution VII)
- No hidden magic - policy author explicitly handles all cases
- More flexible than fixed fallback modes

**Pattern Example**:
```yaml
conditional:
  - name: check-radarr-language
    when:
      and:
        - plugin_metadata:
            plugin_metadata: "radarr:original_language"
            operator: exists
        - plugin_metadata:
            plugin_metadata: "radarr:original_language"
            operator: eq
            value: "jpn"
    then:
      - skip_audio_transcode: true
    else:
      - warn: "No Radarr metadata - using default processing"
```

**Alternatives Considered**:
- `on_missing` declaration (`keep_all`, `skip_file`, `use_default_languages`): Rejected as too language-specific and not generalizable
- Inline defaults (`radarr:original_language | "eng"`): Rejected as adding syntax complexity

## Decision 4: Storage Location

**Decision**: New `plugin_metadata TEXT` column on `files` table storing JSON keyed by plugin name.

**Rationale**:
- JSON provides flexibility for varying plugin schemas
- Plugin name as outer key prevents field collisions
- Single column is simpler than separate table
- Matches existing patterns (e.g., `progress_json`, `actions_json`)

**Schema**:
```json
{
  "radarr": {
    "original_language": "jpn",
    "tmdb_id": 12345,
    "external_title": "My Neighbor Totoro"
  },
  "sonarr": null
}
```

**Alternatives Considered**:
- Separate `file_enrichments` table: Rejected as over-normalized for this use case
- Expand FileInfo with fixed fields: Rejected as not extensible for future plugins

## Decision 5: Validation Strategy

**Decision**: Warnings (not errors) for unrecognized plugin names or field names during policy loading.

**Rationale**:
- Forward compatibility: newer plugins may have fields unknown to current registry
- User experience: don't block policy loading for typos in optional features
- Follows existing VPO pattern of advisory validation

**Implementation**:
- Hard-coded registry of known fields for radarr/sonarr plugins
- `validate_plugin_reference()` returns list of warnings (empty if valid)
- Warnings logged during policy load, but policy still loads successfully

## Decision 6: Schema Versioning

**Decision**: Policy schema V12, database migration v16→v17.

**Rationale**:
- V12 follows existing versioning (current is V11)
- Database schema follows existing migration pattern
- Backward compatible: V11 policies work unchanged

**Migration**:
```sql
ALTER TABLE files ADD COLUMN plugin_metadata TEXT;
```

## Existing Patterns Referenced

| Pattern | Source | Application |
|---------|--------|-------------|
| Condition type union | `policy/models.py:1015-1022` | Add `PluginMetadataCondition` |
| Condition evaluation | `policy/conditions.py` | Add `evaluate_plugin_metadata_condition()` |
| Pydantic model parsing | `policy/loader.py` | Add `PluginMetadataConditionModel` |
| DB migration | `db/schema.py` | Add `migrate_v16_to_v17()` |
| Reason strings for dry-run | `policy/conditions.py:evaluate_*` | Include in all evaluation paths |

## Files to Read Before Implementation

1. `src/video_policy_orchestrator/policy/conditions.py` - Existing condition evaluation patterns
2. `src/video_policy_orchestrator/policy/loader.py` - Pydantic model and conversion patterns
3. `src/video_policy_orchestrator/policy/models.py` - Condition type union definition
4. `src/video_policy_orchestrator/db/schema.py` - Migration function patterns
5. `src/video_policy_orchestrator/db/queries.py` - upsert/select patterns for files table

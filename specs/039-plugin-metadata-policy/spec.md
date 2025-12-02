# Feature Specification: Plugin Metadata Access in Policies

**Feature Branch**: `039-plugin-metadata-policy`
**Created**: 2025-12-01
**Status**: Draft
**Input**: User description: "Update policy schema to access arbitrary metadata offered through plugins using plugin_name:metadata_field syntax in policy documents"

## Clarifications

### Session 2025-12-01

- Q: What fallback behavior should apply when plugin data is missing? → A: Condition-based: users wrap plugin conditions in `exists` checks and use `else` branches in conditional rules (leverages existing pattern, no special fallback syntax needed)
- Q: Where should plugin metadata be stored for policy evaluation? → A: New `plugin_metadata` JSON column on files table storing all plugin enrichments
- Q: What YAML syntax should be used for plugin metadata conditions? → A: Explicit operator style with `plugin_metadata`, `operator`, and `value` fields

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Condition on Plugin-Provided Original Language (Priority: P1)

A library curator wants to create a policy that makes decisions based on the original language of content, which is only available through external metadata plugins like Radarr or Sonarr (not in the media file itself).

**Why this priority**: This is the primary use case driving this feature. Original language data is crucial for intelligent track filtering and organization but is unavailable from media introspection alone.

**Independent Test**: Can be fully tested by creating a policy with a condition on `radarr:original_language` and verifying it evaluates correctly against files that have been enriched by the Radarr plugin.

**Acceptance Scenarios**:

1. **Given** a media file enriched by Radarr with `original_language: jpn`, **When** a policy condition checks `radarr:original_language == "jpn"`, **Then** the condition evaluates to true
2. **Given** a media file NOT enriched by any plugin, **When** a policy condition checks `radarr:original_language`, **Then** the condition evaluates to false (missing data treated as condition not met)
3. **Given** a media file enriched by Sonarr (not Radarr), **When** a policy condition checks `radarr:original_language`, **Then** the condition evaluates to false (wrong plugin source)

---

### User Story 2 - Filter Audio Tracks by Content Language (Priority: P1)

A library curator wants to keep only the original language audio track and their preferred language (e.g., English) for all foreign films, using metadata from Radarr/Sonarr to determine original language.

**Why this priority**: Track filtering is one of VPO's core features, and extending it to use plugin metadata enables powerful new workflows.

**Independent Test**: Can be tested by processing a Japanese anime file enriched with `original_language: jpn` through a policy that keeps only `jpn` and `eng` audio tracks.

**Acceptance Scenarios**:

1. **Given** a file with audio tracks in `jpn`, `eng`, `fre`, `ger` and plugin metadata `original_language: jpn`, **When** applying a filter that keeps the original language plus `eng`, **Then** only `jpn` and `eng` audio tracks remain
2. **Given** a file without plugin enrichment, **When** applying a conditional rule that checks plugin metadata, **Then** the condition evaluates to false and the policy's `else` branch executes (users explicitly handle missing data via conditional rules)

---

### User Story 3 - Conditional Rules Based on External IDs (Priority: P2)

A library curator wants to skip transcoding for certain known titles identified by their TMDB or IMDB ID, or apply different processing based on whether content is from a TV series vs movie.

**Why this priority**: Enables fine-grained control based on external catalog identifiers, useful for edge cases and exceptions.

**Independent Test**: Can be tested by creating conditional rules that check `radarr:tmdb_id` or `sonarr:series_title` and verifying correct rule evaluation.

**Acceptance Scenarios**:

1. **Given** a file enriched with `tmdb_id: 12345`, **When** a conditional rule checks `radarr:tmdb_id == 12345`, **Then** the rule's then-actions execute
2. **Given** a file enriched by Sonarr with `series_title: "Breaking Bad"`, **When** a conditional rule checks `sonarr:series_title contains "Breaking"`, **Then** the rule matches

---

### User Story 4 - Policy Validation with Plugin References (Priority: P2)

A library curator wants clear error messages when their policy references a plugin field incorrectly (typo in plugin name, invalid field name, etc.).

**Why this priority**: Good error handling prevents frustration and makes the feature discoverable.

**Independent Test**: Can be tested by loading policies with invalid plugin references and verifying appropriate error messages.

**Acceptance Scenarios**:

1. **Given** a policy referencing `radarr:nonexistent_field`, **When** loading the policy, **Then** a validation warning indicates the field is not a known plugin field
2. **Given** a policy referencing `unknown_plugin:some_field`, **When** loading the policy, **Then** a validation warning indicates the plugin is not recognized
3. **Given** a policy with valid plugin references, **When** loading the policy, **Then** no warnings are generated

---

### Edge Cases

- What happens when a plugin returns metadata after initial scan but policy was already applied? Behavior: policies operate on current data; re-scanning and re-applying policies uses new metadata.
- What happens when multiple plugins provide the same conceptual field? Each plugin's data is namespaced to its plugin name, so no conflicts are possible.
- What happens if plugin metadata contains special characters in string values? Standard string comparison rules apply; no special handling needed.
- What happens if plugin enrichment data is null/missing for a field? Null comparisons yield false for equality checks; explicit "exists" conditions can check presence.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support referencing plugin metadata in policy conditions using `plugin_name:field_name` syntax
- **FR-002**: System MUST support the following comparison operators for plugin metadata: equals, not equals, contains (for strings), exists
- **FR-003**: System MUST treat missing plugin metadata (plugin not enriched file, or field not present) as condition-not-met rather than as an error
- **FR-004**: System MUST support plugin metadata references in conditional rule conditions
- **FR-005**: System MUST provide validation warnings (not errors) for unrecognized plugin names or field names during policy loading
- **FR-006**: System MUST support plugin metadata conditions using explicit operator syntax (`operator: eq|neq|contains|exists`, `value: <expected>`) within conditional rules; missing plugin data causes conditions to evaluate to false, and users handle fallback via `else` branches
- **FR-007**: System MUST support plugin metadata references in a new schema version while maintaining backward compatibility with V11 and earlier

### Key Entities *(include if feature involves data)*

- **Plugin Metadata Reference**: A colon-separated reference like `radarr:original_language` that identifies a specific field from a specific plugin's enrichment data
- **Known Plugin Fields**: A registry of expected fields per plugin (radarr: original_language, tmdb_id, imdb_id, external_title, external_year; sonarr: same plus series_title, season_number, episode_number, episode_title, tvdb_id)
- **File Enrichment Data**: The metadata returned by plugins via `on_file_scanned`, stored in a `plugin_metadata` JSON column on the files table, keyed by plugin name (e.g., `{"radarr": {"original_language": "jpn", "tmdb_id": 12345}, "sonarr": {...}}`)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can create policies that successfully filter tracks based on plugin-provided original language without manual per-file configuration
- **SC-002**: Policy validation provides clear, actionable feedback for plugin reference errors within 1 second of policy load
- **SC-003**: Policies with plugin references process files at the same speed as equivalent policies without plugin references (no significant performance impact)
- **SC-004**: 100% of existing plugin metadata fields (from Radarr/Sonarr plugins) are accessible via the new syntax

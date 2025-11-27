# Feature Specification: Multi-Language Audio Detection

**Feature Branch**: `035-multi-language-audio-detection`
**Created**: 2025-11-26
**Status**: Draft
**Input**: User description: "Phase 5: Multi-Language Audio Detection - Detect when audio tracks contain multiple spoken languages and automatically enable forced subtitles for mixed-language content"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Detect Multi-Language Audio (Priority: P1)

As a foreign film viewer, I want to know when an audio track contains multiple languages so that I can ensure appropriate subtitles are enabled.

**Why this priority**: This is the foundational capability that all other features depend on. Without language detection, no automated subtitle configuration is possible.

**Independent Test**: Can be fully tested by analyzing a known multi-language audio file (e.g., a film with English dialogue and French scenes) and verifying the system correctly identifies each language segment with percentages.

**Acceptance Scenarios**:

1. **Given** a media file with an audio track containing primarily English (82%) with French scenes (12%) and German scenes (6%), **When** language analysis is performed, **Then** the system identifies English as the primary language and lists French and German as secondary languages with their respective percentages.

2. **Given** a media file with a single-language audio track, **When** language analysis is performed, **Then** the system classifies the track as SINGLE_LANGUAGE with the primary language at 95%+ confidence.

3. **Given** a media file with audio, **When** language analysis is performed, **Then** secondary language segments include timestamps indicating where each language appears.

4. **Given** language analysis is not configured for a library scan, **When** a scan is performed, **Then** no language analysis occurs and no additional processing time is incurred.

---

### User Story 2 - New Condition Type for Multi-Language Policies (Priority: P2)

As a policy author, I want to use multi-language detection in conditional rules so that I can create policies that respond to audio content automatically.

**Why this priority**: This bridges the detection capability (P1) with the action capability (P3). Policies need a condition type to trigger actions based on language analysis results.

**Independent Test**: Can be fully tested by creating a conditional policy with `audio_is_multi_language` conditions and verifying it evaluates correctly against files with known language characteristics.

**Acceptance Scenarios**:

1. **Given** a policy with condition `audio_is_multi_language: true`, **When** evaluated against a file classified as MULTI_LANGUAGE, **Then** the condition evaluates to true.

2. **Given** a policy with condition `audio_is_multi_language: {secondary_language_threshold: 10%}`, **When** evaluated against a file where secondary languages total 8%, **Then** the condition evaluates to false.

3. **Given** a policy with condition `audio_is_multi_language: {primary_language: eng}`, **When** evaluated against a file with German as primary language, **Then** the condition evaluates to false.

4. **Given** a policy combining `audio_is_multi_language` with other conditions using `and`/`or`/`not` operators, **When** evaluated, **Then** the boolean logic evaluates correctly.

---

### User Story 3 - Auto-Enable Forced Subtitles (Priority: P3)

As a viewer of mixed-language content, I want to have forced subtitles automatically enabled for non-English dialogue so that I can understand foreign language portions without manually selecting subtitles.

**Why this priority**: This is the end-user value delivery that depends on both detection (P1) and policy conditions (P2) being in place.

**Independent Test**: Can be fully tested by applying a policy to a multi-language file that has a forced English subtitle track and verifying the subtitle is set as default.

**Acceptance Scenarios**:

1. **Given** a multi-language file with a forced English subtitle track and a policy specifying "enable forced subs for multi-language audio", **When** the policy is applied, **Then** the forced English subtitle track is set as default.

2. **Given** a multi-language file without a matching forced subtitle track, **When** a policy attempts to enable forced subtitles, **Then** a warning is generated indicating no suitable forced subtitle was found.

3. **Given** a single-language file with forced subtitles available, **When** a multi-language-only policy is applied, **Then** no changes are made to subtitle settings.

---

### User Story 4 - Language Detection Integration with Transcription Plugin (Priority: P4)

As a VPO user with the transcription plugin installed, I want language detection to leverage existing Whisper infrastructure so that I don't need additional tools or configuration.

**Why this priority**: This is an optimization/integration story that improves user experience but isn't required for core functionality to work.

**Independent Test**: Can be fully tested by running language detection on a file that already has transcription results and verifying cached results are reused.

**Acceptance Scenarios**:

1. **Given** a file with existing transcription results from the Whisper plugin, **When** language detection is requested, **Then** the system reuses language information from the transcription rather than re-analyzing.

2. **Given** a file without transcription results, **When** language detection is requested, **Then** the system performs language-only detection (faster than full transcription).

3. **Given** language detection results exist for a file, **When** the same file is analyzed again, **Then** cached results are returned without re-processing.

---

### Edge Cases

- What happens when audio contains music or sound effects with no speech? The system should report "insufficient speech detected" rather than guessing a language.
- What happens when languages are mixed within sentences (code-switching)? The system should use the dominant language for that segment and note accuracy may be reduced.
- What happens when the audio track is very short (< 30 seconds)? The system should use the entire track rather than sampling.
- What happens when Whisper model is unavailable or fails to load? The system should report an error and skip language analysis rather than blocking other operations.
- What happens when a file has multiple audio tracks? Language analysis should be performed per-track, with results stored separately for each.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST analyze audio tracks to detect spoken language segments throughout the track.
- **FR-002**: System MUST identify the primary language as the language with the highest percentage of speech time.
- **FR-003**: System MUST identify secondary languages with their respective percentages of speech time.
- **FR-004**: System MUST provide timestamps for secondary language segments.
- **FR-005**: System MUST classify tracks as either SINGLE_LANGUAGE (95%+ primary) or MULTI_LANGUAGE.
- **FR-006**: System MUST store language analysis results with track metadata for reuse.
- **FR-007**: System MUST only run language analysis when explicitly configured (opt-in).
- **FR-008**: System MUST provide a new condition type `audio_is_multi_language` for conditional policies.
- **FR-009**: System MUST support configurable threshold for secondary language percentage in conditions.
- **FR-010**: System MUST support specifying expected primary language in conditions.
- **FR-011**: System MUST integrate `audio_is_multi_language` with existing boolean operators (and, or, not).
- **FR-012**: System MUST support policy actions to set forced subtitle flags based on language conditions.
- **FR-013**: System MUST support policy actions to set default subtitle track based on language conditions.
- **FR-014**: System MUST warn users when a policy requires a forced subtitle that doesn't exist.
- **FR-015**: System MUST use sampling strategy rather than analyzing entire audio tracks (for performance).
- **FR-016**: System MUST cache language analysis results per file hash to avoid re-analysis.
- **FR-017**: System MUST reuse transcription results when available from the transcription plugin.

### Key Entities

- **LanguageSegment**: Represents a detected language within an audio track. Contains language code (ISO 639-2), start timestamp, end timestamp, and confidence score.
- **LanguageAnalysisResult**: Aggregated result for an entire track. Contains primary language, primary percentage, list of secondary languages with percentages, classification (SINGLE_LANGUAGE/MULTI_LANGUAGE), and analysis metadata.
- **MultiLanguageCondition**: Policy condition configuration. Contains optional primary_language, optional secondary_language_threshold, and boolean shorthand support.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Language detection correctly identifies the primary language with 95%+ accuracy for clear speech content.
- **SC-002**: Multi-language classification correctly identifies files with 5%+ secondary language content.
- **SC-003**: Language analysis completes within 60 seconds for a 2-hour film using sampling strategy.
- **SC-004**: Cached results return in under 1 second for previously analyzed files.
- **SC-005**: Conditional policies using `audio_is_multi_language` evaluate correctly for 100% of test cases.
- **SC-006**: Users can configure and apply forced subtitle policies without manual intervention per file.

## Dependencies

- **Sprint 2 (Conditional Logic)**: The `audio_is_multi_language` condition type must integrate with the existing conditional policy evaluation system.
- **VPO Transcription Plugin**: Language detection reuses Whisper infrastructure. The plugin must be installed for language analysis to function.

## Assumptions

- Whisper's language detection capability (~95% accuracy) is acceptable for this use case.
- Sampling at intervals (rather than full audio analysis) provides sufficient accuracy for language detection.
- Users understand that music/effects segments may produce unreliable language detection.
- The transcription plugin uses OpenAI Whisper or compatible models for speech recognition.
- Files with multiple audio tracks will have language analysis performed independently per track.

## Out of Scope

- Per-segment subtitle selection (showing subtitles only for specific language portions).
- Automatic forced subtitle generation from full subtitles.
- Integration with external subtitle extraction tools.
- Multi-language track splitting (creating separate audio tracks per language).
- Real-time language detection during playback.

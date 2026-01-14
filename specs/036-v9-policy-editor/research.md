# Research: V9 Policy Editor GUI

**Phase 0 Output** | **Date**: 2025-11-30

## Research Questions

### 1. Existing Policy Editor Architecture

**Question**: How does the current policy editor work and what needs to be extended?

**Findings**:

The current policy editor (`src/vpo/policy/editor.py`) uses:
- **PolicyRoundTripEditor class**: Loads YAML with ruamel.yaml to preserve comments and unknown fields
- **get_field/set_field methods**: Nested path access like "default_flags.set_first_video_default"
- **API endpoints**: GET/PUT `/api/policies/{name}` for load/save, POST `/api/policies/{name}/validate` for dry-run

Current supported fields (V1-V2 only in GUI):
- `schema_version` (read-only display)
- `track_order` (list input)
- `audio_language_preference`, `subtitle_language_preference` (list input)
- `commentary_patterns` (list input)
- `default_flags.*` (checkbox inputs)
- `transcode.*` (legacy V1-5 flat format)
- `transcription.*` (checkbox/input fields)

**Decision**: Extend PolicyRoundTripEditor with methods for V3-V10 fields. Add new JavaScript section modules for each feature area.

### 2. V3-V10 Schema Field Structure

**Question**: What is the complete structure of fields to support?

**Findings** (from `policy/loader.py` and `policy/models.py`):

**V3 Fields**:
```yaml
audio_filter:
  languages: ["eng", "jpn"]
  fallback: {mode: "keep_all"}
  minimum: 1
  # V10: keep_music_tracks, keep_sfx_tracks, keep_non_speech_tracks, exclude_*_from_language_filter

subtitle_filter:
  languages: ["eng"]
  preserve_forced: true
  remove_all: false

attachment_filter:
  remove_all: false

container:
  target: "mkv"  # or "mp4"
  on_incompatible_codec: "error"  # "skip", "transcode"
```

**V4 Fields**:
```yaml
conditional:
  - name: "Skip anime transcoding"
    when:
      exists:
        track_type: audio
        language: jpn
    then:
      skip_video_transcode: true
      warn: "Skipping Japanese audio content"
```

**V5 Fields**:
```yaml
audio_synthesis:
  tracks:
    - name: "compatibility_stereo"
      codec: aac
      channels: stereo
      source:
        prefer:
          - language: eng
          - channels: max
      bitrate: "192k"
      skip_if_exists:  # V8+
        codec: [aac, eac3]
        channels: 2
```

**V6 Fields**:
```yaml
transcode:
  video:
    target_codec: hevc
    skip_if:
      codec_matches: [hevc, h265]
      resolution_within: "1080p"
      bitrate_under: "15M"
    quality:
      mode: crf  # crf, bitrate, constrained_quality
      crf: 20
      preset: medium
      tune: film
    scaling:
      max_resolution: "1080p"
      algorithm: lanczos
    hardware_acceleration:
      enabled: auto
      fallback_to_cpu: true
  audio:
    preserve_codecs: [truehd, dts-hd, flac]
    transcode_to: aac
    transcode_bitrate: "192k"
```

**V7 Fields**:
- `audio_is_multi_language` condition type in conditional rules
- `set_forced`, `set_default` action types

**V8 Fields**:
- `not_commentary` filter in conditions and synthesis source preferences
- `skip_if_exists` in synthesis tracks

**V9 Fields**:
```yaml
workflow:
  phases: [analyze, apply, transcode]
  auto_process: false
  on_error: continue  # skip, continue, fail
```

**V10 Fields**:
- Extended audio_filter with music/sfx/non_speech track handling options

**Decision**: Support all fields with appropriate UI controls. Group into 6 collapsible accordion sections.

### 3. Accordion Component Pattern

**Question**: How should the accordion UI component be implemented?

**Findings**:

Best practices for vanilla JS accordion:
1. Use `<details>` and `<summary>` HTML elements for semantic markup
2. Add keyboard navigation (Enter/Space to toggle, Tab to navigate)
3. Use `aria-expanded` for accessibility
4. CSS transitions for smooth open/close animation

**Decision**: Create `accordion.js` module with:
- `initAccordion(containerSelector)` - Initialize all accordions in container
- Use `<details class="accordion-section">` elements
- CSS in `policy-editor.css` for styling and animation

### 4. Condition Builder UI Pattern

**Question**: How should the conditional rules condition builder work with 2-level nesting?

**Findings**:

The clarification specified max 2 levels of nesting (e.g., `and` containing `exists/count` conditions).

UI Pattern:
1. Top level: Radio buttons for condition type (exists, count, and, or, not, audio_is_multi_language)
2. For `and`/`or`: Show sub-condition list with add/remove buttons
3. For `exists`/`count`: Show track_type dropdown + filter fields
4. Prevent nesting beyond 2 levels (disable boolean operators in sub-conditions)

**Decision**: Implement condition builder as a recursive component with depth tracking. At depth=2, only allow leaf conditions (exists, count, audio_is_multi_language).

### 5. Validation Strategy

**Question**: How should validation work between client and server?

**Findings**:

Current approach:
1. Client-side: Basic required field checks, format validation (regex for bitrate, language codes)
2. Server-side: Full Pydantic model validation via `PolicyModel.model_validate()`
3. API returns structured validation errors with field paths

**Decision**:
- Keep dual validation approach
- Client validates immediately on blur (< 500ms feedback requirement)
- Server validates on save and validate actions
- Display field-level errors next to inputs
- Use toast/alert for server-side errors not tied to specific fields

### 6. YAML Preview Strategy

**Question**: How should the real-time YAML preview work?

**Findings**:

Current implementation:
1. PolicyRoundTripEditor maintains internal ruamel.yaml document
2. `to_yaml()` method dumps current state
3. Preview updates triggered on form change events

Challenges for new fields:
- Complex nested structures (conditional rules, synthesis tracks)
- List items with multiple fields
- Comments should be preserved

**Decision**:
- Debounce preview updates (300ms) to avoid performance issues
- Use `requestAnimationFrame` for smooth updates
- Show loading indicator during validation API calls
- Preserve existing comments by only updating changed fields

## Alternatives Considered

### 1. Full YAML Editor Instead of Form

**Rejected because**: Users requested visual form-based editing to avoid YAML syntax errors. Form provides validation and guidance.

### 2. React/Vue Framework

**Rejected because**: Project constraint is vanilla JavaScript. Adding a framework would increase complexity and bundle size.

### 3. Unlimited Condition Nesting

**Rejected because**: Clarification specified 2-level max to keep UI manageable. Deep nesting rarely needed.

### 4. Separate Page Per Section

**Rejected because**: Accordion pattern keeps all sections accessible on single page while reducing visual clutter.

## Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Extend existing PolicyRoundTripEditor | Maintains backward compatibility, leverages ruamel.yaml for comment preservation |
| One JS module per section | Separates concerns, easier testing and maintenance |
| HTML5 `<details>` for accordion | Semantic, accessible, works without JavaScript |
| 2-level condition nesting max | Covers 95%+ use cases, manageable UI complexity |
| Debounced YAML preview (300ms) | Balances responsiveness with performance |
| Server-side validation as authority | Pydantic models already exist and handle all edge cases |

## Dependencies

No new external dependencies required. Using:
- ruamel.yaml (existing) - YAML round-trip editing
- pydantic (existing) - Server-side validation
- aiohttp (existing) - API handlers
- Jinja2 (existing) - Template rendering

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Complex conditional UI hard to use | Start with simple conditions, add advanced features progressively |
| Performance with large policies | Debounce updates, only re-render changed sections |
| Breaking existing editor functionality | Comprehensive tests, backward-compatible API |
| Validation errors not clear | Field-level error messages, examples in placeholder text |

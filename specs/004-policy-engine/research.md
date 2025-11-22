# Research: Policy Engine & Reordering

**Feature**: 004-policy-engine
**Date**: 2025-11-22

## MKV Track Operations (mkvtoolnix)

### Decision
Use **mkvmerge for track reordering** (requires remux to new file) and **mkvpropedit for metadata-only changes** (in-place, instant).

### Rationale
- mkvpropedit cannot truly reorder tracks - it only changes track IDs in the header but does NOT change physical `StreamOrder`. Players still see tracks in original order.
- mkvmerge with `--track-order` performs a lossless remux (no re-encoding), creating a new file with tracks in specified physical order. This is fast (minutes, not hours).
- mkvpropedit is ideal for metadata changes (flags, titles, language) - instant, in-place, no temporary files.

### Command Patterns

**Track reordering (mkvmerge):**
```bash
# Reorder: video first (0:0), then swap audio tracks (0:2 before 0:1)
mkvmerge --output "output.mkv" "input.mkv" --track-order 0:0,0:2,0:1

# Combined with metadata
mkvmerge --output "output.mkv" "input.mkv" \
  --track-order 0:0,0:2,0:1 \
  --default-track-flag 0:1 \
  --default-track-flag 1:0
```

**Metadata changes (mkvpropedit):**
```bash
# Set default flags
mkvpropedit "movie.mkv" \
  --edit track:a1 --set flag-default=1 \
  --edit track:a2 --set flag-default=0

# Set track title
mkvpropedit "movie.mkv" --edit track:a1 --set name="English 5.1 Surround"

# Track selectors: track:a1 (first audio), track:s1 (first subtitle), track:v1 (first video)
```

### Key Properties
| Property | Type | Description |
|----------|------|-------------|
| `flag-default` | 0/1 | Default track for playback |
| `flag-forced` | 0/1 | Force display (foreign dialogue) |
| `name` | string | Track title |
| `language` | string | ISO 639-2 language code |

---

## Non-MKV Metadata Operations (ffmpeg)

### Decision
Use **ffmpeg with `-c copy`** for all non-MKV metadata modifications, always outputting to a new file followed by atomic rename. No true in-place editing possible.

### Rationale
- ffmpeg cannot modify metadata in-place on any container format
- Stream copy (`-c copy`) is fast and lossless regardless of file size
- MP4 has reasonable but imperfect track-level metadata support
- AVI has severe limitations for per-stream metadata

### Command Patterns

**Set track metadata:**
```bash
ffmpeg -i input.mp4 -map 0 -c copy \
  -metadata:s:a:0 title="English 5.1" \
  -metadata:s:a:0 language=eng \
  -metadata:s:a:1 title="Director Commentary" \
  -metadata:s:a:1 language=eng \
  output.mp4
```

**Set disposition flags:**
```bash
ffmpeg -i input.mp4 -map 0 -c copy \
  -disposition:a:0 default \
  -disposition:a:1 none \
  output.mp4
```

**Atomic replace pattern:**
```bash
ffmpeg -i input.mp4 -c copy [options] output.tmp.mp4 && mv output.tmp.mp4 input.mp4
```

### Limitations
| Feature | MP4 | AVI |
|---------|-----|-----|
| Track title | Partial (some players read `handler` instead) | No |
| Track language | Yes (ISO 639-2) | No |
| Default disposition | Yes | No |
| Forced disposition | Buggy | No |
| In-place editing | No | No |

### Alternatives Considered
- **AtomicParsley**: MP4-only, limited to iTunes-style metadata
- **exiftool**: General-purpose but slow for video files
- **Direct atom editing**: Too complex, risk of corruption

---

## Policy Schema Validation

### Decision
Use **Pydantic v2** with native Python dataclasses for policy schema validation, combined with PyYAML for parsing.

### Rationale
1. Type-safe and Pythonic - integrates with existing dataclass-based models
2. Built-in validation with automatic type coercion
3. Generates JSON Schema for documentation
4. Structured error objects can be transformed to user-friendly messages
5. No extra schema files to maintain (schema lives in Python code)

### Schema Structure
```yaml
# ~/.vpo/policies/default.yaml
schema_version: 1

track_order:
  - video
  - audio_main
  - audio_alternate
  - subtitle_main
  - audio_commentary
  - subtitle_commentary

audio_language_preference:
  - eng
  - und
  - jpn

subtitle_language_preference:
  - eng
  - und

# Regex patterns - use single quotes to preserve escapes
commentary_patterns:
  - 'commentary'
  - 'director'
  - '\bcast\b'

default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
```

### Versioning Strategy
- Include `schema_version` field in every policy file
- Use `model_validator(mode="before")` to migrate old schemas
- Set max version constraint to reject future versions with clear error
- Migration functions are pure transformations: `_migrate_v1_to_v2(data) -> data`

### Regex Handling
- Use single quotes in YAML for regex patterns (prevents escape interpretation)
- Validate patterns during model validation with `re.compile()`
- Compile patterns once in `model_post_init` for performance
- Use `re.IGNORECASE` by default for user convenience

### Error Messages
- Transform Pydantic's structured errors into user-friendly messages
- Include field location (dot-separated path)
- Example: `"commentary_patterns[2]: Invalid regex 'foo[' - unterminated character set"`
- Use `extra="forbid"` to catch field name typos

### Alternatives Considered
- **jsonschema**: Requires separate schema files, less Pythonic
- **cerberus**: Less active maintenance, fewer features
- **marshmallow**: More verbose, better for serialization than validation
- **dataclasses + manual validation**: Error-prone, repetitive

---

## Implementation Recommendations

### MKV Operations
1. **Metadata-only changes**: Use mkvpropedit (instant, in-place)
2. **Track reordering**: Use mkvmerge with `--track-order` (requires temp file + atomic rename)
3. **Combined operations**: If reordering needed, use mkvmerge with all options at once

### Non-MKV Operations
1. Always use ffmpeg `-c copy` with atomic file replacement
2. Validate metadata was written using ffprobe before replacing original
3. Warn users about MP4 track title and forced flag limitations
4. Recommend MKV conversion for AVI files requiring track-level metadata

### Policy Loading
1. Parse YAML with PyYAML `safe_load`
2. Validate with Pydantic model
3. Compile regex patterns on first load
4. Cache compiled policy for reuse

### Backup Strategy
1. Copy original to `{path}.vpo-backup` before any modification
2. Perform operation to temp file (for mkvmerge/ffmpeg) or in-place (mkvpropedit)
3. Atomic rename temp to original if needed
4. Delete or keep backup based on user profile setting
5. On failure, restore from backup

---

## Dependencies

### Required
- **PyYAML**: Policy file parsing (add to pyproject.toml)
- **pydantic**: Schema validation (add to pyproject.toml)

### External Tools
- **mkvpropedit/mkvmerge**: MKV operations (mkvtoolnix package)
- **ffmpeg**: Non-MKV operations

### Detection
```python
def check_tool_availability() -> dict[str, bool]:
    """Check which external tools are available."""
    return {
        "mkvpropedit": shutil.which("mkvpropedit") is not None,
        "mkvmerge": shutil.which("mkvmerge") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
    }
```

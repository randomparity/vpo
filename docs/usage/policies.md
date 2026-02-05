# Policy Configuration Guide

**Purpose:**
This document describes how to create and configure VPO policy files for organizing and transforming video libraries.

---

## Overview

VPO policies are YAML files that define rules for:
- Track ordering preferences (audio, subtitle priority)
- Default track selection and flags
- Track filtering (remove unwanted audio, subtitles, attachments)
- Container format conversion (MKV, MP4)
- Container metadata reading and writing
- Transcoding settings

---

## Policy Schema Version

VPO uses the **V12 schema** with phased policy format. All policies must use this format with `phases` and optional `config` sections.

**Note:** Older flat policy formats are no longer supported. All policies must use the phased format shown below.

---

## Basic Policy Structure

```yaml
# Required: schema version and phases
schema_version: 12

# Optional global configuration
config:
  on_error: skip  # skip, continue, or fail

# Required: at least one phase
phases:
  - name: organize
    # Track ordering (optional, has defaults)
    track_order:
      - video
      - audio_main
      - audio_alternate
      - subtitle_main
      - subtitle_forced
      - audio_commentary
      - subtitle_commentary
      - attachment

    # Language preferences for track ordering
    audio_filter:
      languages: [eng, und]

    subtitle_filter:
      languages: [eng, und]

    # Default flag behavior
    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true
      set_preferred_subtitle_default: false
      clear_other_defaults: true
```

---

## Track Filtering

Track filtering removes unwanted tracks. Track filtering is applied before track ordering within each phase.

### Audio Filtering

Remove audio tracks that don't match preferred languages:

```yaml
schema_version: 12
phases:
  - name: filter
    audio_filter:
      # Languages to keep (ISO 639-2/B codes)
      languages:
        - eng    # English
        - und    # Undefined/unknown
        - jpn    # Japanese

      # Minimum tracks that must remain (default: 1)
      minimum: 1

      # Fallback when no preferred languages found
      fallback:
        mode: content_language  # See fallback modes below
```

**Fallback Modes:**

| Mode | Behavior |
|------|----------|
| `content_language` | Keep tracks matching the content's original language |
| `keep_all` | Keep all tracks (disable filtering for this file) |
| `keep_first` | Keep first N tracks to meet minimum |
| `error` | Fail with error (requires manual intervention) |

### Subtitle Filtering

Remove subtitle tracks with options to preserve forced subtitles:

```yaml
schema_version: 12
phases:
  - name: filter
    subtitle_filter:
      # Languages to keep (omit for no language filtering)
      languages:
        - eng

      # Keep forced subtitles regardless of language (default: false)
      preserve_forced: true

      # Remove ALL subtitles (overrides other settings)
      # remove_all: true
```

### Attachment Filtering

Remove attachment tracks (fonts, cover art):

```yaml
schema_version: 12
phases:
  - name: filter
    attachment_filter:
      # Remove all attachments (fonts, images, etc.)
      remove_all: true
```

**Warning:** Removing fonts may affect rendering of styled subtitles (ASS/SSA format). VPO will display a warning when removing fonts from files with styled subtitles.

---

## Container Conversion

Convert between container formats (lossless remuxing):

```yaml
schema_version: 12
phases:
  - name: convert
    container:
      # Target format: mkv or mp4
      target: mkv

      # Behavior for incompatible codecs (default: error)
      on_incompatible_codec: error
```

**Incompatible Codec Modes:**

| Mode | Behavior |
|------|----------|
| `error` | Fail with error listing incompatible tracks |
| `skip` | Skip the file with a warning |
| `transcode` | Transcode incompatible tracks (future feature) |

### Codec Compatibility

MKV supports virtually all codecs. MP4 has limitations:

| Codec Type | MKV | MP4 |
|------------|-----|-----|
| H.264, H.265, VP9, AV1 | Yes | Yes |
| AAC, AC3, EAC3, MP3, Opus | Yes | Yes |
| TrueHD, DTS-HD MA | Yes | No |
| FLAC | Yes | Limited |
| PGS, VobSub subtitles | Yes | No |
| SRT, ASS subtitles | Yes | No |
| Attachments (fonts) | Yes | No |

---

## Container Metadata

Policies can read and write container-level metadata tags (title, encoder, creation_time, etc.) using conditional rules. Use `container_metadata` conditions to check tag values and `set_container_metadata` actions to set or clear them.

```yaml
schema_version: 12
phases:
  - name: metadata
    conditional:
      # Clear the encoder tag
      - name: clear-encoder
        when:
          container_metadata:
            field: encoder
            operator: exists
        then:
          - set_container_metadata:
              field: encoder
              value: ""

      # Set title from Radarr plugin metadata
      - name: set-title
        when:
          plugin_metadata:
            plugin: radarr
            field: external_title
            operator: exists
        then:
          - set_container_metadata:
              field: title
              from_plugin_metadata:
                plugin: radarr
                field: external_title
```

Supported operators for conditions: `eq`, `neq`, `contains`, `exists`, `lt`, `lte`, `gt`, `gte`. MKV files use mkvpropedit; other formats use ffmpeg.

For the full reference — including operator details, field validation rules, and working examples — see [Container Metadata Guide](container-metadata.md).

---

## Complete Policy Example

```yaml
# Full-featured policy for organizing a video library
schema_version: 12

# Global configuration
config:
  on_error: skip

phases:
  # First phase: filter unwanted tracks
  - name: filter
    audio_filter:
      languages: [eng, und]
      minimum: 1
      fallback:
        mode: content_language

    subtitle_filter:
      languages: [eng]
      preserve_forced: true

    attachment_filter:
      remove_all: true

  # Second phase: organize remaining tracks
  - name: organize
    track_order:
      - video
      - audio_main
      - audio_alternate
      - subtitle_main
      - subtitle_forced
      - audio_commentary
      - subtitle_commentary
      - attachment

    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true
      set_preferred_subtitle_default: false
      clear_other_defaults: true

    # Commentary track detection
    commentary_patterns:
      - 'commentary'
      - 'director'

  # Third phase: convert container
  - name: convert
    container:
      target: mkv
      on_incompatible_codec: error

  # Fourth phase: clean up container metadata
  - name: metadata
    depends_on: [convert]
    conditional:
      - name: clear-encoder
        when:
          container_metadata:
            field: encoder
            operator: exists
        then:
          - set_container_metadata:
              field: encoder
              value: ""
```

---

## Applying Policies

### Dry Run (Preview Changes)

Always preview changes before applying:

```bash
vpo process --policy my-policy.yaml --dry-run /path/to/file.mkv
```

The dry-run output shows:
- Track dispositions (KEEP/REMOVE with reasons)
- Container changes (if applicable)
- Summary of changes

### Apply Policy

Apply the policy to a file:

```bash
vpo process --policy my-policy.yaml /path/to/file.mkv
```

Apply to multiple files:

```bash
vpo process --policy my-policy.yaml /path/to/files/*.mkv
```

### JSON Output

Get machine-readable output:

```bash
vpo process --policy my-policy.yaml --dry-run --json /path/to/file.mkv
```

---

## Language Codes

VPO uses ISO 639-2/B language codes. Common codes:

| Code | Language |
|------|----------|
| `eng` | English |
| `spa` | Spanish |
| `fra` | French |
| `ger` / `deu` | German |
| `jpn` | Japanese |
| `chi` / `zho` | Chinese |
| `kor` | Korean |
| `und` | Undefined/Unknown |

The `und` code is useful for files with missing language tags.

---

## Best Practices

1. **Always use dry-run first** - Preview changes before applying
2. **Keep minimum: 1 for audio** - Prevents creating audio-less files
3. **Include 'und' in languages** - Catches tracks with missing tags
4. **Use fallback modes** - Handle edge cases gracefully
5. **Test with sample files** - Validate policies before library-wide application

---

## Error Handling

### InsufficientTracksError

Raised when filtering would remove all audio tracks:

```
Error: Filtering audio tracks would leave 0 tracks, but minimum 1 required.
Policy languages: ('eng',), File has: ('jpn', 'fra')
```

**Solutions:**
- Add missing languages to the filter
- Use `fallback.mode: keep_all` or `content_language`

### IncompatibleCodecError

Raised when converting to MP4 with incompatible codecs:

```
Error: Cannot convert to mp4: incompatible tracks: #3 (audio: truehd)
```

**Solutions:**
- Use `on_incompatible_codec: skip` to skip problematic files
- Target MKV instead (supports all codecs)

---

## Related docs

- [CLI Usage](cli-usage.md)
- [Conditional Policies](conditional-policies.md) - If/then/else rules for smart decisions
- [Container Metadata](container-metadata.md) - Reading, writing, and clearing container tags
- [Transcode Policy](transcode-policy.md)
- [External Tools](external-tools.md)
- [Policy Editor](policy-editor.md)
- [ADR-0002: Policy Schema Versioning](../decisions/ADR-0002-policy-schema-versioning.md)
- [ADR-0004: Conditional Policy Schema](../decisions/ADR-0004-conditional-policy-schema.md)

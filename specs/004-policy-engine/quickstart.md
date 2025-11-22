# Quickstart: Policy Engine

Get started with VPO's policy engine to organize your media library tracks.

## Prerequisites

1. **VPO installed** with media introspection (features 002 + 003)
2. **External tools**:
   - `mkvtoolnix` (for MKV files): `apt install mkvtoolnix` or `brew install mkvtoolnix`
   - `ffmpeg` (for non-MKV files): `apt install ffmpeg` or `brew install ffmpeg`

## Step 1: Create a Policy File

Create `~/.vpo/policies/default.yaml`:

```yaml
schema_version: 1

# Track type ordering (first = top priority)
track_order:
  - video
  - audio_main
  - audio_alternate
  - subtitle_main
  - subtitle_forced
  - audio_commentary
  - subtitle_commentary
  - attachment

# Preferred audio languages (first match = default)
audio_language_preference:
  - eng
  - und

# Preferred subtitle languages
subtitle_language_preference:
  - eng
  - und

# Patterns to identify commentary tracks
commentary_patterns:
  - 'commentary'
  - 'director'

# Default flag behavior
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
```

## Step 2: Preview Changes (Dry-Run)

Always preview before applying:

```bash
vpo apply --policy ~/.vpo/policies/default.yaml --dry-run movie.mkv
```

Output:
```
Policy: /home/user/.vpo/policies/default.yaml (v1)
Target: /media/movies/movie.mkv

Proposed changes:
  Track 1 (audio, eng): Set as default
  Track 2 (audio, jpn): Clear default flag
  Reorder: [0, 2, 1, 3] → [0, 1, 2, 3]

Summary: 3 changes (requires remux)

To apply these changes, run without --dry-run
```

## Step 3: Apply Changes

When satisfied with the preview:

```bash
vpo apply --policy ~/.vpo/policies/default.yaml movie.mkv
```

Output:
```
Policy: /home/user/.vpo/policies/default.yaml (v1)
Target: /media/movies/movie.mkv

Applied 3 changes in 2.1s
Backup: /media/movies/movie.mkv.vpo-backup (kept)
```

## Common Policy Examples

### Anime Library (Japanese audio default)

```yaml
schema_version: 1

audio_language_preference:
  - jpn
  - eng
  - und

subtitle_language_preference:
  - eng
  - und

default_flags:
  set_preferred_subtitle_default: true
```

### No Commentary Tracks First

```yaml
schema_version: 1

track_order:
  - video
  - audio_main
  - subtitle_main
  - subtitle_forced
  - audio_alternate
  - audio_commentary
  - subtitle_commentary
  - attachment

commentary_patterns:
  - 'commentary'
  - 'director'
  - 'cast'
  - 'behind the scenes'
```

### Multi-Language (English, German, French)

```yaml
schema_version: 1

audio_language_preference:
  - eng
  - deu
  - fra
  - und

subtitle_language_preference:
  - eng
  - deu
  - fra
  - und
```

## CLI Reference

```bash
# Preview changes
vpo apply -p policy.yaml --dry-run file.mkv

# Apply changes
vpo apply -p policy.yaml file.mkv

# Apply and keep backup
vpo apply -p policy.yaml --keep-backup file.mkv

# Apply and delete backup on success
vpo apply -p policy.yaml --no-keep-backup file.mkv

# JSON output for scripting
vpo apply -p policy.yaml --dry-run --json file.mkv
```

## Troubleshooting

### "Required tool not available"

Install the required external tools:

```bash
# Debian/Ubuntu
sudo apt install mkvtoolnix ffmpeg

# macOS
brew install mkvtoolnix ffmpeg

# Verify installation
mkvpropedit --version
mkvmerge --version
ffmpeg -version
```

### "Policy validation failed"

Check your policy file for:
- Valid YAML syntax
- Correct field names (no typos)
- Valid language codes (ISO 639-2: `eng`, `jpn`, `deu`, not `english`)
- Valid regex patterns (use single quotes for patterns with backslashes)

### "Unsupported container format"

- MKV: Full support (reorder + metadata)
- MP4: Metadata only (flags, titles)
- AVI: Limited support

For best results, consider remuxing to MKV first:
```bash
mkvmerge -o output.mkv input.avi
```

### "Cannot write to file"

Check file permissions:
```bash
ls -la movie.mkv
# Ensure write permission
chmod u+w movie.mkv
```

## Next Steps

- Read the full [CLI Contract](contracts/cli-apply.md)
- Review the [Policy Schema](contracts/policy-schema.yaml)
- Understand the [Data Model](data-model.md)
- Check [Research Notes](research.md) for technical details

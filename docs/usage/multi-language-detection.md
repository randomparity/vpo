# Multi-Language Audio Detection

This guide explains how to use VPO's multi-language audio detection feature to identify and handle media files with mixed-language audio content.

## Overview

Multi-language detection analyzes audio tracks to identify when multiple languages are present in the same track. This is common in:

- Films with foreign dialogue segments (e.g., English movie with French dialogue)
- International productions with code-switching
- Dubbed content where original dialogue bleeds through

When multi-language content is detected, VPO can automatically enable forced subtitles for the non-primary language segments.

## Prerequisites

Multi-language detection requires:

1. **Whisper plugin installed**: The analysis uses OpenAI's Whisper model for speech recognition
2. **Audio tracks scanned**: Files must be in the VPO database

Install the Whisper plugin:

```bash
pip install openai-whisper
```

## Basic Usage

### Analyze a Single File

Use the `inspect` command with `--analyze-languages`:

```bash
vpo inspect --analyze-languages /path/to/movie.mkv
```

For detailed segment information:

```bash
vpo inspect --analyze-languages --show-segments /path/to/movie.mkv
```

### Analyze During Scan

Analyze all files during a library scan:

```bash
vpo scan --analyze-languages /media/videos
```

### Dedicated Analysis Command

Use the `analyze` command group for more control:

```bash
# Run language analysis on a file (requires Whisper plugin)
vpo analyze language /path/to/movie.mkv

# Run analysis on a directory
vpo analyze language /media/movies/ --recursive

# Force re-analysis (ignore cache)
vpo analyze language /path/to/movie.mkv --force

# Output results as JSON
vpo analyze language /path/to/movie.mkv --json
```

#### View Analysis Status

```bash
# Show library-wide summary
vpo analyze status

# Filter by classification
vpo analyze status --filter multi-language
vpo analyze status --filter single-language
vpo analyze status --filter pending

# Show details for a specific file
vpo analyze status /path/to/movie.mkv

# Output as JSON
vpo analyze status --json
```

#### Clear Cached Results

```bash
# Preview what would be cleared (dry run)
vpo analyze clear /media/movies/ --dry-run

# Clear results for a directory
vpo analyze clear /media/movies/ --yes

# Clear all results in library
vpo analyze clear --all --yes

# Clear with JSON output
vpo analyze clear --all --yes --json
```

#### Classify Audio Tracks

```bash
# Classify audio tracks (commentary detection, etc.)
vpo analyze classify /path/to/movie.mkv

# Classify all files in a directory
vpo analyze classify /media/movies/ --recursive
```

## Policy Integration

### The `audio_is_multi_language` Condition

Use the `audio_is_multi_language` condition in V12 phased policies:

```yaml
schema_version: 12
phases:
  - name: analyze
    conditional:
      - name: "Handle multi-language audio"
        when:
          audio_is_multi_language:
            primary_language: eng
            threshold: 0.05
        then:
          - warn: "Multi-language content detected"
```

#### Condition Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `primary_language` | string | (any) | Expected primary language (ISO 639-2) |
| `threshold` | float | 0.05 | Minimum secondary language percentage |
| `track_index` | int | (all) | Specific track to check |

### Automatic Forced Subtitle Enablement

Enable forced subtitles automatically for multi-language content:

```yaml
schema_version: 12
phases:
  - name: analyze
    conditional:
      - name: "Enable forced subs for multi-language"
        when:
          and:
            - audio_is_multi_language:
                primary_language: eng
                threshold: 0.05
            - exists:
                track_type: subtitle
                language: eng
                is_forced: true
        then:
          - set_default:
              track_type: subtitle
              language: eng
          - warn: "Enabled forced subtitles for multi-language content"
```

### Actions: `set_forced` and `set_default`

VPO provides actions for track flag manipulation within conditional rules:

#### `set_forced`

Sets the forced flag on subtitle tracks:

```yaml
# Within a phase's conditional rules
then:
  - set_forced:
      track_type: subtitle
      language: eng
      value: true  # or false to clear
```

#### `set_default`

Sets the default flag on any track type:

```yaml
# Within a phase's conditional rules
then:
  - set_default:
      track_type: subtitle
      language: eng
      value: true
```

## Auto-Analyze with Apply

Automatically run language analysis before applying a policy:

```bash
vpo process --policy multi-language.yaml --auto-analyze /path/to/movie.mkv
```

This ensures language analysis results are available for `audio_is_multi_language` conditions.

## How Detection Works

### Sampling Strategy

VPO uses a sampling-based approach for efficient analysis:

1. **Sample positions**: Audio is sampled at regular intervals (default: every 10 minutes)
2. **Sample duration**: Each sample is 5 seconds long
3. **Language detection**: Whisper detects the language of each sample
4. **Aggregation**: Results are aggregated to determine percentages

For a 2-hour film, this means approximately 12 samples, taking about 24 seconds to analyze.

### Classification

Tracks are classified based on language distribution:

| Classification | Criteria |
|---------------|----------|
| `SINGLE_LANGUAGE` | Primary language >= 95% |
| `MULTI_LANGUAGE` | Primary language < 95% |

### Caching

Analysis results are cached in the database to avoid re-processing:

- Cache key: `(track_id, file_hash)`
- Results persist until file content changes
- Force re-analysis with `--force` flag

## Example Output

### Human-Readable Format

```
File: /media/movies/babel.mkv
Audio Track 1 (English):
  Classification: MULTI_LANGUAGE
  Primary: eng (82%)
  Secondary: spa (12%), jpn (6%)
  Segments:
    0:00:00 - 0:45:00: eng (98% confidence)
    0:45:00 - 0:52:00: spa (95% confidence)
    0:52:00 - 1:30:00: eng (97% confidence)
    1:30:00 - 1:38:00: jpn (92% confidence)
    1:38:00 - 2:15:00: eng (96% confidence)
```

### JSON Format

```bash
vpo inspect --analyze-languages --json /path/to/movie.mkv
```

```json
{
  "language_analysis": {
    "track_id": 1,
    "classification": "MULTI_LANGUAGE",
    "primary_language": "eng",
    "primary_percentage": 0.82,
    "secondary_languages": [
      {"language": "spa", "percentage": 0.12},
      {"language": "jpn", "percentage": 0.06}
    ]
  }
}
```

## Common Issues

### "Language analysis not available"

**Cause**: Analysis hasn't been run on the file.

**Solution**: Run `vpo scan --analyze-languages` or use `--auto-analyze` with apply.

### "Plugin does not support multi_language_detection"

**Cause**: Whisper plugin not installed or outdated.

**Solution**: Install `openai-whisper` package.

### Analysis takes too long

**Cause**: Using large Whisper model.

**Solution**: Configure the plugin to use a smaller model (e.g., "tiny" or "base").

### "Insufficient speech detected"

**Cause**: Audio track contains mostly music or sound effects.

**Solution**: This is expected behavior - no language detection is possible without speech.

## Related docs

- [Conditional Policies](conditional-policies.md) - Using conditions and actions
- [Policy Editor](policy-editor.md) - Visual policy editing
- [CLI Usage](cli-usage.md) - Command-line reference

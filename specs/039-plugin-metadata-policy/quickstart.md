# Quickstart: Plugin Metadata Access in Policies

**Feature**: 039-plugin-metadata-policy

## Overview

This feature enables policy conditions to reference metadata provided by plugins (like Radarr or Sonarr). This allows policies to make decisions based on external data such as original language, TMDB IDs, or series information.

## Prerequisites

- VPO with database schema v17+
- At least one metadata plugin configured (e.g., radarr-metadata, sonarr-metadata)
- Files scanned with plugin enrichment enabled

## Basic Usage

### Check Original Language

```yaml
schema_version: 12

conditional:
  - name: japanese-content
    when:
      plugin_metadata:
        plugin_metadata: "radarr:original_language"
        operator: eq
        value: "jpn"
    then:
      - warn: "Japanese content detected"
```

### Check if Plugin Data Exists

```yaml
conditional:
  - name: has-radarr-data
    when:
      plugin_metadata:
        plugin_metadata: "radarr:tmdb_id"
        operator: exists
    then:
      - warn: "File matched in Radarr library"
```

### Handle Missing Plugin Data

Use `exists` checks and `else` branches for fallback:

```yaml
conditional:
  - name: language-based-processing
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
      - warn: "Preserving original Japanese audio"
    else:
      - warn: "No Radarr language data - using standard processing"
```

## Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equals (default) | `operator: eq`, `value: "jpn"` |
| `neq` | Not equals | `operator: neq`, `value: "eng"` |
| `contains` | Substring match | `operator: contains`, `value: "Director"` |
| `exists` | Field is present | `operator: exists` (no value needed) |

## Available Plugin Fields

### radarr

- `original_language` - ISO 639-2/B code (e.g., "jpn", "eng")
- `external_title` - Movie title
- `external_year` - Release year
- `tmdb_id` - TMDB identifier
- `imdb_id` - IMDB identifier

### sonarr

All radarr fields plus:
- `series_title` - TV series name
- `season_number` - Season number
- `episode_number` - Episode number
- `episode_title` - Episode name
- `tvdb_id` - TVDB identifier

## Common Patterns

### Skip Transcoding for Specific Languages

```yaml
conditional:
  - name: preserve-japanese-audio
    when:
      plugin_metadata:
        plugin_metadata: "radarr:original_language"
        operator: eq
        value: "jpn"
    then:
      - skip_audio_transcode: true
```

### Different Processing for TV vs Movies

```yaml
conditional:
  - name: tv-series-handling
    when:
      plugin_metadata:
        plugin_metadata: "sonarr:series_title"
        operator: exists
    then:
      - warn: "Processing TV episode"
    else:
      - warn: "Processing movie"
```

### Combine with Track Conditions

```yaml
conditional:
  - name: 4k-japanese-films
    when:
      and:
        - plugin_metadata:
            plugin_metadata: "radarr:original_language"
            operator: eq
            value: "jpn"
        - exists:
            track_type: video
            height: { gte: 2160 }
    then:
      - skip_video_transcode: true
```

## Troubleshooting

### Condition Always False

1. **Check plugin enrichment**: Run `vpo inspect <file>` to see if plugin metadata is present
2. **Check plugin name**: Use exact plugin name (e.g., "radarr" not "radarr-metadata")
3. **Check field name**: Verify field exists in plugin's known fields

### Validation Warnings

Warnings about unknown plugins or fields are advisory:
- Check for typos in plugin/field names
- Newer plugin versions may have fields not in the registry
- Warnings don't prevent policy loading

### No Plugin Data for File

If `plugin_metadata` is null:
- Ensure plugin is configured in `~/.vpo/config.toml`
- Ensure file path matches plugin's library path
- Re-scan files after configuring plugin

## Migration from V11

V11 policies continue to work unchanged. To use plugin metadata conditions:

1. Update `schema_version` to 12
2. Add `conditional` rules with `plugin_metadata` conditions
3. Test with `--dry-run` before applying

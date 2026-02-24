# Sonarr Metadata Plugin

The `sonarr-metadata` plugin enriches scanned TV episode files with metadata from your Sonarr instance. When VPO scans a file, this plugin identifies the series and episode through Sonarr's parse endpoint and attaches metadata such as original language, series type, episode info, and air dates. This metadata can then be used in policy conditions and actions.

This plugin is included with VPO and requires no separate installation. Enable it by adding configuration to `~/.vpo/config.toml`.

---

## Requirements

- **Sonarr v3+** (tested with v4.x)
- **API v3** (enabled by default in Sonarr v3+)
- Sonarr must be reachable from the machine running VPO

---

## Configuration

Add a `[plugins.metadata.sonarr]` section to `~/.vpo/config.toml`:

```toml
[plugins.metadata.sonarr]
url = "http://localhost:8989"
api_key = "your-sonarr-api-key"  # pragma: allowlist secret
enabled = true
timeout_seconds = 30
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | *(required)* | Base URL of your Sonarr instance |
| `api_key` | string | *(required)* | API key (Settings > General > Security in Sonarr) |
| `enabled` | bool | `true` | Set to `false` to disable the plugin without removing config |
| `timeout_seconds` | int | `30` | HTTP request timeout for API calls |

---

## API Endpoints Used

The plugin uses the following Sonarr v3 API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v3/system/status` | GET | Connection validation — confirms the URL points to a Sonarr instance |
| `/api/v3/parse?path={path}` | GET | Per-file series/episode identification — primary lookup mechanism |
| `/api/v3/tag` | GET | Tag ID to label resolution — fetched lazily on first use |

**API documentation:**
- Official Sonarr API docs: https://sonarr.tv/docs/api/
- Your instance's Swagger UI: `{url}/swagger` (e.g., `http://localhost:8989/swagger`)

---

## Metadata Fields Provided

The plugin provides the following fields via `MetadataEnrichment`. All fields are available for use in `plugin_metadata` policy conditions.

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `original_language` | `str` | ISO 639-2/B language code (e.g., `eng`, `jpn`, `kor`) |
| `external_source` | `str` | Always `"sonarr"` |
| `external_id` | `int` | Sonarr series ID |
| `external_title` | `str` | Series title from Sonarr |
| `external_year` | `int` | Series premiere year |

### External Identifiers

| Field | Type | Description |
|-------|------|-------------|
| `imdb_id` | `str` | IMDb identifier (e.g., `tt1234567`) |
| `tvdb_id` | `int` | TheTVDB identifier |

### TV-Specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `series_title` | `str` | Series title (same as `external_title`) |
| `season_number` | `int` | Season number of the episode |
| `episode_number` | `int` | Episode number within the season |
| `episode_title` | `str` | Episode title |

### Release Dates

All dates are in ISO 8601 format (`YYYY-MM-DD`).

| Field | Type | Description |
|-------|------|-------------|
| `release_date` | `str` | Primary release date (episode air date, or series premiere if unavailable) |
| `air_date` | `str` | Episode air date |
| `premiere_date` | `str` | Series premiere date (`firstAired` from Sonarr) |

### Series Metadata (v1.1.0)

| Field | Type | Description |
|-------|------|-------------|
| `certification` | `str` | Content rating (e.g., `TV-MA`, `TV-14`, `15`) |
| `genres` | `str` | Comma-separated genre list (e.g., `Drama, Thriller`) |
| `runtime` | `int` | Episode runtime in minutes |
| `status` | `str` | Series status: `continuing`, `ended`, `upcoming`, `deleted` |
| `network` | `str` | TV network (e.g., `HBO`, `Netflix`, `BBC One`) |
| `series_type` | `str` | Series type: `standard`, `daily`, `anime` |
| `monitored` | `bool` | Whether the series is monitored in Sonarr |
| `tags` | `str` | Comma-separated Sonarr tag names (e.g., `4k, anime`) |
| `tvmaze_id` | `int` | TVMaze identifier |
| `season_count` | `int` | Number of seasons |
| `total_episode_count` | `int` | Total number of episodes across all seasons |

> **Note:** The `popularity` field is not available for Sonarr. Popularity scores are only provided by the Radarr plugin for movies.

### Episode Metadata (v1.1.0)

| Field | Type | Description |
|-------|------|-------------|
| `absolute_episode_number` | `int` | Absolute episode number (useful for anime series) |

---

## Using Metadata in Policies

Sonarr metadata is accessed in V13 policies using `plugin_metadata` conditions and `from_plugin_metadata` actions.

### Condition Operators

| Operator | Description | Example Value |
|----------|-------------|---------------|
| `exists` | Field is present and non-null | *(none)* |
| `eq` | Field equals value | `anime`, `true`, `ended` |
| `neq` | Field does not equal value | `eng` |
| `lt` | Field is less than value (numeric) | `30` |
| `gte` | Field is greater than or equal to value (numeric) | `100` |
| `contains` | Field string contains value | `4k`, `Drama` |

### Example: Detect Anime and Force Subtitles

```yaml
conditional:
  - name: force-subs-for-anime
    when:
      and:
        - plugin_metadata:
            plugin: sonarr
            field: series_type
            operator: eq
            value: anime
        - exists:
            track_type: subtitle
            language: eng
    then:
      - set_forced:
          track_type: subtitle
          language: eng
          value: true
      - set_default:
          track_type: subtitle
          language: eng
          value: true
```

### Example: Force Subtitles for Foreign Shows (Non-Anime)

```yaml
conditional:
  - name: force-subs-for-foreign-shows
    when:
      and:
        - plugin_metadata:
            plugin: sonarr
            field: original_language
            operator: neq
            value: eng
        - not:
            plugin_metadata:
              plugin: sonarr
              field: series_type
              operator: eq
              value: anime
        - exists:
            track_type: subtitle
            language: eng
    then:
      - set_forced:
          track_type: subtitle
          language: eng
          value: true
```

### Example: Warn About Large Series

```yaml
conditional:
  - name: warn-large-series
    when:
      plugin_metadata:
        plugin: sonarr
        field: total_episode_count
        operator: gte
        value: 100
    then:
      - warn: "Large series (100+ episodes), consider dedicated policy: {filename}"
```

### Example: Skip Transcode for 4K-Tagged Episodes

```yaml
conditional:
  - name: preserve-4k-tagged
    when:
      plugin_metadata:
        plugin: sonarr
        field: tags
        operator: contains
        value: "4k"
    then:
      - skip_video_transcode: true
```

### Example: Set Video Language from Sonarr

```yaml
conditional:
  - name: set-video-language
    when:
      plugin_metadata:
        plugin: sonarr
        field: original_language
        operator: exists
    then:
      - set_language:
          track_type: video
          from_plugin_metadata:
            plugin: sonarr
            field: original_language
```

For a complete working policy, see [`examples/policies/sonarr-metadata.yaml`](../../../../examples/policies/sonarr-metadata.yaml).

---

## How It Works

The Sonarr plugin uses a **lazy per-file** approach:

1. On each `file.scanned` event, the plugin calls Sonarr's `/api/v3/parse?path={path}` endpoint with the file's absolute path.
2. Sonarr parses the file name and path to identify the series and episode, returning full series and episode metadata in the response.
3. The plugin caches results for the session, so repeated lookups for the same file are instant.
4. Tags are fetched lazily — the tag endpoint is only called when the first series with tags is encountered.

This per-file approach is used because Sonarr's parse endpoint is the most reliable way to map a file path to a specific episode. Unlike Radarr (which has one file per movie), TV series have many episodes and the parse endpoint handles the complex name-matching logic that Sonarr already implements.

---

## Error Handling

| Error Type | Plugin Behavior |
|------------|-----------------|
| Invalid API key (401) | Plugin disables itself permanently for the session, logs error |
| Connection refused | Plugin raises error at startup; scan continues without enrichment |
| Connection timeout | Returns `None` for the file; other files continue normally |
| API error (5xx) | Returns `None` for the file; logs warning |
| Parse returns no match | Returns `None` (expected for files not recognized by Sonarr) |
| Tag fetch failure | Continues without tag resolution; logs warning |
| Unexpected exception | Returns `None`; logs error |

The plugin never causes VPO to abort a scan. All errors are handled gracefully with appropriate logging.

---

## Troubleshooting

### Parse endpoint fails to identify a file

- Verify the file is managed by Sonarr (appears in Sonarr's UI)
- Sonarr's parse endpoint relies on file naming conventions. Files that don't follow standard naming patterns (e.g., `Show Name - S01E01 - Episode Title.mkv`) may not be identified.
- Test the parse endpoint directly: `curl -H "X-Api-Key: YOUR_KEY" "http://localhost:8989/api/v3/parse?path=/path/to/file.mkv"`
- Run `vpo scan` with `-v` (verbose) to see debug logs showing which files were matched.

### API key problems

- Find your API key in Sonarr: Settings > General > Security > API Key
- Test the key manually: `curl -H "X-Api-Key: YOUR_KEY" http://localhost:8989/api/v3/system/status`
- If you see "Invalid API key" in logs, the key is wrong or has been rotated.

### Plugin not loading

- Check that `enabled = true` in your config (or remove the `enabled` line, since `true` is the default)
- Run `vpo plugins list -v` to see plugin loading status
- Check VPO logs for connection errors during startup

### Naming conventions for best results

Sonarr's parse endpoint works best with standard TV naming:
- `Show Name - S01E01 - Episode Title.mkv` (preferred)
- `Show Name/Season 01/Show Name - S01E01.mkv` (also works)
- `show.name.s01e01.720p.mkv` (scene naming, usually works)

Files with non-standard names or absolute numbering (common in anime) may not be recognized. Ensure your Sonarr instance can identify the file in its own UI before expecting the plugin to match it.

---

## Related Docs

- [Plugin Development Guide](../../../../docs/plugins.md) — how to create and manage VPO plugins
- [Radarr Metadata Plugin](../radarr_metadata/README.md) — companion plugin for movies
- [Example Sonarr Policy](../../../../examples/policies/sonarr-metadata.yaml) — complete working policy
- [Policy Schema](../../../../docs/usage/policy-editor.md) — V13 policy editing guide
- [Enrichment Data Model](../../../../specs/038-radarr-sonarr-metadata-plugins/data-model.md) — spec for the enrichment contract

# Radarr Metadata Plugin

The `radarr-metadata` plugin enriches scanned movie files with metadata from your Radarr instance. When VPO scans a file, this plugin looks it up in Radarr's library and attaches metadata such as original language, release dates, ratings, and genre information. This metadata can then be used in policy conditions and actions.

This plugin is included with VPO and requires no separate installation. Enable it by adding configuration to `~/.vpo/config.toml`.

---

## Requirements

- **Radarr v3+** (tested with v5.x)
- **API v3** (enabled by default in Radarr v3+)
- Radarr must be reachable from the machine running VPO

---

## Configuration

Add a `[plugins.metadata.radarr]` section to `~/.vpo/config.toml`:

```toml
[plugins.metadata.radarr]
url = "http://localhost:7878"
api_key = "your-radarr-api-key"  # pragma: allowlist secret
enabled = true
timeout_seconds = 30
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | *(required)* | Base URL of your Radarr instance |
| `api_key` | string | *(required)* | API key (Settings > General > Security in Radarr) |
| `enabled` | bool | `true` | Set to `false` to disable the plugin without removing config |
| `timeout_seconds` | int | `30` | HTTP request timeout for API calls |

---

## API Endpoints Used

The plugin uses the following Radarr v3 API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v3/system/status` | GET | Connection validation — confirms the URL points to a Radarr instance |
| `/api/v3/movie` | GET | Bulk movie metadata fetch — retrieves all movies in the library |
| `/api/v3/moviefile` | GET | File-level metadata — edition, release group, scene name per file |
| `/api/v3/tag` | GET | Tag ID to label resolution — maps numeric tag IDs to human-readable names |

**API documentation:**
- Official Radarr API docs: https://radarr.video/docs/api/
- Your instance's Swagger UI: `{url}/swagger` (e.g., `http://localhost:7878/swagger`)

---

## Metadata Fields Provided

The plugin provides the following fields via `MetadataEnrichment`. All fields are available for use in `plugin_metadata` policy conditions.

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `original_language` | `str` | ISO 639-2/B language code (e.g., `eng`, `fra`, `jpn`) |
| `external_source` | `str` | Always `"radarr"` |
| `external_id` | `int` | Radarr movie ID |
| `external_title` | `str` | Movie title from Radarr |
| `external_year` | `int` | Release year |

### External Identifiers

| Field | Type | Description |
|-------|------|-------------|
| `imdb_id` | `str` | IMDb identifier (e.g., `tt1234567`) |
| `tmdb_id` | `int` | TMDb identifier |

### Release Dates

All dates are in ISO 8601 format (`YYYY-MM-DD`).

| Field | Type | Description |
|-------|------|-------------|
| `release_date` | `str` | Primary release date (first available of digital, physical, cinema) |
| `digital_release` | `str` | Digital release date |
| `physical_release` | `str` | Physical (Blu-ray/DVD) release date |
| `cinema_release` | `str` | Theatrical release date |

### Movie Metadata (v1.1.0)

| Field | Type | Description |
|-------|------|-------------|
| `original_title` | `str` | Original title before translation |
| `certification` | `str` | Content rating (e.g., `PG-13`, `R`, `15`) |
| `genres` | `str` | Comma-separated genre list (e.g., `Action, Science Fiction`) |
| `runtime` | `int` | Runtime in minutes |
| `status` | `str` | Radarr status: `announced`, `inCinemas`, `released`, `deleted` |
| `collection_name` | `str` | Collection name (e.g., `The Dark Knight Collection`) |
| `studio` | `str` | Studio name |
| `rating_tmdb` | `float` | TMDb rating (0.0–10.0) |
| `rating_imdb` | `float` | IMDb rating (0.0–10.0) |
| `popularity` | `float` | TMDb popularity score |
| `monitored` | `bool` | Whether the movie is monitored in Radarr |
| `tags` | `str` | Comma-separated Radarr tag names (e.g., `4k, remux`) |

### File-Level Fields (v1.1.0)

These fields come from the `/api/v3/moviefile` endpoint and describe the specific file rather than the movie.

| Field | Type | Description |
|-------|------|-------------|
| `edition` | `str` | Edition name (e.g., `Director's Cut`, `Extended Edition`) |
| `release_group` | `str` | Release group identifier |
| `scene_name` | `str` | Scene release name |

---

## Using Metadata in Policies

Radarr metadata is accessed in V12 policies using `plugin_metadata` conditions and `from_plugin_metadata` actions.

### Condition Operators

| Operator | Description | Example Value |
|----------|-------------|---------------|
| `exists` | Field is present and non-null | *(none)* |
| `eq` | Field equals value | `eng`, `true`, `released` |
| `neq` | Field does not equal value | `eng` |
| `lt` | Field is less than value (numeric) | `5.0` |
| `gte` | Field is greater than or equal to value (numeric) | `100` |
| `contains` | Field string contains value | `4k`, `Animation` |

### Example: Set Video Language from Radarr

```yaml
conditional:
  - name: set-video-language
    when:
      plugin_metadata:
        plugin: radarr
        field: original_language
        operator: exists
    then:
      - set_language:
          track_type: video
          from_plugin_metadata:
            plugin: radarr
            field: original_language
```

### Example: Force Subtitles for Foreign Films

```yaml
conditional:
  - name: force-subs-for-foreign-films
    when:
      and:
        - plugin_metadata:
            plugin: radarr
            field: original_language
            operator: neq
            value: eng
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

### Example: Skip Transcode for 4K-Tagged Movies

```yaml
conditional:
  - name: preserve-4k-tagged
    when:
      plugin_metadata:
        plugin: radarr
        field: tags
        operator: contains
        value: "4k"
    then:
      - skip_video_transcode: true
```

### Example: Warn on Low-Rated Content

```yaml
conditional:
  - name: warn-low-rated
    when:
      plugin_metadata:
        plugin: radarr
        field: rating_tmdb
        operator: lt
        value: 5.0
    then:
      - warn: "Low TMDb rating (<5.0): {filename}"
```

For a complete working policy, see [`examples/policies/radarr-metadata.yaml`](../../../../examples/policies/radarr-metadata.yaml).

---

## How It Works

The Radarr plugin uses a **bulk cache** approach for efficient lookups:

1. On the first `file.scanned` event, the plugin fetches **all** movies, movie files, and tags from Radarr in three API calls.
2. It builds an in-memory index mapping normalized file paths to movie and file records.
3. Subsequent `file.scanned` events are resolved from this cache with no additional API calls.
4. Path matching uses OS-normalized path comparison (paths are resolved to absolute form).

This approach is efficient because Radarr's `/api/v3/movie` and `/api/v3/moviefile` endpoints return the entire library in a single response, and most VPO scan operations process many files from the same library.

---

## Error Handling

| Error Type | Plugin Behavior |
|------------|-----------------|
| Invalid API key (401) | Plugin disables itself permanently for the session, logs error |
| Connection refused | Plugin raises error at startup; scan continues without enrichment |
| Connection timeout | Returns `None` for the file; other files continue normally |
| API error (5xx) | Returns `None` for the file; logs warning |
| File not found in Radarr | Returns `None` (expected for files not managed by Radarr) |
| Tag fetch failure | Continues without tag resolution; logs warning |
| Unexpected exception | Returns `None`; logs error |

The plugin never causes VPO to abort a scan. All errors are handled gracefully with appropriate logging.

---

## Troubleshooting

### No match found for a file

- Verify the file is managed by Radarr (appears in Radarr's UI)
- Check that the file path seen by VPO matches the path in Radarr. Paths are resolved to their absolute form for comparison; on case-sensitive filesystems (Linux), case must match exactly.
- If Radarr and VPO see different mount points (e.g., Docker volume mounts), the paths won't match. Ensure both tools see the same absolute paths.
- Run `vpo scan` with `-v` (verbose) to see debug logs showing the normalized paths being compared.

### API key problems

- Find your API key in Radarr: Settings > General > Security > API Key
- Test the key manually: `curl -H "X-Api-Key: YOUR_KEY" http://localhost:7878/api/v3/system/status`
- If you see "Invalid API key" in logs, the key is wrong or has been rotated.

### Plugin not loading

- Check that `enabled = true` in your config (or remove the `enabled` line, since `true` is the default)
- Run `vpo plugins list -v` to see plugin loading status
- Check VPO logs for connection errors during startup

### Path mismatch between Radarr and VPO

The plugin normalizes paths for comparison, but the underlying directory paths must resolve to the same location. Common causes of mismatch:

- **Docker**: Radarr sees `/movies/Film.mkv` but VPO sees `/mnt/media/movies/Film.mkv`
- **Symlinks**: Radarr stores the real path, VPO follows a symlink to a different path
- **Case differences**: On macOS (case-insensitive FS by default), handled automatically. On Linux (case-sensitive), paths must match exactly.

---

## Related Docs

- [Plugin Development Guide](../../../../docs/plugins.md) — how to create and manage VPO plugins
- [Sonarr Metadata Plugin](../sonarr_metadata/README.md) — companion plugin for TV series
- [Example Radarr Policy](../../../../examples/policies/radarr-metadata.yaml) — complete working policy
- [Policy Schema](../../../../docs/usage/policy-editor.md) — V12 policy editing guide
- [Enrichment Data Model](../../../../specs/038-radarr-sonarr-metadata-plugins/data-model.md) — spec for the enrichment contract

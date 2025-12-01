# Implementation Plan: Radarr and Sonarr Metadata Plugins

**Branch**: `038-radarr-sonarr-metadata-plugins` | **Date**: 2025-12-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/038-radarr-sonarr-metadata-plugins/spec.md`

## Summary

Implement two VPO analyzer plugins that connect to Radarr (movies) and Sonarr (TV series) APIs to enrich scanned files with metadata, particularly original language information. The plugins subscribe to the `file.scanned` event and return enrichment data that is merged into FileInfo for use in policy conditions and UI display.

**Technical Approach**:
- Radarr: Build session cache from `/api/v3/movie` and `/api/v3/moviefile` endpoints, match files by exact path
- Sonarr: Use `/api/v3/parse?path=` endpoint for efficient per-file lookup
- Both: Normalize language names to ISO 639-2/B using existing VPO `normalize_language()` function

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: aiohttp (HTTP client), existing VPO plugin system
**Storage**: VPO config file (`~/.vpo/config.toml`) for credentials; session-scoped in-memory cache for API responses
**Testing**: pytest with mocked API responses
**Target Platform**: Linux, macOS (same as VPO)
**Project Type**: Single project - extends existing VPO codebase
**Performance Goals**: <1 second per file enrichment, no blocking of scan operations
**Constraints**: Network dependent (graceful degradation on failure), identical file paths required between VPO and Radarr/Sonarr
**Scale/Scope**: Libraries with thousands of movies/episodes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Datetime Integrity | PASS | All timestamps from APIs stored as UTC ISO-8601 |
| II. Stable Identity | PASS | Using external IDs (movie_id, series_id) not paths as keys |
| III. Portable Paths | PASS | Using pathlib.Path, no hardcoded separators |
| IV. Versioned Schemas | PASS | Plugin version tracked, enrichment schema documented |
| V. Idempotent Operations | PASS | Re-scanning refreshes enrichment; safe to repeat |
| VI. IO Separation | PASS | API clients encapsulated behind typed interfaces |
| VII. Explicit Error Handling | PASS | All error scenarios documented with specific behaviors |
| VIII. Structured Logging | PASS | Logging match results, API errors with file context |
| IX. Configuration as Data | PASS | Credentials in config file, not code |
| X. Policy Stability | N/A | Not modifying policy schema |
| XI. Plugin Isolation | PASS | Using established AnalyzerPlugin protocol |
| XII. Safe Concurrency | PASS | Session cache per scan; no shared mutable state |
| XIII. Database Design | PASS | Enrichment via plugin dict return, no schema changes |
| XIV. Test Media Corpus | PASS | Mock API responses for testing |
| XV. Stable CLI/API Contracts | N/A | No CLI changes |
| XVI. Dry-Run Default | N/A | Read-only plugins |
| XVII. Data Privacy | PASS | External API calls opt-in via explicit config; only file paths sent |
| XVIII. Living Documentation | PASS | Contracts and quickstart documented |

**Post-Phase 1 Re-check**: All gates still pass. No schema changes required for initial implementation.

## Project Structure

### Documentation (this feature)

```text
specs/038-radarr-sonarr-metadata-plugins/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output - API research and decisions
├── data-model.md        # Phase 1 output - data models and relationships
├── quickstart.md        # Phase 1 output - implementation guide
├── contracts/           # Phase 1 output - API contracts
│   ├── radarr-api.md    # Radarr v3 API contract
│   ├── sonarr-api.md    # Sonarr v3 API contract
│   └── plugin-enrichment.md  # Plugin return value contract
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/video_policy_orchestrator/
├── plugins/
│   ├── radarr_metadata/           # NEW: Radarr plugin package
│   │   ├── __init__.py            # Package exports
│   │   ├── plugin.py              # RadarrMetadataPlugin class
│   │   ├── client.py              # RadarrClient HTTP client
│   │   └── models.py              # Radarr API response models
│   └── sonarr_metadata/           # NEW: Sonarr plugin package
│       ├── __init__.py            # Package exports
│       ├── plugin.py              # SonarrMetadataPlugin class
│       ├── client.py              # SonarrClient HTTP client
│       └── models.py              # Sonarr API response models
├── config/
│   └── models.py                  # MODIFY: Add MetadataPluginSettings
├── server/
│   └── ui/
│       └── templates/
│           └── file_detail.html   # MODIFY: Display enriched metadata
└── language.py                    # EXISTING: normalize_language() used

tests/
├── unit/
│   └── plugins/
│       ├── test_radarr_models.py      # NEW: Model parsing tests
│       ├── test_radarr_plugin.py      # NEW: Plugin unit tests
│       ├── test_sonarr_models.py      # NEW: Model parsing tests
│       └── test_sonarr_plugin.py      # NEW: Plugin unit tests
└── integration/
    └── plugins/
        ├── test_radarr_integration.py  # NEW: Live API tests (optional)
        └── test_sonarr_integration.py  # NEW: Live API tests (optional)
```

**Structure Decision**: Extending existing VPO single-project structure. New plugin packages follow the established pattern from `plugins/whisper_transcriber/`. Configuration extends existing `config/models.py`. No new top-level directories required.

## Cache Lifecycle

**Session-scoped cache behavior**: Plugin instances are created per scan operation. The cache is built lazily on first `on_file_scanned` call and is automatically garbage collected when the scan completes and the plugin instance goes out of scope. No explicit cache clearing is required.

- Radarr: Cache built eagerly on first file (full movie/file list)
- Sonarr: Cache populated lazily per-file (parse endpoint results)
- Both: Instance lifetime = scan operation lifetime

## Complexity Tracking

No constitution violations requiring justification. The implementation follows established VPO patterns:

- Uses existing AnalyzerPlugin protocol (no new interfaces)
- Stores configuration in existing config system (no new storage)
- Returns enrichment via plugin dict mechanism (no database changes)
- Follows existing plugin package structure from whisper_transcriber

## Implementation Phases

### Phase 1: Core Plugin Infrastructure (P1 Stories)

1. Add configuration models for plugin connections
2. Implement RadarrClient with connection validation
3. Implement SonarrClient with connection validation
4. Create plugin classes with event subscription
5. Unit tests for configuration and clients

### Phase 2: Metadata Enrichment (P2 Stories)

1. Implement Radarr cache building and path matching
2. Implement Sonarr parse endpoint integration
3. Language normalization using existing VPO utilities
4. Enrichment return value formatting
5. Unit tests with mocked API responses

### Phase 3: Policy and UI Integration (P3 Stories)

1. Expose enriched metadata in file detail UI
2. Document policy condition usage
3. Integration tests (optional - requires live services)
4. End-to-end testing with sample files

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| File matching | Exact path match | Per clarification; simplest and most reliable |
| API credentials | Config file | Per clarification; consistent with VPO patterns |
| Cache lifetime | Session only | Per clarification; ensures fresh data per scan |
| Radarr lookup | Full list + local match | No query-by-path API available |
| Sonarr lookup | Parse endpoint | Efficient per-file lookup available |
| Language format | ISO 639-2/B | VPO standard; reuse normalize_language() |

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| API unavailable | Graceful degradation; log and skip enrichment |
| Large libraries | Session cache avoids repeated API calls |
| Path mismatches | Clear documentation; debug logging for troubleshooting |
| API changes | Version-specific contracts; monitor for breaking changes |

## Related Documents

- [Research](research.md) - API research and design decisions
- [Data Model](data-model.md) - Detailed data structures
- [Quickstart](quickstart.md) - Implementation guide
- [Radarr API Contract](contracts/radarr-api.md)
- [Sonarr API Contract](contracts/sonarr-api.md)
- [Plugin Enrichment Contract](contracts/plugin-enrichment.md)

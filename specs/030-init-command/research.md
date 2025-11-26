# Research: VPO Init Command

**Date**: 2025-11-25
**Feature**: 030-init-command

## Research Questions

### 1. TOML File Generation Strategy

**Question**: How should we generate config.toml with comments since Python's tomllib is read-only?

**Decision**: Use a string template approach with embedded comments

**Rationale**:
- Python's `tomllib` (3.11+) and `tomli` (fallback) are read-only parsers
- No standard library for TOML writing with comments
- String templates give full control over formatting and documentation
- Comments are essential for user discoverability (SC-003)

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| `tomlkit` library | Adds new dependency; overkill for one-time generation |
| `toml` library | Deprecated, doesn't preserve comments well |
| Generate without comments | Violates SC-003 - users need inline documentation |
| JSON format | Not human-readable enough; TOML is existing VPO convention |

### 2. Default Data Directory Structure

**Question**: What directories and files should init create?

**Decision**: Create the following structure:
```
~/.vpo/
├── config.toml          # Main configuration file
├── policies/            # User policy files
│   └── default.yaml     # Starter policy
└── plugins/             # User plugin directory
```

**Rationale**:
- Matches existing VPO conventions in `config/loader.py` (DEFAULT_CONFIG_DIR, DEFAULT_PLUGINS_DIR)
- Database (`library.db`) and logs created on-demand by other commands
- Keeps init simple - only creates static configuration, not runtime artifacts

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Create database file | Database should be created on first scan (existing pattern) |
| Create logs/ directory | Created on-demand when logging enabled |
| Create profiles/ directory | Profiles are stored in config.toml, not separate files |

### 3. Existing Configuration Detection

**Question**: How do we detect "already initialized" state?

**Decision**: Check for existence of `config.toml` file as the primary indicator

**Rationale**:
- `config.toml` is the definitive marker of user configuration
- Directory alone may exist without init (user created manually)
- Other files (policies/, plugins/) are optional components

**Detection Logic**:
1. If `~/.vpo/config.toml` exists → Already initialized (require --force)
2. If `~/.vpo/` directory exists but no config.toml → Partial state, report and exit
3. If `~/.vpo/` doesn't exist → Fresh initialization

### 4. Config Template Content

**Question**: What settings should be included in the generated config.toml?

**Decision**: Include ALL settings from VPOConfig with documented defaults

**Rationale**:
- Matches SC-003: "Users can discover and understand all configuration options"
- Existing `config/models.py` defines 10 config sections with ~40 settings
- All settings should be commented out with defaults shown (users uncomment to customize)

**Config Sections** (from models.py):
1. `[tools]` - External tool paths (ffmpeg, ffprobe, mkvmerge, mkvpropedit)
2. `[tools.detection]` - Tool capability caching
3. `[behavior]` - Runtime warnings and suggestions
4. `[plugins]` - Plugin directories and loading
5. `[jobs]` - Job retention and backup settings
6. `[worker]` - Job worker limits
7. `[transcription]` - Whisper model settings
8. `[logging]` - Log level, format, rotation
9. `[server]` - Web UI bind address, port, auth
10. `[language]` - ISO language code standard

### 5. Default Policy Content

**Question**: What should the default policy contain?

**Decision**: Use existing `docs/examples/default-policy.yaml` as the template

**Rationale**:
- Already exists and is well-documented
- Demonstrates all major policy features
- Uses schema_version: 1 (current)
- Tested and known to work with `vpo apply`

### 6. CLI Flag Naming

**Question**: What flags should the init command support?

**Decision**: Follow existing VPO CLI conventions:
- `--data-dir PATH` - Custom data directory (matches VPO_DATA_DIR env var)
- `--force` - Overwrite existing configuration
- `--dry-run` - Show what would be created

**Rationale**:
- `--dry-run` is established VPO convention (Constitution XVI)
- `--force` is standard CLI pattern for destructive operations
- `--data-dir` mirrors the VPO_DATA_DIR environment variable

### 7. Error Handling Strategy

**Question**: How should errors be reported?

**Decision**: Use Click's error handling with clear, actionable messages

**Error Types**:
| Error | Message Pattern |
|-------|-----------------|
| Permission denied | "Cannot write to {path}: Permission denied. Try running with appropriate permissions." |
| Path is file | "Cannot create directory at {path}: A file already exists at this location." |
| Already initialized | "VPO is already initialized at {path}. Use --force to overwrite." |
| Invalid path | "Cannot create directory at {path}: {reason}" |

**Rationale**:
- Click's `click.ClickException` provides consistent error formatting
- Messages should suggest next steps (per Constitution VII)

## Summary of Decisions

| Decision | Choice |
|----------|--------|
| Config generation | String template with inline comments |
| Directory structure | config.toml, policies/, plugins/ |
| Init detection | Check for config.toml existence |
| Config content | All VPOConfig settings, commented defaults |
| Default policy | Copy from docs/examples/default-policy.yaml |
| CLI flags | --data-dir, --force, --dry-run |
| Error handling | Click exceptions with actionable messages |

## Dependencies

No new dependencies required. Uses existing:
- `click` - CLI framework
- `pathlib` - Path operations
- `PyYAML` - Policy file writing (existing dependency)

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Config template gets out of sync with models.py | Generate template from models.py docstrings at build time (future enhancement) |
| Default policy schema changes | Use schema_version: 1 which is stable |
| Partial init on interrupt | Check for incomplete state on subsequent runs |

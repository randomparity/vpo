# Architecture Overview

**Product:** Video Policy Orchestrator (VPO)
**Version:** 0.1.0
**Last Updated:** 2025-11-21

## Overview

VPO follows a layered architecture with clear separation between user interface, business logic, external tool integration, and data persistence. The design prioritizes extensibility through a plugin system while keeping the core minimal.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLI Frontend                                │
│                    (scan, inspect, apply, jobs, profiles)               │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                             Core Engine                                  │
│              (Orchestration, Plugin Management, Scheduling)             │
└───────┬─────────────────┬─────────────────┬─────────────────┬───────────┘
        │                 │                 │                 │
        ▼                 ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│    Media      │ │    Policy     │ │   Execution   │ │    Plugin     │
│  Introspector │ │    Engine     │ │     Layer     │ │    System     │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                 │                 │                 │
        ▼                 │                 │                 ▼
┌───────────────┐         │                 │         ┌───────────────┐
│ External Tools│         │                 │         │    Plugins    │
│ (ffprobe,     │         │                 │         │  (Analyzers,  │
│  mkvmerge)    │         │                 │         │   Mutators,   │
└───────────────┘         │                 │         │  Transcribers)│
                          │                 │         └───────────────┘
                          ▼                 ▼
                    ┌─────────────────────────────┐
                    │          Database           │
                    │   (SQLite: files, tracks,   │
                    │    policies, jobs, history) │
                    └─────────────────────────────┘
```

## Component Descriptions

### CLI Frontend

The user-facing command-line interface providing:
- **scan**: Discover and catalog video files in directories
- **inspect**: View file/track details and current state
- **apply**: Execute policies against the library
- **jobs**: View and manage long-running operations
- **profiles**: Manage policy configurations

Output modes: human-friendly (default) and machine-readable (JSON).

### Core Engine

The central orchestration layer that:
- Coordinates scanning, policy evaluation, and job scheduling
- Manages plugin lifecycle (discovery, loading, execution)
- Exposes stable internal interfaces for plugins
- Handles configuration and logging

### Media Introspector

Abstracts external media tools into a uniform data model:
- Wraps `ffprobe` for general container/codec inspection
- Wraps `mkvmerge`/`mkvpropedit` for MKV-specific operations
- Normalizes track metadata into internal representations
- Handles errors and tool availability detection

### Policy Engine

Processes user-defined policies:
- Reads policy files (YAML/JSON format)
- Compares current state against desired state
- Produces an execution **plan**: an abstract description of changes
- Supports dry-run mode for preview without modification

### Execution Layer

Performs actual file operations:
- Metadata edits (flags, language codes, titles)
- Container remuxing (track reordering)
- Transcoding (codec conversion, quality adjustment)
- File moves and renames

Integrates with the job queue for long-running operations.

### Plugin System

Extensibility framework supporting:
- **Analyzer plugins**: Add metadata, perform checks, tag content
- **Mutator plugins**: Modify containers, rewrite metadata
- **Transcription plugins**: Speech-to-text, language detection

Plugin discovery via:
- Configurable plugin directories
- Python entry points for packaged plugins

### Database

SQLite-based persistence for:
- **Files**: Path, hash, container info, last scanned
- **Tracks**: Type, codec, language, flags, ordering
- **Policies**: Definitions, versions, application history
- **Jobs**: Status, progress, error logs
- **History**: Audit trail of all operations

#### Database Schema (ER Diagram)

```
┌─────────────────────────────────────────────────────────────────┐
│                            _meta                                 │
├─────────────────────────────────────────────────────────────────┤
│ key (TEXT PK)                                                    │
│ value (TEXT)                                                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                            files                                 │
├─────────────────────────────────────────────────────────────────┤
│ id (INTEGER PK AUTOINCREMENT)                                    │
│ path (TEXT UNIQUE NOT NULL)                                      │
│ filename (TEXT NOT NULL)                                         │
│ directory (TEXT NOT NULL)                                        │
│ extension (TEXT NOT NULL)                                        │
│ size_bytes (INTEGER NOT NULL)                                    │
│ modified_at (TEXT NOT NULL)  -- ISO 8601 timestamp               │
│ content_hash (TEXT)          -- xxh64 partial hash               │
│ container_format (TEXT)      -- e.g., "matroska", "mp4"          │
│ scanned_at (TEXT NOT NULL)   -- ISO 8601 timestamp               │
│ scan_status (TEXT NOT NULL)  -- "ok", "error", "pending"         │
│ scan_error (TEXT)            -- error message if status="error"  │
└─────────────────────────────────────────────────────────────────┘
          │
          │ 1:N
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                           tracks                                 │
├─────────────────────────────────────────────────────────────────┤
│ id (INTEGER PK AUTOINCREMENT)                                    │
│ file_id (INTEGER NOT NULL FK → files.id ON DELETE CASCADE)       │
│ track_index (INTEGER NOT NULL)                                   │
│ track_type (TEXT NOT NULL)   -- "video", "audio", "subtitle"     │
│ codec (TEXT)                 -- e.g., "hevc", "aac", "subrip"    │
│ language (TEXT)              -- ISO 639-2 code, e.g., "eng"      │
│ title (TEXT)                 -- track label                      │
│ is_default (INTEGER NOT NULL DEFAULT 0)  -- boolean as 0/1       │
│ is_forced (INTEGER NOT NULL DEFAULT 0)   -- boolean as 0/1       │
└─────────────────────────────────────────────────────────────────┘
```

See `specs/002-library-scanner/data-model.md` for the complete schema including future-ready tables (operations, policies).

#### Example Scanned File JSON

```json
{
  "path": "/media/movies/movie.mkv",
  "filename": "movie.mkv",
  "directory": "/media/movies",
  "extension": "mkv",
  "size_bytes": 4831838208,
  "modified_at": "2024-01-15T10:30:00",
  "content_hash": "xxh64:a1b2c3d4e5f6a7b8:f8e7d6c5b4a39281:4831838208",
  "container_format": "matroska",
  "scanned_at": "2024-01-20T14:00:00",
  "scan_status": "ok",
  "tracks": [
    {
      "index": 0,
      "track_type": "video",
      "codec": "hevc",
      "language": null,
      "title": null,
      "is_default": true,
      "is_forced": false
    },
    {
      "index": 1,
      "track_type": "audio",
      "codec": "opus",
      "language": "eng",
      "title": "English Audio",
      "is_default": true,
      "is_forced": false
    },
    {
      "index": 2,
      "track_type": "subtitle",
      "codec": "subrip",
      "language": "eng",
      "title": "English Subtitles",
      "is_default": true,
      "is_forced": false
    }
  ]
}
```

## Data Flow

### Scan Operation

```
User → CLI → Core Engine → Media Introspector → External Tools
                ↓                                      ↓
            Database ←─────────── Track Metadata ←────┘
```

### Apply Operation

```
User → CLI → Core Engine → Policy Engine → Plan
                ↓              ↓
            Database     Execution Layer → External Tools
                ↓              ↓
            History ←── Job Status
```

## External Dependencies

| Dependency | Purpose | Required |
|------------|---------|----------|
| ffmpeg/ffprobe | Container inspection, transcoding | Yes |
| mkvmerge/mkvpropedit | MKV container manipulation | Yes (for MKV) |
| SQLite | Data persistence | Yes (bundled with Python) |
| Whisper (optional) | Audio transcription | No (plugin) |

## Design Principles

1. **Library-First**: Core functionality as importable library, CLI as thin wrapper
2. **Plugin-Centric**: Specialized behavior in plugins, core stays minimal
3. **Safety-First**: Dry-run by default, no destructive operations without confirmation
4. **Idempotent**: Running the same policy twice produces the same result
5. **Observable**: All operations logged and queryable via database

## Future Considerations

- Alternative database backends (PostgreSQL for multi-user)
- REST API for remote access
- Web UI for visualization
- Container image distribution

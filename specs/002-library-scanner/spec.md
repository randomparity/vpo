# Feature Specification: Library Scanner

**Feature Branch**: `002-library-scanner`
**Created**: 2025-11-21
**Status**: Draft
**Input**: Sprint 1 - Core Domain Modeling & Library Scanner (Read-Only): Build a read-only scanner that indexes video files into a DB with basic metadata; no modifications yet.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Directory Scan CLI (Priority: P1)

As a user with a large media library, I want to recursively scan one or more directories for video files so that the tool can track my library state.

**Why this priority**: This is the foundational capability that enables all other features. Without scanning, no library data exists to query, analyze, or apply policies against.

**Independent Test**: Can be fully tested by running `vpo scan /path/to/videos` against a directory containing video files and verifying files are discovered and counted.

**Acceptance Scenarios**:

1. **Given** a directory containing video files in nested subdirectories, **When** I run `vpo scan /media/videos`, **Then** all video files matching supported extensions are discovered recursively.
2. **Given** a scan command with custom extensions specified, **When** I run `vpo scan /media/videos --extensions mkv,mp4`, **Then** only files with those extensions are included.
3. **Given** a completed scan, **When** the scan finishes, **Then** a summary is displayed showing total files found, total tracks indexed, and elapsed time.
4. **Given** multiple directory arguments, **When** I run `vpo scan /dir1 /dir2`, **Then** all directories are scanned and results are combined.

---

### User Story 2 - Database Schema for Library (Priority: P2)

As a system designer, I want a normalized database schema for videos, tracks, and operations so that policies and history can be stored and queried efficiently.

**Why this priority**: The database is the persistence layer that makes scan results useful across sessions. It must exist before any data can be stored.

**Independent Test**: Can be tested by initializing the database and verifying all required tables exist with correct column definitions.

**Acceptance Scenarios**:

1. **Given** the VPO tool is run for the first time, **When** any command requiring the database executes, **Then** the database and all tables are created automatically.
2. **Given** an existing database with data, **When** a new scan runs, **Then** existing records are updated (not duplicated) based on file path.
3. **Given** a file that has been moved or deleted, **When** a scan runs, **Then** the system can detect the change via stored file hash.

---

### User Story 3 - Metadata Extraction Stub (Priority: P3)

As a developer, I want a thin abstraction for media metadata retrieval so that I can plug in ffprobe/mkvmerge later without changing callers.

**Why this priority**: The abstraction layer decouples the scanner from specific tools, enabling future flexibility without redesign.

**Independent Test**: Can be tested by calling the stub interface with a file path and verifying it returns a structured data object with expected fields.

**Acceptance Scenarios**:

1. **Given** a video file path, **When** I call `MediaIntrospector.get_file_info(path)`, **Then** a structured object is returned containing file and track metadata.
2. **Given** a non-existent file path, **When** I call `MediaIntrospector.get_file_info(path)`, **Then** an appropriate error is raised indicating the file was not found.
3. **Given** a file that is not a video, **When** I call `MediaIntrospector.get_file_info(path)`, **Then** the system either returns empty track data or raises a clear error.

---

### User Story 4 - Spec Documentation Update (Priority: P4)

As a product owner, I want the specification updated with the data model and scanning behavior so that later sprints have a stable foundation.

**Why this priority**: Documentation ensures alignment across stakeholders and provides reference material for future development.

**Independent Test**: Can be verified by reviewing documentation for completeness, accuracy, and inclusion of example data structures.

**Acceptance Scenarios**:

1. **Given** the spec documentation, **When** reviewed, **Then** all database entities are described with their purpose and relationships.
2. **Given** the spec documentation, **When** reviewed, **Then** an example JSON document showing a scanned file's structure is included.

---

### Edge Cases

- What happens when a directory path does not exist or is inaccessible? The system should report a clear error and continue scanning other provided paths.
- What happens when a file cannot be read due to permissions? The system should log the error and continue with other files.
- What happens when the same file is scanned twice in one session? The system should process it once and skip duplicates.
- What happens when the database file is corrupted or locked? The system should report a clear error and exit gracefully.
- What happens when scanning an empty directory? The system should complete successfully with zero files found.
- What happens when a symbolic link points to a video file? The system should follow symlinks by default and avoid infinite loops.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept one or more directory paths as command arguments for scanning.
- **FR-002**: System MUST recursively traverse directories to discover video files.
- **FR-003**: System MUST support configurable file extensions for filtering (default: mkv, mp4, avi, webm, m4v, mov).
- **FR-004**: System MUST create and initialize the SQLite database automatically on first use.
- **FR-005**: System MUST store discovered file metadata including path, size, and modification timestamp.
- **FR-006**: System MUST compute and store a content hash for each file to enable duplicate and move detection.
- **FR-007**: System MUST display a summary after scanning (files found, tracks indexed, elapsed time).
- **FR-008**: System MUST perform idempotent updates when re-scanning (update existing records rather than creating duplicates).
- **FR-009**: System MUST provide a MediaIntrospector interface that returns structured file and track data.
- **FR-010**: System MUST store track information including type, codec, language, and ordering for each file.
- **FR-011**: System MUST handle errors gracefully (missing files, permission denied, invalid paths) without crashing.
- **FR-012**: System MUST support a dry-run or preview mode that shows what would be scanned without writing to the database.

### Key Entities

- **File**: Represents a video file in the library. Key attributes: path (unique identifier), filename, directory, size in bytes, modification timestamp, content hash, container format, scan timestamp, scan status.
- **Track**: Represents a media stream within a file. Key attributes: track index, track type (video/audio/subtitle/other), codec identifier, language code, title/label, default flag, forced flag, ordering position, parent file reference.
- **Operation**: Represents a planned or completed action on a file. Key attributes: operation type, target file, status, timestamp, parameters, result. (Future-ready, minimal implementation for Sprint 1)
- **Policy**: Represents a set of rules for library management. Key attributes: name, definition, version, creation timestamp. (Future-ready, minimal implementation for Sprint 1)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can scan a library of 10,000+ video files to completion without errors or crashes.
- **SC-002**: Scan results persist across CLI sessions - running a query after closing and reopening the CLI returns previously scanned data.
- **SC-003**: Re-scanning the same directory updates existing records rather than creating duplicates (verified by consistent file count).
- **SC-004**: Summary report accurately reflects the number of files found and tracks indexed (verified against manual count of test directory).
- **SC-005**: Scanning a 1,000-file directory completes within a reasonable time frame (under 1 minute on SSD; under 5 minutes on spinning disk/NAS).
- **SC-006**: Database schema supports querying files by any stored attribute (path, extension, size, hash, container format).

## Assumptions

- Default database location is `~/.vpo/library.db` unless overridden by configuration.
- Default supported video extensions are: mkv, mp4, avi, webm, m4v, mov.
- The MediaIntrospector stub will return placeholder/mock data in Sprint 1; real ffprobe/mkvmerge integration is deferred to a later sprint.
- Content hash is computed using a fast algorithm (e.g., partial file hash or xxHash) suitable for large files.
- Symbolic links are followed by default; circular symlink detection is handled by the scanner.
- The scanner operates in read-only mode - no file modifications occur during scanning.

## Example Data Structure

The following JSON represents the structure returned by `MediaIntrospector.get_file_info()` and stored in the database:

```json
{
  "file": {
    "path": "/media/videos/Movies/Example Movie (2024)/Example.Movie.2024.1080p.BluRay.mkv",
    "filename": "Example.Movie.2024.1080p.BluRay.mkv",
    "directory": "/media/videos/Movies/Example Movie (2024)",
    "size_bytes": 8589934592,
    "modified_at": "2024-06-15T10:30:00Z",
    "content_hash": "a1b2c3d4e5f6...",
    "container_format": "matroska",
    "scanned_at": "2025-11-21T14:00:00Z"
  },
  "tracks": [
    {
      "index": 0,
      "type": "video",
      "codec": "hevc",
      "language": null,
      "title": null,
      "default": true,
      "forced": false
    },
    {
      "index": 1,
      "type": "audio",
      "codec": "truehd",
      "language": "eng",
      "title": "TrueHD 7.1 Atmos",
      "default": true,
      "forced": false
    },
    {
      "index": 2,
      "type": "audio",
      "codec": "ac3",
      "language": "eng",
      "title": "Dolby Digital 5.1",
      "default": false,
      "forced": false
    },
    {
      "index": 3,
      "type": "subtitle",
      "codec": "subrip",
      "language": "eng",
      "title": "English (Full)",
      "default": true,
      "forced": false
    },
    {
      "index": 4,
      "type": "subtitle",
      "codec": "subrip",
      "language": "eng",
      "title": "English (SDH)",
      "default": false,
      "forced": false
    }
  ]
}
```

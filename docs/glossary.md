# Glossary

**Purpose:**
Definitions of key terms used throughout VPO documentation and codebase.

---

## Terms

### Container Format

The file format that holds video, audio, and subtitle tracks together. Examples include Matroska (`.mkv`), MP4 (`.mp4`), and AVI (`.avi`). VPO extracts this information via ffprobe.

### Content Hash

A partial hash computed from the first and last 64KB of a file, combined with file size. Used for efficient change detection without hashing entire files. Format: `xxh64:<head_hash>:<tail_hash>:<file_size>`.

### Dry Run

A mode where VPO simulates operations without making actual changes. Use `--dry-run` with scan commands to preview what would happen.

### ffprobe

A command-line tool (part of ffmpeg) that analyzes media files and outputs detailed stream information. VPO uses ffprobe to extract track metadata.

### Introspection

The process of examining a media file to extract metadata about its container format and tracks. Performed by the Media Introspector component using ffprobe.

### Job

A long-running operation such as transcoding or batch file processing. Jobs can be queued, monitored, and cancelled. *(Not yet implemented)*

### Media Item

A single video file in the library, represented in the database with its path, size, timestamps, and associated tracks.

### MKV / Matroska

A flexible, open-standard container format that can hold unlimited video, audio, subtitle, and attachment tracks. VPO has enhanced support for MKV files.

### mkvmerge / mkvpropedit

Tools from MKVToolNix for creating and editing Matroska files. VPO may use these for MKV-specific operations. *(Planned)*

### Plugin

An extension module that adds functionality to VPO. Plugin types include:
- **Analyzer plugins:** Add metadata, perform checks, tag content
- **Mutator plugins:** Modify containers, rewrite metadata, move files
- **Transcription plugins:** Speech-to-text, language detection

*(Plugin system not yet implemented)*

### Policy

A set of rules defining how a video library should be organized. Policies specify track ordering preferences, default track selection, naming conventions, and transformation rules. *(Not yet implemented)*

### Scan

The process of discovering video files in directories, computing content hashes, and storing metadata in the database. Scans are incremental - unchanged files are skipped.

### Scan Run

A single execution of the scan command, which processes one or more directories and records results in the database.

### Track

A single stream within a media file. Track types include:
- **video:** Video streams (H.264, HEVC, AV1, etc.)
- **audio:** Audio streams (AAC, Opus, DTS, etc.)
- **subtitle:** Text or image-based subtitles (SRT, ASS, PGS, etc.)
- **attachment:** Embedded files like fonts

### Track Index

The zero-based position of a track within a media file. Used to identify specific tracks when applying policies.

### Track Flags

Boolean properties on tracks:
- **default:** The track selected by default on playback
- **forced:** The track shown regardless of user preference (e.g., foreign language dialogue)

---

## Abbreviations

| Abbreviation | Meaning |
|--------------|---------|
| ADR | Architecture Decision Record |
| CLI | Command-Line Interface |
| CRF | Constant Rate Factor (video quality setting) |
| DB | Database |
| ER | Entity-Relationship (diagram) |
| FK | Foreign Key |
| JSON | JavaScript Object Notation |
| PK | Primary Key |
| UTC | Coordinated Universal Time |
| VPO | Video Policy Orchestrator |
| YAML | YAML Ain't Markup Language |

---

## Related docs

- [Documentation Index](INDEX.md)
- [Data Model](overview/data-model.md)
- [Architecture Overview](overview/architecture.md)

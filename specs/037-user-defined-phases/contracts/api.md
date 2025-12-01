# API Contract: User-Defined Processing Phases

**Feature**: 037-user-defined-phases
**Date**: 2025-11-30

## Overview

This document defines the API contracts for V11 policy schema and phase execution.

---

## Policy Schema Contract (V11)

### YAML Schema

```yaml
# V11 Policy Schema
schema_version: 11  # Required, must be exactly 11

config:  # Optional, defaults applied if omitted
  audio_language_preference: [string]  # ISO 639-2/B codes
  subtitle_language_preference: [string]
  commentary_patterns: [string]
  on_error: "skip" | "continue" | "fail"  # Default: "continue"

phases:  # Required, at least one phase
  - name: string  # Required, unique, pattern: ^[a-zA-Z][a-zA-Z0-9_-]{0,63}$

    # Operations (all optional, any combination)
    container:
      target: "mkv" | "mp4"

    audio_filter:
      languages: [string]
      minimum: integer
      fallback:
        mode: "content_language" | "first" | "none"

    subtitle_filter:
      languages: [string]
      preserve_forced: boolean
      minimum: integer

    attachment_filter:
      remove_all: boolean
      keep_fonts: boolean

    track_order:
      - "video" | "audio_main" | "audio_alternate" | "audio_commentary" | ...

    default_flags:
      set_first_video_default: boolean
      set_preferred_audio_default: boolean

    conditional:
      - name: string
        when: <condition>
        then: [<action>]
        else: [<action>]  # Optional

    audio_synthesis:
      tracks:
        - name: string
          codec: string
          channels: string
          bitrate: string
          skip_if_exists: <skip_condition>
          source:
            prefer: [<source_preference>]

    transcode:
      video:
        target_codec: string
        skip_if: <skip_condition>
        quality: <quality_config>
        hardware_acceleration: <hw_config>
      audio:
        preserve_codecs: [string]
        transcode_to: string
        transcode_bitrate: string

    transcription:
      enabled: boolean
```

### Validation Errors

| Error Code | Description | Example |
|------------|-------------|---------|
| `INVALID_SCHEMA_VERSION` | schema_version is not 11 | `schema_version: 10` |
| `EMPTY_PHASES` | phases array is empty | `phases: []` |
| `DUPLICATE_PHASE_NAME` | Two phases have same name | `name: foo` appears twice |
| `INVALID_PHASE_NAME` | Name doesn't match pattern | `name: "my phase!"` |
| `RESERVED_PHASE_NAME` | Name is reserved word | `name: config` |
| `INVALID_OPERATION` | Operation config invalid | See operation-specific errors |

---

## CLI Contract

### vpo process

```bash
vpo process [OPTIONS] PATHS...

Options:
  -p, --policy PATH       Policy file to use
  -P, --profile NAME      Named profile from config
  --phases NAMES          Comma-separated phase names to run
  -n, --dry-run           Preview changes without applying
  --on-error MODE         Override config.on_error (skip|continue|fail)
  -R, --recursive         Process directories recursively
  -v, --verbose           Verbose output
  --json                  JSON output format
  -h, --help              Show help

Arguments:
  PATHS                   Files or directories to process
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All files processed successfully |
| 1 | Some files failed (with on_error=continue) |
| 2 | Processing aborted (with on_error=fail) |
| 3 | Invalid policy or arguments |

### --phases Behavior

- Accepts comma-separated phase names: `--phases normalize,transcode`
- Names validated against policy's phases list before processing
- Phases execute in **policy-defined order**, not CLI order
- Invalid phase name causes exit code 3 before any processing

### JSON Output Format

```json
{
  "success": true,
  "files_processed": 5,
  "files_succeeded": 4,
  "files_failed": 1,
  "total_duration_seconds": 45.2,
  "results": [
    {
      "file": "/path/to/video.mkv",
      "success": true,
      "phases": [
        {
          "name": "normalize",
          "success": true,
          "duration_seconds": 2.3,
          "operations": ["audio_filter", "subtitle_filter"],
          "changes": 3
        },
        {
          "name": "transcode",
          "success": true,
          "duration_seconds": 120.5,
          "operations": ["transcode"],
          "changes": 1
        }
      ],
      "total_changes": 4
    }
  ]
}
```

---

## Web API Contract

### GET /api/policies/{name}

Returns policy content for editing.

**Response** (200):
```json
{
  "name": "my-policy",
  "content": "schema_version: 11\n...",
  "last_modified": "2025-11-30T14:30:00Z",
  "schema_version": 11,
  "phases": ["normalize", "transcode"]
}
```

### PUT /api/policies/{name}

Updates policy content.

**Request**:
```json
{
  "content": "schema_version: 11\n...",
  "last_modified": "2025-11-30T14:30:00Z"
}
```

**Response** (200):
```json
{
  "success": true,
  "name": "my-policy",
  "last_modified": "2025-11-30T14:35:00Z",
  "phases": ["normalize", "transcode"]
}
```

**Response** (409 - Conflict):
```json
{
  "error": "concurrent_modification",
  "message": "Policy was modified by another user",
  "server_modified": "2025-11-30T14:32:00Z"
}
```

**Response** (400 - Validation Error):
```json
{
  "error": "validation_error",
  "message": "Invalid policy",
  "details": [
    {"path": "phases[0].name", "error": "RESERVED_PHASE_NAME"}
  ]
}
```

### POST /api/policies/{name}/validate

Validates policy without saving.

**Request**:
```json
{
  "content": "schema_version: 11\n..."
}
```

**Response** (200 - Valid):
```json
{
  "valid": true,
  "schema_version": 11,
  "phases": ["normalize", "transcode"],
  "warnings": []
}
```

**Response** (200 - Invalid):
```json
{
  "valid": false,
  "errors": [
    {"path": "phases", "error": "EMPTY_PHASES", "message": "At least one phase required"}
  ]
}
```

---

## Internal Contracts

### PhaseExecutor Protocol

```python
class PhaseExecutor(Protocol):
    """Protocol for phase execution."""

    def execute_phase(
        self,
        phase: PhaseDefinition,
        context: PhaseExecutionContext,
    ) -> PhaseResult:
        """Execute a single phase on a file.

        Args:
            phase: The phase definition to execute
            context: Execution context with file info and state

        Returns:
            PhaseResult with success/failure and details

        Raises:
            PhaseExecutionError: On unrecoverable error
        """
        ...

    def rollback_phase(
        self,
        context: PhaseExecutionContext,
    ) -> bool:
        """Rollback all changes from current phase.

        Args:
            context: Execution context with backup_path

        Returns:
            True if rollback succeeded, False otherwise
        """
        ...
```

### WorkflowProcessor Interface

```python
class WorkflowProcessor:
    """Orchestrates phase execution for files."""

    def __init__(
        self,
        policy: PolicySchema,
        connection: DaemonConnectionPool,
        dry_run: bool = False,
        verbose: bool = False,
        phase_filter: set[str] | None = None,
    ):
        """Initialize processor.

        Args:
            policy: Validated V11 policy
            connection: Database connection pool
            dry_run: If True, don't modify files
            verbose: Enable verbose logging
            phase_filter: If set, only run these phases
        """
        ...

    def process_file(self, file_path: Path) -> FileProcessingResult:
        """Process a single file through all phases.

        Args:
            file_path: Path to media file

        Returns:
            FileProcessingResult with all phase results
        """
        ...
```

---

## Logging Contract

### Phase Logging Format

All phase operations MUST log with these fields:

```python
logger.info(
    "Phase started",
    extra={
        "phase": "normalize",        # Phase name
        "phase_index": 1,            # 1-based index
        "total_phases": 3,           # Total phase count
        "file": "/path/to/file.mkv", # File being processed
        "operations": ["audio_filter", "subtitle_filter"],
    }
)

logger.info(
    "Phase completed",
    extra={
        "phase": "normalize",
        "success": True,
        "duration_seconds": 2.3,
        "changes_made": 3,
    }
)

logger.error(
    "Phase failed",
    extra={
        "phase": "transcode",
        "operation": "transcode",  # Which operation failed
        "error": "Encoder not found",
        "rolling_back": True,
    }
)
```

---

## Error Handling Contract

### PhaseExecutionError

```python
class PhaseExecutionError(Exception):
    """Raised when phase execution fails."""

    def __init__(
        self,
        phase_name: str,
        operation: str | None,
        message: str,
        cause: Exception | None = None,
    ):
        self.phase_name = phase_name
        self.operation = operation
        self.message = message
        self.cause = cause
        super().__init__(f"Phase '{phase_name}' failed: {message}")
```

### Error Recovery Flow

1. Operation raises exception
2. PhaseExecutor catches, wraps in PhaseExecutionError
3. PhaseExecutor calls rollback_phase()
4. WorkflowProcessor receives PhaseResult(success=False)
5. WorkflowProcessor checks on_error mode:
   - `skip`: Return FileProcessingResult(success=False), continue batch
   - `continue`: Log error, proceed to next phase
   - `fail`: Raise BatchProcessingError, halt batch

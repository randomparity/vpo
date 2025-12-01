# Data Model: User-Defined Processing Phases

**Feature**: 037-user-defined-phases
**Date**: 2025-11-30

## Overview

This document defines the data structures for the V11 policy schema with user-defined phases.

## Entities

### GlobalConfig

Global configuration shared across all phases.

```python
@dataclass(frozen=True)
class GlobalConfig:
    """Global configuration available to all phases."""

    # Language preferences (existing)
    audio_language_preference: tuple[str, ...] = ()
    subtitle_language_preference: tuple[str, ...] = ()

    # Track classification (existing)
    commentary_patterns: tuple[str, ...] = (
        "commentary", "director", "audio description"
    )

    # Error handling (moved from WorkflowConfig)
    on_error: Literal["skip", "continue", "fail"] = "continue"

    # Future: additional shared settings
```

**Validation Rules**:
- Language codes should be ISO 639-2/B (3-letter codes)
- on_error must be one of the literal values
- Empty tuples are valid (use defaults)

---

### PhaseDefinition

A single user-defined phase with its operations.

```python
@dataclass(frozen=True)
class PhaseDefinition:
    """A named phase containing zero or more operations."""

    name: str  # User-defined, validated

    # Operations (all optional, at most one of each type)
    container: ContainerConfig | None = None
    audio_filter: AudioFilterConfig | None = None
    subtitle_filter: SubtitleFilterConfig | None = None
    attachment_filter: AttachmentFilterConfig | None = None
    track_order: tuple[str, ...] | None = None
    default_flags: DefaultFlagsConfig | None = None
    conditional: tuple[ConditionalRule, ...] | None = None
    audio_synthesis: AudioSynthesisConfig | None = None
    transcode: TranscodeConfig | None = None
    transcription: TranscriptionConfig | None = None
```

**Validation Rules**:
- `name` must match pattern `^[a-zA-Z][a-zA-Z0-9_-]{0,63}$`
- `name` must not be in reserved words: `config`, `schema_version`, `phases`
- Operations are optional; empty phase is valid (skipped with warning)

**Relationships**:
- Contains 0+ operation configurations
- Referenced by PolicySchema.phases (ordered list)

---

### PolicySchema (V11)

The top-level policy structure for V11.

```python
@dataclass(frozen=True)
class PolicySchema:
    """V11 policy schema with user-defined phases."""

    schema_version: int  # Must be 11
    config: GlobalConfig
    phases: tuple[PhaseDefinition, ...]

    # Computed properties
    @property
    def phase_names(self) -> tuple[str, ...]:
        """Return ordered list of phase names."""
        return tuple(p.name for p in self.phases)

    def get_phase(self, name: str) -> PhaseDefinition | None:
        """Look up phase by name."""
        for phase in self.phases:
            if phase.name == name:
                return phase
        return None
```

**Validation Rules**:
- schema_version must equal 11 (exact match, not minimum)
- phases must have at least one entry
- All phase names must be unique
- Referenced operations use existing V10 validation

**State Transitions**: N/A (immutable after load)

---

### PhaseExecutionContext

Runtime context for phase execution.

```python
@dataclass
class PhaseExecutionContext:
    """Mutable context passed through phase execution."""

    file_path: Path
    file_info: FileInfo  # Current introspection data
    policy: PolicySchema
    current_phase: str
    phase_index: int
    total_phases: int

    # Execution state
    backup_path: Path | None = None
    file_modified: bool = False
    operations_completed: list[str] = field(default_factory=list)

    # Dry-run output
    dry_run: bool = False
    planned_actions: list[PlannedAction] = field(default_factory=list)
```

**State Transitions**:
1. Created at start of file processing
2. `current_phase` updated as each phase begins
3. `file_modified` set when operations change file
4. `file_info` refreshed after modifying phases
5. `backup_path` set at phase start, cleared on commit

---

### PhaseResult

Result of executing a single phase.

```python
@dataclass(frozen=True)
class PhaseResult:
    """Result from executing a single phase."""

    phase_name: str
    success: bool
    duration_seconds: float
    operations_executed: tuple[str, ...]
    changes_made: int
    message: str | None = None
    error: str | None = None

    # For dry-run output
    planned_actions: tuple[PlannedAction, ...] = ()
```

**Validation Rules**:
- If success is False, error should be set
- operations_executed lists only operations that ran (not skipped)

---

### FileProcessingResult (Updated)

Updated result structure for multi-phase processing.

```python
@dataclass(frozen=True)
class FileProcessingResult:
    """Result from processing a file through all phases."""

    file_path: Path
    success: bool
    phase_results: tuple[PhaseResult, ...]
    total_duration_seconds: float
    total_changes: int

    # Summary
    phases_completed: int
    phases_failed: int
    phases_skipped: int

    # Error info
    failed_phase: str | None = None
    error_message: str | None = None
```

---

## Enumerations

### OperationType

Enumeration of valid operation types (replaces ProcessingPhase role).

```python
class OperationType(Enum):
    """Types of operations that can appear in a phase."""

    CONTAINER = "container"
    AUDIO_FILTER = "audio_filter"
    SUBTITLE_FILTER = "subtitle_filter"
    ATTACHMENT_FILTER = "attachment_filter"
    TRACK_ORDER = "track_order"
    DEFAULT_FLAGS = "default_flags"
    CONDITIONAL = "conditional"
    AUDIO_SYNTHESIS = "audio_synthesis"
    TRANSCODE = "transcode"
    TRANSCRIPTION = "transcription"
```

**Canonical Execution Order** (within a phase):
1. CONTAINER
2. AUDIO_FILTER
3. SUBTITLE_FILTER
4. ATTACHMENT_FILTER
5. TRACK_ORDER
6. DEFAULT_FLAGS
7. CONDITIONAL
8. AUDIO_SYNTHESIS
9. TRANSCODE
10. TRANSCRIPTION

---

### OnErrorMode

Error handling modes (unchanged from V9).

```python
class OnErrorMode(Enum):
    """How to handle errors during phase execution."""

    SKIP = "skip"       # Stop processing this file, continue batch
    CONTINUE = "continue"  # Log error, continue to next phase
    FAIL = "fail"       # Stop entire batch processing
```

---

## Pydantic Models (for YAML Validation)

### PhaseModel

Pydantic model for YAML parsing/validation.

```python
class PhaseModel(BaseModel):
    """Pydantic model for phase definition in YAML."""

    name: str = Field(
        ...,
        pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$",
        description="User-defined phase name"
    )

    # Operations (all optional)
    container: ContainerModel | None = None
    audio_filter: AudioFilterModel | None = None
    subtitle_filter: SubtitleFilterModel | None = None
    attachment_filter: AttachmentFilterModel | None = None
    track_order: list[str] | None = None
    default_flags: DefaultFlagsModel | None = None
    conditional: list[ConditionalRuleModel] | None = None
    audio_synthesis: AudioSynthesisModel | None = None
    transcode: TranscodeModel | None = None
    transcription: TranscriptionModel | None = None

    @field_validator("name")
    @classmethod
    def validate_not_reserved(cls, v: str) -> str:
        reserved = {"config", "schema_version", "phases"}
        if v.lower() in reserved:
            raise ValueError(f"Phase name '{v}' is reserved")
        return v
```

### GlobalConfigModel

```python
class GlobalConfigModel(BaseModel):
    """Pydantic model for global config section."""

    audio_language_preference: list[str] = []
    subtitle_language_preference: list[str] = []
    commentary_patterns: list[str] = [
        "commentary", "director", "audio description"
    ]
    on_error: Literal["skip", "continue", "fail"] = "continue"
```

### PolicyModel (V11)

```python
class PolicyModel(BaseModel):
    """Pydantic model for V11 policy validation."""

    schema_version: Literal[11]
    config: GlobalConfigModel = GlobalConfigModel()
    phases: list[PhaseModel] = Field(..., min_length=1)

    @field_validator("phases")
    @classmethod
    def validate_unique_names(cls, v: list[PhaseModel]) -> list[PhaseModel]:
        names = [p.name for p in v]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate phase names: {set(duplicates)}")
        return v
```

---

## Relationships Diagram

```
PolicySchema (V11)
├── config: GlobalConfig
│   ├── audio_language_preference
│   ├── subtitle_language_preference
│   ├── commentary_patterns
│   └── on_error
└── phases: [PhaseDefinition, ...]
    └── PhaseDefinition
        ├── name (unique)
        ├── container?: ContainerConfig
        ├── audio_filter?: AudioFilterConfig
        ├── subtitle_filter?: SubtitleFilterConfig
        ├── attachment_filter?: AttachmentFilterConfig
        ├── track_order?: [str, ...]
        ├── default_flags?: DefaultFlagsConfig
        ├── conditional?: [ConditionalRule, ...]
        ├── audio_synthesis?: AudioSynthesisConfig
        ├── transcode?: TranscodeConfig
        └── transcription?: TranscriptionConfig
```

---

## Migration Notes

### From V10 to V11

V11 is a **breaking change** (per spec FR-011). No automatic migration provided.

**Manual Migration Steps**:
1. Change `schema_version: 10` to `schema_version: 11`
2. Move `workflow.on_error` to `config.on_error`
3. Remove `workflow` section entirely
4. Create `phases` array with named phases
5. Move operations into appropriate phases

**Example V10 → V11**:

```yaml
# V10 (before)
schema_version: 10
audio_language_preference: [eng, und]
workflow:
  phases: [apply, transcode]
  on_error: continue
audio_filter:
  languages: [eng, und]
transcode:
  video:
    target_codec: hevc

# V11 (after)
schema_version: 11
config:
  audio_language_preference: [eng, und]
  on_error: continue
phases:
  - name: normalize
    audio_filter:
      languages: [eng, und]
  - name: transcode
    transcode:
      video:
        target_codec: hevc
```

# Data Model: Conditional Phase Execution

**Feature**: 043-conditional-phases
**Date**: 2025-12-04

## Overview

This document defines the data structures for conditional phase execution, per-phase error handling, and phase dependencies.

## Entities

### PhaseOutcome (Enum)

Represents the outcome of a phase after execution or skip evaluation.

```
PhaseOutcome
├── PENDING     # Not yet evaluated (initial state)
├── COMPLETED   # Phase executed successfully
├── FAILED      # Phase executed but encountered an error
└── SKIPPED     # Phase was skipped (condition, dependency, or error mode)
```

**State Transitions**:
- PENDING → COMPLETED (phase ran successfully)
- PENDING → FAILED (phase ran but failed)
- PENDING → SKIPPED (skip condition matched, dependency unmet, or on_error=skip)

**Usage**: Stored in processor state during execution; used for dependency resolution.

---

### SkipCondition (Dataclass)

Represents a set of conditions that, if any match, cause a phase to be skipped.

```
SkipCondition
├── video_codec: list[str] | None         # Skip if video codec in list
├── audio_codec_exists: str | None        # Skip if audio codec exists
├── subtitle_language_exists: str | None  # Skip if subtitle language exists
├── container: list[str] | None           # Skip if container in list
├── resolution: str | None                # Skip if resolution matches (e.g., "1080p")
├── resolution_under: str | None          # Skip if resolution under threshold
├── file_size_under: str | None           # Skip if file size under (e.g., "5GB")
├── file_size_over: str | None            # Skip if file size over
├── duration_under: str | None            # Skip if duration under (e.g., "30m")
└── duration_over: str | None             # Skip if duration over
```

**Validation Rules**:
- All fields are optional
- At least one field must be set (empty SkipCondition is rejected)
- Size strings: number + unit (B, KB, MB, GB, TB)
- Duration strings: number + unit (s, m, h)
- Resolution strings: "480p", "720p", "1080p", "4k", "2160p"

**Evaluation**: OR semantics - any matching condition causes skip.

---

### RunIfCondition (Dataclass)

Represents a positive condition that must be true for a phase to run.

```
RunIfCondition
├── phase_modified: str | None    # Run only if named phase modified the file
└── phase_completed: str | None   # Run only if named phase completed (future)
```

**Validation Rules**:
- Exactly one field must be set
- Referenced phase must exist in policy
- Referenced phase must appear before this phase in execution order

---

### SkipReason (Dataclass)

Captures why a phase was skipped for logging and JSON output.

```
SkipReason
├── reason_type: SkipReasonType   # Enum: CONDITION, DEPENDENCY, ERROR_MODE, RUN_IF
├── condition_name: str | None    # Which condition matched (for CONDITION type)
├── condition_value: str | None   # What value triggered the skip
├── dependency_name: str | None   # Which dependency failed (for DEPENDENCY type)
└── message: str                  # Human-readable explanation
```

---

### Extended PhaseDefinition

Additions to the existing `PhaseDefinition` dataclass:

```
PhaseDefinition (existing, extended)
├── name: str                              # Existing
├── ... (existing operation fields)
├── skip_when: SkipCondition | None        # NEW: Skip conditions
├── depends_on: tuple[str, ...] | None     # NEW: Phase dependencies
├── run_if: RunIfCondition | None          # NEW: Positive run condition
└── on_error: OnErrorMode | None           # NEW: Override global error handling
```

**Validation Rules**:
- `depends_on` phase names must exist in policy
- `depends_on` cannot include self-reference
- `run_if.phase_modified` must reference earlier phase
- `skip_when` evaluated before `run_if`

---

### Extended PhaseResult

Additions to the existing `PhaseResult` dataclass:

```
PhaseResult (existing, extended)
├── phase_name: str                # Existing
├── success: bool                  # Existing
├── file_modified: bool            # Existing
├── actions: list[ActionResult]    # Existing
├── outcome: PhaseOutcome          # NEW: Explicit outcome enum
├── skip_reason: SkipReason | None # NEW: Why skipped (if skipped)
└── error: str | None              # Existing (populated on failure)
```

---

### DependencyGraph

Internal structure for dependency validation and resolution.

```
DependencyGraph
├── nodes: set[str]                        # Phase names
├── edges: dict[str, set[str]]             # phase -> set of dependencies
├── reverse_edges: dict[str, set[str]]    # dependency -> set of dependents
└── methods:
    ├── add_phase(name: str)
    ├── add_dependency(phase: str, depends_on: str)
    ├── detect_cycle() -> list[str] | None  # Returns cycle path or None
    ├── get_dependencies(phase: str) -> set[str]
    ├── get_dependents(phase: str) -> set[str]
    └── validate_order(phases: list[str]) -> list[str]  # Returns invalid deps
```

**Algorithm**: DFS with coloring (white/gray/black) for cycle detection.

---

## Pydantic Models (for YAML parsing)

### SkipConditionModel

```python
class SkipConditionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_codec: list[str] | None = None
    audio_codec_exists: str | None = None
    subtitle_language_exists: str | None = None
    container: list[str] | None = None
    resolution: str | None = None
    resolution_under: str | None = None
    file_size_under: str | None = None
    file_size_over: str | None = None
    duration_under: str | None = None
    duration_over: str | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "SkipConditionModel":
        # Validate at least one field is set
        ...
```

### RunIfConditionModel

```python
class RunIfConditionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase_modified: str | None = None
    phase_completed: str | None = None

    @model_validator(mode="after")
    def exactly_one_field(self) -> "RunIfConditionModel":
        # Validate exactly one field is set
        ...
```

### Extended PhaseModel

```python
class PhaseModel(BaseModel):
    # Existing fields...
    name: str
    container: ContainerConfigModel | None = None
    # ... other operations ...

    # NEW fields
    skip_when: SkipConditionModel | None = None
    depends_on: list[str] | None = None
    run_if: RunIfConditionModel | None = None
    on_error: Literal["continue", "stop", "skip"] | None = None
```

---

## Relationships

```
Policy (V11PolicySchema)
├── config: GlobalConfig
│   └── on_error: OnErrorMode (default for all phases)
└── phases: list[PhaseDefinition]
    ├── skip_when: SkipCondition → evaluated against FileInfo + TrackInfo
    ├── depends_on: list[str] → references other phase names
    ├── run_if: RunIfCondition → references other phase names
    └── on_error: OnErrorMode → overrides config.on_error

DependencyGraph ← built from all phases' depends_on fields
    └── validated at policy load time (no cycles)

PhaseResult
    ├── outcome: PhaseOutcome ← set after execution/skip
    └── skip_reason: SkipReason ← populated when outcome=SKIPPED
```

---

## State Machine: Phase Execution

```
                    ┌─────────────┐
                    │   PENDING   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
    ┌─────────────┐  ┌───────────┐  ┌──────────┐
    │   SKIPPED   │  │ COMPLETED │  │  FAILED  │
    │ (condition, │  │  (success)│  │ (error)  │
    │  dependency,│  │           │  │          │
    │  run_if,    │  │           │  │          │
    │  on_error)  │  │           │  │          │
    └─────────────┘  └───────────┘  └──────────┘
```

**Evaluation Order**:
1. Check dependency status (all deps must be COMPLETED)
2. Evaluate `skip_when` conditions
3. Evaluate `run_if` conditions
4. Execute phase operations
5. On error: apply `on_error` (phase-level or global)

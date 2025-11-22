# Evaluator API Contract

**Module**: `video_policy_orchestrator.policy.evaluator`
**Purpose**: Pure-function policy evaluation (no IO, no side effects)

## Core Function

### `evaluate_policy`

Evaluates a policy against file tracks and produces an execution plan.

```python
def evaluate_policy(
    file_info: FileInfo,
    tracks: list[TrackInfo],
    policy: PolicySchema,
) -> Plan:
    """
    Evaluate a policy against file tracks to produce an execution plan.

    This is a pure function with no side effects. Given the same inputs,
    it always produces the same output.

    Args:
        file_info: Metadata about the file being evaluated.
        tracks: List of track metadata from introspection.
        policy: Validated policy configuration.

    Returns:
        Plan describing all changes needed to make tracks conform to policy.

    Raises:
        EvaluationError: If evaluation cannot proceed (e.g., no tracks).
    """
```

## Input Types

### FileInfo

```python
@dataclass(frozen=True)
class FileInfo:
    """Minimal file info needed for evaluation."""
    id: str           # UUID
    path: Path        # File path
    container: str    # Container format (mkv, mp4, avi, etc.)
```

### TrackInfo (from 003-media-introspection)

```python
@dataclass(frozen=True)
class TrackInfo:
    track_index: int
    track_type: Literal["video", "audio", "subtitle", "attachment"]
    codec: str
    language: str          # ISO 639-2, "und" if unknown
    title: str | None
    is_default: bool
    is_forced: bool
    channels: int | None   # Audio only
```

### PolicySchema

See `contracts/policy-schema.yaml` for full schema.

## Output Types

### Plan

```python
@dataclass(frozen=True)
class Plan:
    """Immutable execution plan produced by policy evaluation."""

    file_id: str
    file_path: Path
    policy_version: int
    actions: tuple[PlannedAction, ...]
    requires_remux: bool
    created_at: datetime  # UTC

    @property
    def is_empty(self) -> bool:
        """True if no actions needed."""
        return len(self.actions) == 0

    @property
    def summary(self) -> str:
        """Human-readable summary of changes."""
```

### PlannedAction

```python
@dataclass(frozen=True)
class PlannedAction:
    """A single planned change. Immutable."""

    action_type: ActionType
    track_index: int | None  # None for REORDER (file-level)
    track_id: str | None     # Track UID if available
    current_value: Any
    desired_value: Any

    @property
    def description(self) -> str:
        """Human-readable description of this action."""
```

### ActionType

```python
class ActionType(Enum):
    """Types of changes that can be planned."""

    REORDER = "reorder"           # Change track positions
    SET_DEFAULT = "set_default"   # Set default flag to true
    CLEAR_DEFAULT = "clear_default"  # Set default flag to false
    SET_FORCED = "set_forced"     # Set forced flag to true
    CLEAR_FORCED = "clear_forced" # Set forced flag to false
    SET_TITLE = "set_title"       # Change track title
    SET_LANGUAGE = "set_language" # Change language tag
```

## Evaluation Algorithm

### Track Classification

```python
def classify_track(
    track: TrackInfo,
    policy: PolicySchema,
) -> TrackType:
    """
    Classify a track according to policy rules.

    Returns:
        TrackType enum value for sorting.
    """
```

Classification rules:
1. Video tracks → `video`
2. Audio tracks:
   - If title matches commentary_patterns → `audio_commentary`
   - If language in audio_language_preference → `audio_main`
   - Otherwise → `audio_alternate`
3. Subtitle tracks:
   - If title matches commentary_patterns → `subtitle_commentary`
   - If is_forced flag set → `subtitle_forced`
   - Otherwise → `subtitle_main`
4. Attachment tracks → `attachment`

### Ordering Algorithm

```python
def compute_desired_order(
    tracks: list[TrackInfo],
    policy: PolicySchema,
) -> list[int]:
    """
    Compute desired track order according to policy.

    Returns:
        List of track indices in desired order.
    """
```

Sorting key for each track:
1. Primary: Position of track type in `policy.track_order`
2. Secondary (audio_main): Position of language in `audio_language_preference`
3. Secondary (subtitle_main): Position of language in `subtitle_language_preference`
4. Tertiary: Original track index (stable sort)

### Default Flag Algorithm

```python
def compute_default_flags(
    tracks: list[TrackInfo],
    policy: PolicySchema,
) -> dict[int, bool]:
    """
    Compute desired default flag state for each track.

    Returns:
        Dict mapping track_index to desired is_default value.
    """
```

Rules:
1. If `set_first_video_default`: First video track → default=true
2. If `set_preferred_audio_default`: First audio matching language preference → default=true
3. If `set_preferred_subtitle_default`: First subtitle matching language preference → default=true
4. If `clear_other_defaults`: All other tracks of same type → default=false

Edge cases:
- No matching language: Use first non-commentary track of that type
- All tracks are commentary: Use first track
- No tracks of type: Skip that type

## Error Handling

```python
class EvaluationError(Exception):
    """Base class for evaluation errors."""
    pass

class NoTracksError(EvaluationError):
    """File has no tracks to evaluate."""
    pass

class UnsupportedContainerError(EvaluationError):
    """Container format not supported for requested operations."""
    pass
```

## Contract Guarantees

1. **Determinism**: Same inputs always produce same output
2. **Purity**: No side effects, no IO, no randomness
3. **Immutability**: All output objects are frozen dataclasses
4. **Completeness**: Plan contains all actions needed to reach desired state
5. **Idempotence**: Applying plan to already-conforming file produces empty plan

## Usage Example

```python
from video_policy_orchestrator.policy.evaluator import evaluate_policy
from video_policy_orchestrator.policy.loader import load_policy
from video_policy_orchestrator.introspector import get_tracks

# Load inputs
policy = load_policy(Path("~/.vpo/policies/default.yaml"))
file_info = FileInfo(id="abc123", path=Path("movie.mkv"), container="mkv")
tracks = get_tracks(file_info.path)

# Evaluate (pure function)
plan = evaluate_policy(file_info, tracks, policy)

# Inspect results
if plan.is_empty:
    print("No changes needed")
else:
    print(f"Plan requires {len(plan.actions)} changes")
    if plan.requires_remux:
        print("Track reordering needed (will use mkvmerge)")
    for action in plan.actions:
        print(f"  {action.description}")
```

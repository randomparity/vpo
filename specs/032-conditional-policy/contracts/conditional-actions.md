# Contract: Conditional Actions

**Module**: `src/video_policy_orchestrator/policy/actions.py`
**Version**: 1.0.0

## Purpose

Execute conditional actions (skip, warn, fail) and manage skip flags that affect downstream policy processing.

## Interface

### Main Functions

```python
def execute_actions(
    actions: tuple[ConditionalAction, ...],
    context: ActionContext,
) -> ActionResult:
    """
    Execute a sequence of conditional actions.

    Args:
        actions: Tuple of actions to execute in order
        context: Context containing file info for placeholder substitution

    Returns:
        ActionResult with skip_flags and warnings

    Raises:
        ConditionalFailError: If a FailAction is executed

    Behavior:
        - Actions execute in order
        - SkipActions accumulate flags (OR semantics)
        - WarnActions accumulate messages
        - FailAction raises exception immediately (stops processing)
    """

@dataclass(frozen=True)
class ActionContext:
    """Context for action execution and placeholder substitution."""
    filename: str      # Base filename (e.g., "movie.mkv")
    path: Path         # Full file path
    rule_name: str     # Name of the matching rule

@dataclass(frozen=True)
class ActionResult:
    """Result of action execution."""
    skip_flags: SkipFlags
    warnings: tuple[str, ...]
```

### Action Handlers

```python
def handle_skip_action(
    action: SkipAction,
    current_flags: SkipFlags,
) -> SkipFlags:
    """
    Apply a skip action to current flags.

    Returns new SkipFlags with the specified flag set to True.
    Existing True flags remain True (OR accumulation).
    """

def handle_warn_action(
    action: WarnAction,
    context: ActionContext,
) -> str:
    """
    Format a warning message with placeholder substitution.

    Returns the formatted message string.
    Does not raise exceptions.
    """

def handle_fail_action(
    action: FailAction,
    context: ActionContext,
) -> NoReturn:
    """
    Raise a ConditionalFailError with formatted message.

    Always raises; never returns.
    """
```

### Placeholder Substitution

```python
def substitute_placeholders(
    message: str,
    context: ActionContext,
) -> str:
    """
    Replace placeholders in message with context values.

    Supported placeholders:
        {filename}  - Base filename without path
        {path}      - Full file path as string
        {rule_name} - Name of the conditional rule

    Unknown placeholders are left unchanged.
    """
```

## Behavior Specifications

### Skip Actions

| Action | Flag Set | Effect on Processing |
|--------|----------|---------------------|
| `skip_video_transcode: true` | `skip_flags.skip_video_transcode = True` | Video transcode actions skipped in Plan |
| `skip_audio_transcode: true` | `skip_flags.skip_audio_transcode = True` | Audio transcode actions skipped |
| `skip_track_filter: true` | `skip_flags.skip_track_filter = True` | Track filtering bypassed |

**Accumulation**:
```python
# Multiple skip actions in same rule OR across rules
# Flags are OR'd together
actions = [
    SkipAction(SkipType.VIDEO_TRANSCODE),
    SkipAction(SkipType.AUDIO_TRANSCODE),
]
# Result: skip_video_transcode=True, skip_audio_transcode=True
```

### Warn Actions

| Input | Context | Output |
|-------|---------|--------|
| `warn: "Missing English audio in {filename}"` | filename="movie.mkv" | "Missing English audio in movie.mkv" |
| `warn: "Rule {rule_name} matched"` | rule_name="4K check" | "Rule 4K check matched" |
| `warn: "Path: {path}"` | path="/media/movie.mkv" | "Path: /media/movie.mkv" |

**Warning Collection**:
- Warnings accumulate in order of execution
- Multiple warn actions produce multiple warning strings
- Warnings are returned, not logged (caller decides logging)

### Fail Actions

| Input | Context | Exception |
|-------|---------|-----------|
| `fail: "Corrupted: {filename}"` | filename="bad.mkv" | `ConditionalFailError("Corrupted: bad.mkv")` |

**Fail Behavior**:
- Immediately raises `ConditionalFailError`
- Subsequent actions in the rule are NOT executed
- Subsequent rules are NOT evaluated
- Processing of the file stops

## Exception Types

```python
class ConditionalFailError(PolicyError):
    """Raised when a fail action is triggered."""
    def __init__(self, message: str, rule_name: str, file_path: Path):
        self.message = message
        self.rule_name = rule_name
        self.file_path = file_path
        super().__init__(f"Rule '{rule_name}' failed: {message}")
```

## Integration with Plan

The `SkipFlags` from action execution are passed to the plan evaluator:

```python
def evaluate_policy(
    file_id: str,
    file_path: Path,
    container: str,
    tracks: list[TrackInfo],
    policy: PolicySchema,
    skip_flags: SkipFlags = SkipFlags(),  # NEW parameter
) -> Plan:
    """
    Evaluate policy with skip flags from conditional rules.

    Skip flags affect:
    - skip_video_transcode: Omit ActionType.TRANSCODE for video
    - skip_audio_transcode: Omit ActionType.TRANSCODE for audio
    - skip_track_filter: Skip compute_track_dispositions()
    """
```

## Dry-Run Output

Actions should be traceable in dry-run output:

```
=== Conditional Actions ===
Rule "Skip HEVC transcode":
  ✓ skip_video_transcode: true

Rule "Warn on missing audio":
  ⚠ Warning: "No English audio track found in movie.mkv"

Rule "Block corrupted files":
  ✗ Fail: "Video codec unknown - manual review required"
```

## Dependencies

- `SkipFlags` from `policy/models.py`
- `ConditionalAction` types from `policy/models.py`
- `PolicyError` from `policy/exceptions.py`

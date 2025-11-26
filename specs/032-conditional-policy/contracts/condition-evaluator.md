# Contract: Condition Evaluator

**Module**: `src/video_policy_orchestrator/policy/conditions.py`
**Version**: 1.0.0

## Purpose

Evaluate condition expressions against a file's track list to produce a boolean result.

## Interface

### Main Functions

```python
def evaluate_condition(
    condition: Condition,
    tracks: list[TrackInfo],
    depth: int = 0,
) -> bool:
    """
    Evaluate a condition against a list of tracks.

    Args:
        condition: The condition to evaluate (any Condition type)
        tracks: List of TrackInfo from the file being processed
        depth: Current nesting depth (internal, starts at 0)

    Returns:
        True if condition matches, False otherwise

    Raises:
        PolicyValidationError: If nesting depth exceeds 3 levels
        PolicyValidationError: If condition contains invalid track_type

    Invariants:
        - Pure function: same inputs always produce same output
        - No side effects or I/O operations
        - Depth tracking prevents infinite recursion
    """

def evaluate_exists(
    condition: ExistsCondition,
    tracks: list[TrackInfo],
) -> bool:
    """
    Check if at least one track matches the condition criteria.

    Returns True if any track matches ALL specified filters.
    Returns False if no tracks match or track_type has no tracks.
    """

def evaluate_count(
    condition: CountCondition,
    tracks: list[TrackInfo],
) -> bool:
    """
    Count matching tracks and compare against threshold.

    Returns True if count comparison is satisfied.
    Comparison operators: eq, lt, lte, gt, gte
    """

def matches_track(
    track: TrackInfo,
    track_type: str,
    filters: TrackFilters,
) -> bool:
    """
    Check if a single track matches type and all filter criteria.

    Matching rules:
    - track_type must match exactly
    - All specified filters must match (AND semantics)
    - Unspecified filters (None) match any value
    - Codec matching uses alias normalization
    - Language matching uses cross-standard normalization
    """

def compare_value(
    actual: int | None,
    comparison: Comparison,
) -> bool:
    """
    Compare a numeric value against a comparison spec.

    Returns False if actual is None (missing property).
    Operators: eq, lt, lte, gt, gte
    """
```

### Helper Functions

```python
def normalize_codec(codec: str) -> str:
    """Return canonical codec name (e.g., 'h265' -> 'hevc')."""

def codecs_match(a: str, b: str) -> bool:
    """Check if two codec names are equivalent via aliases."""

def get_evaluation_trace(
    condition: Condition,
    tracks: list[TrackInfo],
) -> str:
    """
    Generate human-readable explanation of condition evaluation.

    Used for dry-run output to explain why condition matched/didn't match.
    Example: "exists(video, height >= 2160) → MATCHED (track[0] height=2160)"
    """
```

## Behavior Specifications

### Exists Condition

| Scenario | Input | Expected Result |
|----------|-------|-----------------|
| Track exists matching all criteria | `exists: {track_type: video, height: {gte: 2160}}` with 4K video | True |
| Track exists but wrong type | `exists: {track_type: audio}` with only video tracks | False |
| Track exists but filter fails | `exists: {track_type: video, codec: hevc}` with h264 video | False |
| Empty track list | Any exists condition | False |
| Multiple matching tracks | `exists: {track_type: audio}` with 3 audio tracks | True |

### Count Condition

| Scenario | Input | Expected Result |
|----------|-------|-----------------|
| Exact count match | `count: {track_type: audio, eq: 2}` with 2 audio tracks | True |
| Less than threshold | `count: {track_type: audio, gt: 1}` with 1 audio track | False |
| Greater than threshold | `count: {track_type: subtitle, gte: 3}` with 5 subtitle tracks | True |
| Zero count | `count: {track_type: attachment, eq: 0}` with no attachments | True |

### Boolean Operators

| Operator | Behavior |
|----------|----------|
| `and` | Short-circuit AND: returns False on first False, True if all True |
| `or` | Short-circuit OR: returns True on first True, False if all False |
| `not` | Logical negation of inner condition |

### Nesting Depth

```
Level 0: Top-level condition (exists, count, and, or, not)
Level 1: First nested condition (inside and/or/not)
Level 2: Second nested condition
Level 3: Maximum allowed depth
Level 4+: PolicyValidationError raised
```

Example at depth 3 (valid):
```yaml
and:                    # Level 0
  - or:                 # Level 1
      - not:            # Level 2
          exists: ...   # Level 3 (ExistsCondition is terminal)
```

### Codec Alias Matching

When `codec` filter is specified:
1. Normalize both filter codec and track codec to canonical form
2. Compare canonical forms
3. If filter is a list, match if any alias matches

Example:
```yaml
codec: [hevc, h265, x265]  # All match a track with codec "hvc1"
```

### Language Matching

Reuses existing `languages_match()` from evaluator.py:
- Handles ISO 639-1, 639-2/B, 639-2/T codes
- "eng" matches "en", "English", etc.
- "und" (undefined) never matches specific languages

## Error Handling

| Error | Condition | Message |
|-------|-----------|---------|
| PolicyValidationError | Nesting depth > 3 | "Condition nesting exceeds maximum depth of 3" |
| PolicyValidationError | Unknown track_type | "Unknown track_type: '{value}' (expected: video, audio, subtitle, attachment)" |
| PolicyValidationError | Invalid comparison operator | "Invalid comparison operator: '{op}'" |

## Dependencies

- `TrackInfo` from `db/models.py`
- `languages_match()` from `policy/evaluator.py`
- Condition dataclasses from `policy/models.py`

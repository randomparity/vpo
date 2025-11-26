# Quickstart: Conditional Policy Logic

**Feature**: 032-conditional-policy
**Time to First Test**: ~30 minutes

## Prerequisites

- VPO development environment set up (`uv pip install -e ".[dev]"`)
- Existing tests passing (`uv run pytest`)
- Understanding of VPO policy system (see `docs/usage/policies.md`)

## Implementation Order

### Step 1: Define Data Models (15 min)

Create condition and action dataclasses in `policy/models.py`:

```python
# Add to policy/models.py

from enum import Enum
from dataclasses import dataclass, field
from typing import Literal

class ComparisonOperator(Enum):
    EQ = "eq"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"

@dataclass(frozen=True)
class Comparison:
    operator: ComparisonOperator
    value: int

@dataclass(frozen=True)
class TrackFilters:
    language: str | tuple[str, ...] | None = None
    codec: str | tuple[str, ...] | None = None
    is_default: bool | None = None
    is_forced: bool | None = None
    channels: int | Comparison | None = None
    width: int | Comparison | None = None
    height: int | Comparison | None = None

@dataclass(frozen=True)
class ExistsCondition:
    track_type: str
    filters: TrackFilters = field(default_factory=TrackFilters)

# ... (see data-model.md for complete definitions)
```

### Step 2: Write First Test (10 min)

Create `tests/unit/policy/test_conditions.py`:

```python
import pytest
from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.policy.conditions import evaluate_condition
from video_policy_orchestrator.policy.models import (
    ExistsCondition,
    TrackFilters,
    Comparison,
    ComparisonOperator,
)

def make_video_track(height: int = 1080, codec: str = "h264") -> TrackInfo:
    return TrackInfo(
        index=0,
        track_type="video",
        codec=codec,
        language=None,
        title=None,
        is_default=True,
        is_forced=False,
        channels=None,
        channel_layout=None,
        width=height * 16 // 9,
        height=height,
        frame_rate="24000/1001",
    )

class TestExistsCondition:
    def test_exists_video_true(self):
        tracks = [make_video_track()]
        condition = ExistsCondition(track_type="video", filters=TrackFilters())

        result = evaluate_condition(condition, tracks)

        assert result is True

    def test_exists_video_with_height_filter(self):
        tracks = [make_video_track(height=2160)]
        condition = ExistsCondition(
            track_type="video",
            filters=TrackFilters(
                height=Comparison(ComparisonOperator.GTE, 2160)
            ),
        )

        result = evaluate_condition(condition, tracks)

        assert result is True

    def test_exists_no_match(self):
        tracks = [make_video_track(height=1080)]
        condition = ExistsCondition(
            track_type="video",
            filters=TrackFilters(
                height=Comparison(ComparisonOperator.GTE, 2160)
            ),
        )

        result = evaluate_condition(condition, tracks)

        assert result is False
```

### Step 3: Implement Condition Evaluator (20 min)

Create `policy/conditions.py`:

```python
"""Condition evaluation for conditional policy rules."""

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.policy.models import (
    Condition,
    ExistsCondition,
    CountCondition,
    AndCondition,
    OrCondition,
    NotCondition,
    TrackFilters,
    Comparison,
    ComparisonOperator,
)
from video_policy_orchestrator.policy.exceptions import PolicyValidationError

MAX_NESTING_DEPTH = 3

def evaluate_condition(
    condition: Condition,
    tracks: list[TrackInfo],
    depth: int = 0,
) -> bool:
    """Evaluate a condition against tracks."""
    if depth > MAX_NESTING_DEPTH:
        raise PolicyValidationError(
            f"Condition nesting exceeds maximum depth of {MAX_NESTING_DEPTH}"
        )

    match condition:
        case ExistsCondition():
            return _evaluate_exists(condition, tracks)
        case CountCondition():
            return _evaluate_count(condition, tracks)
        case AndCondition():
            return all(
                evaluate_condition(c, tracks, depth + 1)
                for c in condition.conditions
            )
        case OrCondition():
            return any(
                evaluate_condition(c, tracks, depth + 1)
                for c in condition.conditions
            )
        case NotCondition():
            return not evaluate_condition(condition.inner, tracks, depth + 1)
        case _:
            raise PolicyValidationError(f"Unknown condition type: {type(condition)}")


def _evaluate_exists(condition: ExistsCondition, tracks: list[TrackInfo]) -> bool:
    """Check if any track matches the condition."""
    return any(
        _matches_track(track, condition.track_type, condition.filters)
        for track in tracks
    )


def _matches_track(
    track: TrackInfo,
    track_type: str,
    filters: TrackFilters,
) -> bool:
    """Check if a track matches type and filters."""
    if track.track_type != track_type:
        return False

    if filters.height is not None:
        if not _compare_value(track.height, filters.height):
            return False

    # Add other filter checks...
    return True


def _compare_value(actual: int | None, comparison: int | Comparison) -> bool:
    """Compare actual value against comparison spec."""
    if actual is None:
        return False

    if isinstance(comparison, int):
        return actual == comparison

    match comparison.operator:
        case ComparisonOperator.EQ:
            return actual == comparison.value
        case ComparisonOperator.LT:
            return actual < comparison.value
        case ComparisonOperator.LTE:
            return actual <= comparison.value
        case ComparisonOperator.GT:
            return actual > comparison.value
        case ComparisonOperator.GTE:
            return actual >= comparison.value
```

### Step 4: Run Test

```bash
uv run pytest tests/unit/policy/test_conditions.py -v
```

Expected output:
```
tests/unit/policy/test_conditions.py::TestExistsCondition::test_exists_video_true PASSED
tests/unit/policy/test_conditions.py::TestExistsCondition::test_exists_video_with_height_filter PASSED
tests/unit/policy/test_conditions.py::TestExistsCondition::test_exists_no_match PASSED
```

## Development Checkpoints

| Checkpoint | Tests | Files Modified |
|------------|-------|----------------|
| 1. Models compile | N/A | `policy/models.py` |
| 2. ExistsCondition works | 3 tests | `policy/conditions.py` |
| 3. CountCondition works | 3 tests | `policy/conditions.py` |
| 4. Boolean operators work | 6 tests | `policy/conditions.py` |
| 5. Nesting depth enforced | 2 tests | `policy/conditions.py` |
| 6. Actions execute | 5 tests | `policy/actions.py` |
| 7. Rule evaluation | 5 tests | `policy/evaluator.py` |
| 8. Pydantic validation | 8 tests | `policy/validation.py` |
| 9. Schema v4 loads | 3 tests | `policy/loader.py` |
| 10. Integration test | 3 tests | `tests/integration/` |

## Key Files Reference

| File | Purpose |
|------|---------|
| `policy/models.py` | Dataclass definitions for conditions, actions, rules |
| `policy/conditions.py` | Condition evaluation logic |
| `policy/actions.py` | Action execution (skip, warn, fail) |
| `policy/validation.py` | Pydantic models for YAML validation |
| `policy/loader.py` | Policy loading, schema version check |
| `policy/evaluator.py` | Integration with plan generation |

## Example Policy for Testing

Save as `tests/fixtures/policies/conditional-test.yaml`:

```yaml
schema_version: 4
track_order: [video, audio, subtitle]

conditional:
  - name: "Skip HEVC transcode"
    when:
      exists:
        track_type: video
        codec: [hevc, h265, x265]
    then:
      - skip_video_transcode: true

  - name: "Warn on missing English"
    when:
      not:
        exists:
          track_type: audio
          language: eng
    then:
      - warn: "No English audio in {filename}"

audio_language_preference: [eng, jpn]
subtitle_language_preference: [eng]
```

## Troubleshooting

### Import Error
```
ModuleNotFoundError: No module named 'video_policy_orchestrator.policy.conditions'
```
→ Create `policy/conditions.py` file

### Pydantic Validation Error
```
ValidationError: 1 validation error for ConditionModel
```
→ Check YAML syntax matches Pydantic model (use `alias="and"` for reserved words)

### Type Error in Match Statement
```
TypeError: match requires Python 3.10+
```
→ Ensure using Python 3.10+ (`python --version`)

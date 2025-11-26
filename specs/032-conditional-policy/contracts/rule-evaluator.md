# Contract: Rule Evaluator

**Module**: `src/video_policy_orchestrator/policy/evaluator.py` (extended)
**Version**: 1.0.0

## Purpose

Evaluate conditional rules against a file's tracks and execute matching actions. Integrates with the existing policy evaluation flow.

## Interface

### Main Functions

```python
def evaluate_conditional_rules(
    rules: tuple[ConditionalRule, ...],
    tracks: list[TrackInfo],
    file_path: Path,
) -> ConditionalResult:
    """
    Evaluate conditional rules and execute matching actions.

    Args:
        rules: Tuple of ConditionalRule from PolicySchema
        tracks: List of TrackInfo from the file
        file_path: Path to the file being processed

    Returns:
        ConditionalResult with matched rule, skip flags, warnings, and trace

    Raises:
        ConditionalFailError: If a matched rule has a fail action

    Behavior:
        - Rules are evaluated in document order
        - First rule whose 'when' condition matches wins
        - Execute 'then' actions for matched rule
        - If no rules match, check last rule for 'else' clause
        - Generate evaluation trace for all rules (for dry-run)
    """

def integrate_conditional_result(
    plan: Plan,
    result: ConditionalResult,
) -> Plan:
    """
    Merge conditional result into a Plan.

    Returns new Plan with:
        - conditional_result field populated
        - skip_flags field populated
        - Any skip flags applied to actions tuple
    """
```

### Extended evaluate_policy

```python
def evaluate_policy(
    file_id: str,
    file_path: Path,
    container: str,
    tracks: list[TrackInfo],
    policy: PolicySchema,
    transcription_results: dict[int, TranscriptionResultRecord] | None = None,
) -> Plan:
    """
    Evaluate policy including conditional rules.

    Extended flow:
    1. If policy has conditional_rules:
       a. evaluate_conditional_rules()
       b. If ConditionalFailError raised, propagate
       c. Extract skip_flags from result
    2. If skip_flags.skip_track_filter is False:
       a. compute_track_dispositions()
    3. Continue with track ordering, default flags, etc.
    4. If skip_flags.skip_video_transcode is True:
       a. Omit video transcode actions
    5. Build and return Plan with conditional_result
    """
```

## Behavior Specifications

### Rule Evaluation Order

```
Given rules: [R1, R2, R3]

Evaluate R1.when:
  - If True: Execute R1.then, return (matched=R1, branch="then")
  - If False: Continue to R2

Evaluate R2.when:
  - If True: Execute R2.then, return (matched=R2, branch="then")
  - If False: Continue to R3

Evaluate R3.when:
  - If True: Execute R3.then, return (matched=R3, branch="then")
  - If False:
    - If R3.else exists: Execute R3.else, return (matched=R3, branch="else")
    - Else: return (matched=None, branch=None)
```

### First-Match-Wins Semantics

| Rules | Track State | Result |
|-------|-------------|--------|
| R1: height>=2160→skip, R2: hevc→warn | 4K HEVC video | R1 matches, R2 not evaluated |
| R1: height>=2160→skip, R2: hevc→warn | 1080p HEVC video | R1 fails, R2 matches |
| R1: height>=2160→skip, R2: hevc→warn | 1080p h264 video | R1 fails, R2 fails, no match |

### Else Clause Handling

The `else` clause only applies to the **last rule** that was evaluated:

```yaml
conditional:
  - name: "Rule A"
    when: { exists: { track_type: video, height: { gte: 2160 } } }
    then:
      skip_video_transcode: true
    else:
      warn: "Not 4K"  # Only executes if Rule A's condition is False
```

If Rule A matches, its `then` executes. If Rule A doesn't match and has `else`, the `else` executes.

**Important**: If there are multiple rules and the first matches, later rules' `else` clauses are NOT executed.

### Evaluation Trace

For dry-run output, generate trace for ALL rules (not just matched):

```python
@dataclass(frozen=True)
class RuleEvaluation:
    rule_name: str
    matched: bool
    reason: str  # e.g., "exists(video, height>=2160) → True (track[0] height=2160)"
    actions_executed: tuple[str, ...]  # e.g., ("skip_video_transcode",)
```

### Skip Flag Application

Skip flags modify subsequent plan generation:

| Flag | Effect |
|------|--------|
| `skip_video_transcode` | Remove `PlannedAction(action_type=TRANSCODE)` where track is video |
| `skip_audio_transcode` | Remove `PlannedAction(action_type=TRANSCODE)` where track is audio |
| `skip_track_filter` | Skip `compute_track_dispositions()`, keep all tracks |

## Data Structures

```python
@dataclass(frozen=True)
class ConditionalResult:
    """Complete result of conditional rule evaluation."""
    matched_rule: str | None        # Name of first matching rule
    matched_branch: Literal["then", "else"] | None
    skip_flags: SkipFlags           # Accumulated skip flags
    warnings: tuple[str, ...]       # Warning messages from warn actions
    evaluation_trace: tuple[RuleEvaluation, ...]  # For dry-run

@dataclass(frozen=True)
class RuleEvaluation:
    """Trace of evaluating a single rule."""
    rule_name: str
    condition_trace: str            # Human-readable condition evaluation
    matched: bool
    branch_executed: Literal["then", "else"] | None
    actions_executed: tuple[str, ...]
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No rules in policy | Return empty ConditionalResult |
| All rules fail to match | Return ConditionalResult(matched_rule=None) |
| Rule has fail action | Raise ConditionalFailError, stop evaluation |
| Invalid condition in rule | PolicyValidationError at load time (not evaluation time) |

## Integration Example

```python
# In evaluate_policy():
conditional_result = None
skip_flags = SkipFlags()

if policy.conditional_rules:
    conditional_result = evaluate_conditional_rules(
        rules=policy.conditional_rules,
        tracks=tracks,
        file_path=file_path,
    )
    skip_flags = conditional_result.skip_flags

# Apply skip_track_filter
if not skip_flags.skip_track_filter:
    track_dispositions = compute_track_dispositions(tracks, policy)
else:
    track_dispositions = tuple(
        TrackDisposition(
            track_index=t.index,
            track_type=t.track_type,
            codec=t.codec,
            language=t.language,
            action="KEEP",
            reason="Track filtering skipped by conditional rule",
        )
        for t in tracks
    )

# ... continue with ordering, flags, etc. ...

# Apply skip_video_transcode to final actions
if skip_flags.skip_video_transcode:
    actions = tuple(
        a for a in actions
        if not (a.action_type == ActionType.TRANSCODE and is_video_track(a.track_index))
    )

return Plan(
    # ... existing fields ...
    conditional_result=conditional_result,
    skip_flags=skip_flags,
)
```

## Dependencies

- `evaluate_condition()` from `policy/conditions.py`
- `execute_actions()` from `policy/actions.py`
- `ConditionalRule`, `SkipFlags` from `policy/models.py`
- `TrackInfo` from `db/models.py`

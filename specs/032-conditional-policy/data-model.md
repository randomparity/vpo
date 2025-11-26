# Data Model: Conditional Policy Logic

**Feature**: 032-conditional-policy
**Date**: 2025-11-26
**Schema Version**: 4 (extends v3)

## Entity Overview

```
PolicySchema (v4)
├── conditional_rules: tuple[ConditionalRule, ...]
│   └── ConditionalRule
│       ├── name: str
│       ├── when: Condition
│       ├── then_actions: tuple[ConditionalAction, ...]
│       └── else_actions: tuple[ConditionalAction, ...] | None
│
├── Condition (union type)
│   ├── ExistsCondition
│   │   ├── track_type: str
│   │   └── filters: TrackFilters
│   ├── CountCondition
│   │   ├── track_type: str
│   │   ├── filters: TrackFilters
│   │   └── comparison: Comparison
│   ├── AndCondition
│   │   └── conditions: tuple[Condition, ...]
│   ├── OrCondition
│   │   └── conditions: tuple[Condition, ...]
│   └── NotCondition
│       └── inner: Condition
│
└── ConditionalAction (union type)
    ├── SkipAction
    │   └── skip_type: SkipType
    ├── WarnAction
    │   └── message: str
    └── FailAction
        └── message: str

Plan (extended)
├── conditional_result: ConditionalResult | None
└── skip_flags: SkipFlags
```

## Domain Models (dataclasses)

### ConditionalRule

```python
@dataclass(frozen=True)
class ConditionalRule:
    """A named rule with condition and actions."""
    name: str
    when: Condition
    then_actions: tuple[ConditionalAction, ...]
    else_actions: tuple[ConditionalAction, ...] | None = None
```

**Validation Rules**:
- `name` must be non-empty string
- `when` must be a valid Condition
- `then_actions` must have at least one action
- `else_actions` is optional

### Condition Types

```python
@dataclass(frozen=True)
class ExistsCondition:
    """Check if at least one track matches criteria."""
    track_type: str  # "video", "audio", "subtitle", "attachment"
    filters: TrackFilters

@dataclass(frozen=True)
class CountCondition:
    """Check count of matching tracks against threshold."""
    track_type: str
    filters: TrackFilters
    operator: ComparisonOperator
    value: int

@dataclass(frozen=True)
class AndCondition:
    """All sub-conditions must be true."""
    conditions: tuple[Condition, ...]

@dataclass(frozen=True)
class OrCondition:
    """At least one sub-condition must be true."""
    conditions: tuple[Condition, ...]

@dataclass(frozen=True)
class NotCondition:
    """Negate a condition."""
    inner: Condition

# Type alias for union
Condition = ExistsCondition | CountCondition | AndCondition | OrCondition | NotCondition
```

### TrackFilters

```python
@dataclass(frozen=True)
class TrackFilters:
    """Criteria for matching track properties."""
    language: str | tuple[str, ...] | None = None
    codec: str | tuple[str, ...] | None = None
    is_default: bool | None = None
    is_forced: bool | None = None
    channels: int | Comparison | None = None
    width: int | Comparison | None = None
    height: int | Comparison | None = None
    title: str | TitleMatch | None = None

@dataclass(frozen=True)
class Comparison:
    """Numeric comparison with operator."""
    operator: ComparisonOperator
    value: int

@dataclass(frozen=True)
class TitleMatch:
    """String matching for title field."""
    contains: str | None = None
    regex: str | None = None

class ComparisonOperator(Enum):
    EQ = "eq"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
```

### ConditionalAction Types

```python
class SkipType(Enum):
    VIDEO_TRANSCODE = "skip_video_transcode"
    AUDIO_TRANSCODE = "skip_audio_transcode"
    TRACK_FILTER = "skip_track_filter"

@dataclass(frozen=True)
class SkipAction:
    """Set a skip flag to suppress later processing."""
    skip_type: SkipType

@dataclass(frozen=True)
class WarnAction:
    """Log a warning message and continue."""
    message: str  # Supports {filename}, {path}, {rule_name} placeholders

@dataclass(frozen=True)
class FailAction:
    """Stop processing with an error."""
    message: str  # Supports placeholders

# Type alias for union
ConditionalAction = SkipAction | WarnAction | FailAction
```

### Plan Extensions

```python
@dataclass(frozen=True)
class SkipFlags:
    """Flags set by conditional rules to suppress operations."""
    skip_video_transcode: bool = False
    skip_audio_transcode: bool = False
    skip_track_filter: bool = False

@dataclass(frozen=True)
class ConditionalResult:
    """Result of conditional rule evaluation."""
    matched_rule: str | None  # Name of first matching rule, None if no match
    matched_branch: Literal["then", "else"] | None
    warnings: tuple[str, ...]  # Formatted warning messages
    evaluation_trace: tuple[RuleEvaluation, ...]  # For dry-run output

@dataclass(frozen=True)
class RuleEvaluation:
    """Trace of a single rule's evaluation."""
    rule_name: str
    matched: bool
    reason: str  # Human-readable explanation

# Extended Plan
@dataclass(frozen=True)
class Plan:
    # Existing fields...
    file_id: str
    file_path: Path
    policy_version: int
    actions: tuple[PlannedAction, ...]
    requires_remux: bool
    track_dispositions: tuple[TrackDisposition, ...]
    container_change: ContainerChange | None
    tracks_removed: int
    tracks_kept: int

    # New fields for Sprint 2
    conditional_result: ConditionalResult | None = None
    skip_flags: SkipFlags = field(default_factory=SkipFlags)
```

## Pydantic Validation Models

```python
class TrackFiltersModel(BaseModel):
    """Pydantic model for track filter validation."""
    language: str | list[str] | None = None
    codec: str | list[str] | None = None
    is_default: bool | None = None
    is_forced: bool | None = None
    channels: int | dict[str, int] | None = None
    width: int | dict[str, int] | None = None
    height: int | dict[str, int] | None = None
    title: str | dict[str, str] | None = None

class ConditionModel(BaseModel):
    """Pydantic model for condition validation."""
    exists: dict[str, Any] | None = None
    count: dict[str, Any] | None = None
    and_: list["ConditionModel"] | None = Field(None, alias="and")
    or_: list["ConditionModel"] | None = Field(None, alias="or")
    not_: "ConditionModel" | None = Field(None, alias="not")

    @model_validator(mode="after")
    def exactly_one_condition_type(self) -> "ConditionModel":
        set_fields = sum(1 for f in [self.exists, self.count, self.and_, self.or_, self.not_] if f is not None)
        if set_fields != 1:
            raise ValueError("Condition must have exactly one of: exists, count, and, or, not")
        return self

class ConditionalActionModel(BaseModel):
    """Pydantic model for action validation."""
    skip_video_transcode: bool | None = None
    skip_audio_transcode: bool | None = None
    skip_track_filter: bool | None = None
    warn: str | None = None
    fail: str | None = None

class ConditionalRuleModel(BaseModel):
    """Pydantic model for rule validation."""
    name: str
    when: ConditionModel
    then_: list[ConditionalActionModel] = Field(..., alias="then")
    else_: list[ConditionalActionModel] | None = Field(None, alias="else")

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Rule name cannot be empty")
        return v

class PolicyModelV4(PolicyModelV3):
    """Extended policy model for schema v4."""
    conditional: list[ConditionalRuleModel] | None = None
```

## Codec Alias Map

```python
CODEC_ALIASES: dict[str, set[str]] = {
    "hevc": {"hevc", "h265", "x265", "hvc1", "hev1"},
    "avc": {"avc", "h264", "x264", "avc1"},
    "aac": {"aac", "mp4a", "mp4a-40-2"},
    "ac3": {"ac3", "a52", "ac-3"},
    "eac3": {"eac3", "ec-3", "ec3"},
    "dts": {"dts", "dca"},
    "truehd": {"truehd", "mlp"},
    "flac": {"flac"},
    "opus": {"opus"},
    "vorbis": {"vorbis"},
}

def normalize_codec(codec: str) -> str:
    """Return canonical codec name for alias matching."""
    codec_lower = codec.lower()
    for canonical, aliases in CODEC_ALIASES.items():
        if codec_lower in aliases:
            return canonical
    return codec_lower
```

## State Transitions

### Condition Evaluation State

```
Initial: Condition tree parsed
    ↓
Evaluate: Recursive descent through tree
    ↓
For each node:
    - ExistsCondition → scan tracks, return bool
    - CountCondition → count matches, compare, return bool
    - AndCondition → evaluate all children, return all()
    - OrCondition → evaluate all children, return any()
    - NotCondition → evaluate child, return not
    ↓
Final: bool result + evaluation trace
```

### Rule Matching State

```
Initial: List of ConditionalRule
    ↓
For each rule (in order):
    - Evaluate when condition
    - If True: execute then_actions, STOP (first-match-wins)
    - If False: continue to next rule
    ↓
After all rules:
    - If no match and last rule has else: execute else_actions
    - Otherwise: no conditional actions
    ↓
Final: ConditionalResult with matched rule, branch, warnings
```

## Relationships

```
PolicySchema (1) ──contains──> (0..*) ConditionalRule
ConditionalRule (1) ──has──> (1) Condition (when)
ConditionalRule (1) ──has──> (1..*) ConditionalAction (then)
ConditionalRule (1) ──has──> (0..*) ConditionalAction (else)

Condition ──composes──> Condition (recursive for and/or/not)
Condition ──references──> TrackFilters (for exists/count)

Plan (1) ──has──> (0..1) ConditionalResult
Plan (1) ──has──> (1) SkipFlags

ConditionalResult (1) ──has──> (0..*) RuleEvaluation (trace)
```

## Schema Version Migration

### v3 → v4 Changes

**Added Fields**:
- `PolicySchema.conditional_rules: tuple[ConditionalRule, ...]`
- `Plan.conditional_result: ConditionalResult | None`
- `Plan.skip_flags: SkipFlags`

**Backward Compatibility**:
- v3 policies remain valid (conditional_rules defaults to empty tuple)
- Existing v3 policies work unchanged
- New `conditional` section requires `schema_version: 4`

**Validation**:
```python
MAX_SCHEMA_VERSION = 4

def validate_schema_version(policy: dict) -> None:
    version = policy.get("schema_version", 1)
    if "conditional" in policy and version < 4:
        raise PolicyValidationError(
            "The 'conditional' section requires schema_version >= 4"
        )
```

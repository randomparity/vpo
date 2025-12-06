# Contract: Policy Conditions

**Feature**: 044-audio-track-classification
**Date**: 2025-12-05
**Module**: `policy/models.py`, `policy/conditions.py`

## Overview

This contract defines the new policy condition types for audio track classification.

---

## Condition Types

### IsOriginalCondition

Check if an audio track is classified as the original (theatrical) audio.

**Dataclass Definition**:

```python
@dataclass(frozen=True)
class IsOriginalCondition:
    """Check if audio track is classified as original (not dubbed).

    Evaluates to True if track's original_dubbed_status is 'original'
    and confidence meets threshold.

    Attributes:
        language: Optional language filter (ISO 639-2).
        min_confidence: Minimum confidence threshold (default 0.7).
    """
    language: str | None = None
    min_confidence: float = 0.7
```

**YAML Syntax**:

```yaml
# Boolean shorthand
is_original: true

# With language filter
is_original:
  language: jpn

# With confidence threshold
is_original:
  min_confidence: 0.8

# With both
is_original:
  language: eng
  min_confidence: 0.9
```

**Evaluation Logic**:

```python
def evaluate_is_original(
    condition: IsOriginalCondition,
    classification: TrackClassificationResult | None,
) -> tuple[bool, str]:
    """
    Evaluate is_original condition.

    Returns:
        (result, reason) tuple where result is True if track is original.
    """
    if classification is None:
        return (False, "Track has no classification result")

    if classification.original_dubbed_status != OriginalDubbedStatus.ORIGINAL:
        return (False, f"Track is {classification.original_dubbed_status.value}")

    if classification.confidence < condition.min_confidence:
        return (
            False,
            f"Confidence {classification.confidence:.1%} below threshold "
            f"{condition.min_confidence:.1%}",
        )

    if condition.language and classification.language != condition.language:
        return (
            False,
            f"Language {classification.language} does not match {condition.language}",
        )

    return (True, "Track is classified as original")
```

---

### IsDubbedCondition

Check if an audio track is classified as a dubbed version.

**Dataclass Definition**:

```python
@dataclass(frozen=True)
class IsDubbedCondition:
    """Check if audio track is classified as dubbed.

    Evaluates to True if track's original_dubbed_status is 'dubbed'
    and confidence meets threshold.

    Attributes:
        original_language: Optional filter for what the track is dubbed from.
        min_confidence: Minimum confidence threshold (default 0.7).
    """
    original_language: str | None = None
    min_confidence: float = 0.7
```

**YAML Syntax**:

```yaml
# Boolean shorthand
is_dubbed: true

# With original language filter (track is dubbed FROM this language)
is_dubbed:
  original_language: jpn  # English dub of Japanese anime

# With confidence threshold
is_dubbed:
  min_confidence: 0.8
```

**Evaluation Logic**:

```python
def evaluate_is_dubbed(
    condition: IsDubbedCondition,
    classification: TrackClassificationResult | None,
    original_language: str | None,  # Detected original language for the file
) -> tuple[bool, str]:
    """
    Evaluate is_dubbed condition.

    Returns:
        (result, reason) tuple where result is True if track is dubbed.
    """
    if classification is None:
        return (False, "Track has no classification result")

    if classification.original_dubbed_status != OriginalDubbedStatus.DUBBED:
        return (False, f"Track is {classification.original_dubbed_status.value}")

    if classification.confidence < condition.min_confidence:
        return (
            False,
            f"Confidence {classification.confidence:.1%} below threshold",
        )

    if condition.original_language:
        if original_language != condition.original_language:
            return (
                False,
                f"Original language {original_language} does not match "
                f"{condition.original_language}",
            )

    return (True, "Track is classified as dubbed")
```

---

## Pydantic Models

### IsOriginalModel

```python
class IsOriginalModel(BaseModel):
    """Pydantic model for is_original condition validation."""
    model_config = ConfigDict(extra="forbid")

    language: str | None = None
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
```

### IsDubbedModel

```python
class IsDubbedModel(BaseModel):
    """Pydantic model for is_dubbed condition validation."""
    model_config = ConfigDict(extra="forbid")

    original_language: str | None = None
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
```

---

## Conversion Functions

### _convert_is_original

```python
def _convert_is_original(
    value: bool | dict,
) -> IsOriginalCondition:
    """
    Convert YAML is_original value to IsOriginalCondition.

    Args:
        value: Boolean True or dict with options.

    Returns:
        IsOriginalCondition instance.
    """
    if value is True:
        return IsOriginalCondition()

    model = IsOriginalModel.model_validate(value)
    return IsOriginalCondition(
        language=model.language,
        min_confidence=model.min_confidence,
    )
```

### _convert_is_dubbed

```python
def _convert_is_dubbed(
    value: bool | dict,
) -> IsDubbedCondition:
    """
    Convert YAML is_dubbed value to IsDubbedCondition.

    Args:
        value: Boolean True or dict with options.

    Returns:
        IsDubbedCondition instance.
    """
    if value is True:
        return IsDubbedCondition()

    model = IsDubbedModel.model_validate(value)
    return IsDubbedCondition(
        original_language=model.original_language,
        min_confidence=model.min_confidence,
    )
```

---

## Integration with Existing Conditions

### Condition Union Type

```python
# In policy/models.py
Condition = Union[
    ExistsCondition,
    CountCondition,
    AudioIsMultiLanguageCondition,
    IsOriginalCondition,      # NEW
    IsDubbedCondition,        # NEW
    AndCondition,
    OrCondition,
    NotCondition,
]
```

### ConditionModel Extension

```python
# In policy/loader.py
class ConditionModel(BaseModel):
    exists: TrackFiltersModel | None = None
    count: CountConditionModel | None = None
    audio_is_multi_language: AudioIsMultiLanguageModel | bool | None = None
    is_original: IsOriginalModel | bool | None = None      # NEW
    is_dubbed: IsDubbedModel | bool | None = None          # NEW
    and_: list["ConditionModel"] | None = Field(default=None, alias="and")
    or_: list["ConditionModel"] | None = Field(default=None, alias="or")
    not_: "ConditionModel | None" = Field(default=None, alias="not")
```

### evaluate_condition Extension

```python
# In policy/conditions.py
def evaluate_condition(
    condition: Condition,
    tracks: list[TrackInfo],
    language_results: dict[int, LanguageAnalysisResult] | None = None,
    classification_results: dict[int, TrackClassificationResult] | None = None,  # NEW
) -> tuple[bool, str]:
    """Evaluate a condition against tracks."""
    if isinstance(condition, IsOriginalCondition):
        # Find matching track and evaluate
        for track in tracks:
            if track.id and classification_results:
                result = classification_results.get(track.id)
                match, reason = evaluate_is_original(condition, result)
                if match:
                    return (True, reason)
        return (False, "No track matches is_original condition")

    if isinstance(condition, IsDubbedCondition):
        # Similar logic for is_dubbed
        ...
```

---

## Policy Examples

### Basic Original/Dubbed Preference

```yaml
schema_version: 12

audio:
  order:
    - is_original: true  # Original tracks first
    - "*"
  default:
    is_original: true    # Set original as default
```

### Anime-Specific Policy

```yaml
schema_version: 12

conditional:
  - name: "Japanese anime with English dub"
    when:
      and:
        - is_dubbed:
            original_language: jpn
        - exists:
            track_type: audio
            language: jpn
    then:
      - set_default:
          track_type: audio
          language: jpn
      - warn: "Setting Japanese original as default for anime"
```

### Combined with Multi-Language Detection

```yaml
schema_version: 12

conditional:
  - name: "Multi-language dubbed content"
    when:
      and:
        - audio_is_multi_language: true
        - is_dubbed: true
    then:
      - set_forced:
          track_type: subtitle
          language: eng
          is_forced: true
```

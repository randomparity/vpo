"""Serializer that converts Condition dataclasses back to expression strings.

Used for round-trip editing: load structured YAML conditions, display
as expression strings in the UI or CLI output.
"""

from __future__ import annotations

from vpo.policy.types.conditions import (
    AndCondition,
    AudioIsMultiLanguageCondition,
    Comparison,
    ComparisonOperator,
    Condition,
    ContainerMetadataCondition,
    CountCondition,
    ExistsCondition,
    IsDubbedCondition,
    IsOriginalCondition,
    MetadataComparisonOperator,
    NotCondition,
    OrCondition,
    PluginMetadataCondition,
    TitleMatch,
    TrackFilters,
)

# Reverse mapping: ComparisonOperator -> expression operator string
_COMP_OP_STR: dict[ComparisonOperator, str] = {
    ComparisonOperator.EQ: "==",
    ComparisonOperator.LT: "<",
    ComparisonOperator.LTE: "<=",
    ComparisonOperator.GT: ">",
    ComparisonOperator.GTE: ">=",
}

# Reverse mapping: MetadataComparisonOperator -> expression operator string
_META_OP_STR: dict[MetadataComparisonOperator, str] = {
    MetadataComparisonOperator.EQ: "==",
    MetadataComparisonOperator.NEQ: "!=",
    MetadataComparisonOperator.LT: "<",
    MetadataComparisonOperator.LTE: "<=",
    MetadataComparisonOperator.GT: ">",
    MetadataComparisonOperator.GTE: ">=",
}


def serialize_condition(condition: Condition) -> str:
    """Convert a Condition dataclass into an expression string.

    Produces minimal parenthesization based on operator precedence.

    Args:
        condition: The condition to serialize.

    Returns:
        An expression string that can be parsed back to the same condition.
    """
    return _serialize(condition, _Precedence.TOP)


class _Precedence:
    """Operator precedence levels (higher = tighter binding)."""

    TOP = 0  # outermost, no parens needed
    OR = 1
    AND = 2
    NOT = 3
    ATOM = 4


def _serialize(condition: Condition, parent_prec: int) -> str:
    """Serialize with precedence-aware parenthesization."""
    if isinstance(condition, OrCondition):
        inner = " or ".join(_serialize(c, _Precedence.OR) for c in condition.conditions)
        if parent_prec > _Precedence.OR:
            return f"({inner})"
        return inner

    if isinstance(condition, AndCondition):
        inner = " and ".join(
            _serialize(c, _Precedence.AND) for c in condition.conditions
        )
        if parent_prec > _Precedence.AND:
            return f"({inner})"
        return inner

    if isinstance(condition, NotCondition):
        inner = _serialize(condition.inner, _Precedence.NOT)
        return f"not {inner}"

    if isinstance(condition, ExistsCondition):
        return _serialize_exists(condition)

    if isinstance(condition, CountCondition):
        return _serialize_count(condition)

    if isinstance(condition, AudioIsMultiLanguageCondition):
        return _serialize_multi_language(condition)

    if isinstance(condition, PluginMetadataCondition):
        return _serialize_plugin(condition)

    if isinstance(condition, ContainerMetadataCondition):
        return _serialize_container_meta(condition)

    if isinstance(condition, IsOriginalCondition):
        return _serialize_is_original(condition)

    if isinstance(condition, IsDubbedCondition):
        return _serialize_is_dubbed(condition)

    msg = f"Unknown condition type: {type(condition).__name__}"
    raise ValueError(msg)


def _serialize_exists(cond: ExistsCondition) -> str:
    parts = [cond.track_type]
    parts.extend(_serialize_filters(cond.filters))
    return f"exists({', '.join(parts)})"


def _serialize_count(cond: CountCondition) -> str:
    parts = [cond.track_type]
    parts.extend(_serialize_filters(cond.filters))
    op_str = _COMP_OP_STR[cond.operator]
    return f"count({', '.join(parts)}) {op_str} {cond.value}"


def _serialize_filters(filters: TrackFilters) -> list[str]:
    """Serialize track filters into argument strings."""
    parts: list[str] = []

    if filters.language is not None:
        if isinstance(filters.language, tuple):
            vals = ", ".join(filters.language)
            parts.append(f"lang in [{vals}]")
        else:
            parts.append(f"lang == {filters.language}")

    if filters.codec is not None:
        if isinstance(filters.codec, tuple):
            vals = ", ".join(filters.codec)
            parts.append(f"codec in [{vals}]")
        else:
            parts.append(f"codec == {filters.codec}")

    if filters.channels is not None:
        parts.append(_serialize_int_or_comparison("channels", filters.channels))

    if filters.height is not None:
        parts.append(_serialize_int_or_comparison("height", filters.height))

    if filters.width is not None:
        parts.append(_serialize_int_or_comparison("width", filters.width))

    if filters.is_default is not None:
        parts.append(f"default == {str(filters.is_default).lower()}")

    if filters.is_forced is not None:
        parts.append(f"forced == {str(filters.is_forced).lower()}")

    if filters.title is not None:
        if isinstance(filters.title, TitleMatch):
            if filters.title.contains:
                parts.append(f'title == "{filters.title.contains}"')
            elif filters.title.regex:
                parts.append(f'title == "{filters.title.regex}"')
        else:
            parts.append(f'title == "{filters.title}"')

    if filters.not_commentary is not None:
        parts.append(f"not_commentary == {str(filters.not_commentary).lower()}")

    return parts


def _serialize_int_or_comparison(name: str, value: int | Comparison) -> str:
    if isinstance(value, Comparison):
        op_str = _COMP_OP_STR[value.operator]
        return f"{name} {op_str} {value.value}"
    return f"{name} == {value}"


def _serialize_multi_language(cond: AudioIsMultiLanguageCondition) -> str:
    parts: list[str] = []
    if cond.track_index is not None:
        parts.append(f"track_index == {cond.track_index}")
    if cond.threshold != 0.05:
        parts.append(f"threshold == {cond.threshold}")
    if cond.primary_language is not None:
        parts.append(f"primary_language == {cond.primary_language}")
    return f"multi_language({', '.join(parts)})"


def _serialize_plugin(cond: PluginMetadataCondition) -> str:
    base = f"plugin({cond.plugin}, {cond.field})"
    if cond.operator == MetadataComparisonOperator.EXISTS:
        return base
    op_str = _META_OP_STR.get(cond.operator, "==")
    return f"{base} {op_str} {_format_value(cond.value)}"


def _serialize_container_meta(cond: ContainerMetadataCondition) -> str:
    base = f"container_meta({cond.field})"
    if cond.operator == MetadataComparisonOperator.EXISTS:
        return base
    op_str = _META_OP_STR.get(cond.operator, "==")
    return f"{base} {op_str} {_format_value(cond.value)}"


def _serialize_is_original(cond: IsOriginalCondition) -> str:
    parts: list[str] = []
    if cond.value is not True:
        parts.append(f"value == {str(cond.value).lower()}")
    if cond.min_confidence != 0.7:
        parts.append(f"confidence == {cond.min_confidence}")
    if cond.language is not None:
        parts.append(f"lang == {cond.language}")
    return f"is_original({', '.join(parts)})"


def _serialize_is_dubbed(cond: IsDubbedCondition) -> str:
    parts: list[str] = []
    if cond.value is not True:
        parts.append(f"value == {str(cond.value).lower()}")
    if cond.min_confidence != 0.7:
        parts.append(f"confidence == {cond.min_confidence}")
    if cond.language is not None:
        parts.append(f"lang == {cond.language}")
    return f"is_dubbed({', '.join(parts)})"


def _format_value(value: str | int | float | bool | None) -> str:
    """Format a metadata value for serialization."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        # Use quotes if the value contains spaces or special characters
        if " " in value or not value.isalnum():
            return f'"{value}"'
        return value
    return str(value)

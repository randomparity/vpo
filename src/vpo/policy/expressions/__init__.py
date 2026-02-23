"""Expression language for VPO policy conditions.

Provides parse_expression() to convert expression strings like
'exists(audio, lang == eng)' into Condition dataclasses, and
serialize_condition() for the reverse operation.
"""

from vpo.policy.expressions.errors import ExpressionError, LexError, ParseError
from vpo.policy.expressions.parser import parse_expression
from vpo.policy.expressions.serializer import serialize_condition

__all__ = [
    "ExpressionError",
    "LexError",
    "ParseError",
    "parse_expression",
    "serialize_condition",
]

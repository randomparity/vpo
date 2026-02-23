"""Tests for the expression language lexer."""

import pytest

from vpo.policy.expressions.errors import LexError
from vpo.policy.expressions.lexer import tokenize
from vpo.policy.expressions.tokens import TokenType


def _types(tokens):
    """Extract token types, excluding EOF."""
    return [t.type for t in tokens if t.type != TokenType.EOF]


def _values(tokens):
    """Extract token values, excluding EOF."""
    return [t.value for t in tokens if t.type != TokenType.EOF]


class TestBasicTokens:
    def test_empty_string(self):
        tokens = tokenize("")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF

    def test_whitespace_only(self):
        tokens = tokenize("   \t\n  ")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF

    def test_single_identifier(self):
        tokens = tokenize("audio")
        assert _types(tokens) == [TokenType.IDENT]
        assert _values(tokens) == ["audio"]

    def test_identifier_with_underscores(self):
        tokens = tokenize("not_commentary")
        assert _types(tokens) == [TokenType.IDENT]
        assert _values(tokens) == ["not_commentary"]

    def test_identifier_with_hyphens(self):
        tokens = tokenize("dts-hd")
        assert _types(tokens) == [TokenType.IDENT]
        assert _values(tokens) == ["dts-hd"]

    def test_identifier_with_digits(self):
        tokens = tokenize("h265")
        assert _types(tokens) == [TokenType.IDENT]
        assert _values(tokens) == ["h265"]


class TestKeywords:
    def test_and(self):
        tokens = tokenize("and")
        assert _types(tokens) == [TokenType.KW_AND]

    def test_or(self):
        tokens = tokenize("or")
        assert _types(tokens) == [TokenType.KW_OR]

    def test_not(self):
        tokens = tokenize("not")
        assert _types(tokens) == [TokenType.KW_NOT]

    def test_in(self):
        tokens = tokenize("in")
        assert _types(tokens) == [TokenType.OP_IN]

    def test_true(self):
        tokens = tokenize("true")
        assert _types(tokens) == [TokenType.BOOLEAN]
        assert _values(tokens) == ["true"]

    def test_false(self):
        tokens = tokenize("false")
        assert _types(tokens) == [TokenType.BOOLEAN]
        assert _values(tokens) == ["false"]

    def test_keyword_case_sensitive(self):
        """Keywords must be lowercase to be recognized."""
        tokens = tokenize("AND")
        assert _types(tokens) == [TokenType.IDENT]

    def test_keyword_mixed_case_is_ident(self):
        tokens = tokenize("True")
        assert _types(tokens) == [TokenType.IDENT]


class TestNumbers:
    def test_integer(self):
        tokens = tokenize("42")
        assert _types(tokens) == [TokenType.NUMBER]
        assert _values(tokens) == ["42"]

    def test_float(self):
        tokens = tokenize("3.14")
        assert _types(tokens) == [TokenType.NUMBER]
        assert _values(tokens) == ["3.14"]

    def test_zero(self):
        tokens = tokenize("0")
        assert _types(tokens) == [TokenType.NUMBER]


class TestSizeLiterals:
    def test_megabytes_uppercase(self):
        tokens = tokenize("15M")
        assert _types(tokens) == [TokenType.SIZE_LITERAL]
        assert _values(tokens) == ["15M"]

    def test_kilobytes_lowercase(self):
        tokens = tokenize("192k")
        assert _types(tokens) == [TokenType.SIZE_LITERAL]
        assert _values(tokens) == ["192k"]

    def test_gigabytes(self):
        tokens = tokenize("1GB")
        assert _types(tokens) == [TokenType.SIZE_LITERAL]
        assert _values(tokens) == ["1GB"]

    def test_decimal_size(self):
        tokens = tokenize("1.5GB")
        assert _types(tokens) == [TokenType.SIZE_LITERAL]
        assert _values(tokens) == ["1.5GB"]

    def test_megabytes_long(self):
        tokens = tokenize("500MB")
        assert _types(tokens) == [TokenType.SIZE_LITERAL]
        assert _values(tokens) == ["500MB"]


class TestStrings:
    def test_double_quoted(self):
        tokens = tokenize('"hello world"')
        assert _types(tokens) == [TokenType.STRING]
        assert _values(tokens) == ["hello world"]

    def test_single_quoted(self):
        tokens = tokenize("'dts-hd'")
        assert _types(tokens) == [TokenType.STRING]
        assert _values(tokens) == ["dts-hd"]

    def test_empty_string(self):
        tokens = tokenize('""')
        assert _types(tokens) == [TokenType.STRING]
        assert _values(tokens) == [""]

    def test_unterminated_string(self):
        with pytest.raises(LexError, match="Unterminated string"):
            tokenize('"hello')


class TestOperators:
    @pytest.mark.parametrize(
        "source,expected_type",
        [
            ("==", TokenType.OP_EQ),
            ("!=", TokenType.OP_NEQ),
            ("<", TokenType.OP_LT),
            ("<=", TokenType.OP_LTE),
            (">", TokenType.OP_GT),
            (">=", TokenType.OP_GTE),
        ],
    )
    def test_comparison_operators(self, source, expected_type):
        tokens = tokenize(source)
        assert _types(tokens) == [expected_type]


class TestDelimiters:
    def test_parens(self):
        tokens = tokenize("()")
        assert _types(tokens) == [TokenType.LPAREN, TokenType.RPAREN]

    def test_brackets(self):
        tokens = tokenize("[]")
        assert _types(tokens) == [TokenType.LBRACKET, TokenType.RBRACKET]

    def test_comma(self):
        tokens = tokenize(",")
        assert _types(tokens) == [TokenType.COMMA]


class TestComplexExpressions:
    def test_exists_call(self):
        tokens = tokenize("exists(audio, lang == eng)")
        expected = [
            TokenType.IDENT,  # exists
            TokenType.LPAREN,
            TokenType.IDENT,  # audio
            TokenType.COMMA,
            TokenType.IDENT,  # lang
            TokenType.OP_EQ,
            TokenType.IDENT,  # eng
            TokenType.RPAREN,
        ]
        assert _types(tokens) == expected

    def test_count_with_comparison(self):
        tokens = tokenize("count(audio) >= 2")
        expected = [
            TokenType.IDENT,  # count
            TokenType.LPAREN,
            TokenType.IDENT,  # audio
            TokenType.RPAREN,
            TokenType.OP_GTE,
            TokenType.NUMBER,  # 2
        ]
        assert _types(tokens) == expected

    def test_boolean_composition(self):
        tokens = tokenize("exists(video) and not exists(audio, lang == eng)")
        expected = [
            TokenType.IDENT,  # exists
            TokenType.LPAREN,
            TokenType.IDENT,  # video
            TokenType.RPAREN,
            TokenType.KW_AND,
            TokenType.KW_NOT,
            TokenType.IDENT,  # exists
            TokenType.LPAREN,
            TokenType.IDENT,  # audio
            TokenType.COMMA,
            TokenType.IDENT,  # lang
            TokenType.OP_EQ,
            TokenType.IDENT,  # eng
            TokenType.RPAREN,
        ]
        assert _types(tokens) == expected

    def test_list_value(self):
        tokens = tokenize("codec in [hevc, h265]")
        expected = [
            TokenType.IDENT,  # codec
            TokenType.OP_IN,
            TokenType.LBRACKET,
            TokenType.IDENT,  # hevc
            TokenType.COMMA,
            TokenType.IDENT,  # h265
            TokenType.RBRACKET,
        ]
        assert _types(tokens) == expected

    def test_plugin_with_string(self):
        tokens = tokenize('plugin(radarr, original_language) == "jpn"')
        expected = [
            TokenType.IDENT,  # plugin
            TokenType.LPAREN,
            TokenType.IDENT,  # radarr
            TokenType.COMMA,
            TokenType.IDENT,  # original_language
            TokenType.RPAREN,
            TokenType.OP_EQ,
            TokenType.STRING,  # jpn
        ]
        assert _types(tokens) == expected


class TestPositionTracking:
    def test_position_tracking(self):
        tokens = tokenize("a == b")
        # a is at position 0, col 1
        assert tokens[0].position == 0
        assert tokens[0].column == 1
        # == is at position 2, col 3
        assert tokens[1].position == 2
        assert tokens[1].column == 3
        # b is at position 5, col 6
        assert tokens[2].position == 5
        assert tokens[2].column == 6


class TestErrors:
    def test_invalid_character(self):
        with pytest.raises(LexError, match="Unexpected character"):
            tokenize("@invalid")

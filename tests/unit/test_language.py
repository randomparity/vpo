"""Unit tests for language code normalization utilities."""

import pytest

from video_policy_orchestrator.language import (
    DEFAULT_STANDARD,
    get_language_name,
    is_valid_language_code,
    languages_match,
    normalize_language,
)


class TestNormalizeLanguage:
    """Tests for normalize_language function."""

    def test_iso_639_1_to_639_2b_german(self):
        """Test converting German from ISO 639-1 to 639-2/B."""
        assert normalize_language("de") == "ger"

    def test_iso_639_1_to_639_2b_english(self):
        """Test converting English from ISO 639-1 to 639-2/B."""
        assert normalize_language("en") == "eng"

    def test_iso_639_1_to_639_2b_japanese(self):
        """Test converting Japanese from ISO 639-1 to 639-2/B."""
        assert normalize_language("ja") == "jpn"

    def test_iso_639_1_to_639_2b_french(self):
        """Test converting French from ISO 639-1 to 639-2/B."""
        assert normalize_language("fr") == "fre"

    def test_iso_639_2t_to_639_2b_german(self):
        """Test converting German from ISO 639-2/T to 639-2/B."""
        assert normalize_language("deu") == "ger"

    def test_iso_639_2t_to_639_2b_french(self):
        """Test converting French from ISO 639-2/T to 639-2/B."""
        assert normalize_language("fra") == "fre"

    def test_iso_639_2t_to_639_2b_chinese(self):
        """Test converting Chinese from ISO 639-2/T to 639-2/B."""
        assert normalize_language("zho") == "chi"

    def test_already_639_2b(self):
        """Test that already-normalized codes are unchanged."""
        assert normalize_language("eng") == "eng"
        assert normalize_language("ger") == "ger"
        assert normalize_language("jpn") == "jpn"

    def test_special_codes(self):
        """Test special language codes."""
        assert normalize_language("und") == "und"
        assert normalize_language("mis") == "mis"
        assert normalize_language("mul") == "mul"
        assert normalize_language("zxx") == "zxx"

    def test_none_returns_und(self):
        """Test that None input returns 'und'."""
        assert normalize_language(None) == "und"

    def test_empty_returns_und(self):
        """Test that empty string returns 'und'."""
        assert normalize_language("") == "und"

    def test_case_insensitive(self):
        """Test that input is case-insensitive."""
        assert normalize_language("DE") == "ger"
        assert normalize_language("En") == "eng"
        assert normalize_language("GER") == "ger"
        assert normalize_language("DEU") == "ger"

    def test_whitespace_stripped(self):
        """Test that whitespace is stripped."""
        assert normalize_language("  de  ") == "ger"
        assert normalize_language("\teng\n") == "eng"

    def test_unknown_code_returns_und(self):
        """Test that unrecognized codes return 'und'."""
        assert normalize_language("xx") == "und"
        assert normalize_language("abcdef") == "und"

    def test_target_639_1(self):
        """Test converting to ISO 639-1 target."""
        assert normalize_language("ger", target="639-1") == "de"
        assert normalize_language("eng", target="639-1") == "en"
        assert normalize_language("de", target="639-1") == "de"

    def test_target_639_2t(self):
        """Test converting to ISO 639-2/T target."""
        assert normalize_language("ger", target="639-2/T") == "deu"
        assert normalize_language("de", target="639-2/T") == "deu"
        assert normalize_language("fre", target="639-2/T") == "fra"

    def test_target_639_2b_is_default(self):
        """Test that 639-2/B is the default target."""
        assert DEFAULT_STANDARD == "639-2/B"
        assert normalize_language("de") == normalize_language("de", target="639-2/B")


class TestLanguagesMatch:
    """Tests for languages_match function."""

    def test_same_code_matches(self):
        """Test that identical codes match."""
        assert languages_match("eng", "eng") is True
        assert languages_match("ger", "ger") is True

    def test_639_1_matches_639_2b(self):
        """Test that ISO 639-1 matches ISO 639-2/B."""
        assert languages_match("de", "ger") is True
        assert languages_match("en", "eng") is True
        assert languages_match("ja", "jpn") is True
        assert languages_match("fr", "fre") is True

    def test_639_2t_matches_639_2b(self):
        """Test that ISO 639-2/T matches ISO 639-2/B."""
        assert languages_match("deu", "ger") is True
        assert languages_match("fra", "fre") is True
        assert languages_match("zho", "chi") is True

    def test_639_1_matches_639_2t(self):
        """Test that ISO 639-1 matches ISO 639-2/T."""
        assert languages_match("de", "deu") is True
        assert languages_match("fr", "fra") is True

    def test_different_languages_dont_match(self):
        """Test that different languages don't match."""
        assert languages_match("en", "de") is False
        assert languages_match("eng", "ger") is False
        assert languages_match("en", "ger") is False

    def test_case_insensitive(self):
        """Test that matching is case-insensitive."""
        assert languages_match("DE", "ger") is True
        assert languages_match("en", "ENG") is True

    def test_none_handling(self):
        """Test None input handling."""
        assert languages_match(None, None) is True  # Both undefined
        assert languages_match(None, "und") is True
        assert languages_match("und", None) is True
        assert languages_match(None, "eng") is False
        assert languages_match("eng", None) is False

    def test_und_matches_und(self):
        """Test that undefined matches undefined."""
        assert languages_match("und", "und") is True

    def test_symmetry(self):
        """Test that matching is symmetric."""
        assert languages_match("de", "ger") == languages_match("ger", "de")
        assert languages_match("en", "de") == languages_match("de", "en")


class TestGetLanguageName:
    """Tests for get_language_name function."""

    def test_common_languages(self):
        """Test names for common languages."""
        assert get_language_name("eng") == "English"
        assert get_language_name("ger") == "German"
        assert get_language_name("jpn") == "Japanese"
        assert get_language_name("fre") == "French"
        assert get_language_name("spa") == "Spanish"

    def test_iso_639_1_codes(self):
        """Test that 639-1 codes are normalized before lookup."""
        assert get_language_name("en") == "English"
        assert get_language_name("de") == "German"
        assert get_language_name("ja") == "Japanese"

    def test_iso_639_2t_codes(self):
        """Test that 639-2/T codes are normalized before lookup."""
        assert get_language_name("deu") == "German"
        assert get_language_name("fra") == "French"

    def test_special_codes(self):
        """Test names for special codes."""
        assert get_language_name("und") == "Undefined"
        assert get_language_name("mul") == "Multiple"
        assert get_language_name("zxx") == "No linguistic content"

    def test_none_returns_undefined(self):
        """Test that None returns 'Undefined'."""
        assert get_language_name(None) == "Undefined"

    def test_unknown_code_returns_uppercase(self):
        """Test that unknown codes return uppercase version."""
        assert get_language_name("xyz") == "XYZ"


class TestIsValidLanguageCode:
    """Tests for is_valid_language_code function."""

    def test_valid_639_1_codes(self):
        """Test valid ISO 639-1 codes."""
        assert is_valid_language_code("en") is True
        assert is_valid_language_code("de") is True
        assert is_valid_language_code("ja") is True
        assert is_valid_language_code("fr") is True

    def test_valid_639_2b_codes(self):
        """Test valid ISO 639-2/B codes."""
        assert is_valid_language_code("eng") is True
        assert is_valid_language_code("ger") is True
        assert is_valid_language_code("jpn") is True
        assert is_valid_language_code("fre") is True

    def test_valid_639_2t_codes(self):
        """Test valid ISO 639-2/T codes."""
        assert is_valid_language_code("deu") is True
        assert is_valid_language_code("fra") is True
        assert is_valid_language_code("zho") is True

    def test_invalid_codes(self):
        """Test invalid codes."""
        assert is_valid_language_code("xx") is False
        assert is_valid_language_code("abcdef") is False
        assert is_valid_language_code("1") is False
        assert is_valid_language_code("") is False
        assert is_valid_language_code(None) is False

    def test_case_insensitive(self):
        """Test that validation is case-insensitive."""
        assert is_valid_language_code("EN") is True
        assert is_valid_language_code("ENG") is True
        assert is_valid_language_code("De") is True


class TestCommonLanguageConversions:
    """Integration tests for common real-world language code scenarios."""

    @pytest.mark.parametrize(
        "input_code,expected",
        [
            # From Whisper (ISO 639-1)
            ("en", "eng"),
            ("de", "ger"),
            ("fr", "fre"),
            ("ja", "jpn"),
            ("zh", "chi"),
            ("ko", "kor"),
            ("es", "spa"),
            ("pt", "por"),
            ("ru", "rus"),
            ("ar", "ara"),
            ("hi", "hin"),
            ("it", "ita"),
            ("nl", "dut"),
            ("pl", "pol"),
            ("tr", "tur"),
            ("sv", "swe"),
            ("da", "dan"),
            ("fi", "fin"),
            ("no", "nor"),
            ("cs", "cze"),
            ("hu", "hun"),
            ("ro", "rum"),
            ("el", "gre"),
            ("he", "heb"),
            ("th", "tha"),
            ("vi", "vie"),
            ("id", "ind"),
            # From FFprobe (usually already 639-2/B)
            ("eng", "eng"),
            ("ger", "ger"),
            ("jpn", "jpn"),
            ("fre", "fre"),
            # ISO 639-2/T variants
            ("deu", "ger"),
            ("fra", "fre"),
            ("nld", "dut"),
            ("ces", "cze"),
            ("slk", "slo"),
            ("ron", "rum"),
            ("ell", "gre"),
        ],
    )
    def test_common_conversions(self, input_code, expected):
        """Test common language code conversions."""
        assert normalize_language(input_code) == expected

    @pytest.mark.parametrize(
        "code1,code2",
        [
            ("de", "ger"),
            ("de", "deu"),
            ("ger", "deu"),
            ("en", "eng"),
            ("fr", "fre"),
            ("fr", "fra"),
            ("fre", "fra"),
            ("nl", "dut"),
            ("nl", "nld"),
            ("cs", "cze"),
            ("cs", "ces"),
        ],
    )
    def test_cross_standard_matching(self, code1, code2):
        """Test that codes for same language match across standards."""
        assert languages_match(code1, code2) is True
        assert languages_match(code2, code1) is True

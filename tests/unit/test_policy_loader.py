"""Unit tests for policy loading and validation."""

from pathlib import Path
from textwrap import dedent

import pytest

from video_policy_orchestrator.policy.loader import (
    PolicyValidationError,
    load_policy,
    load_policy_from_dict,
)
from video_policy_orchestrator.policy.models import TrackType

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def valid_policy_yaml(tmp_path: Path) -> Path:
    """Create a valid policy YAML file."""
    content = dedent("""
        schema_version: 1
        track_order:
          - video
          - audio_main
          - subtitle_main
        audio_language_preference:
          - eng
          - jpn
        subtitle_language_preference:
          - eng
        commentary_patterns:
          - commentary
          - director
        default_flags:
          set_first_video_default: true
          set_preferred_audio_default: true
          set_preferred_subtitle_default: false
          clear_other_defaults: true
    """).strip()
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text(content)
    return policy_file


@pytest.fixture
def minimal_policy_yaml(tmp_path: Path) -> Path:
    """Create a minimal valid policy with just schema_version."""
    content = "schema_version: 1\n"
    policy_file = tmp_path / "minimal.yaml"
    policy_file.write_text(content)
    return policy_file


# =============================================================================
# Loading Tests
# =============================================================================


class TestLoadPolicy:
    """Tests for loading policy from file."""

    def test_load_valid_policy(self, valid_policy_yaml: Path):
        """Loading a valid policy file should succeed."""
        policy = load_policy(valid_policy_yaml)
        assert policy.schema_version == 1
        assert policy.track_order == (
            TrackType.VIDEO,
            TrackType.AUDIO_MAIN,
            TrackType.SUBTITLE_MAIN,
        )
        assert policy.audio_language_preference == ("eng", "jpn")
        assert policy.subtitle_language_preference == ("eng",)

    def test_load_minimal_policy_uses_defaults(self, minimal_policy_yaml: Path):
        """Minimal policy should use default values."""
        policy = load_policy(minimal_policy_yaml)
        assert policy.schema_version == 1
        # Check defaults are applied
        assert len(policy.track_order) > 0
        assert "eng" in policy.audio_language_preference
        assert policy.default_flags.set_first_video_default is True

    def test_load_nonexistent_file_raises_error(self, tmp_path: Path):
        """Loading a non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_policy(tmp_path / "nonexistent.yaml")

    def test_load_empty_file_raises_error(self, tmp_path: Path):
        """Loading an empty file should raise PolicyValidationError."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        with pytest.raises(PolicyValidationError, match="empty"):
            load_policy(empty_file)

    def test_load_invalid_yaml_raises_error(self, tmp_path: Path):
        """Loading invalid YAML should raise PolicyValidationError."""
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("{ invalid yaml: [")
        with pytest.raises(PolicyValidationError, match="YAML"):
            load_policy(invalid_file)

    def test_load_non_mapping_raises_error(self, tmp_path: Path):
        """Loading YAML that isn't a mapping should raise error."""
        list_file = tmp_path / "list.yaml"
        list_file.write_text("- item1\n- item2")
        with pytest.raises(PolicyValidationError, match="mapping"):
            load_policy(list_file)


# =============================================================================
# Validation Tests
# =============================================================================


class TestPolicyValidation:
    """Tests for policy validation rules."""

    def test_missing_schema_version_raises_error(self):
        """Missing schema_version should raise error."""
        with pytest.raises(PolicyValidationError):
            load_policy_from_dict({})

    def test_invalid_schema_version_type_raises_error(self):
        """Non-coercible schema_version should raise error."""
        # Note: Pydantic will coerce "1" to 1, so we use something non-coercible
        with pytest.raises(PolicyValidationError):
            load_policy_from_dict({"schema_version": "not_a_number"})

    def test_schema_version_zero_raises_error(self):
        """schema_version of 0 should raise error."""
        with pytest.raises(PolicyValidationError):
            load_policy_from_dict({"schema_version": 0})

    def test_schema_version_too_high_raises_error(self):
        """schema_version higher than supported should raise error."""
        with pytest.raises(PolicyValidationError):
            load_policy_from_dict({"schema_version": 999})

    def test_invalid_track_type_raises_error(self):
        """Unknown track type in track_order should raise error."""
        with pytest.raises(PolicyValidationError, match="Unknown track type"):
            load_policy_from_dict(
                {
                    "schema_version": 1,
                    "track_order": ["video", "invalid_type"],
                }
            )

    def test_empty_track_order_raises_error(self):
        """Empty track_order should raise error."""
        with pytest.raises(PolicyValidationError, match="empty"):
            load_policy_from_dict(
                {
                    "schema_version": 1,
                    "track_order": [],
                }
            )

    def test_invalid_language_code_raises_error(self):
        """Invalid language codes should raise error."""
        with pytest.raises(PolicyValidationError, match="Invalid language code"):
            load_policy_from_dict(
                {
                    "schema_version": 1,
                    "audio_language_preference": ["english"],  # Should be "eng"
                }
            )

    def test_empty_language_preference_raises_error(self):
        """Empty language preference should raise error."""
        with pytest.raises(PolicyValidationError, match="empty"):
            load_policy_from_dict(
                {
                    "schema_version": 1,
                    "audio_language_preference": [],
                }
            )

    def test_invalid_regex_pattern_raises_error(self):
        """Invalid regex in commentary_patterns should raise error."""
        with pytest.raises(PolicyValidationError):
            load_policy_from_dict(
                {
                    "schema_version": 1,
                    "commentary_patterns": ["[invalid(regex"],
                }
            )

    def test_extra_field_raises_error(self):
        """Extra/unknown fields should raise error."""
        with pytest.raises(PolicyValidationError):
            load_policy_from_dict(
                {
                    "schema_version": 1,
                    "unknown_field": "value",
                }
            )

    def test_invalid_default_flags_field_raises_error(self):
        """Extra field in default_flags should raise error."""
        with pytest.raises(PolicyValidationError):
            load_policy_from_dict(
                {
                    "schema_version": 1,
                    "default_flags": {
                        "set_first_video_default": True,
                        "invalid_flag": True,
                    },
                }
            )


# =============================================================================
# Language Code Tests
# =============================================================================


class TestLanguageCodeValidation:
    """Tests for language code validation."""

    def test_valid_iso_639_2_codes(self):
        """Valid ISO 639-2 language codes should be accepted."""
        policy = load_policy_from_dict(
            {
                "schema_version": 1,
                "audio_language_preference": ["eng", "jpn", "fra", "und"],
            }
        )
        assert policy.audio_language_preference == ("eng", "jpn", "fra", "und")

    def test_valid_iso_639_1_codes(self):
        """ISO 639-1 two-letter codes should be accepted."""
        policy = load_policy_from_dict(
            {
                "schema_version": 1,
                "audio_language_preference": ["en", "ja", "fr"],
            }
        )
        assert policy.audio_language_preference == ("en", "ja", "fr")

    def test_uppercase_language_rejected(self):
        """Uppercase language codes should be rejected."""
        with pytest.raises(PolicyValidationError, match="Invalid language code"):
            load_policy_from_dict(
                {
                    "schema_version": 1,
                    "audio_language_preference": ["ENG"],
                }
            )

    def test_long_language_code_rejected(self):
        """Language codes longer than 3 chars should be rejected."""
        with pytest.raises(PolicyValidationError, match="Invalid language code"):
            load_policy_from_dict(
                {
                    "schema_version": 1,
                    "audio_language_preference": ["english"],
                }
            )


# =============================================================================
# Commentary Pattern Tests
# =============================================================================


class TestCommentaryPatternValidation:
    """Tests for commentary pattern validation."""

    def test_valid_simple_patterns(self):
        """Simple string patterns should be accepted."""
        policy = load_policy_from_dict(
            {
                "schema_version": 1,
                "commentary_patterns": ["commentary", "director", "making of"],
            }
        )
        assert "commentary" in policy.commentary_patterns

    def test_valid_regex_patterns(self):
        """Valid regex patterns should be accepted."""
        policy = load_policy_from_dict(
            {
                "schema_version": 1,
                "commentary_patterns": [
                    r"\bcast\b",
                    r"behind.+scenes?",
                    r"audio\s*description",
                ],
            }
        )
        assert len(policy.commentary_patterns) == 3

    def test_invalid_regex_rejected(self):
        """Invalid regex patterns should be rejected."""
        with pytest.raises(PolicyValidationError):
            load_policy_from_dict(
                {
                    "schema_version": 1,
                    "commentary_patterns": ["[unclosed"],
                }
            )


# =============================================================================
# Default Flags Tests
# =============================================================================


class TestDefaultFlagsValidation:
    """Tests for default_flags validation."""

    def test_all_flags_specified(self):
        """Specifying all flags should work."""
        policy = load_policy_from_dict(
            {
                "schema_version": 1,
                "default_flags": {
                    "set_first_video_default": False,
                    "set_preferred_audio_default": False,
                    "set_preferred_subtitle_default": True,
                    "clear_other_defaults": False,
                },
            }
        )
        assert policy.default_flags.set_first_video_default is False
        assert policy.default_flags.set_preferred_subtitle_default is True
        assert policy.default_flags.clear_other_defaults is False

    def test_partial_flags_uses_defaults(self):
        """Partial default_flags should fill in defaults."""
        policy = load_policy_from_dict(
            {
                "schema_version": 1,
                "default_flags": {
                    "set_preferred_subtitle_default": True,
                },
            }
        )
        # Specified value
        assert policy.default_flags.set_preferred_subtitle_default is True
        # Default values
        assert policy.default_flags.set_first_video_default is True
        assert policy.default_flags.clear_other_defaults is True

    def test_invalid_flag_type_rejected(self):
        """Non-coercible flag values should be rejected."""
        # Note: Pydantic will coerce truthy strings like "yes" to True
        # So we use something that can't be coerced to boolean
        with pytest.raises(PolicyValidationError):
            load_policy_from_dict(
                {
                    "schema_version": 1,
                    "default_flags": {
                        "set_first_video_default": [1, 2, 3],  # List can't be boolean
                    },
                }
            )

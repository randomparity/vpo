"""Unit tests for phased policy validation.

Tests for the user-defined phases feature validation:
- Case-insensitive phase name collision detection
- Phase name validation patterns
"""

import pytest

from vpo.policy.loader import (
    PolicyValidationError,
    load_policy_from_dict,
)
from vpo.policy.types import (
    GlobalConfig,
    OnErrorMode,
    PhaseDefinition,
    PolicySchema,
)


class TestPhasedPolicyPhaseNameValidation:
    """Tests for phased policy phase name validation."""

    def test_unique_phase_names_valid(self):
        """Test that different phase names are accepted."""
        data = {
            "schema_version": 12,
            "config": {"on_error": "continue"},
            "phases": [
                {"name": "prepare", "audio_filter": {"languages": ["eng"]}},
                {"name": "cleanup", "audio_filter": {"languages": ["jpn"]}},
                {"name": "finalize", "track_order": ["video", "audio_main"]},
            ],
        }
        policy = load_policy_from_dict(data)
        assert len(policy.phases) == 3
        assert policy.phase_names == ("prepare", "cleanup", "finalize")

    def test_exact_duplicate_phase_names_rejected(self):
        """Test that exact duplicate phase names are rejected."""
        data = {
            "schema_version": 12,
            "config": {"on_error": "continue"},
            "phases": [
                {"name": "prepare", "audio_filter": {"languages": ["eng"]}},
                {"name": "prepare", "audio_filter": {"languages": ["jpn"]}},
            ],
        }
        with pytest.raises(PolicyValidationError, match="Duplicate phase names"):
            load_policy_from_dict(data)

    def test_case_insensitive_collision_rejected(self):
        """Test that phase names differing only by case are rejected."""
        data = {
            "schema_version": 12,
            "config": {"on_error": "continue"},
            "phases": [
                {"name": "prepare", "audio_filter": {"languages": ["eng"]}},
                {"name": "Prepare", "audio_filter": {"languages": ["jpn"]}},
            ],
        }
        with pytest.raises(
            PolicyValidationError, match="case-insensitive.*'prepare'.*'Prepare'"
        ):
            load_policy_from_dict(data)

    def test_case_insensitive_collision_mixed_case(self):
        """Test case-insensitive collision with mixed case names."""
        data = {
            "schema_version": 12,
            "config": {"on_error": "continue"},
            "phases": [
                {"name": "MyPhase", "audio_filter": {"languages": ["eng"]}},
                {"name": "myPHASE", "audio_filter": {"languages": ["jpn"]}},
            ],
        }
        with pytest.raises(
            PolicyValidationError, match="case-insensitive.*'MyPhase'.*'myPHASE'"
        ):
            load_policy_from_dict(data)

    def test_similar_but_different_names_valid(self):
        """Test that similar but different names are allowed."""
        data = {
            "schema_version": 12,
            "config": {"on_error": "continue"},
            "phases": [
                {"name": "prepare", "audio_filter": {"languages": ["eng"]}},
                {"name": "prepare1", "audio_filter": {"languages": ["jpn"]}},
                {"name": "prepares", "track_order": ["video", "audio_main"]},
            ],
        }
        policy = load_policy_from_dict(data)
        assert len(policy.phases) == 3


class TestPolicySchemaPostInit:
    """Tests for PolicySchema __post_init__ validation."""

    def test_case_insensitive_collision_in_dataclass(self):
        """Test that PolicySchema also checks case-insensitive collisions."""
        config = GlobalConfig(
            audio_language_preference=("eng",),
            subtitle_language_preference=("eng",),
            commentary_patterns=(),
            on_error=OnErrorMode.CONTINUE,
        )
        phase1 = PhaseDefinition(name="test", track_order=None)
        phase2 = PhaseDefinition(name="TEST", track_order=None)

        with pytest.raises(ValueError, match="case-insensitive"):
            PolicySchema(
                schema_version=12,
                config=config,
                phases=(phase1, phase2),
            )

    def test_valid_phases_in_dataclass(self):
        """Test that valid phases pass PolicySchema validation."""
        config = GlobalConfig(
            audio_language_preference=("eng",),
            subtitle_language_preference=("eng",),
            commentary_patterns=(),
            on_error=OnErrorMode.CONTINUE,
        )
        phase1 = PhaseDefinition(name="prepare", track_order=None)
        phase2 = PhaseDefinition(name="finalize", track_order=None)

        policy = PolicySchema(
            schema_version=12,
            config=config,
            phases=(phase1, phase2),
        )
        assert policy.phase_names == ("prepare", "finalize")

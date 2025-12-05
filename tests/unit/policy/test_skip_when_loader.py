"""Unit tests for loading skip_when conditions from YAML.

T013: Tests for PhaseSkipConditionModel validation and conversion.
"""

from pathlib import Path

import pytest

from video_policy_orchestrator.policy.loader import (
    PolicyValidationError,
    load_policy,
    load_policy_from_dict,
)
from video_policy_orchestrator.policy.models import PhasedPolicySchema


class TestSkipWhenYamlLoading:
    """Tests for loading skip_when from YAML."""

    def test_load_skip_when_video_codec(self) -> None:
        """Load policy with video_codec skip condition."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "transcode",
                    "skip_when": {"video_codec": ["hevc", "h265"]},
                    "transcode": {
                        "video": {"target_codec": "hevc"},
                    },
                }
            ],
        }
        policy = load_policy_from_dict(policy_dict)
        assert isinstance(policy, PhasedPolicySchema)
        assert policy.phases[0].skip_when is not None
        assert policy.phases[0].skip_when.video_codec == ("hevc", "h265")

    def test_load_skip_when_file_size(self) -> None:
        """Load policy with file_size skip condition."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "compress",
                    "skip_when": {"file_size_under": "1GB"},
                    "transcode": {
                        "video": {"target_codec": "hevc"},
                    },
                }
            ],
        }
        policy = load_policy_from_dict(policy_dict)
        assert isinstance(policy, PhasedPolicySchema)
        assert policy.phases[0].skip_when is not None
        assert policy.phases[0].skip_when.file_size_under == "1GB"

    def test_load_skip_when_resolution(self) -> None:
        """Load policy with resolution skip condition."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "upscale",
                    "skip_when": {"resolution": "4k"},
                    "transcode": {
                        "video": {"target_codec": "hevc"},
                    },
                }
            ],
        }
        policy = load_policy_from_dict(policy_dict)
        assert isinstance(policy, PhasedPolicySchema)
        assert policy.phases[0].skip_when is not None
        assert policy.phases[0].skip_when.resolution == "4k"

    def test_load_skip_when_duration(self) -> None:
        """Load policy with duration skip condition."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "analyze",
                    "skip_when": {"duration_under": "30m"},
                    "transcription": {"enabled": True},
                }
            ],
        }
        policy = load_policy_from_dict(policy_dict)
        assert isinstance(policy, PhasedPolicySchema)
        assert policy.phases[0].skip_when is not None
        assert policy.phases[0].skip_when.duration_under == "30m"

    def test_load_skip_when_multiple_conditions(self) -> None:
        """Load policy with multiple skip conditions (OR logic)."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "transcode",
                    "skip_when": {
                        "video_codec": ["hevc", "h265"],
                        "file_size_under": "500MB",
                    },
                    "transcode": {
                        "video": {"target_codec": "hevc"},
                    },
                }
            ],
        }
        policy = load_policy_from_dict(policy_dict)
        assert isinstance(policy, PhasedPolicySchema)
        assert policy.phases[0].skip_when is not None
        assert policy.phases[0].skip_when.video_codec == ("hevc", "h265")
        assert policy.phases[0].skip_when.file_size_under == "500MB"

    def test_load_fixture_skip_when_basic(self, tmp_path: Path) -> None:
        """Load the skip-when-basic fixture file."""
        fixture_path = Path(
            "tests/fixtures/policies/v12/conditional-phases/skip-when-basic.yaml"
        )
        if fixture_path.exists():
            policy = load_policy(fixture_path)
            assert isinstance(policy, PhasedPolicySchema)
            # Find the transcode phase
            transcode_phase = next(
                (p for p in policy.phases if p.name == "transcode"), None
            )
            assert transcode_phase is not None
            assert transcode_phase.skip_when is not None
            assert transcode_phase.skip_when.video_codec == ("hevc", "h265")


class TestSkipWhenValidation:
    """Tests for skip_when validation errors."""

    def test_skip_when_empty_raises_error(self) -> None:
        """Empty skip_when raises validation error."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "transcode",
                    "skip_when": {},
                    "transcode": {
                        "video": {"target_codec": "hevc"},
                    },
                }
            ],
        }
        with pytest.raises(PolicyValidationError) as exc_info:
            load_policy_from_dict(policy_dict)
        assert "at least one condition" in str(exc_info.value).lower()

    def test_skip_when_invalid_resolution(self) -> None:
        """Invalid resolution value raises error."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "transcode",
                    "skip_when": {"resolution": "invalid"},
                    "transcode": {
                        "video": {"target_codec": "hevc"},
                    },
                }
            ],
        }
        with pytest.raises(PolicyValidationError) as exc_info:
            load_policy_from_dict(policy_dict)
        assert "resolution" in str(exc_info.value).lower()

    def test_skip_when_invalid_file_size(self) -> None:
        """Invalid file size format raises error."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "transcode",
                    "skip_when": {"file_size_under": "invalid"},
                    "transcode": {
                        "video": {"target_codec": "hevc"},
                    },
                }
            ],
        }
        with pytest.raises(PolicyValidationError) as exc_info:
            load_policy_from_dict(policy_dict)
        assert "file size" in str(exc_info.value).lower()

    def test_skip_when_invalid_duration(self) -> None:
        """Invalid duration format raises error."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "transcode",
                    "skip_when": {"duration_under": "invalid"},
                    "transcode": {
                        "video": {"target_codec": "hevc"},
                    },
                }
            ],
        }
        with pytest.raises(PolicyValidationError) as exc_info:
            load_policy_from_dict(policy_dict)
        assert "duration" in str(exc_info.value).lower()

    def test_skip_when_unknown_field_raises_error(self) -> None:
        """Unknown field in skip_when raises error."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "transcode",
                    "skip_when": {"unknown_field": "value"},
                    "transcode": {
                        "video": {"target_codec": "hevc"},
                    },
                }
            ],
        }
        with pytest.raises(PolicyValidationError):
            load_policy_from_dict(policy_dict)


class TestDependsOnValidation:
    """Tests for depends_on validation."""

    def test_depends_on_valid_earlier_phase(self) -> None:
        """depends_on can reference earlier phases."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {"name": "normalize", "container": {"target": "mkv"}},
                {
                    "name": "transcode",
                    "depends_on": ["normalize"],
                    "transcode": {"video": {"target_codec": "hevc"}},
                },
            ],
        }
        policy = load_policy_from_dict(policy_dict)
        assert isinstance(policy, PhasedPolicySchema)
        assert policy.phases[1].depends_on == ("normalize",)

    def test_depends_on_unknown_phase_raises_error(self) -> None:
        """depends_on referencing unknown phase raises error."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "transcode",
                    "depends_on": ["nonexistent"],
                    "transcode": {"video": {"target_codec": "hevc"}},
                },
            ],
        }
        with pytest.raises(PolicyValidationError) as exc_info:
            load_policy_from_dict(policy_dict)
        assert "unknown phase" in str(exc_info.value).lower()

    def test_depends_on_later_phase_raises_error(self) -> None:
        """depends_on referencing later phase raises error."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "transcode",
                    "depends_on": ["cleanup"],
                    "transcode": {"video": {"target_codec": "hevc"}},
                },
                {"name": "cleanup", "attachment_filter": {"remove_all": True}},
            ],
        }
        with pytest.raises(PolicyValidationError) as exc_info:
            load_policy_from_dict(policy_dict)
        assert "later" in str(exc_info.value).lower()

    def test_depends_on_self_raises_error(self) -> None:
        """depends_on referencing self raises error."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "transcode",
                    "depends_on": ["transcode"],
                    "transcode": {"video": {"target_codec": "hevc"}},
                },
            ],
        }
        with pytest.raises(PolicyValidationError) as exc_info:
            load_policy_from_dict(policy_dict)
        assert (
            "later" in str(exc_info.value).lower()
            or "same" in str(exc_info.value).lower()
        )


class TestRunIfValidation:
    """Tests for run_if validation."""

    def test_run_if_phase_modified_valid(self) -> None:
        """run_if phase_modified can reference earlier phases."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "transcode",
                    "transcode": {"video": {"target_codec": "hevc"}},
                },
                {
                    "name": "verify",
                    "run_if": {"phase_modified": "transcode"},
                    "conditional": [
                        {
                            "name": "check",
                            "when": {"exists": {"track_type": "video"}},
                            "then": [{"warn": "test"}],
                        }
                    ],
                },
            ],
        }
        policy = load_policy_from_dict(policy_dict)
        assert isinstance(policy, PhasedPolicySchema)
        assert policy.phases[1].run_if is not None
        assert policy.phases[1].run_if.phase_modified == "transcode"

    def test_run_if_unknown_phase_raises_error(self) -> None:
        """run_if referencing unknown phase raises error."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "verify",
                    "run_if": {"phase_modified": "nonexistent"},
                    "conditional": [
                        {
                            "name": "check",
                            "when": {"exists": {"track_type": "video"}},
                            "then": [{"warn": "test"}],
                        }
                    ],
                },
            ],
        }
        with pytest.raises(PolicyValidationError) as exc_info:
            load_policy_from_dict(policy_dict)
        assert "unknown phase" in str(exc_info.value).lower()

    def test_run_if_empty_raises_error(self) -> None:
        """Empty run_if raises error."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "verify",
                    "run_if": {},
                    "conditional": [
                        {
                            "name": "check",
                            "when": {"exists": {"track_type": "video"}},
                            "then": [{"warn": "test"}],
                        }
                    ],
                },
            ],
        }
        with pytest.raises(PolicyValidationError) as exc_info:
            load_policy_from_dict(policy_dict)
        assert "exactly one" in str(exc_info.value).lower()


class TestOnErrorOverrideLoading:
    """Tests for per-phase on_error loading."""

    def test_load_on_error_skip(self) -> None:
        """Load phase with on_error: skip."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "analyze",
                    "on_error": "skip",
                    "transcription": {"enabled": True},
                }
            ],
        }
        policy = load_policy_from_dict(policy_dict)
        assert isinstance(policy, PhasedPolicySchema)
        from video_policy_orchestrator.policy.models import OnErrorMode

        assert policy.phases[0].on_error == OnErrorMode.SKIP

    def test_load_on_error_continue(self) -> None:
        """Load phase with on_error: continue."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "analyze",
                    "on_error": "continue",
                    "transcription": {"enabled": True},
                }
            ],
        }
        policy = load_policy_from_dict(policy_dict)
        assert isinstance(policy, PhasedPolicySchema)
        from video_policy_orchestrator.policy.models import OnErrorMode

        assert policy.phases[0].on_error == OnErrorMode.CONTINUE

    def test_load_on_error_fail(self) -> None:
        """Load phase with on_error: fail."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "analyze",
                    "on_error": "fail",
                    "transcription": {"enabled": True},
                }
            ],
        }
        policy = load_policy_from_dict(policy_dict)
        assert isinstance(policy, PhasedPolicySchema)
        from video_policy_orchestrator.policy.models import OnErrorMode

        assert policy.phases[0].on_error == OnErrorMode.FAIL

    def test_on_error_none_when_not_specified(self) -> None:
        """on_error is None when not specified (uses global)."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "analyze",
                    "transcription": {"enabled": True},
                }
            ],
        }
        policy = load_policy_from_dict(policy_dict)
        assert isinstance(policy, PhasedPolicySchema)
        assert policy.phases[0].on_error is None

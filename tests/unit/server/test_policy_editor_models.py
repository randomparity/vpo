"""Unit tests for PolicyEditorRequest V12 fields.

Tests the V12 policy support in PolicyEditorRequest:
- from_dict() handling of phases and config
- to_policy_dict() V12 structure generation
- Backward compatibility with legacy policies
"""

import pytest

from vpo.server.ui.models import PolicyEditorRequest

# All optional PolicyEditorRequest fields defaulted to None.
# Tests merge overrides on top of this to set only the fields they care about.
_OPTIONAL_NONE = {
    "transcode": None,
    "transcription": None,
    "audio_filter": None,
    "subtitle_filter": None,
    "attachment_filter": None,
    "container": None,
    "conditional": None,
    "audio_synthesis": None,
    "workflow": None,
    "phases": None,
    "config": None,
    "display_name": None,
    "description": None,
    "category": None,
}


def _make_request(base_fields, **overrides):
    """Create a PolicyEditorRequest with optional fields defaulted to None."""
    return PolicyEditorRequest(**base_fields, **{**_OPTIONAL_NONE, **overrides})


class TestPolicyEditorRequestV12:
    """Tests for PolicyEditorRequest V12 support."""

    @pytest.fixture
    def base_fields(self):
        """Base fields required for all PolicyEditorRequest instances."""
        return {
            "track_order": ["video", "audio_main"],
            "audio_language_preference": ["eng", "und"],
            "subtitle_language_preference": ["eng"],
            "commentary_patterns": ["commentary"],
            "default_flags": {"set_first_video_default": True},
            "last_modified_timestamp": "2024-01-01T00:00:00Z",
        }

    def test_from_dict_with_v12_fields(self, base_fields):
        """Test from_dict correctly parses V12 phases and config."""
        data = {
            **base_fields,
            "phases": [
                {"name": "cleanup", "audio_filter": {"languages": ["eng"]}},
                {"name": "optimize", "transcode": {"target_codec": "hevc"}},
            ],
            "config": {"on_error": "skip"},
        }
        request = PolicyEditorRequest.from_dict(data)

        assert request.phases == data["phases"]
        assert request.config == data["config"]

    def test_from_dict_without_v12_fields(self, base_fields):
        """Test from_dict handles missing V12 fields with defaults."""
        request = PolicyEditorRequest.from_dict(base_fields)

        assert request.phases is None
        assert request.config == {}  # Defaults to empty dict

    def test_to_policy_dict_v12_with_phases(self, base_fields):
        """Test to_policy_dict produces V12 structure when phases present."""
        request = _make_request(
            base_fields,
            phases=[{"name": "test", "audio_filter": {"languages": ["eng"]}}],
            config={"on_error": "skip"},
        )
        result = request.to_policy_dict()

        assert result["schema_version"] == 12
        assert "phases" in result
        assert result["phases"] == [
            {"name": "test", "audio_filter": {"languages": ["eng"]}}
        ]
        assert result["config"] == {"on_error": "skip"}
        # V12 should not include legacy fields at top level
        assert "track_order" not in result

    def test_to_policy_dict_v12_without_explicit_config(self, base_fields):
        """Test to_policy_dict builds config from legacy fields if not provided."""
        request = _make_request(
            base_fields,
            phases=[{"name": "test"}],
        )
        result = request.to_policy_dict()

        assert result["schema_version"] == 12
        assert result["config"]["audio_language_preference"] == ["eng", "und"]
        assert result["config"]["subtitle_language_preference"] == ["eng"]
        assert result["config"]["commentary_patterns"] == ["commentary"]
        assert result["config"]["on_error"] == "continue"  # Default

    def test_to_policy_dict_legacy_without_phases(self, base_fields):
        """Test to_policy_dict produces legacy structure when no V12 features used."""
        request = _make_request(base_fields)
        result = request.to_policy_dict()

        assert result["schema_version"] == 12
        assert "track_order" in result
        assert "phases" not in result
        assert "config" not in result

    def test_to_policy_dict_v9_with_workflow(self, base_fields):
        """Test to_policy_dict produces V9 when workflow is set."""
        request = _make_request(
            base_fields,
            workflow={"phases": ["ANALYZE", "APPLY"], "on_error": "skip"},
        )
        result = request.to_policy_dict()

        assert result["schema_version"] == 12
        assert result["workflow"] == {
            "phases": ["ANALYZE", "APPLY"],
            "on_error": "skip",
        }
        assert "phases" not in result


class TestPolicyEditorRequestVersionDetection:
    """Tests for PolicyEditorRequest schema version detection."""

    @pytest.fixture
    def base_request_kwargs(self):
        """Base kwargs for PolicyEditorRequest."""
        return {
            "track_order": ["video", "audio_main"],
            "audio_language_preference": ["eng"],
            "subtitle_language_preference": ["eng"],
            "commentary_patterns": [],
            "default_flags": {},
            **_OPTIONAL_NONE,
            "last_modified_timestamp": "2024-01-01T00:00:00Z",
        }

    def test_v12_takes_precedence(self, base_request_kwargs):
        """Test that phases present means V12, even with other features."""
        request = PolicyEditorRequest(
            **{
                **base_request_kwargs,
                "phases": [{"name": "test"}],
                "config": {"on_error": "skip"},
                # Also set V9 workflow - should be ignored
                "workflow": {"phases": ["APPLY"]},
                # Also set V3 filters - should be ignored
                "audio_filter": {"languages": ["eng"]},
            }
        )
        result = request.to_policy_dict()

        # V12 wins because phases is set
        assert result["schema_version"] == 12
        assert "phases" in result
        # Legacy fields should not appear at top level
        assert "workflow" not in result
        assert "audio_filter" not in result


class TestPolicyEditorRequestMetadata:
    """Tests for metadata fields in PolicyEditorRequest round-trip."""

    @pytest.fixture
    def base_fields(self):
        """Base fields required for all PolicyEditorRequest instances."""
        return {
            "track_order": ["video", "audio_main"],
            "audio_language_preference": ["eng"],
            "subtitle_language_preference": ["eng"],
            "commentary_patterns": [],
            "default_flags": {},
            "last_modified_timestamp": "2024-01-01T00:00:00Z",
        }

    def test_phased_policy_dict_includes_metadata(self, base_fields):
        """Phased policy dict emits metadata when set."""
        request = _make_request(
            base_fields,
            phases=[{"name": "test"}],
            config={"on_error": "skip"},
            display_name="My Policy",
            description="A test policy",
            category="organize",
        )
        result = request.to_policy_dict()

        assert result["name"] == "My Policy"
        assert result["description"] == "A test policy"
        assert result["category"] == "organize"

    def test_phased_policy_dict_omits_null_metadata(self, base_fields):
        """Phased policy dict does not include metadata keys when None."""
        request = _make_request(
            base_fields,
            phases=[{"name": "test"}],
            config={"on_error": "skip"},
        )
        result = request.to_policy_dict()

        assert "name" not in result
        assert "description" not in result
        assert "category" not in result

    def test_legacy_policy_dict_includes_metadata(self, base_fields):
        """Legacy policy dict emits metadata when set."""
        request = _make_request(
            base_fields,
            display_name="My Legacy Policy",
            description="Legacy desc",
            category="archive",
        )
        result = request.to_policy_dict()

        assert result["name"] == "My Legacy Policy"
        assert result["description"] == "Legacy desc"
        assert result["category"] == "archive"

    def test_legacy_policy_dict_omits_null_metadata(self, base_fields):
        """Legacy policy dict does not include metadata keys when None."""
        request = _make_request(base_fields)
        result = request.to_policy_dict()

        assert "name" not in result
        assert "description" not in result
        assert "category" not in result

    def test_from_dict_preserves_metadata(self, base_fields):
        """from_dict round-trips metadata through to_policy_dict."""
        data = {
            **base_fields,
            "phases": [{"name": "test"}],
            "config": {"on_error": "skip"},
            "display_name": "Round Trip Name",
            "description": "Round trip desc",
            "category": "transcode",
        }
        request = PolicyEditorRequest.from_dict(data)
        result = request.to_policy_dict()

        assert result["name"] == "Round Trip Name"
        assert result["description"] == "Round trip desc"
        assert result["category"] == "transcode"

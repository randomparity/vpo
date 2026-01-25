"""Unit tests for policy/editor.py.

Tests the PolicyRoundTripEditor class:
- YAML comment preservation during round-trip
- Unknown field preservation
- Field accessors for V3-V10 schema features
- Path validation and allowed directory constraints
- Load/save functionality with validation
"""

import pytest

from vpo.policy.editor import KNOWN_POLICY_FIELDS, PolicyRoundTripEditor
from vpo.policy.loader import PolicyValidationError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def minimal_policy_content() -> str:
    """Minimal valid policy content."""
    return """schema_version: 12
phases:
  - name: test
    container:
      target: mkv
"""


@pytest.fixture
def policy_with_comments() -> str:
    """Policy content with YAML comments."""
    return """# Top-level comment
schema_version: 12  # Schema version comment
# Phase section comment
phases:
  - name: test  # Phase name comment
    container:
      target: mkv
"""


@pytest.fixture
def policy_with_unknown_fields() -> str:
    """Policy content with unknown fields."""
    return """schema_version: 12
custom_field: custom_value
phases:
  - name: test
    container:
      target: mkv
another_unknown: 42
"""


@pytest.fixture
def policy_file(tmp_path, minimal_policy_content):
    """Create a temporary policy file."""
    policy_path = tmp_path / "test_policy.yaml"
    policy_path.write_text(minimal_policy_content)
    return policy_path


@pytest.fixture
def policy_file_with_comments(tmp_path, policy_with_comments):
    """Create a temporary policy file with comments."""
    policy_path = tmp_path / "commented_policy.yaml"
    policy_path.write_text(policy_with_comments)
    return policy_path


@pytest.fixture
def policy_file_with_unknown(tmp_path, policy_with_unknown_fields):
    """Create a temporary policy file with unknown fields."""
    policy_path = tmp_path / "unknown_fields_policy.yaml"
    policy_path.write_text(policy_with_unknown_fields)
    return policy_path


# =============================================================================
# Tests for PolicyRoundTripEditor initialization
# =============================================================================


class TestPolicyRoundTripEditorInit:
    """Tests for PolicyRoundTripEditor.__init__ method."""

    def test_initializes_with_valid_path(self, policy_file):
        """Successfully initializes with an existing policy file."""
        editor = PolicyRoundTripEditor(policy_file)

        assert editor.policy_path == policy_file.resolve()

    def test_raises_when_file_not_found(self, tmp_path):
        """Raises FileNotFoundError for non-existent file."""
        non_existent = tmp_path / "does_not_exist.yaml"

        with pytest.raises(FileNotFoundError) as exc_info:
            PolicyRoundTripEditor(non_existent)

        assert "not found" in str(exc_info.value)

    def test_allows_path_within_allowed_dir(self, tmp_path, minimal_policy_content):
        """Successfully initializes when path is within allowed_dir."""
        allowed_dir = tmp_path / "policies"
        allowed_dir.mkdir()
        policy_path = allowed_dir / "test.yaml"
        policy_path.write_text(minimal_policy_content)

        editor = PolicyRoundTripEditor(policy_path, allowed_dir=allowed_dir)

        assert editor.policy_path == policy_path.resolve()

    def test_raises_when_path_outside_allowed_dir(
        self, tmp_path, minimal_policy_content
    ):
        """Raises ValueError when path is outside allowed_dir."""
        allowed_dir = tmp_path / "policies"
        allowed_dir.mkdir()
        outside_dir = tmp_path / "other"
        outside_dir.mkdir()
        policy_path = outside_dir / "test.yaml"
        policy_path.write_text(minimal_policy_content)

        with pytest.raises(ValueError) as exc_info:
            PolicyRoundTripEditor(policy_path, allowed_dir=allowed_dir)

        assert "outside allowed directory" in str(exc_info.value)


# =============================================================================
# Tests for PolicyRoundTripEditor.load
# =============================================================================


class TestPolicyRoundTripEditorLoad:
    """Tests for PolicyRoundTripEditor.load method."""

    def test_loads_policy_data(self, policy_file):
        """Successfully loads policy data from file."""
        editor = PolicyRoundTripEditor(policy_file)

        data = editor.load()

        assert data["schema_version"] == 12
        assert "phases" in data

    def test_preserves_unknown_fields_on_load(self, policy_file_with_unknown):
        """Unknown fields are preserved when loading."""
        editor = PolicyRoundTripEditor(policy_file_with_unknown)

        data = editor.load()

        assert data["custom_field"] == "custom_value"
        assert data["another_unknown"] == 42

    def test_raises_on_empty_file(self, tmp_path):
        """Raises PolicyValidationError for empty file."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")

        editor = PolicyRoundTripEditor(empty_file)

        with pytest.raises(PolicyValidationError) as exc_info:
            editor.load()

        assert "empty" in str(exc_info.value).lower()

    def test_raises_on_non_mapping_file(self, tmp_path):
        """Raises PolicyValidationError when file is not a YAML mapping."""
        list_file = tmp_path / "list.yaml"
        list_file.write_text("- item1\n- item2\n")

        editor = PolicyRoundTripEditor(list_file)

        with pytest.raises(PolicyValidationError) as exc_info:
            editor.load()

        assert "mapping" in str(exc_info.value).lower()

    def test_raises_on_invalid_yaml_syntax(self, tmp_path):
        """Raises PolicyValidationError for invalid YAML syntax."""
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("schema_version: 12\n  invalid_indent: true")

        editor = PolicyRoundTripEditor(invalid_file)

        with pytest.raises(PolicyValidationError) as exc_info:
            editor.load()

        assert "Failed to load" in str(exc_info.value)


# =============================================================================
# Tests for PolicyRoundTripEditor.save
# =============================================================================


class TestPolicyRoundTripEditorSave:
    """Tests for PolicyRoundTripEditor.save method."""

    def test_saves_updated_data(self, policy_file):
        """Successfully saves updated policy data."""
        editor = PolicyRoundTripEditor(policy_file)
        data = editor.load()

        # Update a field
        data["schema_version"] = 12
        editor.save(data)

        # Verify by reloading
        editor2 = PolicyRoundTripEditor(policy_file)
        reloaded = editor2.load()
        assert reloaded["schema_version"] == 12

    def test_preserves_unknown_fields_on_save(self, policy_file_with_unknown):
        """Unknown fields are preserved when saving."""
        editor = PolicyRoundTripEditor(policy_file_with_unknown)
        data = editor.load()

        # Update a known field
        data["schema_version"] = 12
        editor.save(data)

        # Verify unknown fields preserved
        editor2 = PolicyRoundTripEditor(policy_file_with_unknown)
        reloaded = editor2.load()
        assert reloaded["custom_field"] == "custom_value"
        assert reloaded["another_unknown"] == 42

    def test_raises_on_invalid_policy(self, policy_file):
        """Raises PolicyValidationError when saving invalid policy."""
        editor = PolicyRoundTripEditor(policy_file)
        data = editor.load()

        # Set invalid schema version
        data["schema_version"] = 999

        with pytest.raises(PolicyValidationError):
            editor.save(data)


# =============================================================================
# Tests for comment preservation
# =============================================================================


class TestCommentPreservation:
    """Tests for YAML comment preservation during round-trip."""

    def test_preserves_comments_on_round_trip(self, policy_file_with_comments):
        """Comments are preserved after load/save cycle."""
        editor = PolicyRoundTripEditor(policy_file_with_comments)
        data = editor.load()

        # Make a minor change
        data["schema_version"] = 12
        editor.save(data)

        # Read raw file content
        content = policy_file_with_comments.read_text()

        # Check comments are preserved
        assert "# Top-level comment" in content
        assert "# Schema version comment" in content
        assert "# Phase section comment" in content
        assert "# Phase name comment" in content


# =============================================================================
# Tests for field accessors
# =============================================================================


class TestFieldAccessors:
    """Tests for field accessor methods."""

    def test_get_set_audio_filter(self):
        """Test get/set for audio_filter field."""
        data: dict = {}

        # Initially None
        assert PolicyRoundTripEditor.get_audio_filter(data) is None

        # Set value
        audio_filter = {"include_languages": ["eng", "jpn"]}
        PolicyRoundTripEditor.set_audio_filter(data, audio_filter)
        assert PolicyRoundTripEditor.get_audio_filter(data) == audio_filter

        # Remove value
        PolicyRoundTripEditor.set_audio_filter(data, None)
        assert PolicyRoundTripEditor.get_audio_filter(data) is None
        assert "audio_filter" not in data

    def test_get_set_subtitle_filter(self):
        """Test get/set for subtitle_filter field."""
        data: dict = {}

        assert PolicyRoundTripEditor.get_subtitle_filter(data) is None

        sub_filter = {"include_languages": ["eng"]}
        PolicyRoundTripEditor.set_subtitle_filter(data, sub_filter)
        assert PolicyRoundTripEditor.get_subtitle_filter(data) == sub_filter

        PolicyRoundTripEditor.set_subtitle_filter(data, None)
        assert "subtitle_filter" not in data

    def test_get_set_attachment_filter(self):
        """Test get/set for attachment_filter field."""
        data: dict = {}

        assert PolicyRoundTripEditor.get_attachment_filter(data) is None

        attach_filter = {"remove_all": True}
        PolicyRoundTripEditor.set_attachment_filter(data, attach_filter)
        assert PolicyRoundTripEditor.get_attachment_filter(data) == attach_filter

        PolicyRoundTripEditor.set_attachment_filter(data, None)
        assert "attachment_filter" not in data

    def test_get_set_container(self):
        """Test get/set for container field."""
        data: dict = {}

        assert PolicyRoundTripEditor.get_container(data) is None

        container = {"target": "mkv"}
        PolicyRoundTripEditor.set_container(data, container)
        assert PolicyRoundTripEditor.get_container(data) == container

        PolicyRoundTripEditor.set_container(data, None)
        assert "container" not in data

    def test_get_set_conditional(self):
        """Test get/set for conditional field."""
        data: dict = {}

        assert PolicyRoundTripEditor.get_conditional(data) is None

        conditional = [{"name": "rule1", "when": {"exists": {"track_type": "audio"}}}]
        PolicyRoundTripEditor.set_conditional(data, conditional)
        assert PolicyRoundTripEditor.get_conditional(data) == conditional

        PolicyRoundTripEditor.set_conditional(data, None)
        assert "conditional" not in data

    def test_get_set_audio_synthesis(self):
        """Test get/set for audio_synthesis field."""
        data: dict = {}

        assert PolicyRoundTripEditor.get_audio_synthesis(data) is None

        synthesis = [{"name": "stereo", "from_track": 0}]
        PolicyRoundTripEditor.set_audio_synthesis(data, synthesis)
        assert PolicyRoundTripEditor.get_audio_synthesis(data) == synthesis

        PolicyRoundTripEditor.set_audio_synthesis(data, None)
        assert "audio_synthesis" not in data

    def test_get_set_transcode(self):
        """Test get/set for transcode field."""
        data: dict = {}

        assert PolicyRoundTripEditor.get_transcode(data) is None

        transcode = {"video": {"target_codec": "hevc"}}
        PolicyRoundTripEditor.set_transcode(data, transcode)
        assert PolicyRoundTripEditor.get_transcode(data) == transcode

        PolicyRoundTripEditor.set_transcode(data, None)
        assert "transcode" not in data

    def test_get_set_video_transcode(self):
        """Test get/set for video_transcode nested field."""
        data: dict = {}

        # Initially None (no transcode key)
        assert PolicyRoundTripEditor.get_video_transcode(data) is None

        # Set creates parent if needed
        video_config = {"target_codec": "hevc", "crf": 20}
        PolicyRoundTripEditor.set_video_transcode(data, video_config)
        assert PolicyRoundTripEditor.get_video_transcode(data) == video_config
        assert "transcode" in data

        # Remove cleans up parent if empty
        PolicyRoundTripEditor.set_video_transcode(data, None)
        assert "transcode" not in data

    def test_get_set_audio_transcode(self):
        """Test get/set for audio_transcode nested field."""
        data: dict = {}

        assert PolicyRoundTripEditor.get_audio_transcode(data) is None

        audio_config = {"transcode_to": "aac", "transcode_bitrate": "192k"}
        PolicyRoundTripEditor.set_audio_transcode(data, audio_config)
        assert PolicyRoundTripEditor.get_audio_transcode(data) == audio_config

        PolicyRoundTripEditor.set_audio_transcode(data, None)
        assert "transcode" not in data

    def test_video_and_audio_transcode_coexist(self):
        """Test that video and audio transcode can coexist."""
        data: dict = {}

        video_config = {"target_codec": "hevc"}
        audio_config = {"transcode_to": "aac"}

        PolicyRoundTripEditor.set_video_transcode(data, video_config)
        PolicyRoundTripEditor.set_audio_transcode(data, audio_config)

        assert PolicyRoundTripEditor.get_video_transcode(data) == video_config
        assert PolicyRoundTripEditor.get_audio_transcode(data) == audio_config

        # Remove video, audio should remain
        PolicyRoundTripEditor.set_video_transcode(data, None)
        assert PolicyRoundTripEditor.get_audio_transcode(data) == audio_config
        assert "transcode" in data

    def test_get_set_workflow(self):
        """Test get/set for workflow field."""
        data: dict = {}

        assert PolicyRoundTripEditor.get_workflow(data) is None

        workflow = {"auto_process": True, "on_error": "skip"}
        PolicyRoundTripEditor.set_workflow(data, workflow)
        assert PolicyRoundTripEditor.get_workflow(data) == workflow

        PolicyRoundTripEditor.set_workflow(data, None)
        assert "workflow" not in data

    def test_get_set_phases(self):
        """Test get/set for phases field."""
        data: dict = {}

        assert PolicyRoundTripEditor.get_phases(data) is None

        phases = [{"name": "normalize"}, {"name": "transcode"}]
        PolicyRoundTripEditor.set_phases(data, phases)
        assert PolicyRoundTripEditor.get_phases(data) == phases

        PolicyRoundTripEditor.set_phases(data, None)
        assert "phases" not in data

    def test_get_set_config(self):
        """Test get/set for config field."""
        data: dict = {}

        assert PolicyRoundTripEditor.get_config(data) is None

        config = {"on_error": "continue"}
        PolicyRoundTripEditor.set_config(data, config)
        assert PolicyRoundTripEditor.get_config(data) == config

        PolicyRoundTripEditor.set_config(data, None)
        assert "config" not in data


# =============================================================================
# Tests for utility methods
# =============================================================================


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_get_policy_name(self, policy_file):
        """Test get_policy_name returns filename stem."""
        editor = PolicyRoundTripEditor(policy_file)

        assert editor.get_policy_name() == "test_policy"

    def test_get_unknown_fields(self):
        """Test get_unknown_fields identifies non-standard fields."""
        editor_cls = PolicyRoundTripEditor
        data = {
            "schema_version": 12,
            "phases": [],
            "custom_field": "value",
            "another_unknown": 42,
        }

        unknown = editor_cls.get_unknown_fields(editor_cls, data)

        assert set(unknown) == {"custom_field", "another_unknown"}

    def test_get_unknown_fields_empty_when_all_known(self):
        """Test get_unknown_fields returns empty for valid-only fields."""
        editor_cls = PolicyRoundTripEditor
        data = {
            "schema_version": 12,
            "phases": [],
            "config": {"on_error": "skip"},
        }

        unknown = editor_cls.get_unknown_fields(editor_cls, data)

        assert unknown == []

    def test_get_phase_names(self):
        """Test get_phase_names extracts phase names."""
        data = {
            "phases": [
                {"name": "normalize"},
                {"name": "transcode"},
                {"name": "verify"},
            ]
        }

        names = PolicyRoundTripEditor.get_phase_names(data)

        assert names == ["normalize", "transcode", "verify"]

    def test_get_phase_names_handles_missing(self):
        """Test get_phase_names returns empty list when no phases."""
        data: dict = {"schema_version": 12}

        names = PolicyRoundTripEditor.get_phase_names(data)

        assert names == []

    def test_get_phase_names_handles_invalid_entries(self):
        """Test get_phase_names handles non-dict entries."""
        data = {
            "phases": [
                {"name": "valid"},
                "invalid_string_entry",
                {"name": "also_valid"},
            ]
        }

        names = PolicyRoundTripEditor.get_phase_names(data)

        assert names == ["valid", "also_valid"]

    def test_is_phased_policy_true(self):
        """Test is_phased_policy returns True when phases present."""
        data = {"schema_version": 12, "phases": []}

        assert PolicyRoundTripEditor.is_phased_policy(data) is True

    def test_is_phased_policy_false(self):
        """Test is_phased_policy returns False when no phases."""
        data = {"schema_version": 12, "audio_filter": {}}

        assert PolicyRoundTripEditor.is_phased_policy(data) is False


# =============================================================================
# Tests for KNOWN_POLICY_FIELDS constant
# =============================================================================


class TestKnownPolicyFields:
    """Tests for KNOWN_POLICY_FIELDS constant."""

    def test_contains_expected_v1_v2_fields(self):
        """KNOWN_POLICY_FIELDS includes V1-V2 base fields."""
        expected = {
            "schema_version",
            "track_order",
            "audio_language_preference",
            "subtitle_language_preference",
            "commentary_patterns",
            "default_flags",
            "transcode",
            "transcription",
        }
        assert expected.issubset(KNOWN_POLICY_FIELDS)

    def test_contains_expected_v3_fields(self):
        """KNOWN_POLICY_FIELDS includes V3+ fields."""
        expected = {
            "audio_filter",
            "subtitle_filter",
            "attachment_filter",
            "container",
        }
        assert expected.issubset(KNOWN_POLICY_FIELDS)

    def test_contains_expected_v4_v5_fields(self):
        """KNOWN_POLICY_FIELDS includes V4-V5 fields."""
        expected = {"conditional", "audio_synthesis"}
        assert expected.issubset(KNOWN_POLICY_FIELDS)

    def test_contains_expected_phased_fields(self):
        """KNOWN_POLICY_FIELDS includes phased policy fields."""
        expected = {"phases", "config", "workflow"}
        assert expected.issubset(KNOWN_POLICY_FIELDS)

    def test_contains_metadata_fields(self):
        """KNOWN_POLICY_FIELDS includes metadata fields."""
        expected = {"description", "category"}
        assert expected.issubset(KNOWN_POLICY_FIELDS)

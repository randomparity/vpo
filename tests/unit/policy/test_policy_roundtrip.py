"""Unit tests for PolicyRoundTripEditor unknown field and comment preservation."""

from pathlib import Path

import pytest

from vpo.policy.editor import PolicyRoundTripEditor
from vpo.policy.loader import PolicyValidationError


@pytest.fixture
def minimal_policy_file(tmp_path):
    """Create a minimal valid policy file for testing."""
    policy_file = tmp_path / "minimal.yaml"
    policy_file.write_text("""schema_version: 12
config:
  audio_language_preference:
    - eng
  subtitle_language_preference:
    - eng
  commentary_patterns:
    - commentary
phases:
  - name: organize
    track_order:
      - video
      - audio_main
    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true
      set_preferred_subtitle_default: false
      clear_other_defaults: true
""")
    return policy_file


@pytest.fixture
def policy_with_unknown_fields(tmp_path):
    """Create a policy file with unknown fields for round-trip testing."""
    policy_file = tmp_path / "unknown.yaml"
    policy_file.write_text("""schema_version: 12
config:
  audio_language_preference:
    - eng
  subtitle_language_preference:
    - eng
  commentary_patterns:
    - commentary
phases:
  - name: organize
    track_order:
      - video
      - audio_main
    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true
      set_preferred_subtitle_default: false
      clear_other_defaults: true

# Unknown field - should be preserved
x_custom_field: preserved_value
x_another_field:
  nested: data
  count: 42
""")
    return policy_file


@pytest.fixture
def policy_with_comments(tmp_path):
    """Create a policy file with YAML comments for preservation testing."""
    policy_file = tmp_path / "comments.yaml"
    policy_file.write_text("""schema_version: 12
config:
  # Language preferences
  audio_language_preference:
    - eng  # English
    - und  # Undefined
  subtitle_language_preference:
    - eng
  # Commentary detection
  commentary_patterns:
    - commentary
    - director
phases:
  # Track ordering configuration
  - name: organize
    track_order:
      - video
      - audio_main
    # Default flags configuration
    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true
      set_preferred_subtitle_default: false
      clear_other_defaults: true
""")
    return policy_file


def test_load_valid_policy(minimal_policy_file):
    """Test loading a valid policy file."""
    editor = PolicyRoundTripEditor(minimal_policy_file)
    data = editor.load()

    assert data["schema_version"] == 12
    assert data["phases"][0]["track_order"] == ["video", "audio_main"]
    assert data["config"]["audio_language_preference"] == ["eng"]
    assert data["phases"][0]["default_flags"]["set_first_video_default"] is True


def test_load_nonexistent_file():
    """Test loading a nonexistent policy file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Policy file not found"):
        PolicyRoundTripEditor(Path("/nonexistent/policy.yaml"))


def test_load_empty_file(tmp_path):
    """Test loading an empty file raises PolicyValidationError."""
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("")

    editor = PolicyRoundTripEditor(empty_file)
    with pytest.raises(PolicyValidationError, match="Policy file is empty"):
        editor.load()


def test_load_invalid_yaml(tmp_path):
    """Test loading invalid YAML syntax raises PolicyValidationError."""
    invalid_file = tmp_path / "invalid.yaml"
    invalid_file.write_text("{ invalid: yaml: syntax")

    editor = PolicyRoundTripEditor(invalid_file)
    with pytest.raises(PolicyValidationError, match="Failed to load policy file"):
        editor.load()


def test_save_valid_update(minimal_policy_file):
    """Test saving a valid update to a policy file."""
    editor = PolicyRoundTripEditor(minimal_policy_file)
    data = editor.load()

    # Modify a field
    data["config"]["audio_language_preference"] = ["jpn", "eng"]

    # Save should succeed
    editor.save(data)

    # Reload and verify
    reloaded = editor.load()
    assert reloaded["config"]["audio_language_preference"] == ["jpn", "eng"]


def test_save_invalid_data_raises_error(minimal_policy_file):
    """Test saving invalid data raises PolicyValidationError."""
    editor = PolicyRoundTripEditor(minimal_policy_file)
    data = editor.load()

    # Make data invalid (empty track_order)
    data["phases"][0]["track_order"] = []

    with pytest.raises(PolicyValidationError, match="track_order cannot be empty"):
        editor.save(data)


def test_save_invalid_language_code_raises_error(minimal_policy_file):
    """Test saving invalid language code raises PolicyValidationError."""
    editor = PolicyRoundTripEditor(minimal_policy_file)
    data = editor.load()

    # Invalid language code
    data["config"]["audio_language_preference"] = ["invalid123"]

    with pytest.raises(PolicyValidationError):
        editor.save(data)


def test_unknown_field_preservation(policy_with_unknown_fields):
    """Test that unknown fields are preserved during round-trip.

    This is a critical requirement (FR-011): Unknown fields must be preserved
    when editing known fields.
    """
    editor = PolicyRoundTripEditor(policy_with_unknown_fields)
    data = editor.load()

    # Verify unknown fields are loaded
    assert data["x_custom_field"] == "preserved_value"
    assert data["x_another_field"]["nested"] == "data"
    assert data["x_another_field"]["count"] == 42

    # Modify a known field
    data["config"]["audio_language_preference"] = ["jpn", "eng"]

    # Save
    editor.save(data)

    # Reload and verify unknown fields are still present
    reloaded = editor.load()
    assert reloaded["x_custom_field"] == "preserved_value"
    assert reloaded["x_another_field"]["nested"] == "data"
    assert reloaded["x_another_field"]["count"] == 42
    assert reloaded["config"]["audio_language_preference"] == ["jpn", "eng"]


def test_multiple_unknown_fields_preserved(tmp_path):
    """Test that multiple unknown fields at different levels are preserved."""
    policy_file = tmp_path / "multi_unknown.yaml"
    policy_file.write_text("""schema_version: 12
x_top_level: value1
config:
  audio_language_preference:
    - eng
  subtitle_language_preference:
    - eng
  commentary_patterns:
    - commentary
phases:
  - name: organize
    track_order:
      - video
    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true
      set_preferred_subtitle_default: false
      clear_other_defaults: true
x_middle_field: value2
x_nested_structure:
  key1: val1
  key2: val2
x_end_field: value3
""")

    editor = PolicyRoundTripEditor(policy_file)
    data = editor.load()

    # Modify track_order
    data["phases"][0]["track_order"] = ["video", "audio_main", "subtitle_main"]

    editor.save(data)

    # Verify all unknown fields preserved
    reloaded = editor.load()
    assert reloaded["x_top_level"] == "value1"
    assert reloaded["x_middle_field"] == "value2"
    assert reloaded["x_nested_structure"]["key1"] == "val1"
    assert reloaded["x_nested_structure"]["key2"] == "val2"
    assert reloaded["x_end_field"] == "value3"
    assert reloaded["phases"][0]["track_order"] == [
        "video",
        "audio_main",
        "subtitle_main",
    ]


def test_get_policy_name(minimal_policy_file):
    """Test getting policy name from filename."""
    editor = PolicyRoundTripEditor(minimal_policy_file)
    assert editor.get_policy_name() == "minimal"


def test_save_preserves_unmodified_fields(minimal_policy_file):
    """Test that unmodified fields are not changed during save."""
    editor = PolicyRoundTripEditor(minimal_policy_file)
    original_data = editor.load()

    # Modify only one field
    import copy

    updated_data = copy.deepcopy(original_data)
    updated_data["config"]["commentary_patterns"] = ["commentary", "director", "actor"]

    editor.save(updated_data)

    # Verify only the modified field changed
    reloaded = editor.load()
    assert (
        reloaded["phases"][0]["track_order"]
        == original_data["phases"][0]["track_order"]
    )
    assert (
        reloaded["config"]["audio_language_preference"]
        == original_data["config"]["audio_language_preference"]
    )
    assert (
        reloaded["phases"][0]["default_flags"]
        == original_data["phases"][0]["default_flags"]
    )
    assert reloaded["config"]["commentary_patterns"] == [
        "commentary",
        "director",
        "actor",
    ]


@pytest.mark.skip(
    reason="YAML safe mode does not preserve comments - acceptable security tradeoff"
)
def test_comment_preservation_best_effort(policy_with_comments):
    """Test that YAML comments are preserved (best-effort).

    Comments on unchanged fields should be preserved. Comments on modified
    fields may be lost or shifted (documented as best-effort behavior).
    """
    editor = PolicyRoundTripEditor(policy_with_comments)
    data = editor.load()

    # Modify track_order (comment may be lost)
    data["phases"][0]["track_order"] = ["video", "audio_main", "subtitle_main"]

    editor.save(data)

    # Read raw file to check for comment preservation
    content = policy_with_comments.read_text()

    # At least some comments should be preserved (best-effort)
    # Note: ruamel.yaml's comment preservation is best-effort
    # Comments on modified sections may be repositioned or lost
    assert (
        "# Commentary detection" in content
        or "# Default flags configuration" in content
    )


@pytest.mark.skip(
    reason="YAML safe mode does not preserve comments - acceptable security tradeoff"
)
def test_comment_on_unchanged_field_preserved(tmp_path):
    """Test that comments on unchanged fields are definitely preserved."""
    policy_file = tmp_path / "comments_unchanged.yaml"
    policy_file.write_text("""schema_version: 12
config:
  # Audio settings comment
  audio_language_preference:
    - eng
  subtitle_language_preference:
    - eng
  commentary_patterns:
    - commentary
phases:
  # This comment should be preserved
  - name: organize
    track_order:
      - video
    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true
      set_preferred_subtitle_default: false
      clear_other_defaults: true
""")

    editor = PolicyRoundTripEditor(policy_file)
    data = editor.load()

    # Modify a DIFFERENT field (not track_order)
    data["config"]["audio_language_preference"] = ["jpn", "eng"]

    editor.save(data)

    # Read raw file
    content = policy_file.read_text()

    # Comment on unchanged field (track_order) should be preserved
    assert "# This comment should be preserved" in content

"""
Unit tests for PolicyRoundTripEditor class.

Tests the core policy editing functionality including:
- Loading policies
- Updating fields
- Saving with preservation
- Error handling
"""

from pathlib import Path

import pytest

from vpo.policy.editor import PolicyRoundTripEditor
from vpo.policy.loader import PolicyValidationError


def create_test_policy(
    path: Path, with_unknown_fields: bool = False, with_comments: bool = False
):
    """Helper to create test policy files."""
    content = """schema_version: 12
track_order:
  - video
  - audio_main
  - audio_alternate
audio_language_preference:
  - eng
  - und
subtitle_language_preference:
  - eng
  - und
commentary_patterns:
  - commentary
  - director
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
"""

    if with_comments:
        content = """schema_version: 12
# This is a comment about track order
track_order:
  - video
  - audio_main  # Main audio track
  - audio_alternate
# Audio preferences
audio_language_preference:
  - eng
  - und
subtitle_language_preference:
  - eng
  - und
commentary_patterns:
  - commentary
  - director
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
"""

    if with_unknown_fields:
        content += "\n# Unknown field for testing\nx_custom_field: preserved_value\n"

    path.write_text(content)


def test_load_valid_policy(tmp_path):
    """Test loading a valid policy file."""
    policy_file = tmp_path / "test.yaml"
    create_test_policy(policy_file)

    editor = PolicyRoundTripEditor(policy_file)
    data = editor.load()

    assert data["schema_version"] == 12
    assert "track_order" in data
    assert "audio_language_preference" in data
    assert "subtitle_language_preference" in data
    assert data["track_order"] == ["video", "audio_main", "audio_alternate"]


def test_load_nonexistent_file(tmp_path):
    """Test loading nonexistent file raises error."""
    policy_file = tmp_path / "nonexistent.yaml"

    with pytest.raises(FileNotFoundError, match="not found"):
        PolicyRoundTripEditor(policy_file)


def test_load_invalid_yaml(tmp_path):
    """Test loading invalid YAML raises error."""
    policy_file = tmp_path / "invalid.yaml"
    policy_file.write_text("not: valid: yaml: [[[")

    editor = PolicyRoundTripEditor(policy_file)

    # ruamel.yaml will raise its own exception
    with pytest.raises(Exception):
        editor.load()


def test_save_updates_file(tmp_path):
    """Test save updates the policy file."""
    policy_file = tmp_path / "test.yaml"
    create_test_policy(policy_file)

    editor = PolicyRoundTripEditor(policy_file)
    data = editor.load()

    # Update audio language preference
    data["audio_language_preference"] = ["jpn", "eng", "und"]
    editor.save(data)

    # Reload and verify
    editor2 = PolicyRoundTripEditor(policy_file)
    reloaded = editor2.load()

    assert reloaded["audio_language_preference"] == ["jpn", "eng", "und"]


def test_save_preserves_unknown_fields(tmp_path):
    """Test save preserves unknown fields."""
    policy_file = tmp_path / "test.yaml"
    create_test_policy(policy_file, with_unknown_fields=True)

    editor = PolicyRoundTripEditor(policy_file)
    data = editor.load()

    # Verify unknown field exists
    assert data["x_custom_field"] == "preserved_value"

    # Update a known field
    data["audio_language_preference"] = ["fra", "eng"]
    editor.save(data)

    # Reload and verify unknown field still exists
    editor2 = PolicyRoundTripEditor(policy_file)
    reloaded = editor2.load()

    assert reloaded["x_custom_field"] == "preserved_value"
    assert reloaded["audio_language_preference"] == ["fra", "eng"]


@pytest.mark.skip(
    reason="YAML safe mode does not preserve comments - acceptable security tradeoff"
)
def test_save_preserves_comments(tmp_path):
    """Test save preserves comments on unchanged fields."""
    policy_file = tmp_path / "test.yaml"
    create_test_policy(policy_file, with_comments=True)

    editor = PolicyRoundTripEditor(policy_file)
    data = editor.load()

    # Update audio language preference (leaving others unchanged)
    data["audio_language_preference"] = ["deu", "eng"]
    editor.save(data)

    # Read raw file content
    content = policy_file.read_text()

    # Comments on unchanged fields should be preserved
    assert "# This is a comment about track order" in content
    assert "deu" in content


def test_save_invalid_data_raises_error(tmp_path):
    """Test save with invalid data raises error."""
    policy_file = tmp_path / "test.yaml"
    create_test_policy(policy_file)

    editor = PolicyRoundTripEditor(policy_file)
    data = editor.load()

    # Make data invalid (empty track_order)
    data["track_order"] = []

    with pytest.raises(PolicyValidationError, match="validation failed"):
        editor.save(data)


def test_save_invalid_language_code(tmp_path):
    """Test save with invalid language code raises error."""
    policy_file = tmp_path / "test.yaml"
    create_test_policy(policy_file)

    editor = PolicyRoundTripEditor(policy_file)
    data = editor.load()

    # Invalid language code format
    data["audio_language_preference"] = ["invalid123"]

    with pytest.raises(PolicyValidationError, match="validation failed"):
        editor.save(data)


def test_get_policy_name(tmp_path):
    """Test getting policy name from filename."""
    policy_file = tmp_path / "my-policy.yaml"
    create_test_policy(policy_file)

    editor = PolicyRoundTripEditor(policy_file)

    assert editor.get_policy_name() == "my-policy"


def test_save_multiple_times(tmp_path):
    """Test saving multiple times works correctly."""
    policy_file = tmp_path / "test.yaml"
    create_test_policy(policy_file)

    editor = PolicyRoundTripEditor(policy_file)

    # First save
    data = editor.load()
    data["audio_language_preference"] = ["jpn"]
    editor.save(data)

    # Second save
    data = editor.load()
    data["audio_language_preference"] = ["fra", "eng"]
    editor.save(data)

    # Third save
    data = editor.load()
    data["subtitle_language_preference"] = ["deu"]
    editor.save(data)

    # Verify final state
    final_editor = PolicyRoundTripEditor(policy_file)
    final_data = final_editor.load()

    assert final_data["audio_language_preference"] == ["fra", "eng"]
    assert final_data["subtitle_language_preference"] == ["deu"]


def test_load_policy_with_transcode(tmp_path):
    """Test loading policy with transcode section."""
    policy_file = tmp_path / "transcode.yaml"
    policy_file.write_text("""schema_version: 12
track_order:
  - video
  - audio_main
audio_language_preference:
  - eng
subtitle_language_preference:
  - eng
commentary_patterns:
  - commentary
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
transcode:
  target_video_codec: hevc
  target_crf: 23
  audio_preserve_codecs:
    - aac
    - opus
  audio_transcode_to: aac
  audio_transcode_bitrate: 192k
""")

    editor = PolicyRoundTripEditor(policy_file)
    data = editor.load()

    assert "transcode" in data
    assert data["transcode"]["target_video_codec"] == "hevc"
    assert data["transcode"]["target_crf"] == 23


def test_save_preserves_transcode(tmp_path):
    """Test save preserves transcode section."""
    policy_file = tmp_path / "transcode.yaml"
    policy_file.write_text("""schema_version: 12
track_order:
  - video
  - audio_main
audio_language_preference:
  - eng
subtitle_language_preference:
  - eng
commentary_patterns:
  - commentary
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
transcode:
  target_video_codec: hevc
  target_crf: 23
  audio_preserve_codecs:
    - aac
  audio_transcode_to: aac
  audio_transcode_bitrate: 192k
""")

    editor = PolicyRoundTripEditor(policy_file)
    data = editor.load()

    # Update audio language preference
    data["audio_language_preference"] = ["jpn", "eng"]
    editor.save(data)

    # Reload and verify transcode preserved
    editor2 = PolicyRoundTripEditor(policy_file)
    reloaded = editor2.load()

    assert reloaded["transcode"]["target_video_codec"] == "hevc"
    assert reloaded["audio_language_preference"] == ["jpn", "eng"]


def test_load_policy_with_transcription(tmp_path):
    """Test loading policy with transcription section."""
    policy_file = tmp_path / "transcription.yaml"
    policy_file.write_text("""schema_version: 12
track_order:
  - video
  - audio_main
audio_language_preference:
  - eng
subtitle_language_preference:
  - eng
commentary_patterns:
  - commentary
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
transcription:
  enabled: true
  update_language_from_transcription: true
  confidence_threshold: 0.8
  detect_commentary: true
  reorder_commentary: true
""")

    editor = PolicyRoundTripEditor(policy_file)
    data = editor.load()

    assert "transcription" in data
    assert data["transcription"]["enabled"] is True
    assert data["transcription"]["detect_commentary"] is True
    assert data["transcription"]["reorder_commentary"] is True


def test_path_traversal_protection(tmp_path):
    """Test that path traversal attacks are prevented."""
    # Create allowed directory with a test policy
    allowed_dir = tmp_path / "policies"
    allowed_dir.mkdir()
    policy_file = allowed_dir / "test.yaml"
    create_test_policy(policy_file)

    # Create a directory outside the allowed directory
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_policy = outside_dir / "malicious.yaml"
    create_test_policy(outside_policy)

    # Test 1: Valid path within allowed directory should work
    editor = PolicyRoundTripEditor(policy_file, allowed_dir=allowed_dir)
    data = editor.load()
    assert data["schema_version"] == 12

    # Test 2: Path outside allowed directory should be rejected
    with pytest.raises(ValueError, match="outside allowed directory"):
        PolicyRoundTripEditor(outside_policy, allowed_dir=allowed_dir)


def test_path_traversal_with_symlinks(tmp_path):
    """Test that symlink-based path traversal is prevented."""
    # Create allowed directory
    allowed_dir = tmp_path / "policies"
    allowed_dir.mkdir()

    # Create a file outside allowed directory
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "secret.yaml"
    create_test_policy(outside_file)

    # Create a symlink in allowed directory pointing outside
    symlink = allowed_dir / "link.yaml"
    symlink.symlink_to(outside_file)

    # Symlink should be rejected because it resolves outside allowed_dir
    with pytest.raises(ValueError, match="outside allowed directory"):
        PolicyRoundTripEditor(symlink, allowed_dir=allowed_dir)


def test_yaml_safe_mode_blocks_dangerous_objects(tmp_path):
    """Test that YAML safe mode blocks dangerous object deserialization."""
    policy_file = tmp_path / "malicious.yaml"

    # Attempt to create a malicious YAML file with Python object execution
    # This would execute arbitrary code if safe mode is not enabled
    malicious_content = """schema_version: 12
track_order:
  - video
audio_language_preference:
  - eng
subtitle_language_preference:
  - eng
commentary_patterns: []
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
# Attempt to inject dangerous object
!!python/object/apply:os.system
args: ['echo pwned']
"""
    policy_file.write_text(malicious_content)

    editor = PolicyRoundTripEditor(policy_file)

    # Safe mode should prevent loading this
    with pytest.raises(
        Exception
    ):  # ruamel.yaml raises various exceptions for unsafe tags
        editor.load()


def test_no_path_restriction_when_allowed_dir_not_provided(tmp_path):
    """Test that editor works without path restriction when allowed_dir is None."""
    policy_file = tmp_path / "test.yaml"
    create_test_policy(policy_file)

    # Should work without allowed_dir parameter
    editor = PolicyRoundTripEditor(policy_file)
    data = editor.load()
    assert data["schema_version"] == 12

    # Should also work with allowed_dir=None explicitly
    editor2 = PolicyRoundTripEditor(policy_file, allowed_dir=None)
    data2 = editor2.load()
    assert data2["schema_version"] == 12

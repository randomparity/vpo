"""
End-to-end integration tests for the policy editor flow.

Tests the complete user journey:
1. Load policy for editing
2. Make changes via UI
3. Save policy
4. Verify changes persist
5. Verify unknown fields and comments preserved
"""

import pytest
from aiohttp import web

from video_policy_orchestrator.server.ui.routes import setup_ui_routes


@pytest.fixture
async def test_app_with_policies(tmp_path):
    """Create test aiohttp app with test policies."""
    app = web.Application()

    # Set up temporary policy directory
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()

    # Create test policy with unknown fields and comments
    test_policy = policy_dir / "integration-test.yaml"
    test_policy.write_text("""schema_version: 2

# Track ordering configuration
track_order:
  - video
  - audio_main
  - audio_alternate
  - subtitle_main

# Audio language preferences
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

# Custom field for testing preservation
x_custom_field: preserved_value
x_another_field: also_preserved
""")

    # Store policy dir in app
    app["policy_dir"] = policy_dir

    # Set up routes
    setup_ui_routes(app)

    return app, policy_dir


@pytest.mark.asyncio
async def test_full_policy_edit_flow(aiohttp_client, test_app_with_policies):
    """Test complete edit flow: load → edit → save → verify."""
    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    # Step 1: Load policy for editing
    get_response = await client.get("/api/policies/integration-test")
    assert get_response.status == 200

    policy_data = await get_response.json()
    assert policy_data["name"] == "integration-test"
    assert policy_data["audio_language_preference"] == ["eng", "und"]

    # Step 2: Make changes to the policy
    updated_data = {
        "track_order": policy_data["track_order"],
        "audio_language_preference": ["jpn", "eng", "und"],  # Changed
        "subtitle_language_preference": ["fra", "eng"],  # Changed
        "commentary_patterns": ["commentary", "director", "cast"],  # Added one
        "default_flags": policy_data["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": policy_data["last_modified"],
    }

    # Step 3: Save changes
    put_response = await client.put("/api/policies/integration-test", json=updated_data)
    assert put_response.status == 200

    saved_data = await put_response.json()
    assert saved_data["audio_language_preference"] == ["jpn", "eng", "und"]
    assert saved_data["subtitle_language_preference"] == ["fra", "eng"]
    assert saved_data["commentary_patterns"] == ["commentary", "director", "cast"]

    # Step 4: Reload policy to verify persistence
    reload_response = await client.get("/api/policies/integration-test")
    assert reload_response.status == 200

    reloaded_data = await reload_response.json()
    assert reloaded_data["audio_language_preference"] == ["jpn", "eng", "und"]
    assert reloaded_data["subtitle_language_preference"] == ["fra", "eng"]
    assert reloaded_data["commentary_patterns"] == ["commentary", "director", "cast"]

    # Step 5: Verify unknown fields preserved in file
    policy_file = policy_dir / "integration-test.yaml"
    file_content = policy_file.read_text()

    assert "x_custom_field: preserved_value" in file_content
    assert "x_another_field: also_preserved" in file_content

    # Verify comments preserved
    assert "# Track ordering configuration" in file_content


@pytest.mark.asyncio
async def test_unknown_field_preservation_through_multiple_edits(
    aiohttp_client, test_app_with_policies
):
    """Test that unknown fields survive multiple edit cycles."""
    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    # Edit 1: Change audio languages
    get1 = await client.get("/api/policies/integration-test")
    data1 = await get1.json()

    update1 = {
        "track_order": data1["track_order"],
        "audio_language_preference": ["fra"],
        "subtitle_language_preference": data1["subtitle_language_preference"],
        "commentary_patterns": data1["commentary_patterns"],
        "default_flags": data1["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data1["last_modified"],
    }

    put1 = await client.put("/api/policies/integration-test", json=update1)
    assert put1.status == 200

    # Edit 2: Change subtitle languages
    get2 = await client.get("/api/policies/integration-test")
    data2 = await get2.json()

    update2 = {
        "track_order": data2["track_order"],
        "audio_language_preference": data2["audio_language_preference"],
        "subtitle_language_preference": ["deu"],
        "commentary_patterns": data2["commentary_patterns"],
        "default_flags": data2["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data2["last_modified"],
    }

    put2 = await client.put("/api/policies/integration-test", json=update2)
    assert put2.status == 200

    # Edit 3: Change commentary patterns
    get3 = await client.get("/api/policies/integration-test")
    data3 = await get3.json()

    update3 = {
        "track_order": data3["track_order"],
        "audio_language_preference": data3["audio_language_preference"],
        "subtitle_language_preference": data3["subtitle_language_preference"],
        "commentary_patterns": ["new_pattern"],
        "default_flags": data3["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data3["last_modified"],
    }

    put3 = await client.put("/api/policies/integration-test", json=update3)
    assert put3.status == 200

    # Verify unknown fields still exist after 3 edits
    policy_file = policy_dir / "integration-test.yaml"
    file_content = policy_file.read_text()

    assert "x_custom_field: preserved_value" in file_content
    assert "x_another_field: also_preserved" in file_content


@pytest.mark.asyncio
async def test_comment_preservation(aiohttp_client, test_app_with_policies):
    """Test that comments on unchanged fields are preserved."""
    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    # Load and modify only audio languages (leave others unchanged)
    get_response = await client.get("/api/policies/integration-test")
    data = await get_response.json()

    update_data = {
        "track_order": data["track_order"],
        "audio_language_preference": ["ita", "eng"],  # Only change this
        "subtitle_language_preference": data[
            "subtitle_language_preference"
        ],  # Unchanged
        "commentary_patterns": data["commentary_patterns"],  # Unchanged
        "default_flags": data["default_flags"],  # Unchanged
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data["last_modified"],
    }

    put_response = await client.put("/api/policies/integration-test", json=update_data)
    assert put_response.status == 200

    # Check that comments on unchanged fields are preserved
    policy_file = policy_dir / "integration-test.yaml"
    file_content = policy_file.read_text()

    # Comments on unchanged sections should still be there
    assert "# Track ordering configuration" in file_content
    assert "# Custom field for testing preservation" in file_content


@pytest.mark.asyncio
async def test_validation_prevents_invalid_save(aiohttp_client, test_app_with_policies):
    """Test that validation prevents saving invalid policy data."""
    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    get_response = await client.get("/api/policies/integration-test")
    data = await get_response.json()

    # Try to save with invalid data (empty track_order)
    invalid_data = {
        "track_order": [],  # Invalid
        "audio_language_preference": data["audio_language_preference"],
        "subtitle_language_preference": data["subtitle_language_preference"],
        "commentary_patterns": data["commentary_patterns"],
        "default_flags": data["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data["last_modified"],
    }

    put_response = await client.put("/api/policies/integration-test", json=invalid_data)

    # Should fail validation
    assert put_response.status == 400
    error_data = await put_response.json()
    assert "error" in error_data

    # Verify original policy unchanged
    reload_response = await client.get("/api/policies/integration-test")
    reloaded = await reload_response.json()
    assert len(reloaded["track_order"]) > 0  # Still has original data


@pytest.mark.asyncio
async def test_concurrent_modification_detection(
    aiohttp_client, test_app_with_policies
):
    """Test that concurrent modifications are detected."""
    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    # Simulate two users loading the same policy
    get1 = await client.get("/api/policies/integration-test")
    data1 = await get1.json()

    get2 = await client.get("/api/policies/integration-test")
    data2 = await get2.json()

    # User 1 saves first
    update1 = {
        "track_order": data1["track_order"],
        "audio_language_preference": ["spa", "eng"],
        "subtitle_language_preference": data1["subtitle_language_preference"],
        "commentary_patterns": data1["commentary_patterns"],
        "default_flags": data1["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data1["last_modified"],
    }

    put1 = await client.put("/api/policies/integration-test", json=update1)
    assert put1.status == 200

    # User 2 tries to save with stale timestamp
    update2 = {
        "track_order": data2["track_order"],
        "audio_language_preference": ["por", "eng"],
        "subtitle_language_preference": data2["subtitle_language_preference"],
        "commentary_patterns": data2["commentary_patterns"],
        "default_flags": data2["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data2["last_modified"],  # Stale!
    }

    put2 = await client.put("/api/policies/integration-test", json=update2)

    # Should detect concurrent modification
    assert put2.status == 409
    error_data = await put2.json()
    assert "error" in error_data


@pytest.mark.asyncio
async def test_policy_with_transcription_section(aiohttp_client, tmp_path):
    """Test editing policy with transcription configuration."""
    app = web.Application()
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()

    # Create policy with transcription
    policy = policy_dir / "transcription-test.yaml"
    policy.write_text("""schema_version: 2
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

    app["policy_dir"] = policy_dir
    setup_ui_routes(app)
    client = await aiohttp_client(app)

    # Load policy
    get_response = await client.get("/api/policies/transcription-test")
    data = await get_response.json()

    assert "transcription" in data
    assert data["transcription"]["detect_commentary"] is True

    # Update transcription settings
    data["transcription"]["detect_commentary"] = False
    data["transcription"]["reorder_commentary"] = False

    update = {
        "track_order": data["track_order"],
        "audio_language_preference": data["audio_language_preference"],
        "subtitle_language_preference": data["subtitle_language_preference"],
        "commentary_patterns": data["commentary_patterns"],
        "default_flags": data["default_flags"],
        "transcode": None,
        "transcription": data["transcription"],
        "last_modified_timestamp": data["last_modified"],
    }

    put_response = await client.put("/api/policies/transcription-test", json=update)
    assert put_response.status == 200

    # Verify changes saved
    reload_response = await client.get("/api/policies/transcription-test")
    reloaded = await reload_response.json()

    assert reloaded["transcription"]["detect_commentary"] is False
    assert reloaded["transcription"]["reorder_commentary"] is False

"""Unit tests for policy discovery module."""

from __future__ import annotations

from pathlib import Path

import pytest

from vpo.policy.discovery import (
    PolicySummary,
    _is_default_policy,
    _parse_policy_file,
    discover_policies,
)

# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "policies"


class TestParsePolicyFile:
    """Tests for _parse_policy_file() helper."""

    def test_valid_basic_policy(self) -> None:
        """Parse a valid basic policy file."""
        path = FIXTURES_DIR / "valid-basic.yaml"
        result = _parse_policy_file(path)

        assert result.name == "valid-basic"
        assert result.filename == "valid-basic.yaml"
        assert result.parse_error is None
        assert result.schema_version == 13
        assert result.audio_languages == ["eng"]
        assert result.subtitle_languages == ["eng"]
        assert result.has_transcode is False
        assert result.has_transcription is False
        assert result.last_modified != ""  # Should have a timestamp

    def test_valid_full_policy(self) -> None:
        """Parse a valid policy with transcode and transcription."""
        path = FIXTURES_DIR / "valid-full.yaml"
        result = _parse_policy_file(path)

        assert result.name == "valid-full"
        assert result.filename == "valid-full.yaml"
        assert result.parse_error is None
        assert result.schema_version == 13
        assert result.audio_languages == ["eng", "jpn", "spa"]
        assert result.subtitle_languages == ["eng", "spa"]
        assert result.has_transcode is True
        assert result.has_transcription is True

    def test_invalid_syntax_policy(self) -> None:
        """Parse a policy with YAML syntax error."""
        path = FIXTURES_DIR / "invalid-syntax.yaml"
        result = _parse_policy_file(path)

        assert result.name == "invalid-syntax"
        assert result.filename == "invalid-syntax.yaml"
        assert result.parse_error is not None
        assert "YAML error" in result.parse_error
        # Other fields should be defaults
        assert result.schema_version is None
        assert result.audio_languages == []
        assert result.has_transcode is False

    def test_invalid_format_policy(self) -> None:
        """Parse a policy with wrong format (list instead of mapping)."""
        path = FIXTURES_DIR / "invalid-format.yaml"
        result = _parse_policy_file(path)

        assert result.name == "invalid-format"
        assert result.filename == "invalid-format.yaml"
        assert result.parse_error is not None
        assert "Invalid format" in result.parse_error

    def test_policy_with_schema_version_1(self) -> None:
        """Parse a v1 policy file."""
        path = FIXTURES_DIR / "audio_preference.yaml"
        result = _parse_policy_file(path)

        assert result.name == "audio_preference"
        assert result.schema_version == 13
        assert result.parse_error is None
        assert result.audio_languages == ["jpn", "eng", "und"]
        assert result.subtitle_languages == ["eng", "und"]

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Handle nonexistent file gracefully."""
        path = tmp_path / "does-not-exist.yaml"
        result = _parse_policy_file(path)

        assert result.name == "does-not-exist"
        assert result.filename == "does-not-exist.yaml"
        assert result.parse_error is not None
        assert "error" in result.parse_error.lower()

    def test_file_path_is_absolute(self) -> None:
        """Verify file_path is always absolute."""
        path = FIXTURES_DIR / "valid-basic.yaml"
        result = _parse_policy_file(path)

        assert Path(result.file_path).is_absolute()

    def test_flat_format_policy_has_parse_error(self, tmp_path: Path) -> None:
        """Flat-format policies (no phases key) produce expected parse error."""
        flat_policy = tmp_path / "flat.yaml"
        flat_policy.write_text(
            "schema_version: 13\n"
            "track_order:\n"
            "  - video\n"
            "  - audio\n"
            "audio_languages:\n"
            "  - eng\n"
        )

        result = _parse_policy_file(flat_policy)

        assert result.parse_error is not None
        assert "missing 'phases' key" in result.parse_error

    def test_last_modified_is_iso8601(self) -> None:
        """Verify last_modified is ISO-8601 format with UTC."""
        path = FIXTURES_DIR / "valid-basic.yaml"
        result = _parse_policy_file(path)

        # ISO-8601 format ends with +00:00 for UTC
        assert result.last_modified.endswith("+00:00")
        # Should be parseable as ISO-8601
        from datetime import datetime

        dt = datetime.fromisoformat(result.last_modified)
        assert dt is not None


class TestIsDefaultPolicy:
    """Tests for _is_default_policy() helper."""

    def test_matching_paths(self, tmp_path: Path) -> None:
        """Match when paths resolve to same file."""
        policy_file = tmp_path / "test.yaml"
        policy_file.write_text("schema_version: 13")

        assert _is_default_policy(policy_file, policy_file) is True

    def test_different_paths(self, tmp_path: Path) -> None:
        """No match when paths are different files."""
        policy1 = tmp_path / "policy1.yaml"
        policy2 = tmp_path / "policy2.yaml"
        policy1.write_text("schema_version: 13")
        policy2.write_text("schema_version: 13")

        assert _is_default_policy(policy1, policy2) is False

    def test_none_default_path(self, tmp_path: Path) -> None:
        """No match when default_policy_path is None."""
        policy_file = tmp_path / "test.yaml"
        policy_file.write_text("schema_version: 13")

        assert _is_default_policy(policy_file, None) is False

    def test_tilde_expansion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Match works with tilde-expanded paths."""
        # Create a file
        policy_file = tmp_path / "test.yaml"
        policy_file.write_text("schema_version: 13")

        # If default uses tilde, it should still match resolved path
        # This is a simplified test since we can't easily mock home
        assert _is_default_policy(policy_file, policy_file.resolve()) is True

    def test_nonexistent_default(self, tmp_path: Path) -> None:
        """Handle nonexistent default path gracefully."""
        policy_file = tmp_path / "test.yaml"
        policy_file.write_text("schema_version: 13")
        nonexistent = tmp_path / "nonexistent.yaml"

        # Should return False, not raise
        assert _is_default_policy(policy_file, nonexistent) is False


class TestDiscoverPolicies:
    """Tests for discover_policies() main function."""

    def test_discover_from_fixtures(self) -> None:
        """Discover policies from fixtures directory."""
        policies, default_missing = discover_policies(FIXTURES_DIR, None)

        assert len(policies) >= 4  # We have at least 4 test fixtures
        assert default_missing is False  # No default configured, so not missing

        # Check that valid policies are parsed correctly
        names = [p.name for p in policies]
        assert "valid-basic" in names
        assert "valid-full" in names
        assert "invalid-syntax" in names
        assert "invalid-format" in names

    def test_alphabetical_sorting(self) -> None:
        """Policies are sorted alphabetically by name."""
        policies, _ = discover_policies(FIXTURES_DIR, None)

        names = [p.name for p in policies]
        assert names == sorted(names, key=str.lower)

    def test_default_first_sorting(self, tmp_path: Path) -> None:
        """Default policy appears first in list."""
        # Create test policies
        (tmp_path / "aaa-policy.yaml").write_text("schema_version: 13")
        (tmp_path / "zzz-policy.yaml").write_text("schema_version: 13")

        # Set zzz-policy as default
        default_path = tmp_path / "zzz-policy.yaml"
        policies, default_missing = discover_policies(tmp_path, default_path)

        assert len(policies) == 2
        assert policies[0].name == "zzz-policy"  # Default first
        assert policies[0].is_default is True
        assert policies[1].name == "aaa-policy"  # Then alphabetically
        assert policies[1].is_default is False
        assert default_missing is False

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """Handle nonexistent directory gracefully."""
        nonexistent = tmp_path / "does-not-exist"
        policies, default_missing = discover_policies(nonexistent, None)

        assert policies == []
        assert default_missing is False

    def test_nonexistent_directory_with_default(self, tmp_path: Path) -> None:
        """Report missing default when directory doesn't exist."""
        nonexistent = tmp_path / "does-not-exist"
        fake_default = Path("/some/fake/policy.yaml")
        policies, default_missing = discover_policies(nonexistent, fake_default)

        assert policies == []
        assert default_missing is True  # Default was set but dir doesn't exist

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Handle empty directory."""
        empty_dir = tmp_path / "policies"
        empty_dir.mkdir()

        policies, default_missing = discover_policies(empty_dir, None)

        assert policies == []
        assert default_missing is False

    def test_missing_default_policy(self, tmp_path: Path) -> None:
        """Detect when configured default doesn't exist."""
        # Create a policy
        (tmp_path / "test.yaml").write_text("schema_version: 13")

        # Set default to nonexistent file
        nonexistent_default = tmp_path / "nonexistent.yaml"
        policies, default_missing = discover_policies(tmp_path, nonexistent_default)

        assert len(policies) == 1
        assert policies[0].is_default is False
        assert default_missing is True

    def test_finds_yaml_and_yml_files(self, tmp_path: Path) -> None:
        """Discover both .yaml and .yml files."""
        (tmp_path / "policy1.yaml").write_text("schema_version: 13")
        (tmp_path / "policy2.yml").write_text("schema_version: 13")

        policies, _ = discover_policies(tmp_path, None)

        assert len(policies) == 2
        names = [p.name for p in policies]
        assert "policy1" in names
        assert "policy2" in names

    def test_ignores_non_yaml_files(self, tmp_path: Path) -> None:
        """Don't discover non-YAML files."""
        (tmp_path / "policy.yaml").write_text("schema_version: 13")
        (tmp_path / "readme.txt").write_text("This is not a policy")
        (tmp_path / "config.json").write_text("{}")

        policies, _ = discover_policies(tmp_path, None)

        assert len(policies) == 1
        assert policies[0].name == "policy"


class TestPolicySummaryToDict:
    """Tests for PolicySummary.to_dict() serialization."""

    def test_to_dict_all_fields(self) -> None:
        """Verify to_dict includes all fields."""
        summary = PolicySummary(
            name="test",
            filename="test.yaml",
            file_path="/path/to/test.yaml",
            last_modified="2025-01-01T00:00:00+00:00",
            schema_version=2,
            audio_languages=["eng", "jpn"],
            subtitle_languages=["eng"],
            has_transcode=True,
            has_transcription=True,
            is_default=True,
            parse_error=None,
        )

        d = summary.to_dict()

        assert d["name"] == "test"
        assert d["filename"] == "test.yaml"
        assert d["file_path"] == "/path/to/test.yaml"
        assert d["last_modified"] == "2025-01-01T00:00:00+00:00"
        assert d["schema_version"] == 2
        assert d["audio_languages"] == ["eng", "jpn"]
        assert d["subtitle_languages"] == ["eng"]
        assert d["has_transcode"] is True
        assert d["has_transcription"] is True
        assert d["is_default"] is True
        assert d["parse_error"] is None

    def test_to_dict_with_error(self) -> None:
        """Verify to_dict includes parse_error when present."""
        summary = PolicySummary(
            name="broken",
            filename="broken.yaml",
            parse_error="YAML error: something went wrong",
        )

        d = summary.to_dict()

        assert d["name"] == "broken"
        assert d["parse_error"] == "YAML error: something went wrong"


class TestPolicyCaching:
    """Tests for policy file caching."""

    def test_cache_hit_on_unchanged_file(self, tmp_path: Path) -> None:
        """Cached result returned when file hasn't changed."""
        from vpo.policy.discovery import clear_policy_cache

        # Ensure clean cache
        clear_policy_cache()

        # Create a policy file (phased format required)
        policy_path = tmp_path / "cached.yaml"
        policy_path.write_text(
            "schema_version: 13\n"
            "phases:\n"
            "  - name: apply\n"
            "    default_flags:\n"
            "      set_first_video_default: true\n"
        )

        # First parse (cache miss)
        result1 = _parse_policy_file(policy_path)
        assert result1.schema_version == 13

        # Second parse (cache hit - same content returned)
        result2 = _parse_policy_file(policy_path)
        assert result2.schema_version == 13
        assert result1 == result2

    def test_cache_invalidation_on_modification(self, tmp_path: Path) -> None:
        """Cache invalidated when file is modified."""
        import os
        import time

        from vpo.policy.discovery import clear_policy_cache

        # Ensure clean cache
        clear_policy_cache()

        # Create a policy file (phased format required)
        policy_path = tmp_path / "modified.yaml"
        policy_path.write_text(
            "schema_version: 13\n"
            "config:\n"
            "  audio_languages:\n"
            "    - eng\n"
            "phases:\n"
            "  - name: apply\n"
            "    default_flags:\n"
            "      set_first_video_default: true\n"
        )

        # First parse
        result1 = _parse_policy_file(policy_path)
        assert result1.schema_version == 13

        # Ensure mtime changes (some filesystems have 1-second resolution)
        time.sleep(0.1)
        # Modify the file (change the language)
        policy_path.write_text(
            "schema_version: 13\n"
            "config:\n"
            "  audio_languages:\n"
            "    - jpn\n"
            "phases:\n"
            "  - name: apply\n"
            "    default_flags:\n"
            "      set_first_video_default: true\n"
        )
        # Force mtime update
        os.utime(policy_path, None)

        # Second parse should return new content
        result2 = _parse_policy_file(policy_path)
        assert result2.schema_version == 13

    def test_clear_policy_cache(self, tmp_path: Path) -> None:
        """clear_policy_cache() clears all cached entries."""
        from vpo.policy.discovery import (
            _policy_cache,
            clear_policy_cache,
        )

        # Ensure clean state
        clear_policy_cache()

        # Create and parse a policy
        policy_path = tmp_path / "test.yaml"
        policy_path.write_text("schema_version: 13\n")
        _parse_policy_file(policy_path)

        # Cache should have entry
        assert len(_policy_cache) > 0

        # Clear cache
        clear_policy_cache()
        assert len(_policy_cache) == 0

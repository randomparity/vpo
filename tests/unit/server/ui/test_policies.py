"""Unit tests for policies list view models and helpers."""

from __future__ import annotations

from vpo.server.ui.models import (
    PoliciesContext,
    PolicyListItem,
    PolicyListResponse,
    format_language_preferences,
)


class TestFormatLanguagePreferences:
    """Tests for format_language_preferences() helper."""

    def test_empty_list(self) -> None:
        """Return em dash for empty list."""
        result = format_language_preferences([])
        assert result == "\u2014"  # em dash

    def test_single_language(self) -> None:
        """Format single language."""
        result = format_language_preferences(["eng"])
        assert result == "eng"

    def test_two_languages(self) -> None:
        """Format two languages."""
        result = format_language_preferences(["eng", "jpn"])
        assert result == "eng, jpn"

    def test_three_languages(self) -> None:
        """Format three languages (max without truncation)."""
        result = format_language_preferences(["eng", "jpn", "spa"])
        assert result == "eng, jpn, spa"

    def test_four_languages_truncates(self) -> None:
        """Truncate at 4+ languages."""
        result = format_language_preferences(["eng", "jpn", "spa", "fre"])
        assert result == "eng, jpn, spa +1 more"

    def test_many_languages_truncates(self) -> None:
        """Truncate many languages."""
        result = format_language_preferences(
            ["eng", "jpn", "spa", "fre", "ger", "ita", "por"]
        )
        assert result == "eng, jpn, spa +4 more"


class TestPolicyListItem:
    """Tests for PolicyListItem dataclass."""

    def test_to_dict_all_fields(self) -> None:
        """Verify to_dict includes all fields."""
        item = PolicyListItem(
            name="test",
            filename="test.yaml",
            file_path="/path/to/test.yaml",
            last_modified="2025-01-01T00:00:00+00:00",
            schema_version=12,
            display_name="My Test Policy",
            description="Test policy description",
            category="organize",
            audio_languages="eng, jpn",
            subtitle_languages="eng",
            has_transcode=True,
            has_transcription=True,
            is_default=True,
            parse_error=None,
        )

        d = item.to_dict()

        assert d["name"] == "test"
        assert d["filename"] == "test.yaml"
        assert d["file_path"] == "/path/to/test.yaml"
        assert d["last_modified"] == "2025-01-01T00:00:00+00:00"
        assert d["schema_version"] == 12
        assert d["display_name"] == "My Test Policy"
        assert d["description"] == "Test policy description"
        assert d["category"] == "organize"
        assert d["audio_languages"] == "eng, jpn"
        assert d["subtitle_languages"] == "eng"
        assert d["has_transcode"] is True
        assert d["has_transcription"] is True
        assert d["is_default"] is True
        assert d["parse_error"] is None

    def test_to_dict_with_error(self) -> None:
        """Verify to_dict includes parse_error when present."""
        item = PolicyListItem(
            name="broken",
            filename="broken.yaml",
            file_path="/path/broken.yaml",
            last_modified="",
            schema_version=None,
            display_name=None,
            description=None,
            category=None,
            audio_languages="\u2014",
            subtitle_languages="\u2014",
            has_transcode=False,
            has_transcription=False,
            is_default=False,
            parse_error="YAML error: something went wrong",
        )

        d = item.to_dict()

        assert d["name"] == "broken"
        assert d["parse_error"] == "YAML error: something went wrong"
        assert d["schema_version"] is None
        assert d["description"] is None
        assert d["category"] is None


class TestPolicyListResponse:
    """Tests for PolicyListResponse dataclass."""

    def test_to_dict_basic(self) -> None:
        """Verify to_dict includes all fields."""
        response = PolicyListResponse(
            policies=[
                PolicyListItem(
                    name="test",
                    filename="test.yaml",
                    file_path="/path/test.yaml",
                    last_modified="2025-01-01T00:00:00+00:00",
                    schema_version=12,
                    display_name=None,
                    description="Test description",
                    category="organize",
                    audio_languages="eng",
                    subtitle_languages="eng",
                    has_transcode=False,
                    has_transcription=False,
                    is_default=False,
                )
            ],
            total=1,
            policies_directory="/home/user/.vpo/policies",
            default_policy_path="/home/user/.vpo/policies/default.yaml",
            default_policy_missing=False,
            directory_exists=True,
        )

        d = response.to_dict()

        assert len(d["policies"]) == 1
        assert d["total"] == 1
        assert d["policies_directory"] == "/home/user/.vpo/policies"
        assert d["default_policy_path"] == "/home/user/.vpo/policies/default.yaml"
        assert d["default_policy_missing"] is False
        assert d["directory_exists"] is True

    def test_to_dict_empty_policies(self) -> None:
        """Verify to_dict works with empty policies list."""
        response = PolicyListResponse(
            policies=[],
            total=0,
            policies_directory="/home/user/.vpo/policies",
            default_policy_path=None,
            default_policy_missing=False,
            directory_exists=False,
        )

        d = response.to_dict()

        assert d["policies"] == []
        assert d["total"] == 0
        assert d["default_policy_path"] is None
        assert d["directory_exists"] is False


class TestPoliciesContext:
    """Tests for PoliciesContext dataclass."""

    def test_default(self) -> None:
        """Verify default() creates context with policies directory."""
        ctx = PoliciesContext.default()

        assert ctx.policies_directory.endswith(".vpo/policies")
        assert "~" not in ctx.policies_directory  # Should be expanded

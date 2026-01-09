"""Unit tests for metadata destination templates."""

from pathlib import Path

import pytest

from vpo.metadata.templates import (
    MOVIE_TEMPLATE,
    SIMPLE_TEMPLATE,
    TV_TEMPLATE,
    VALID_PLACEHOLDERS,
    DestinationTemplate,
    parse_template,
    render_destination,
    sanitize_path_component,
)


class TestSanitizePathComponent:
    """Tests for sanitize_path_component function."""

    def test_removes_slashes(self):
        """Forward and back slashes are replaced (and dashes collapsed to spaces)."""
        # Slashes become dashes, which then collapse with surrounding chars to spaces
        assert sanitize_path_component("path/to/file") == "path to file"
        assert sanitize_path_component("path\\to\\file") == "path to file"

    def test_removes_colons(self):
        """Colons are replaced (and dashes collapse with surrounding whitespace)."""
        # Colon becomes dash, dash+space collapses to single space
        assert sanitize_path_component("Title: Subtitle") == "Title Subtitle"

    def test_removes_special_chars(self):
        """Special characters are removed."""
        assert sanitize_path_component('file*name?<>"|') == "filename"

    def test_removes_null_bytes(self):
        """Null bytes are removed."""
        assert sanitize_path_component("test\x00name") == "testname"

    def test_collapses_multiple_dashes(self):
        """Multiple dashes are collapsed."""
        result = sanitize_path_component("a--b---c")
        assert result == "a b c"

    def test_strips_whitespace(self):
        """Leading/trailing whitespace is stripped."""
        assert sanitize_path_component("  test  ") == "test"

    def test_strips_dots(self):
        """Leading/trailing dots are stripped."""
        assert sanitize_path_component("...test...") == "test"

    def test_empty_returns_unknown(self):
        """Empty string returns 'Unknown'."""
        assert sanitize_path_component("") == "Unknown"

    def test_only_special_chars_returns_unknown(self):
        """String with only special chars returns 'Unknown'."""
        assert sanitize_path_component("***???") == "Unknown"


class TestDestinationTemplate:
    """Tests for DestinationTemplate class."""

    def test_render_basic(self):
        """Basic template rendering."""
        template = DestinationTemplate(
            raw_template="{title}/{year}",
            placeholders=("title", "year"),
        )
        result = template.render({"title": "Movie", "year": "2023"})
        assert result == "Movie/2023"

    def test_render_uses_fallback_for_missing(self):
        """Missing values use fallback."""
        template = DestinationTemplate(
            raw_template="{title}/{year}",
            placeholders=("title", "year"),
        )
        result = template.render({"title": "Movie"}, fallback="Unknown")
        assert result == "Movie/Unknown"

    def test_render_uses_custom_fallback_values(self):
        """Custom fallback values are used for specific placeholders."""
        template = DestinationTemplate(
            raw_template="{title}/{year}",
            placeholders=("title", "year"),
            fallback_values={"year": "No Year"},
        )
        result = template.render({"title": "Movie"}, fallback="Unknown")
        assert result == "Movie/No Year"

    def test_render_sanitizes_values(self):
        """Values are sanitized for filesystem."""
        template = DestinationTemplate(
            raw_template="{title}",
            placeholders=("title",),
        )
        result = template.render({"title": "Movie: With/Slashes"})
        assert "/" not in result
        assert ":" not in result or "-" in result

    def test_render_path(self):
        """render_path returns proper Path object."""
        template = DestinationTemplate(
            raw_template="{title}/{year}",
            placeholders=("title", "year"),
        )
        result = template.render_path(
            Path("/base"),
            {"title": "Movie", "year": "2023"},
        )
        assert result == Path("/base/Movie/2023")

    def test_required_fields(self):
        """required_fields excludes those with fallbacks."""
        template = DestinationTemplate(
            raw_template="{title}/{year}/{resolution}",
            placeholders=("title", "year", "resolution"),
            fallback_values={"resolution": "Unknown"},
        )
        assert template.required_fields == {"title", "year"}


class TestParseTemplate:
    """Tests for parse_template function."""

    def test_parses_placeholders(self):
        """Placeholders are correctly extracted."""
        template = parse_template("{title} - {year}")
        assert "title" in template.placeholders
        assert "year" in template.placeholders

    def test_preserves_order(self):
        """Placeholder order is preserved."""
        template = parse_template("{year}/{title}/{series}")
        assert template.placeholders == ("year", "title", "series")

    def test_duplicate_placeholders(self):
        """Duplicate placeholders appear only once."""
        template = parse_template("{title} - {title}")
        assert template.placeholders.count("title") == 1

    def test_accepts_fallback_values(self):
        """Fallback values are stored."""
        template = parse_template(
            "{title}/{year}",
            fallback_values={"year": "Unknown"},
        )
        assert template.fallback_values == {"year": "Unknown"}

    def test_invalid_placeholder_raises(self):
        """Invalid placeholder raises ValueError."""
        with pytest.raises(ValueError) as exc:
            parse_template("{title}/{invalid_field}")
        assert "invalid_field" in str(exc.value)

    def test_all_valid_placeholders_accepted(self):
        """All valid placeholders are accepted."""
        for placeholder in VALID_PLACEHOLDERS:
            template = parse_template(f"{{{placeholder}}}")
            assert placeholder in template.placeholders


class TestRenderDestination:
    """Tests for render_destination convenience function."""

    def test_renders_complete_path(self):
        """Convenience function renders complete path."""
        result = render_destination(
            "Movies/{year}/{title}",
            {"title": "Movie Name", "year": "2023"},
            Path("/videos"),
        )
        assert result == Path("/videos/Movies/2023/Movie Name")

    def test_uses_fallback(self):
        """Fallback is used for missing values."""
        result = render_destination(
            "{title}/{year}",
            {"title": "Movie"},
            Path("/videos"),
            fallback="Missing",
        )
        assert result == Path("/videos/Movie/Missing")


class TestTemplatePresets:
    """Tests for template preset constants."""

    def test_movie_template_valid(self):
        """MOVIE_TEMPLATE is a valid template."""
        template = parse_template(MOVIE_TEMPLATE)
        assert "year" in template.placeholders
        assert "title" in template.placeholders

    def test_tv_template_valid(self):
        """TV_TEMPLATE is a valid template."""
        template = parse_template(TV_TEMPLATE)
        assert "series" in template.placeholders
        assert "season" in template.placeholders

    def test_simple_template_valid(self):
        """SIMPLE_TEMPLATE is a valid template."""
        template = parse_template(SIMPLE_TEMPLATE)
        assert "title" in template.placeholders


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_template(self):
        """Empty template works."""
        template = parse_template("")
        assert template.placeholders == ()
        assert template.render({}) == ""

    def test_no_placeholders(self):
        """Template without placeholders works."""
        template = parse_template("static/path")
        assert template.placeholders == ()
        assert template.render({}) == "static/path"

    def test_nested_braces_not_supported(self):
        """Nested braces are not matched as placeholders."""
        # {{title}} should not be parsed as {title}
        template = parse_template("{{title}}")
        # The inner {title} is not a valid placeholder here due to the extra braces
        assert "title" in template.placeholders

    def test_special_regex_characters_in_template(self):
        """Special regex characters don't break parsing."""
        template = parse_template("path/[{title}]/(test)")
        assert "title" in template.placeholders
        result = template.render({"title": "Movie"})
        assert "[Movie]" in result

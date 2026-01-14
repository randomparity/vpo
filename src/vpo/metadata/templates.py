"""Destination template rendering for file organization.

This module provides template parsing and rendering for organizing
output files based on extracted metadata.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DestinationTemplate:
    """Parsed destination template with placeholder handling.

    Templates use {placeholder} syntax for metadata substitution.
    Supports fallback values for missing metadata.
    """

    raw_template: str
    placeholders: tuple[str, ...]
    fallback_values: dict[str, str] = field(default_factory=dict)

    def render(
        self,
        metadata: dict[str, str],
        fallback: str = "Unknown",
    ) -> str:
        """Render template with metadata values.

        Args:
            metadata: Dictionary of metadata values.
            fallback: Default fallback for missing values.

        Returns:
            Rendered path string.
        """
        result = self.raw_template

        for placeholder in self.placeholders:
            pattern = "{" + placeholder + "}"
            if placeholder in metadata:
                value = metadata[placeholder]
            elif placeholder in self.fallback_values:
                value = self.fallback_values[placeholder]
            else:
                value = fallback

            # Sanitize value for filesystem
            value = sanitize_path_component(value)
            result = result.replace(pattern, value)

        return result

    def render_path(
        self,
        base_dir: Path,
        metadata: dict[str, str],
        fallback: str = "Unknown",
    ) -> Path:
        """Render template as a Path relative to base directory.

        Args:
            base_dir: Base directory for output.
            metadata: Dictionary of metadata values.
            fallback: Default fallback for missing values.

        Returns:
            Absolute Path to destination.
        """
        rendered = self.render(metadata, fallback)
        return base_dir / rendered

    @property
    def required_fields(self) -> set[str]:
        """Fields required by this template (without fallbacks)."""
        return set(self.placeholders) - set(self.fallback_values.keys())


# Regex to find placeholders in template strings
PLACEHOLDER_PATTERN = re.compile(r"\{(\w+)\}")

# Valid placeholder names
VALID_PLACEHOLDERS = frozenset(
    {
        "title",
        "year",
        "series",
        "season",
        "episode",
        "resolution",
        "codec",
        "source",
        "filename",  # Original filename (without extension)
        "extension",  # File extension
    }
)


def parse_template(
    template: str,
    fallback_values: dict[str, str] | None = None,
) -> DestinationTemplate:
    """Parse a template string into a DestinationTemplate.

    Args:
        template: Template string with {placeholder} syntax.
        fallback_values: Default values for placeholders.

    Returns:
        Parsed DestinationTemplate.

    Raises:
        ValueError: If template contains invalid placeholders.
    """
    # Find all placeholders
    matches = PLACEHOLDER_PATTERN.findall(template)

    # Validate placeholders
    invalid = set(matches) - VALID_PLACEHOLDERS
    if invalid:
        raise ValueError(
            f"Invalid placeholders in template: {', '.join(sorted(invalid))}. "
            f"Valid placeholders: {', '.join(sorted(VALID_PLACEHOLDERS))}"
        )

    return DestinationTemplate(
        raw_template=template,
        placeholders=tuple(dict.fromkeys(matches)),  # Unique, preserve order
        fallback_values=fallback_values or {},
    )


def sanitize_path_component(value: str) -> str:
    """Sanitize a string for use as a path component.

    Removes or replaces characters that are invalid in filenames.

    Args:
        value: String to sanitize.

    Returns:
        Sanitized string safe for filesystem use.
    """
    # Replace common problematic characters
    replacements = {
        "/": "-",
        "\\": "-",
        ":": "-",
        "*": "",
        "?": "",
        '"': "",
        "<": "",
        ">": "",
        "|": "",
        "\0": "",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)

    # Collapse multiple dashes/spaces
    value = re.sub(r"[-\s]+", " ", value)

    # Remove leading/trailing spaces and dots
    value = value.strip(" .")

    # If empty after sanitization, use a placeholder
    if not value:
        value = "Unknown"

    return value


def render_destination(
    template: str,
    metadata: dict[str, str],
    base_dir: Path,
    fallback: str = "Unknown",
) -> Path:
    """Convenience function to render a destination path.

    Args:
        template: Template string with {placeholder} syntax.
        metadata: Dictionary of metadata values.
        base_dir: Base directory for output.
        fallback: Default fallback for missing values.

    Returns:
        Absolute Path to destination.
    """
    parsed = parse_template(template)
    return parsed.render_path(base_dir, metadata, fallback)


# Common template presets
MOVIE_TEMPLATE = "Movies/{year}/{title}"
TV_TEMPLATE = "TV Shows/{series}/Season {season}"
SIMPLE_TEMPLATE = "Processed/{title}"

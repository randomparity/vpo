"""Data models for Web UI Shell.

This module defines the navigation and template context structures
used for server-side rendering.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AboutInfo:
    """Information displayed on the About page.

    Attributes:
        version: Application version (e.g., "0.1.0").
        git_hash: Git commit hash if available.
        profile_name: Current profile name or "Default".
        api_url: Base URL for API access.
        docs_url: URL to documentation.
        is_read_only: Always True for this version.
    """

    version: str
    git_hash: str | None
    profile_name: str
    api_url: str
    docs_url: str
    is_read_only: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "git_hash": self.git_hash,
            "profile_name": self.profile_name,
            "api_url": self.api_url,
            "docs_url": self.docs_url,
            "is_read_only": self.is_read_only,
        }


@dataclass
class NavigationItem:
    """Represents a single navigation link in the sidebar.

    Attributes:
        id: Unique identifier matching route path (e.g., "jobs").
        label: Display text shown in navigation (e.g., "Jobs").
        path: URL path (e.g., "/jobs").
        icon: Optional icon identifier for future use.
    """

    id: str
    label: str
    path: str
    icon: str | None = None


@dataclass
class NavigationState:
    """Tracks which navigation item is currently active.

    Attributes:
        items: Ordered list of all navigation items.
        active_id: ID of the currently active section, or None for 404.
    """

    items: list[NavigationItem]
    active_id: str | None


@dataclass
class TemplateContext:
    """Context passed to Jinja2 templates for rendering.

    Attributes:
        nav: Navigation configuration and state.
        section_title: Title for the current section.
        section_content: Optional HTML content for section body.
        error_message: Optional error message for error pages.
    """

    nav: NavigationState
    section_title: str
    section_content: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for Jinja2 template context."""
        return {
            "nav": self.nav,
            "section_title": self.section_title,
            "section_content": self.section_content,
            "error_message": self.error_message,
        }


# Default navigation items configuration
NAVIGATION_ITEMS: list[NavigationItem] = [
    NavigationItem(id="jobs", label="Jobs", path="/jobs"),
    NavigationItem(id="library", label="Library", path="/library"),
    NavigationItem(id="transcriptions", label="Transcriptions", path="/transcriptions"),
    NavigationItem(id="policies", label="Policies", path="/policies"),
    NavigationItem(id="approvals", label="Approvals", path="/approvals"),
    NavigationItem(id="about", label="About", path="/about"),
]

DEFAULT_SECTION = "jobs"

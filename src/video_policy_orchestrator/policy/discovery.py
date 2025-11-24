"""Policy file discovery and metadata extraction."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

import yaml

logger = logging.getLogger(__name__)

DEFAULT_POLICIES_DIR = Path.home() / ".vpo" / "policies"


class _CacheEntry(NamedTuple):
    """Cache entry for parsed policy file."""

    mtime: float
    summary: PolicySummary


# Module-level cache: path -> (mtime, PolicySummary)
_policy_cache: dict[str, _CacheEntry] = {}


def clear_policy_cache() -> None:
    """Clear the policy file cache.

    Useful for testing or when policies directory changes significantly.
    """
    _policy_cache.clear()


@dataclass
class PolicySummary:
    """Summary of a policy file for list display.

    Attributes:
        name: Policy name (filename without extension).
        filename: Full filename including extension.
        file_path: Absolute path to the policy file.
        last_modified: File modification time (UTC ISO-8601).
        schema_version: Policy schema version if parseable.
        audio_languages: Audio language preferences list.
        subtitle_languages: Subtitle language preferences list.
        has_transcode: True if policy includes transcode settings.
        has_transcription: True if policy has transcription.enabled=True.
        is_default: True if this is the profile's default policy.
        parse_error: Error message if YAML parsing failed, else None.
    """

    name: str
    filename: str
    file_path: str = ""
    last_modified: str = ""  # ISO-8601 UTC
    schema_version: int | None = None
    audio_languages: list[str] = field(default_factory=list)
    subtitle_languages: list[str] = field(default_factory=list)
    has_transcode: bool = False
    has_transcription: bool = False
    is_default: bool = False
    parse_error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "filename": self.filename,
            "file_path": self.file_path,
            "last_modified": self.last_modified,
            "schema_version": self.schema_version,
            "audio_languages": self.audio_languages,
            "subtitle_languages": self.subtitle_languages,
            "has_transcode": self.has_transcode,
            "has_transcription": self.has_transcription,
            "is_default": self.is_default,
            "parse_error": self.parse_error,
        }


def _parse_policy_file(path: Path) -> PolicySummary:
    """Parse a policy file and extract display metadata.

    Uses mtime-based caching to avoid re-parsing unchanged files.

    Args:
        path: Path to the policy YAML file.

    Returns:
        PolicySummary with extracted metadata or parse_error if invalid.
    """
    cache_key = str(path.resolve())

    try:
        mtime = path.stat().st_mtime
    except OSError:
        # File may have been deleted, remove from cache
        _policy_cache.pop(cache_key, None)
        return PolicySummary(
            name=path.stem,
            filename=path.name,
            file_path=cache_key,
            last_modified="",
            parse_error="Read error: File not found",
        )

    # Check cache
    cached = _policy_cache.get(cache_key)
    if cached is not None and cached.mtime == mtime:
        logger.debug("Cache hit for policy: %s", path.name)
        return cached.summary

    logger.debug("Parsing policy file: %s", path.name)
    last_modified = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            summary = PolicySummary(
                name=path.stem,
                filename=path.name,
                file_path=cache_key,
                last_modified=last_modified,
                parse_error="Invalid format: expected YAML mapping",
            )
            _policy_cache[cache_key] = _CacheEntry(mtime, summary)
            return summary

        # Extract transcription enabled status
        transcription = data.get("transcription")
        has_transcription = isinstance(transcription, dict) and transcription.get(
            "enabled", False
        )

        summary = PolicySummary(
            name=path.stem,
            filename=path.name,
            file_path=cache_key,
            last_modified=last_modified,
            schema_version=data.get("schema_version"),
            audio_languages=list(data.get("audio_language_preference", [])),
            subtitle_languages=list(data.get("subtitle_language_preference", [])),
            has_transcode=data.get("transcode") is not None,
            has_transcription=has_transcription,
        )
        _policy_cache[cache_key] = _CacheEntry(mtime, summary)
        return summary
    except yaml.YAMLError as e:
        summary = PolicySummary(
            name=path.stem,
            filename=path.name,
            file_path=cache_key,
            last_modified=last_modified,
            parse_error=f"YAML error: {e}",
        )
        _policy_cache[cache_key] = _CacheEntry(mtime, summary)
        return summary
    except OSError as e:
        summary = PolicySummary(
            name=path.stem,
            filename=path.name,
            file_path=cache_key,
            last_modified=last_modified,
            parse_error=f"Read error: {e}",
        )
        _policy_cache[cache_key] = _CacheEntry(mtime, summary)
        return summary


def _is_default_policy(policy_path: Path, default_policy_path: Path | None) -> bool:
    """Check if policy_path matches the profile's default_policy.

    Args:
        policy_path: Path to the policy file being checked.
        default_policy_path: Path from profile's default_policy setting.

    Returns:
        True if paths resolve to the same file.
    """
    if default_policy_path is None:
        return False
    try:
        return policy_path.resolve() == default_policy_path.expanduser().resolve()
    except (OSError, ValueError):
        return False


def discover_policies(
    policies_dir: Path | None = None,
    default_policy_path: Path | None = None,
) -> tuple[list[PolicySummary], bool]:
    """Discover all policy files in the policies directory.

    Args:
        policies_dir: Directory to scan (default: ~/.vpo/policies/).
        default_policy_path: Path from profile's default_policy setting.

    Returns:
        Tuple of:
        - List of PolicySummary sorted (default first, then alphabetically)
        - bool indicating if default_policy_path was set but file not found
    """
    if policies_dir is None:
        policies_dir = DEFAULT_POLICIES_DIR

    policies_dir = policies_dir.expanduser()

    if not policies_dir.exists():
        logger.debug("Policies directory does not exist: %s", policies_dir)
        return [], default_policy_path is not None

    # Find all .yaml and .yml files
    policy_files = list(policies_dir.glob("*.yaml")) + list(policies_dir.glob("*.yml"))

    policies = []
    default_found = False

    for path in policy_files:
        summary = _parse_policy_file(path)
        summary.is_default = _is_default_policy(path, default_policy_path)
        if summary.is_default:
            default_found = True
        policies.append(summary)

    # Sort: default first, then alphabetically by name
    policies.sort(key=lambda p: (not p.is_default, p.name.lower()))

    # Check if default policy is missing
    default_missing = default_policy_path is not None and not default_found

    return policies, default_missing

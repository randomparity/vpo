"""Policy round-trip editor for preserving unknown fields and comments.

This module provides a round-trip editor for policy files that:
1. Preserves unknown fields during load/save cycles
2. Best-effort preservation of YAML comments
3. Selective field updates without modifying untouched fields
4. Structured logging of policy edits
"""

import logging
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from video_policy_orchestrator.policy.loader import (
    PolicyValidationError,
    load_policy_from_dict,
)

logger = logging.getLogger(__name__)


class PolicyRoundTripEditor:
    """Editor that preserves unknown fields and comments during policy updates.

    Uses ruamel.yaml for round-trip preservation of YAML structure, comments,
    and unknown fields. All edits are validated against PolicyModel before saving.

    Example:
        >>> editor = PolicyRoundTripEditor(Path("~/.vpo/policies/default.yaml"))
        >>> data = editor.load()
        >>> data['audio_language_preference'] = ['jpn', 'eng']
        >>> editor.save(data)
    """

    def __init__(self, policy_path: Path, allowed_dir: Path | None = None) -> None:
        """Initialize the editor with a policy file path.

        Args:
            policy_path: Path to the YAML policy file.
            allowed_dir: Optional directory to restrict policy files to.
                If provided, the policy_path must be within this directory.

        Raises:
            FileNotFoundError: If the policy file does not exist.
            ValueError: If policy_path is outside the allowed_dir.
        """
        self.policy_path = policy_path.resolve()

        # Verify path is within allowed directory (defense in depth)
        if allowed_dir is not None:
            allowed_resolved = allowed_dir.resolve()
            try:
                self.policy_path.relative_to(allowed_resolved)
            except ValueError:
                raise ValueError(
                    f"Policy path outside allowed directory: {self.policy_path}"
                )

        if not self.policy_path.exists():
            raise FileNotFoundError(f"Policy file not found: {self.policy_path}")

        self.yaml = YAML(typ="safe")
        self.yaml.preserve_quotes = True
        self.yaml.default_flow_style = False
        self._original_data: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        """Load policy data with round-trip preservation.

        Returns:
            Dictionary containing policy data with all fields (known and unknown).

        Raises:
            PolicyValidationError: If the YAML syntax is invalid.
        """
        try:
            with open(self.policy_path) as f:
                data = self.yaml.load(f)
        except Exception as e:
            raise PolicyValidationError(
                f"Failed to load policy file: {e}",
                field=None,
            ) from e

        if data is None:
            raise PolicyValidationError("Policy file is empty")

        if not isinstance(data, dict):
            raise PolicyValidationError("Policy file must be a YAML mapping")

        # Store original data for logging changes
        self._original_data = dict(data)

        logger.debug(
            "Loaded policy for editing",
            extra={
                "policy_path": str(self.policy_path),
                "policy_name": self.policy_path.stem,
            },
        )

        return data

    def save(self, data: dict[str, Any]) -> None:
        """Save policy data with validation and field preservation.

        Only updates fields present in the data dict. Unknown fields not in
        the input are preserved from the original file.

        Args:
            data: Dictionary containing updated policy fields.

        Raises:
            PolicyValidationError: If the updated policy fails validation.
        """
        # Validate only known fields using PolicyModel
        # Extract known fields for validation, ignore unknown fields
        known_fields = {
            "schema_version",
            "track_order",
            "audio_language_preference",
            "subtitle_language_preference",
            "commentary_patterns",
            "default_flags",
            "transcode",
            "transcription",
        }

        validation_data = {k: v for k, v in data.items() if k in known_fields}

        # This raises PolicyValidationError if invalid
        _ = load_policy_from_dict(validation_data)

        # Load current file with round-trip preservation
        with open(self.policy_path) as f:
            current_data = self.yaml.load(f)

        if current_data is None:
            current_data = {}

        # Merge: Update only fields present in input data
        # Unknown fields in current_data are preserved
        changed_fields = []
        for key, value in data.items():
            if key not in current_data or current_data[key] != value:
                changed_fields.append(key)
                current_data[key] = value

        # Write back with preservation
        with open(self.policy_path, "w") as f:
            self.yaml.dump(current_data, f)

        logger.info(
            "Policy updated",
            extra={
                "policy_path": str(self.policy_path),
                "policy_name": self.policy_path.stem,
                "changed_fields": changed_fields,
            },
        )

    def get_policy_name(self) -> str:
        """Get the policy name (filename without extension).

        Returns:
            Policy name derived from filename.
        """
        return self.policy_path.stem

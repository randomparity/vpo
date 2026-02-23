"""Policy round-trip editor for preserving unknown fields and comments.

This module provides a round-trip editor for policy files that:
1. Preserves unknown fields during load/save cycles
2. Best-effort preservation of YAML comments
3. Selective field updates without modifying untouched fields
4. Structured logging of policy edits
5. Field accessors for V3-V10 schema features (036-v9-policy-editor)
"""

import logging
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from vpo.policy.loader import (
    PolicyValidationError,
    load_policy_from_dict,
)

logger = logging.getLogger(__name__)

# Known policy fields by schema version
# V1-V2: Base fields
# V3: keep_audio, keep_subtitles, filter_attachments, container
# V4: conditional
# V5: audio_synthesis
# V6: transcode (extended with video/audio)
# V7: Multi-language conditions (in conditional)
# V9: workflow
# V10: music/sfx/non_speech track types (in transcription)
# Phased policy: phases, config (user-defined phases)
# Metadata: description, category (for documentation and filtering)
KNOWN_POLICY_FIELDS = {
    # V1-V2 base fields
    "schema_version",
    "track_order",
    "audio_languages",
    "subtitle_languages",
    "commentary_patterns",
    "default_flags",
    "transcode",
    "transcription",
    # V3+ fields
    "keep_audio",
    "keep_subtitles",
    "filter_attachments",
    "container",
    # V4+ fields
    "rules",
    # V5+ fields
    "audio_synthesis",
    # V9+ fields
    "workflow",
    # Phased policy fields (user-defined phases)
    "phases",
    "config",
    # Policy metadata fields
    "name",
    "description",
    "category",
}


class PolicyRoundTripEditor:
    """Editor that preserves unknown fields and comments during policy updates.

    Uses ruamel.yaml for round-trip preservation of YAML structure, comments,
    and unknown fields. All edits are validated against PolicyModel before saving.

    Example:
        >>> editor = PolicyRoundTripEditor(Path("~/.vpo/policies/default.yaml"))
        >>> data = editor.load()
        >>> data['audio_languages'] = ['jpn', 'eng']
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

        self.yaml = YAML(typ="rt")
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
            with open(self.policy_path, encoding="utf-8") as f:
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
        # Extract known fields for validation, ignore unknown fields
        validation_data = {k: v for k, v in data.items() if k in KNOWN_POLICY_FIELDS}

        # This raises PolicyValidationError if invalid
        _ = load_policy_from_dict(validation_data)

        # Load current file with round-trip preservation
        with open(self.policy_path, encoding="utf-8") as f:
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
        with open(self.policy_path, "w", encoding="utf-8") as f:
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

    def get_unknown_fields(self, data: dict[str, Any]) -> list[str]:
        """Get list of unknown fields in the policy data.

        Args:
            data: Policy data dictionary.

        Returns:
            List of field names not in KNOWN_POLICY_FIELDS.
        """
        return [k for k in data.keys() if k not in KNOWN_POLICY_FIELDS]

    # =========================================================================
    # V3+ Field Accessors (keep_audio, keep_subtitles, filter_attachments, container)
    # =========================================================================

    @staticmethod
    def get_keep_audio(data: dict[str, Any]) -> dict[str, Any] | None:
        """Get keep_audio configuration from policy data (V3+).

        Args:
            data: Policy data dictionary.

        Returns:
            Audio filter configuration dict or None if not configured.
        """
        return data.get("keep_audio")

    @staticmethod
    def set_keep_audio(data: dict[str, Any], value: dict[str, Any] | None) -> None:
        """Set keep_audio configuration in policy data (V3+).

        Args:
            data: Policy data dictionary to modify.
            value: Audio filter configuration or None to remove.
        """
        if value is None:
            data.pop("keep_audio", None)
        else:
            data["keep_audio"] = value

    @staticmethod
    def get_keep_subtitles(data: dict[str, Any]) -> dict[str, Any] | None:
        """Get keep_subtitles configuration from policy data (V3+).

        Args:
            data: Policy data dictionary.

        Returns:
            Subtitle filter configuration dict or None if not configured.
        """
        return data.get("keep_subtitles")

    @staticmethod
    def set_keep_subtitles(data: dict[str, Any], value: dict[str, Any] | None) -> None:
        """Set keep_subtitles configuration in policy data (V3+).

        Args:
            data: Policy data dictionary to modify.
            value: Subtitle filter configuration or None to remove.
        """
        if value is None:
            data.pop("keep_subtitles", None)
        else:
            data["keep_subtitles"] = value

    @staticmethod
    def get_filter_attachments(data: dict[str, Any]) -> dict[str, Any] | None:
        """Get filter_attachments configuration from policy data (V3+).

        Args:
            data: Policy data dictionary.

        Returns:
            Attachment filter configuration dict or None if not configured.
        """
        return data.get("filter_attachments")

    @staticmethod
    def set_filter_attachments(
        data: dict[str, Any], value: dict[str, Any] | None
    ) -> None:
        """Set filter_attachments configuration in policy data (V3+).

        Args:
            data: Policy data dictionary to modify.
            value: Attachment filter configuration or None to remove.
        """
        if value is None:
            data.pop("filter_attachments", None)
        else:
            data["filter_attachments"] = value

    @staticmethod
    def get_container(data: dict[str, Any]) -> dict[str, Any] | None:
        """Get container configuration from policy data (V3+).

        Args:
            data: Policy data dictionary.

        Returns:
            Container configuration dict or None if not configured.
        """
        return data.get("container")

    @staticmethod
    def set_container(data: dict[str, Any], value: dict[str, Any] | None) -> None:
        """Set container configuration in policy data (V3+).

        Args:
            data: Policy data dictionary to modify.
            value: Container configuration or None to remove.
        """
        if value is None:
            data.pop("container", None)
        else:
            data["container"] = value

    # =========================================================================
    # Rules Field Accessors (conditional rules)
    # =========================================================================

    @staticmethod
    def get_rules(data: dict[str, Any]) -> dict[str, Any] | None:
        """Get conditional rules config from policy data.

        Args:
            data: Policy data dictionary.

        Returns:
            Rules config dict (match/items) or None if not configured.
        """
        return data.get("rules")

    @staticmethod
    def set_rules(data: dict[str, Any], value: dict[str, Any] | None) -> None:
        """Set conditional rules config in policy data.

        Args:
            data: Policy data dictionary to modify.
            value: Rules config dict (match/items) or None to remove.
        """
        if value is None:
            data.pop("rules", None)
        else:
            data["rules"] = value

    # =========================================================================
    # V5+ Field Accessors (audio_synthesis)
    # =========================================================================

    @staticmethod
    def get_audio_synthesis(data: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Get audio synthesis configurations from policy data (V5+).

        Args:
            data: Policy data dictionary.

        Returns:
            List of audio synthesis track configs or None if not configured.
        """
        return data.get("audio_synthesis")

    @staticmethod
    def set_audio_synthesis(
        data: dict[str, Any], value: list[dict[str, Any]] | None
    ) -> None:
        """Set audio synthesis configurations in policy data (V5+).

        Args:
            data: Policy data dictionary to modify.
            value: List of audio synthesis configs or None to remove.
        """
        if value is None:
            data.pop("audio_synthesis", None)
        else:
            data["audio_synthesis"] = value

    # =========================================================================
    # V6+ Field Accessors (transcode.video, transcode.audio)
    # =========================================================================

    @staticmethod
    def get_transcode(data: dict[str, Any]) -> dict[str, Any] | None:
        """Get transcode configuration from policy data (V6+).

        Args:
            data: Policy data dictionary.

        Returns:
            Transcode configuration dict or None if not configured.
        """
        return data.get("transcode")

    @staticmethod
    def set_transcode(data: dict[str, Any], value: dict[str, Any] | None) -> None:
        """Set transcode configuration in policy data (V6+).

        Args:
            data: Policy data dictionary to modify.
            value: Transcode configuration or None to remove.
        """
        if value is None:
            data.pop("transcode", None)
        else:
            data["transcode"] = value

    @staticmethod
    def get_video_transcode(data: dict[str, Any]) -> dict[str, Any] | None:
        """Get video transcode configuration from policy data (V6+).

        Args:
            data: Policy data dictionary.

        Returns:
            Video transcode configuration dict or None if not configured.
        """
        transcode = data.get("transcode")
        if transcode is None:
            return None
        return transcode.get("video")

    @staticmethod
    def set_video_transcode(data: dict[str, Any], value: dict[str, Any] | None) -> None:
        """Set video transcode configuration in policy data (V6+).

        Creates the transcode parent key if needed.

        Args:
            data: Policy data dictionary to modify.
            value: Video transcode configuration or None to remove.
        """
        if value is None:
            transcode = data.get("transcode")
            if transcode is not None:
                transcode.pop("video", None)
                # Remove transcode if empty
                if not transcode:
                    data.pop("transcode", None)
        else:
            if "transcode" not in data:
                data["transcode"] = {}
            data["transcode"]["video"] = value

    @staticmethod
    def get_audio_transcode(data: dict[str, Any]) -> dict[str, Any] | None:
        """Get audio transcode configuration from policy data (V6+).

        Args:
            data: Policy data dictionary.

        Returns:
            Audio transcode configuration dict or None if not configured.
        """
        transcode = data.get("transcode")
        if transcode is None:
            return None
        return transcode.get("audio")

    @staticmethod
    def set_audio_transcode(data: dict[str, Any], value: dict[str, Any] | None) -> None:
        """Set audio transcode configuration in policy data (V6+).

        Creates the transcode parent key if needed.

        Args:
            data: Policy data dictionary to modify.
            value: Audio transcode configuration or None to remove.
        """
        if value is None:
            transcode = data.get("transcode")
            if transcode is not None:
                transcode.pop("audio", None)
                # Remove transcode if empty
                if not transcode:
                    data.pop("transcode", None)
        else:
            if "transcode" not in data:
                data["transcode"] = {}
            data["transcode"]["audio"] = value

    # =========================================================================
    # V9+ Field Accessors (workflow)
    # =========================================================================

    @staticmethod
    def get_workflow(data: dict[str, Any]) -> dict[str, Any] | None:
        """Get workflow configuration from policy data (V9+).

        Args:
            data: Policy data dictionary.

        Returns:
            Workflow configuration dict or None if not configured.
        """
        return data.get("workflow")

    @staticmethod
    def set_workflow(data: dict[str, Any], value: dict[str, Any] | None) -> None:
        """Set workflow configuration in policy data (V9+).

        Args:
            data: Policy data dictionary to modify.
            value: Workflow configuration or None to remove.
        """
        if value is None:
            data.pop("workflow", None)
        else:
            data["workflow"] = value

    # =========================================================================
    # Phased Policy Field Accessors (phases, config)
    # =========================================================================

    @staticmethod
    def get_phases(data: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Get user-defined phases from policy data.

        Args:
            data: Policy data dictionary.

        Returns:
            List of phase definitions or None if not configured.
        """
        return data.get("phases")

    @staticmethod
    def set_phases(data: dict[str, Any], value: list[dict[str, Any]] | None) -> None:
        """Set user-defined phases in policy data.

        Args:
            data: Policy data dictionary to modify.
            value: List of phase definitions or None to remove.
        """
        if value is None:
            data.pop("phases", None)
        else:
            data["phases"] = value

    @staticmethod
    def get_config(data: dict[str, Any]) -> dict[str, Any] | None:
        """Get global config from policy data.

        Args:
            data: Policy data dictionary.

        Returns:
            Global config dict or None if not configured.
        """
        return data.get("config")

    @staticmethod
    def set_config(data: dict[str, Any], value: dict[str, Any] | None) -> None:
        """Set global config in policy data.

        Args:
            data: Policy data dictionary to modify.
            value: Global config or None to remove.
        """
        if value is None:
            data.pop("config", None)
        else:
            data["config"] = value

    @staticmethod
    def get_phase_names(data: dict[str, Any]) -> list[str]:
        """Get list of phase names from policy data.

        Args:
            data: Policy data dictionary.

        Returns:
            List of phase names, empty if no phases defined.
        """
        phases = data.get("phases")
        if phases is None:
            return []
        return [p.get("name", "") for p in phases if isinstance(p, dict)]

    @staticmethod
    def is_phased_policy(data: dict[str, Any]) -> bool:
        """Check if policy data is phased format (has phases array).

        Args:
            data: Policy data dictionary.

        Returns:
            True if this is a phased policy with phases, False otherwise.
        """
        return "phases" in data

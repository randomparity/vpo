"""Whisper-based transcription plugin for VPO."""

from vpo.plugins.whisper_transcriber.plugin import (
    PluginDependencyError,
    WhisperTranscriptionPlugin,
    plugin_instance,
)

__all__ = ["PluginDependencyError", "WhisperTranscriptionPlugin", "plugin_instance"]

"""Introspector module for Video Policy Orchestrator.

This module provides media introspection capabilities:

- MediaIntrospector: Protocol defining the introspection interface
- FFprobeIntrospector: Production implementation using ffprobe
- StubIntrospector: Stub implementation for testing
- MediaIntrospectionError: Exception for introspection failures
"""

from video_policy_orchestrator.introspector.ffprobe import FFprobeIntrospector
from video_policy_orchestrator.introspector.interface import (
    MediaIntrospectionError,
    MediaIntrospector,
)
from video_policy_orchestrator.introspector.stub import StubIntrospector

__all__ = [
    "MediaIntrospector",
    "MediaIntrospectionError",
    "FFprobeIntrospector",
    "StubIntrospector",
]

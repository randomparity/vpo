"""VPO Daemon Server module.

This module provides the daemon mode functionality for running VPO as a
long-lived background service. It includes HTTP server for health checks,
signal handling for graceful shutdown, and lifecycle management.

Exports:
    DaemonLifecycle: Manages daemon startup/shutdown state
    ShutdownState: Tracks shutdown progress for graceful termination
    HealthStatus: Response payload for health check endpoint
    create_app: Factory function to create the aiohttp Application
"""

from vpo.server.app import HealthStatus, create_app
from vpo.server.lifecycle import DaemonLifecycle, ShutdownState

__all__ = [
    "DaemonLifecycle",
    "ShutdownState",
    "HealthStatus",
    "create_app",
]

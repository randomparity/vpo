"""Web UI module for VPO daemon server.

This module provides server-rendered HTML pages with navigation
for the VPO web interface.
"""

from __future__ import annotations

from video_policy_orchestrator.server.ui.models import (
    NAVIGATION_ITEMS,
    NavigationItem,
    NavigationState,
    TemplateContext,
)
from video_policy_orchestrator.server.ui.routes import setup_ui_routes

__all__ = [
    "NAVIGATION_ITEMS",
    "NavigationItem",
    "NavigationState",
    "TemplateContext",
    "setup_ui_routes",
]

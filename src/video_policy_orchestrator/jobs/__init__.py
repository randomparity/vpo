"""Job system module for Video Policy Orchestrator.

This module provides the job queue system for long-running operations:
- queue: Job queue operations (enqueue, claim, release)
- worker: Job worker for processing queued jobs
- progress: FFmpeg progress parsing utilities
"""

# API Contracts: Project Skeleton Setup

**Feature**: 001-project-skeleton
**Date**: 2025-11-21

## Overview

This is an infrastructure sprint. No API contracts are defined in this phase.

## Future Contracts

API contracts will be added in subsequent sprints:

| Sprint | Contract | Description |
|--------|----------|-------------|
| Sprint 1 | scan.yaml | Directory scanning CLI interface |
| Sprint 2 | inspect.yaml | Media file inspection API |
| Sprint 3 | policy.yaml | Policy evaluation API |
| Sprint 4 | plugin.yaml | Plugin discovery and loading API |

## CLI Interface Preview

While no formal contracts exist yet, the planned CLI structure from the README:

```text
vpo scan <directory>     # Scan for video files
vpo inspect <file>       # Show file metadata
vpo apply <policy>       # Apply policy (dry-run by default)
vpo jobs                 # List queued operations
vpo profiles             # Manage configuration profiles
```

These commands will be formally specified in their respective sprint contracts.

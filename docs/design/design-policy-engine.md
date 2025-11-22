# Policy Engine Design

**Purpose:**
This document describes the design of VPO's policy engine for defining and applying library organization rules.

> **Status:** This feature is planned but not yet implemented. This document captures the intended design.

---

## Overview

The policy engine will allow users to define rules for organizing video libraries:
- Track ordering preferences (audio, subtitle priority)
- Default track selection
- Metadata normalization
- File naming and organization

---

## Planned Policy Format

Policies will be defined in YAML or JSON:

```yaml
version: 1
name: "Standard Library Policy"

audio:
  order:
    - codec: ["truehd", "dts-hd", "flac"]  # Lossless first
    - codec: ["eac3", "ac3", "dts"]        # Lossy surround
    - codec: ["aac", "opus"]               # Stereo fallback
  default:
    language: "eng"
    channels: "highest"

subtitles:
  order:
    - language: "eng"
      forced: true  # Forced subs first
    - language: "eng"
  default:
    language: "eng"

metadata:
  normalize_language_codes: true
  remove_empty_titles: true
```

---

## Planned Components

### Policy Parser

- Read YAML/JSON policy files
- Validate against schema
- Support policy versioning for migrations

### Policy Evaluator

- Compare current file state against policy
- Generate list of required changes
- Support dry-run mode (preview without changes)

### Conflict Resolution

When multiple rules could apply:
1. More specific rules take precedence
2. Earlier rules in the file take precedence
3. Explicit values override wildcards

---

## Idempotence Guarantee

Applying the same policy twice must produce identical results:
- No duplicate operations
- No data corruption
- Stable track ordering

---

## Planned CLI Commands

```bash
# Preview policy changes (dry run)
vpo apply --dry-run --policy my-policy.yaml /media/movies

# Apply policy to library
vpo apply --policy my-policy.yaml /media/movies

# Validate policy syntax
vpo policy validate my-policy.yaml
```

---

## Implementation Notes

This feature depends on:
- Completed: Library scanner (002)
- Completed: Media introspection (003)
- Required: Execution layer for applying changes

---

## Related docs

- [Design Docs Index](DESIGN_INDEX.md)
- [Project Overview](../overview/project-overview.md)
- [Architecture Overview](../overview/architecture.md)
- [Plugin Design](design-plugins.md)

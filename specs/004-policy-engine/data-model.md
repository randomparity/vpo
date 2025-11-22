# Data Model: Policy Engine & Reordering

**Feature**: 004-policy-engine
**Date**: 2025-11-22

## Entity Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Policy    │────▶│    Plan     │────▶│  PlannedAction  │
└─────────────┘     └─────────────┘     └─────────────────┘
                           │
                           ▼
                    ┌─────────────────┐
                    │ OperationRecord │
                    └─────────────────┘
```

## Entities

### Policy

User-defined configuration specifying desired track organization. Loaded from YAML files.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| schema_version | int | >= 1 | Schema version for migrations |
| track_order | list[TrackType] | non-empty | Desired ordering of track types |
| audio_language_preference | list[str] | ISO 639-2, non-empty | Preferred audio languages |
| subtitle_language_preference | list[str] | ISO 639-2, non-empty | Preferred subtitle languages |
| commentary_patterns | list[str] | valid regex | Patterns to identify commentary |
| default_flags | DefaultFlagsConfig | - | Default flag behavior settings |

**TrackType enum**: `video`, `audio_main`, `audio_alternate`, `audio_commentary`, `subtitle_main`, `subtitle_forced`, `subtitle_commentary`, `attachment`

**DefaultFlagsConfig**:
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| set_first_video_default | bool | true | Set first video track as default |
| set_preferred_audio_default | bool | true | Set preferred audio as default |
| set_preferred_subtitle_default | bool | false | Set preferred subtitle as default |
| clear_other_defaults | bool | true | Clear default flag on non-preferred tracks |

### Plan

Output of policy evaluation representing intended changes. Immutable once created.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| file_id | str | UUID | Reference to MediaFile being modified |
| file_path | Path | exists | Path to media file |
| policy_version | int | >= 1 | Schema version of policy used |
| actions | list[PlannedAction] | - | Ordered list of changes to apply |
| requires_remux | bool | - | True if track reordering needed |
| created_at | datetime | UTC | When plan was created |

**Derived properties**:
- `is_empty`: True if no actions needed
- `summary`: Human-readable summary of changes

### PlannedAction

A single change to be applied. Immutable.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| action_type | ActionType | enum | Type of change |
| track_index | int | >= 0 | Track index in current file |
| track_id | str | - | Track UID if available |
| current_value | Any | - | Value before change |
| desired_value | Any | - | Value after change |

**ActionType enum**:
| Value | Description | Requires Remux |
|-------|-------------|----------------|
| `REORDER` | Change track position | Yes (MKV only) |
| `SET_DEFAULT` | Change default flag | No |
| `CLEAR_DEFAULT` | Remove default flag | No |
| `SET_FORCED` | Change forced flag | No |
| `CLEAR_FORCED` | Remove forced flag | No |
| `SET_TITLE` | Change track title | No |
| `SET_LANGUAGE` | Change language tag | No |

### OperationRecord

Audit log entry for an applied change. Persisted to database.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | str | UUID, unique | Primary key |
| file_id | str | UUID, FK → files | Reference to MediaFile |
| file_path | str | - | Path at time of operation |
| policy_name | str | - | Name/path of policy used |
| policy_version | int | >= 1 | Schema version of policy |
| actions_json | str | valid JSON | Serialized list of applied actions |
| status | OperationStatus | enum | Success/failure status |
| error_message | str | nullable | Error details if failed |
| backup_path | str | nullable | Path to backup file if retained |
| started_at | datetime | UTC | When operation started |
| completed_at | datetime | UTC, nullable | When operation completed |

**OperationStatus enum**: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `ROLLED_BACK`

## Database Schema Extension

```sql
-- New table for operation audit log
CREATE TABLE IF NOT EXISTS operations (
    id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL REFERENCES files(id),
    file_path TEXT NOT NULL,
    policy_name TEXT NOT NULL,
    policy_version INTEGER NOT NULL,
    actions_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    error_message TEXT,
    backup_path TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,

    CONSTRAINT valid_status CHECK (
        status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'ROLLED_BACK')
    )
);

CREATE INDEX IF NOT EXISTS idx_operations_file_id ON operations(file_id);
CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status);
CREATE INDEX IF NOT EXISTS idx_operations_started_at ON operations(started_at);
```

## State Transitions

### OperationRecord Lifecycle

```
     ┌──────────────────────────────────────┐
     │                                      │
     ▼                                      │
┌─────────┐    ┌─────────────┐    ┌───────────────┐
│ PENDING │───▶│ IN_PROGRESS │───▶│   COMPLETED   │
└─────────┘    └─────────────┘    └───────────────┘
                     │
                     │ (on error)
                     ▼
              ┌─────────────┐    ┌───────────────┐
              │   FAILED    │───▶│  ROLLED_BACK  │
              └─────────────┘    └───────────────┘
                                   (backup restored)
```

### Track Classification Flow

```
Input: Track from file
         │
         ▼
┌─────────────────────┐
│ Check track type    │
│ (video/audio/sub)   │
└─────────────────────┘
         │
         ▼ (if audio or subtitle)
┌─────────────────────┐
│ Match title against │
│ commentary_patterns │
└─────────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────────┐
│  Main  │ │ Commentary │
└────────┘ └────────────┘
```

## Validation Rules

### Policy Validation
1. `schema_version` must be <= current supported version
2. `track_order` must contain at least one entry
3. `audio_language_preference` must contain valid ISO 639-2 codes
4. `commentary_patterns` must be valid regex (validated at load time)
5. Unknown fields rejected (`extra="forbid"`)

### Plan Validation
1. `file_id` must reference existing file in database
2. `file_path` must exist on filesystem
3. Actions must be consistent (no conflicting changes to same track)

### Operation Validation
1. Cannot start operation on file with existing `IN_PROGRESS` operation
2. `completed_at` must be >= `started_at`
3. `error_message` required if status is `FAILED`

## Relationships

```
MediaFile (from 003)          Policy (in-memory)
    │                              │
    │ 1                            │
    ├───────────────┐              │
    │               │              │
    ▼ *             ▼ 1            ▼
TrackInfo      OperationRecord    Plan
(from 003)          │              │
                    │              │
                    └──────────────┘
                    (policy_name links to policy used)
```

## Integration with Existing Models

### From 003-media-introspection

**TrackInfo** (read-only for policy engine):
- `track_index`: Position in file
- `track_type`: video/audio/subtitle
- `codec`: Codec identifier
- `language`: ISO 639-2 code
- `title`: Track title (used for commentary matching)
- `is_default`: Current default flag
- `is_forced`: Current forced flag
- `channels`: Audio channel count (for sorting)

**MediaFile** (read-only):
- `id`: UUID for stable reference
- `path`: Current file path
- `container`: Container format (mkv, mp4, etc.)

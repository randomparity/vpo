# Time and Timezones

**Purpose:**
This document describes VPO's conventions for handling time and timezones throughout the codebase.

---

## Overview

VPO follows a "UTC everywhere" pattern: all timestamps are stored, transmitted, and processed in UTC. Conversion to local time happens only at the presentation layer (CLI output).

---

## Core Rules

### 1. Use UTC Internally

All datetime objects in Python code should be timezone-aware and use UTC:

```python
from datetime import datetime, timezone

# Correct: timezone-aware UTC
now = datetime.now(timezone.utc)

# Incorrect: naive datetime (no timezone)
now = datetime.now()  # Don't do this

# Incorrect: local time
now = datetime.now().astimezone()  # Don't do this
```

### 2. Serialize as ISO 8601

Timestamps are stored and transmitted as ISO 8601 strings with the `Z` suffix indicating UTC:

```text
2024-01-15T10:30:00+00:00
```

The `datetime.isoformat()` method handles this automatically for timezone-aware datetimes.

### 3. Store as TEXT in SQLite

SQLite doesn't have a native datetime type. All timestamps are stored as TEXT in ISO 8601 format:

```sql
CREATE TABLE files (
    ...
    modified_at TEXT NOT NULL,    -- ISO 8601 UTC timestamp
    scanned_at TEXT NOT NULL,     -- ISO 8601 UTC timestamp
    ...
);
```

This allows:
- Human-readable values in database dumps
- Lexicographic sorting works correctly
- No timezone conversion bugs

### 4. Convert to Local Time Only for Display

Local time conversion happens only when displaying to users:

```python
# In CLI output code:
from datetime import datetime

utc_time = datetime.fromisoformat(record.scanned_at)
local_time = utc_time.astimezone()  # Convert to local
print(f"Scanned at: {local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
```

---

## Implementation Examples

### Creating Timestamps

From `src/video_policy_orchestrator/db/models.py`:

```python
from datetime import datetime, timezone

@dataclass
class FileInfo:
    ...
    scanned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### Converting Domain Objects to Database Records

```python
@classmethod
def from_file_info(cls, info: FileInfo) -> "FileRecord":
    return cls(
        ...
        modified_at=info.modified_at.isoformat(),
        scanned_at=info.scanned_at.isoformat(),
        ...
    )
```

### File Modification Times

File system timestamps from `os.stat()` are converted to UTC:

```python
from datetime import datetime, timezone

stat = path.stat()
modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
```

---

## Common Pitfalls to Avoid

### Naive Datetimes

Never create datetime objects without timezone information:

```python
# BAD: Creates naive datetime
datetime.now()
datetime.utcnow()  # Deprecated in Python 3.12+

# GOOD: Creates timezone-aware UTC datetime
datetime.now(timezone.utc)
```

### Local Time in Storage

Never store local time in the database:

```python
# BAD: Stores local time
scanned_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# GOOD: Stores UTC in ISO 8601
scanned_at = datetime.now(timezone.utc).isoformat()
```

### Inconsistent Parsing

When parsing timestamps, always handle the timezone:

```python
# For ISO 8601 strings (Python 3.11+)
dt = datetime.fromisoformat(timestamp_string)

# For older Python or non-standard formats
from datetime import datetime, timezone
dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
```

---

## Related ADR

See [ADR-0001: UTC Everywhere](../decisions/ADR-0001-utc-everywhere.md) for the decision record on this approach.

---

## Related docs

- [Documentation Index](../INDEX.md)
- [Design Docs Index](../design/DESIGN_INDEX.md)
- [Data Model](../overview/data-model.md)
- [Database Design](../design/design-database.md)

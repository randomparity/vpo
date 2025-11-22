# ADR-0001: UTC Everywhere

**Status:** Accepted
**Date:** 2024-01-15
**Decision Makers:** Project maintainers

---

## Context

VPO needs to store and process timestamps for:
- File modification times
- Scan timestamps
- Future: Job scheduling, policy application history

Timestamp handling is a common source of bugs in applications, particularly when:
- Users are in different timezones
- Databases don't have native timezone support (SQLite)
- Data is exchanged between systems

---

## Decision

**Store and process all timestamps in UTC. Convert to local time only at the presentation layer (CLI output).**

### Implementation

1. **Python code**: Use timezone-aware datetime objects with UTC:
   ```python
   from datetime import datetime, timezone
   now = datetime.now(timezone.utc)
   ```

2. **Database storage**: Store as ISO 8601 TEXT with timezone:
   ```sql
   scanned_at TEXT NOT NULL  -- e.g., "2024-01-15T10:30:00+00:00"
   ```

3. **CLI output**: Convert to local time for display:
   ```python
   local_time = utc_time.astimezone()
   ```

---

## Options Considered

### Option 1: Local Time Everywhere

Store timestamps in the user's local timezone.

**Pros:**
- Intuitive for single-user systems
- No conversion needed for display

**Cons:**
- Ambiguous during DST transitions
- Breaks when user changes timezone
- Causes issues if database is shared or moved

**Rejected:** Too many edge cases and potential for data corruption.

### Option 2: UTC Everywhere (Selected)

Store all timestamps in UTC, convert only for display.

**Pros:**
- Unambiguous representation
- Works across timezones
- Standard practice in distributed systems
- SQLite TEXT sorting works correctly

**Cons:**
- Requires conversion for display
- Slightly more complex implementation

**Selected:** Industry standard approach with well-understood tradeoffs.

### Option 3: Unix Timestamps

Store as integer seconds since epoch.

**Pros:**
- Compact storage
- Easy arithmetic

**Cons:**
- Not human-readable in database
- Loses sub-second precision
- Requires conversion for all operations

**Rejected:** Loss of readability outweighs storage benefits.

---

## Consequences

### Positive

- No timezone-related bugs
- Database dumps are human-readable
- Safe to move database between systems
- Lexicographic sorting works correctly

### Negative

- Must remember to use `timezone.utc` consistently
- Display code needs explicit conversion
- File system timestamps must be converted on read

### Neutral

- Python's `datetime.fromisoformat()` handles parsing automatically
- SQLite's TEXT type has no performance penalty for this use case

---

## Related docs

- [Time and Timezones](../internals/time-and-timezones.md)
- [Database Design](../design/design-database.md)
- [Data Model](../overview/data-model.md)

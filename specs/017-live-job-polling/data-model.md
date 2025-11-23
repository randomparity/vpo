# Data Model: Live Job Status Updates (Polling)

**Feature**: 017-live-job-polling
**Date**: 2025-11-23

## Overview

This feature introduces client-side state management for polling behavior. No database schema changes are required. All entities below are JavaScript objects maintained in browser memory.

## Client-Side Entities

### PollingConfig

Configuration for polling behavior, delivered via HTML data attributes.

```typescript
interface PollingConfig {
    /** Polling interval in milliseconds (2000-60000, default 5000) */
    interval: number;

    /** Whether polling is enabled */
    enabled: boolean;

    /** Log polling interval in milliseconds (default 15000) */
    logInterval: number;
}
```

**Validation Rules**:
- `interval`: Must be between 2000ms (2s) and 60000ms (60s)
- `enabled`: Boolean, defaults to true
- `logInterval`: Must be >= interval, defaults to 15000ms

**Source**: Embedded in HTML as `data-polling-*` attributes on `<body>` element.

### BackoffState

Tracks exponential backoff state for error recovery.

```typescript
interface BackoffState {
    /** Number of consecutive failures */
    errorCount: number;

    /** Current delay in milliseconds */
    currentDelay: number;

    /** Timestamp of last successful request */
    lastSuccessTime: number | null;

    /** Timestamp of last error */
    lastErrorTime: number | null;
}
```

**State Transitions**:
- On success: `errorCount` → 0, `currentDelay` → base interval, `lastSuccessTime` → now
- On error (< 3 failures): `errorCount` += 1, delay unchanged
- On error (>= 3 failures): `errorCount` += 1, `currentDelay` = min(10s * 2^(errors-3), 120s)

**Constants**:
```javascript
const BACKOFF = {
    INITIAL_DELAY: 10000,         // 10 seconds
    MAX_DELAY: 120000,            // 2 minutes
    FAILURES_BEFORE_BACKOFF: 3,   // Start backoff after 3 failures
    MULTIPLIER: 2                 // Double delay each time
};
```

### PollingState

Runtime state for an active polling loop.

```typescript
interface PollingState {
    /** Whether polling is currently active */
    isActive: boolean;

    /** Whether page is currently visible */
    isVisible: boolean;

    /** Timeout ID for next scheduled poll */
    timerId: number | null;

    /** Backoff state for error handling */
    backoff: BackoffState;

    /** Connection status for UI indicator */
    connectionStatus: 'connected' | 'reconnecting' | 'error';

    /** Timestamp of last data fetch */
    lastFetchTime: number | null;
}
```

**Lifecycle**:
1. Created when page loads
2. `isActive` set to true when polling starts
3. `isVisible` updated via Page Visibility API
4. `timerId` holds reference to active setTimeout
5. Cleanup on page unload or navigation

### JobsPollingContext

Extended state for Jobs dashboard polling.

```typescript
interface JobsPollingContext extends PollingState {
    /** Current filter parameters */
    filters: {
        status: string;
        type: string;
        since: string;
    };

    /** Current pagination offset */
    offset: number;

    /** Total jobs count from last response */
    totalJobs: number;

    /** Cached job data for comparison */
    cachedJobs: Map<string, JobListItem>;
}
```

### JobDetailPollingContext

Extended state for Job detail view polling.

```typescript
interface JobDetailPollingContext extends PollingState {
    /** Job ID being viewed */
    jobId: string;

    /** Whether job is in terminal state (no more updates expected) */
    isTerminal: boolean;

    /** Log polling state (separate from job status polling) */
    logPolling: {
        isActive: boolean;
        timerId: number | null;
        lastLineCount: number;
    };
}
```

**Terminal States**: `completed`, `failed`, `cancelled`
- When job reaches terminal state, polling continues briefly then stops
- Log polling stops immediately when job is terminal

## Server-Side Models

### PollingConfigResponse (New)

Response model for polling configuration endpoint (optional enhancement).

```python
@dataclass
class PollingConfigResponse:
    """Polling configuration for client."""
    interval_ms: int = 5000
    enabled: bool = True
    log_interval_ms: int = 15000

    def to_dict(self) -> dict:
        return {
            "interval_ms": self.interval_ms,
            "enabled": self.enabled,
            "log_interval_ms": self.log_interval_ms,
        }
```

**Note**: Initially, config will be embedded in templates. This model is for potential future `/api/config/polling` endpoint.

## Existing Entities (Unchanged)

The following existing models are used by polling but not modified:

### JobListItem (from ui/models.py)

```python
@dataclass
class JobListItem:
    id: str
    job_type: str
    status: str
    file_path: str | None
    progress_percent: int | None
    created_at: str | None
    completed_at: str | None
    duration_seconds: int | None
```

### JobDetailItem (from ui/models.py)

```python
@dataclass
class JobDetailItem:
    id: str
    id_short: str
    job_type: str
    status: str
    priority: int
    file_path: str | None
    policy_name: str | None
    created_at: str | None
    started_at: str | None
    completed_at: str | None
    duration_seconds: int | None
    progress_percent: int | None
    error_message: str | None
    output_path: str | None
    summary: str | None
    summary_raw: dict | None
    has_logs: bool
```

### JobLogsResponse (from ui/models.py)

```python
@dataclass
class JobLogsResponse:
    job_id: str
    lines: list[str]
    total_lines: int
    offset: int
    has_more: bool
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser                                   │
│  ┌────────────────┐    ┌────────────────┐    ┌───────────────┐  │
│  │ PollingConfig  │───▶│  PollingState  │───▶│  DOM Updates  │  │
│  │ (from HTML)    │    │  (runtime)     │    │  (UI)         │  │
│  └────────────────┘    └───────┬────────┘    └───────────────┘  │
│                                │                                 │
│                    ┌───────────▼───────────┐                    │
│                    │   setTimeout loop     │                    │
│                    │   - fetch()           │                    │
│                    │   - update state      │                    │
│                    │   - schedule next     │                    │
│                    └───────────┬───────────┘                    │
│                                │                                 │
└────────────────────────────────┼────────────────────────────────┘
                                 │ HTTP GET
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Server                                    │
│  ┌────────────────┐    ┌────────────────┐    ┌───────────────┐  │
│  │ /api/jobs      │    │ /api/jobs/{id} │    │ /api/jobs/    │  │
│  │                │    │                │    │ {id}/logs     │  │
│  └───────┬────────┘    └───────┬────────┘    └───────┬───────┘  │
│          │                     │                     │          │
│          └─────────────────────┴─────────────────────┘          │
│                                │                                 │
│                    ┌───────────▼───────────┐                    │
│                    │   SQLite Database     │                    │
│                    │   (jobs table)        │                    │
│                    └───────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

## State Persistence

- **Not persisted**: All polling state is ephemeral browser memory
- **Page reload**: Resets all polling state to defaults
- **Tab close**: All state destroyed, timers cleaned up via `beforeunload`
- **Browser back/forward**: Full page reload, state reset

## Thread Safety Considerations

### Client-Side (JavaScript)
- Single-threaded execution model
- No race conditions between callbacks
- `setTimeout` callbacks queued in event loop

### Server-Side (Python)
- Existing `DaemonConnectionPool` handles thread safety
- `asyncio.to_thread()` used for database queries
- No changes to concurrency model required

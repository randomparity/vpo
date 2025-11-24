# Research: Live Job Status Updates (Polling)

**Feature**: 017-live-job-polling
**Date**: 2025-11-23

## Research Tasks

### 1. Page Visibility API Best Practices

**Decision**: Use `document.visibilityState` and `visibilitychange` event

**Rationale**:
- Standard API supported by all modern browsers (Chrome 33+, Firefox 18+, Safari 7+, Edge 12+)
- Simple event-based interface: `document.addEventListener('visibilitychange', callback)`
- `document.visibilityState` returns 'visible' or 'hidden'
- No vendor prefixes needed for target browser versions

**Alternatives Considered**:
- `window.onfocus`/`onblur`: Less reliable, doesn't detect minimized windows
- `requestAnimationFrame` pause detection: More complex, indirect

**Implementation Pattern**:
```javascript
let isPageVisible = !document.hidden;
document.addEventListener('visibilitychange', () => {
    isPageVisible = !document.hidden;
    if (isPageVisible) {
        // Resume polling with immediate fetch
        startPolling();
    } else {
        // Pause polling
        stopPolling();
    }
});
```

### 2. JavaScript Polling with Exponential Backoff

**Decision**: Use `setTimeout` with dynamic delay calculation

**Rationale**:
- `setTimeout` preferred over `setInterval` for variable delays
- Allows delay adjustment based on error count
- Easier to cancel and restart
- Prevents overlapping requests if network is slow

**Backoff Strategy** (per clarification):
- Initial delay after error: 10 seconds
- Trigger: After 3 consecutive failures
- Doubling: Delay doubles after each subsequent failure
- Maximum: 2 minutes (120 seconds)
- Reset: On successful request

**Implementation Pattern**:
```javascript
const BACKOFF_CONFIG = {
    initialDelay: 10000,      // 10s initial backoff
    maxDelay: 120000,         // 2min max
    failuresBeforeBackoff: 3, // Start backoff after 3 failures
    multiplier: 2             // Double each time
};

function calculateDelay(errorCount, baseInterval) {
    if (errorCount < BACKOFF_CONFIG.failuresBeforeBackoff) {
        return baseInterval;
    }
    const backoffErrors = errorCount - BACKOFF_CONFIG.failuresBeforeBackoff;
    const delay = BACKOFF_CONFIG.initialDelay * Math.pow(BACKOFF_CONFIG.multiplier, backoffErrors);
    return Math.min(delay, BACKOFF_CONFIG.maxDelay);
}
```

**Alternatives Considered**:
- `setInterval`: Doesn't support variable delays, can cause request stacking
- Web Workers: Overkill for simple polling, adds complexity
- Service Workers: Better for offline-first, but more complex setup

### 3. DOM Update Without Flicker

**Decision**: Use targeted DOM updates with element comparison

**Rationale**:
- Avoid full table re-render to prevent scroll position reset
- Compare job data before updating to minimize DOM changes
- Use `requestAnimationFrame` for smooth visual updates if batching needed

**Implementation Pattern**:
```javascript
function updateJobRow(jobId, newData) {
    const row = document.querySelector(`tr[data-job-id="${jobId}"]`);
    if (!row) {
        // New job - append to table
        appendJobRow(newData);
        return;
    }

    // Update only changed cells
    const statusCell = row.querySelector('.status-badge');
    if (statusCell && statusCell.textContent !== newData.status) {
        statusCell.textContent = newData.status;
        statusCell.className = 'status-badge status-badge--' + newData.status;
    }
    // ... update other cells
}
```

**Alternatives Considered**:
- Virtual DOM library (Preact, etc.): Adds dependencies, overkill for this scale
- innerHTML replacement: Causes flicker, resets scroll, loses focus
- DocumentFragment: Good for batch inserts, but we're updating existing rows

### 4. Preserving Filter/Sort State During Polling

**Decision**: Maintain filter state in module-scoped variables, include in API requests

**Rationale**:
- Existing `jobs.js` already maintains `currentFilters` object
- Polling requests use same `buildQueryString()` function
- No additional state management needed

**Implementation Pattern**:
```javascript
// Existing pattern in jobs.js - reuse
let currentFilters = { status: '', type: '', since: '' };
let currentOffset = 0;

async function pollJobs() {
    // Uses same buildQueryString() as manual fetch
    const response = await fetch('/api/jobs' + buildQueryString());
    // ...
}
```

### 5. Error Indicator UX Pattern

**Decision**: Subtle status indicator in header/toolbar area

**Rationale**:
- Non-disruptive to job viewing workflow
- Clear but not alarming (connection issues are recoverable)
- Shows connection state: connected, reconnecting, error

**Implementation Pattern**:
```javascript
function setConnectionStatus(status) {
    const indicator = document.getElementById('connection-status');
    if (!indicator) return;

    indicator.className = 'connection-status connection-status--' + status;
    indicator.title = {
        'connected': 'Live updates active',
        'reconnecting': 'Reconnecting...',
        'error': 'Connection lost - retrying'
    }[status];
}
```

**Visual Design**:
- Small dot or icon in toolbar
- Green: Connected/polling active
- Yellow/Orange: Reconnecting (during backoff)
- Red: Error (max retries exceeded, but still trying)

### 6. Log Polling Strategy

**Decision**: Longer polling interval for logs (15s vs 5s for job status)

**Rationale**:
- Log content is larger payload than job metadata
- Logs change less frequently than status
- Reduces server load for detail view
- User can manually refresh if needed

**Implementation**:
- Status polling: Use configured interval (default 5s)
- Log polling: Fixed 15s interval, only when job is "running"
- Stop log polling when job completes/fails

### 7. Configuration Delivery to Client

**Decision**: Embed polling config in HTML template as data attribute

**Rationale**:
- No additional API request needed
- Config available immediately on page load
- Server controls the value based on daemon configuration
- Simple to implement and maintain

**Implementation Pattern**:
```html
<!-- In base.html or section template -->
<body data-polling-interval="{{ polling_interval }}" data-polling-enabled="{{ polling_enabled }}">
```

```javascript
// In polling.js
const config = {
    interval: parseInt(document.body.dataset.pollingInterval || '5000', 10),
    enabled: document.body.dataset.pollingEnabled !== 'false'
};
```

**Alternatives Considered**:
- `/api/config` endpoint: Extra HTTP request, but more flexible
- Inline `<script>` with JSON: Works but less clean than data attributes
- Hardcoded defaults only: Loses configurability

## Summary of Decisions

| Area | Decision | Key Benefit |
|------|----------|-------------|
| Visibility Detection | Page Visibility API | Standard, reliable, well-supported |
| Polling Mechanism | setTimeout with backoff | Flexible delay, prevents request stacking |
| DOM Updates | Targeted cell updates | No flicker, preserves scroll position |
| Filter State | Reuse existing pattern | No new code needed |
| Error Display | Subtle status indicator | Non-disruptive UX |
| Log Polling | Longer interval (15s) | Reduces server load |
| Config Delivery | HTML data attributes | No extra API call |

## Dependencies Confirmed

- No new npm/Python packages required
- All browser APIs available in target browsers
- Existing API endpoints sufficient for polling needs

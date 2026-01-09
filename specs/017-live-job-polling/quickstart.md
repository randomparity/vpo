# Quickstart: Live Job Status Updates (Polling)

**Feature**: 017-live-job-polling
**Date**: 2025-11-23

## Prerequisites

- Python 3.10+ installed
- VPO development environment set up
- Browser with DevTools for JavaScript debugging

## Setup

```bash
# Checkout feature branch
git checkout 017-live-job-polling

# Install dependencies (if not already installed)
uv pip install -e ".[dev]"

# Build Rust extension (if needed)
uv run maturin develop
```

## Running the Development Server

```bash
# Start the VPO daemon with web UI
uv run vpo serve --port 8080

# Or with verbose logging
uv run vpo serve --port 8080 --log-level debug
```

Access the web UI at: http://localhost:8080/jobs

## Key Files to Modify

### Client-Side (JavaScript)

1. **`src/vpo/server/static/js/polling.js`** (NEW)
   - Core polling utilities
   - Page Visibility API integration
   - Exponential backoff logic

2. **`src/vpo/server/static/js/jobs.js`** (MODIFY)
   - Integrate polling into dashboard
   - Add connection status indicator
   - Update job rows without full re-render

3. **`src/vpo/server/static/js/job_detail.js`** (MODIFY)
   - Add polling for job status updates
   - Add log polling for running jobs
   - Handle terminal state detection

### Server-Side (Python)

4. **`src/vpo/server/ui/routes.py`** (MODIFY)
   - Add polling config to template context
   - No new endpoints needed initially

5. **`src/vpo/server/ui/templates/base.html`** (MODIFY)
   - Add polling config data attributes
   - Add connection status indicator element

## Development Workflow

### Step 1: Create polling.js Module

```javascript
// src/vpo/server/static/js/polling.js
(function() {
    'use strict';

    // Configuration
    const DEFAULT_INTERVAL = 5000;
    const LOG_INTERVAL = 15000;
    const BACKOFF = {
        INITIAL_DELAY: 10000,
        MAX_DELAY: 120000,
        FAILURES_BEFORE_BACKOFF: 3,
        MULTIPLIER: 2
    };

    // Export for use by other modules
    window.VPOPolling = {
        // ... polling utilities
    };
})();
```

### Step 2: Test Visibility API

Open browser DevTools console and verify:

```javascript
// Check current visibility state
console.log('Visible:', !document.hidden);

// Test visibility change detection
document.addEventListener('visibilitychange', () => {
    console.log('Visibility changed to:', document.visibilityState);
});
```

### Step 3: Test API Endpoints

```bash
# List jobs
curl http://localhost:8080/api/jobs

# Get specific job
curl http://localhost:8080/api/jobs/{job_id}

# Get job logs
curl http://localhost:8080/api/jobs/{job_id}/logs
```

### Step 4: Create a Test Job

```bash
# Create a scan job to test polling
uv run vpo scan /path/to/media --async

# Check daemon logs for job ID
```

## Testing Checklist

### Manual Browser Testing

- [ ] Jobs dashboard updates when job status changes
- [ ] New jobs appear in list during polling
- [ ] Filter state preserved during polling
- [ ] No page flicker or scroll reset on update
- [ ] Polling pauses when tab is hidden
- [ ] Polling resumes when tab becomes visible
- [ ] Connection status indicator shows correctly
- [ ] Backoff behavior on simulated network errors

### Test Network Errors

1. Open DevTools → Network tab
2. Enable "Offline" mode or throttle to "Offline"
3. Observe console logs for backoff behavior
4. Re-enable network
5. Verify polling resumes and status shows "connected"

### Test with Running Job

1. Start a scan job on a directory with many files
2. Open Jobs dashboard
3. Verify progress percentage updates
4. Open job detail view
5. Verify logs update while job is running
6. Wait for job completion
7. Verify polling stops after terminal state

## Debug Tips

### JavaScript Console Logging

Add to `polling.js`:
```javascript
const DEBUG = true;
function log(...args) {
    if (DEBUG) console.log('[Polling]', ...args);
}
```

### Network Request Inspection

1. Open DevTools → Network tab
2. Filter by "Fetch/XHR"
3. Observe polling requests at configured interval
4. Check request timing and response data

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Polling doesn't start | Script not loaded | Check script tag in template |
| No updates visible | DOM selectors wrong | Verify element IDs in HTML |
| Rapid requests | Backoff not working | Check error count logic |
| Memory leak | Timers not cleaned | Verify cleanup on unload |

## Running Tests

```bash
# Run all tests
uv run pytest

# Run server tests only
uv run pytest tests/unit/server/

# Run with verbose output
uv run pytest -v tests/unit/server/test_polling_config.py
```

## Code Style

```bash
# Format Python code
uv run ruff format .

# Lint Python code
uv run ruff check .

# JavaScript: Use consistent 4-space indentation (matches existing files)
```

## Next Steps

After implementation:

1. Run full test suite: `uv run pytest`
2. Manual browser testing on Chrome, Firefox, Safari
3. Update documentation if needed
4. Create PR with description of changes

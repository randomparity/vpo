# Quickstart: Web UI REST API Endpoints

**Feature**: 028-webui-rest-api
**Date**: 2025-11-25

## Overview

This feature documents the existing REST API endpoints for the VPO Web UI. All endpoints are already implemented and functional.

## Prerequisites

- VPO installed with development dependencies
- Daemon running (`uv run vpo serve --port 8080`)

## Quick Verification

```bash
# Start the daemon
uv run vpo serve --port 8080

# Test jobs endpoint
curl http://localhost:8080/api/jobs

# Test library endpoint
curl http://localhost:8080/api/library

# Test policies endpoint
curl http://localhost:8080/api/policies
```

## Development Tasks

### Task 1: Create API Documentation

**Location**: `docs/api-webui.md`

**Steps**:
1. Create new file `docs/api-webui.md`
2. Document all 16 endpoints with consistent format
3. Include request parameters, response schemas, and examples
4. Add to `docs/INDEX.md`

**Reference**: Use `contracts/openapi.yaml` and `data-model.md` as source of truth.

### Task 2: Verify Documentation Accuracy

**Steps**:
1. For each documented endpoint, make a test request
2. Verify response matches documented schema
3. Verify error responses match documented format

### Task 3: Add Documentation Link to README

**Steps**:
1. Add link to `docs/api-webui.md` in main README
2. Reference in CLAUDE.md Web UI section

## Testing

```bash
# Run existing API tests
uv run pytest tests/unit/server/ -v

# Test specific endpoint handler
uv run pytest tests/unit/server/test_routes.py -k "api_jobs"
```

## Files to Modify

| File | Change |
|------|--------|
| `docs/api-webui.md` | NEW: API reference documentation |
| `docs/INDEX.md` | Add link to api-webui.md |
| `README.md` | Optional: Add API docs link |

## Implementation Notes

- All endpoints already exist in `server/ui/routes.py`
- Response models defined in `server/ui/models.py`
- CSRF middleware applies to POST/PUT endpoints
- No code changes required for endpoints themselves

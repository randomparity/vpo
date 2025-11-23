# Route Contracts: Web UI Shell

**Feature**: 013-web-ui-shell
**Date**: 2025-11-23

## Overview

The Web UI Shell exposes HTML page routes for browser navigation. All routes return server-rendered HTML (not JSON APIs). The existing `/health` endpoint remains unchanged.

## Routes

### GET /

**Description**: Root redirect to default section

**Request**: None

**Response**:
- Status: `302 Found`
- Headers: `Location: /jobs`

**Behavior**: Redirects to Jobs section (default per spec FR-008)

---

### GET /jobs

**Description**: Jobs section page

**Request**: None

**Response**:
- Status: `200 OK`
- Content-Type: `text/html; charset=utf-8`
- Body: Full HTML page with navigation (Jobs active) and placeholder content

**Template Context**:
```python
{
    "nav": NavigationState(items=[...], active_id="jobs"),
    "section_title": "Jobs",
    "section_content": "<p>Jobs section - coming soon</p>"
}
```

---

### GET /library

**Description**: Library section page

**Request**: None

**Response**:
- Status: `200 OK`
- Content-Type: `text/html; charset=utf-8`
- Body: Full HTML page with navigation (Library active) and placeholder content

**Template Context**:
```python
{
    "nav": NavigationState(items=[...], active_id="library"),
    "section_title": "Library",
    "section_content": "<p>Library section - coming soon</p>"
}
```

---

### GET /transcriptions

**Description**: Transcriptions section page

**Request**: None

**Response**:
- Status: `200 OK`
- Content-Type: `text/html; charset=utf-8`
- Body: Full HTML page with navigation (Transcriptions active) and placeholder content

**Template Context**:
```python
{
    "nav": NavigationState(items=[...], active_id="transcriptions"),
    "section_title": "Transcriptions",
    "section_content": "<p>Transcriptions section - coming soon</p>"
}
```

---

### GET /policies

**Description**: Policies section page

**Request**: None

**Response**:
- Status: `200 OK`
- Content-Type: `text/html; charset=utf-8`
- Body: Full HTML page with navigation (Policies active) and placeholder content

**Template Context**:
```python
{
    "nav": NavigationState(items=[...], active_id="policies"),
    "section_title": "Policies",
    "section_content": "<p>Policies section - coming soon</p>"
}
```

---

### GET /approvals

**Description**: Approvals section page

**Request**: None

**Response**:
- Status: `200 OK`
- Content-Type: `text/html; charset=utf-8`
- Body: Full HTML page with navigation (Approvals active) and placeholder content

**Template Context**:
```python
{
    "nav": NavigationState(items=[...], active_id="approvals"),
    "section_title": "Approvals",
    "section_content": "<p>Approvals section - coming soon</p>"
}
```

---

### GET /static/{path:path}

**Description**: Static file serving (CSS, JS, images)

**Request**: Path to static asset

**Response**:
- Status: `200 OK` (file exists) or `404 Not Found`
- Content-Type: Based on file extension (text/css, application/javascript, etc.)
- Body: File contents
- Headers: `Cache-Control: public, max-age=3600` (1 hour)

**Served Files**:
- `/static/css/main.css` - Main stylesheet
- `/static/js/nav.js` - Navigation JavaScript

---

### GET /{unknown_path}

**Description**: 404 handler for unknown routes

**Request**: Any path not matching above routes

**Response**:
- Status: `404 Not Found`
- Content-Type: `text/html; charset=utf-8`
- Body: Full HTML page with navigation and "Page not found" message

**Template Context**:
```python
{
    "nav": NavigationState(items=[...], active_id=None),
    "section_title": "Page Not Found",
    "error_message": "The page you requested could not be found."
}
```

---

## Existing Routes (Unchanged)

### GET /health

**Description**: Health check endpoint (from 012-daemon-systemd-server)

**Response**: JSON health status (unchanged)

---

## Route Registration Order

Routes should be registered in this order to ensure correct matching:

1. `/` (exact match, redirect)
2. `/health` (exact match, API)
3. `/jobs` (exact match, UI)
4. `/library` (exact match, UI)
5. `/transcriptions` (exact match, UI)
6. `/policies` (exact match, UI)
7. `/approvals` (exact match, UI)
8. `/static/{path}` (prefix match, static files)
9. Catch-all 404 handler (middleware)

---

## HTTP Headers

All HTML responses include:
- `Content-Type: text/html; charset=utf-8`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`

Static file responses include:
- `Cache-Control: public, max-age=3600`
- Appropriate `Content-Type` for file extension

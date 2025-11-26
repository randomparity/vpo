# Research: Web UI REST API Endpoints

**Feature**: 028-webui-rest-api
**Date**: 2025-11-25

## Overview

This feature documents existing, fully-implemented REST API endpoints. No technical unknowns exist regarding implementation since all endpoints are functional. Research focuses on API documentation best practices.

## Research Topics

### 1. API Documentation Format

**Decision**: Markdown-based API reference at `docs/api-webui.md`

**Rationale**:
- Consistent with existing VPO documentation format (markdown in `/docs/`)
- No build step required (unlike OpenAPI tooling)
- Easy to maintain alongside code changes
- Human-readable without special tooling

**Alternatives considered**:
- OpenAPI/Swagger spec: More formal but requires tooling; overkill for internal API
- JSDoc/docstrings: Already present in code but not user-facing
- Postman collection: Good for testing but not documentation

### 2. Documentation Structure

**Decision**: Organize by resource type with consistent endpoint sections

**Rationale**:
- Mirrors the spec's functional requirement groupings (Jobs, Library, etc.)
- Each endpoint follows same template: method, path, params, response, example
- Enables copy-paste usage by frontend developers

**Template per endpoint**:
```markdown
### GET /api/resource
Description of what endpoint does.

**Query Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| limit | integer | No | Page size (1-100, default 50) |

**Response**: `200 OK`
```json
{
  "items": [...],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

**Errors**:
- `400 Bad Request`: Invalid parameter
- `404 Not Found`: Resource not found
- `503 Service Unavailable`: Database not available
```

### 3. Response Schema Documentation

**Decision**: Document response shapes inline with JSON examples

**Rationale**:
- Existing response models in `ui/models.py` already define schemas via dataclasses
- JSON examples are more immediately useful than formal schema definitions
- Frontend developers can copy-paste expected response structure

### 4. Existing Endpoint Inventory

Based on `server/ui/routes.py` analysis:

| Endpoint | Method | Handler | Status |
|----------|--------|---------|--------|
| `/api/jobs` | GET | `api_jobs_handler` | Implemented |
| `/api/jobs/{id}` | GET | `api_job_detail_handler` | Implemented |
| `/api/jobs/{id}/logs` | GET | `api_job_logs_handler` | Implemented |
| `/api/jobs/{id}/errors` | GET | `api_job_errors_handler` | Implemented |
| `/api/library` | GET | `library_api_handler` | Implemented |
| `/api/library/{id}` | GET | `api_file_detail_handler` | Implemented |
| `/api/library/languages` | GET | `api_library_languages_handler` | Implemented |
| `/api/transcriptions` | GET | `api_transcriptions_handler` | Implemented |
| `/api/transcriptions/{id}` | GET | `api_transcription_detail_handler` | Implemented |
| `/api/policies` | GET | `policies_api_handler` | Implemented |
| `/api/policies/{name}` | GET | `api_policy_detail_handler` | Implemented |
| `/api/policies/{name}` | PUT | `api_policy_update_handler` | Implemented |
| `/api/policies/{name}/validate` | POST | `api_policy_validate_handler` | Implemented |
| `/api/plans` | GET | `api_plans_handler` | Implemented |
| `/api/plans/{id}/approve` | POST | `api_plan_approve_handler` | Implemented |
| `/api/plans/{id}/reject` | POST | `api_plan_reject_handler` | Implemented |

**Total**: 16 endpoints implemented, 0 to implement

### 5. CSRF Protection Pattern

**Decision**: Document CSRF token requirement for mutations

**Rationale**:
- POST/PUT endpoints require CSRF token in `X-CSRF-Token` header
- Token available from HTML page context (`csrf_token` in template)
- Important for frontend developers to understand

### 6. Error Response Format

**Decision**: Document standard error structure

**Existing pattern**:
```json
{
  "error": "Human-readable message",
  "details": "Optional additional context"
}
```

For validation errors:
```json
{
  "error": "Validation failed",
  "errors": [
    {"field": "field_name", "message": "Error message", "code": "error_code"}
  ],
  "details": "2 validation error(s) found"
}
```

## Conclusions

No technical unknowns remain. The documentation task is straightforward:
1. Create `docs/api-webui.md` following the structure above
2. Document all 16 endpoints with consistent formatting
3. Include CSRF requirements for mutations
4. Add JSON examples for all responses

## Dependencies

- None (all endpoints already implemented)

## Risks

- **Low**: Documentation may drift from implementation
  - Mitigation: Reference existing handler docstrings and models

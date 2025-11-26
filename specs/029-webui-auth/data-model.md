# Data Model: Web UI Authentication

**Feature**: 029-webui-auth
**Date**: 2025-11-25

## Entities

### ServerConfig (Extended)

Extends existing `ServerConfig` dataclass in `config/models.py`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| bind | str | "127.0.0.1" | Network address to bind to (existing) |
| port | int | 8321 | HTTP server port (existing) |
| shutdown_timeout | float | 30.0 | Graceful shutdown timeout (existing) |
| **auth_token** | str \| None | None | **NEW**: Shared secret for HTTP Basic Auth |

**Validation rules**:
- `auth_token`: Any printable ASCII string, or None/empty for disabled
- Empty string or whitespace-only treated as None (auth disabled)

**Lifecycle**:
- Loaded at server startup from config/env
- Immutable during server runtime
- No persistence beyond config file

---

## No New Database Tables

This feature does not introduce any database changes. Authentication state is:
- **Stateless**: Each request validated independently
- **Configuration-driven**: Token from env/config, not stored in DB
- **No session storage**: Browser handles Basic Auth credential caching

---

## Configuration Precedence

```
┌─────────────────────────────────────────────────────────────┐
│                    Token Resolution                          │
├─────────────────────────────────────────────────────────────┤
│ 1. VPO_AUTH_TOKEN environment variable (highest priority)   │
│ 2. server.auth_token in config.toml                         │
│ 3. None (auth disabled - backward compatible default)       │
└─────────────────────────────────────────────────────────────┘
```

---

## State Diagram

```
┌──────────────────┐
│  Server Startup  │
└────────┬─────────┘
         │
         ▼
    ┌────────────┐
    │ Load Token │
    │ from Config│
    └────────┬───┘
         │
         ▼
    ┌─────────────────┐     Yes     ┌─────────────────┐
    │ Token empty or  │────────────▶│ Log Warning:    │
    │ None?           │             │ "No auth config"│
    └────────┬────────┘             └────────┬────────┘
         │ No                                │
         ▼                                   ▼
┌─────────────────────┐          ┌─────────────────────┐
│ Auth Middleware     │          │ No Auth Middleware  │
│ Enabled             │          │ (open access)       │
└─────────────────────┘          └─────────────────────┘
```

---

## Request Flow (Auth Enabled)

```
┌─────────┐     ┌─────────────────┐     ┌─────────────┐     ┌─────────────┐
│ Request │────▶│ Auth Middleware │────▶│ Route       │────▶│ Response    │
└─────────┘     └────────┬────────┘     │ Handler     │     └─────────────┘
                         │              └─────────────┘
                         │
                    ┌────┴────┐
                    │ /health │
                    │ path?   │
                    └────┬────┘
                     Yes │ No
                         ▼
                  ┌──────────────┐
                  │ Has valid    │     No    ┌───────────────┐
                  │ Authorization│─────────▶│ 401 Response  │
                  │ header?      │          │ + WWW-Auth    │
                  └──────┬───────┘          └───────────────┘
                         │ Yes
                         ▼
                  ┌──────────────┐
                  │ Token matches│     No    ┌───────────────┐
                  │ (constant-   │─────────▶│ 401 Response  │
                  │ time)?       │          │ + WWW-Auth    │
                  └──────┬───────┘          └───────────────┘
                         │ Yes
                         ▼
                  ┌──────────────┐
                  │ Continue to  │
                  │ route handler│
                  └──────────────┘
```

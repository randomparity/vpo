# Research: Web UI Authentication

**Feature**: 029-webui-auth
**Date**: 2025-11-25

## Research Topics

### 1. aiohttp Middleware for HTTP Basic Auth

**Decision**: Use `@web.middleware` decorator pattern to create auth middleware.

**Rationale**:
- aiohttp middleware is the idiomatic way to implement cross-cutting concerns like authentication
- Middleware can inspect requests before handlers and short-circuit with 401 responses
- Existing codebase already uses middleware pattern (see `static_cache_middleware` in `app.py`)
- Middleware ordering is explicit via `app.middlewares` list

**Alternatives considered**:
- Decorator on each route handler: Rejected - too verbose, easy to miss endpoints
- Subapplication with auth: Rejected - overcomplicates routing structure
- aiohttp-basicauth library: Rejected - adds external dependency for simple feature

**Implementation pattern**:
```python
@web.middleware
async def auth_middleware(request: web.Request, handler: RequestHandler) -> web.StreamResponse:
    # Skip auth for health endpoint
    if request.path == "/health":
        return await handler(request)

    # Check Authorization header
    auth_header = request.headers.get("Authorization")
    if not _validate_auth(auth_header, expected_token):
        return web.Response(
            status=401,
            headers={"WWW-Authenticate": 'Basic realm="VPO"'}
        )

    return await handler(request)
```

---

### 2. Constant-Time Token Comparison

**Decision**: Use Python's `secrets.compare_digest()` for token validation.

**Rationale**:
- Part of Python standard library (no external dependencies)
- Specifically designed to prevent timing attacks
- Recommended by Python security documentation
- Simple API: `secrets.compare_digest(a, b)` returns bool

**Alternatives considered**:
- Direct string comparison (`==`): Rejected - vulnerable to timing attacks
- hmac.compare_digest: Works but `secrets` module is more semantically appropriate
- Custom implementation: Rejected - error-prone, unnecessary

**Implementation**:
```python
import secrets

def validate_token(provided: str, expected: str) -> bool:
    # Both must be strings; compare_digest handles length-constant comparison
    return secrets.compare_digest(provided.encode(), expected.encode())
```

---

### 3. HTTP Basic Auth Header Parsing

**Decision**: Manual parsing of `Authorization: Basic <base64>` header.

**Rationale**:
- Simple, well-documented RFC 7617 format
- Base64 decoding is in Python stdlib (`base64.b64decode`)
- Format: `Basic <base64(username:password)>`
- We only validate password (token), username is ignored per spec

**Alternatives considered**:
- aiohttp-security: Rejected - heavyweight for simple Basic Auth
- Third-party parsers: Rejected - trivial to implement correctly

**Implementation**:
```python
import base64

def parse_basic_auth(auth_header: str) -> tuple[str, str] | None:
    """Parse Basic Auth header, return (username, password) or None if invalid."""
    if not auth_header or not auth_header.startswith("Basic "):
        return None
    try:
        encoded = auth_header[6:]  # Skip "Basic "
        decoded = base64.b64decode(encoded).decode("utf-8")
        if ":" not in decoded:
            return None
        username, password = decoded.split(":", 1)
        return (username, password)
    except (ValueError, UnicodeDecodeError):
        return None
```

---

### 4. Configuration Precedence Pattern

**Decision**: Follow existing VPO pattern - environment variable takes precedence over config file.

**Rationale**:
- Consistent with existing `VPO_*` environment variables in `loader.py`
- Follows 12-factor app principles for secrets management
- Allows secure injection in container/systemd environments
- Config file provides fallback for simpler deployments

**Existing pattern in loader.py**:
```python
server = ServerConfig(
    bind=_get_env_str("VPO_SERVER_BIND", server_file.get("bind", "127.0.0.1")),
    port=_get_env_int("VPO_SERVER_PORT", server_file.get("port", 8321)),
    ...
)
```

**New addition**:
```python
# In ServerConfig dataclass
auth_token: str | None = None

# In loader
auth_token=os.environ.get("VPO_AUTH_TOKEN") or server_file.get("auth_token")
```

---

### 5. Endpoints to Exclude from Auth

**Decision**: Only `/health` endpoint is excluded from authentication.

**Rationale**:
- `/health` is used by load balancers, Kubernetes probes, and monitoring systems
- These systems typically cannot provide auth credentials
- Other endpoints (`/api/*`, UI routes, `/static/*`) all require auth when enabled
- Static files could leak application structure; better to protect them

**Alternatives considered**:
- Exclude `/static/*`: Rejected - static files could reveal version/structure info
- Exclude `/api/about`: Rejected - version info should be protected
- Configurable exclusion list: Rejected - overcomplicates for minimal benefit

---

### 6. Empty/Whitespace Token Handling

**Decision**: Treat empty or whitespace-only tokens as "auth disabled".

**Rationale**:
- Prevents accidental lockout from typos in config
- Empty string is semantically "not configured"
- Whitespace-only is likely a config error, treat same as empty
- Consistent with how other optional config values work

**Implementation**:
```python
def is_auth_enabled(token: str | None) -> bool:
    return token is not None and token.strip() != ""
```

---

## Summary

All technical decisions align with existing VPO patterns and use Python standard library where possible. No external dependencies required. The implementation is minimal, secure, and backward-compatible.

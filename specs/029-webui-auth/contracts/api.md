# API Contract: Web UI Authentication

**Feature**: 029-webui-auth
**Date**: 2025-11-25

## Authentication Scheme

**Type**: HTTP Basic Authentication (RFC 7617)
**Realm**: `VPO`

### Request Format

```http
Authorization: Basic <base64(username:password)>
```

Where:
- `username`: Any string (ignored by VPO)
- `password`: The configured auth token (`VPO_AUTH_TOKEN` or `server.auth_token`)

### Example

Token: `my-secret-token`

```http
GET /api/jobs HTTP/1.1
Host: localhost:8321
Authorization: Basic dXNlcjpteS1zZWNyZXQtdG9rZW4=
```

(Base64 of `user:my-secret-token`)

---

## Response Codes

### 401 Unauthorized

Returned when:
- No `Authorization` header provided (and auth is enabled)
- Invalid `Authorization` header format
- Incorrect token

**Response**:
```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Basic realm="VPO"
Content-Type: text/plain

Unauthorized
```

### 200 OK (or appropriate status)

Returned when:
- Auth is disabled (no token configured), OR
- Valid credentials provided

Request proceeds to normal route handler.

---

## Endpoint Protection Matrix

| Endpoint Pattern | Auth Required | Rationale |
|------------------|---------------|-----------|
| `GET /health` | No | Load balancer/monitoring probes |
| `GET /api/*` | Yes | API endpoints contain sensitive data |
| `GET /` (UI routes) | Yes | Web UI access |
| `GET /static/*` | Yes | Prevents structure disclosure |
| `POST /api/*` | Yes | Mutation operations |
| `PUT /api/*` | Yes | Mutation operations |
| `DELETE /api/*` | Yes | Mutation operations |

---

## Configuration

### Environment Variable

```bash
export VPO_AUTH_TOKEN="your-secret-token-here"
```

### Config File (`~/.vpo/config.toml`)

```toml
[server]
bind = "127.0.0.1"
port = 8321
auth_token = "your-secret-token-here"
```

### Precedence

1. `VPO_AUTH_TOKEN` environment variable (highest)
2. `server.auth_token` in config file
3. No auth (empty/unset = disabled)

---

## Browser Behavior

When a browser receives a 401 response with `WWW-Authenticate: Basic realm="VPO"`:

1. Browser displays native login dialog
2. User enters any username and the token as password
3. Browser caches credentials for the session
4. Subsequent requests include `Authorization` header automatically

---

## Security Considerations

1. **Transport Security**: Basic Auth credentials are Base64-encoded, NOT encrypted. Always use HTTPS in production or restrict to localhost.

2. **Token Storage**: Never commit tokens to version control. Use environment variables for production deployments.

3. **Timing Attacks**: Token comparison uses constant-time algorithm (`secrets.compare_digest`).

4. **No Rate Limiting**: This minimal implementation does not rate-limit failed auth attempts. Consider reverse proxy rate limiting for production.

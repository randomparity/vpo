# Quickstart: Web UI Authentication

**Feature**: 029-webui-auth
**Date**: 2025-11-25

## Prerequisites

- VPO installed and running
- Access to set environment variables or edit `~/.vpo/config.toml`

## Enable Authentication

### Option 1: Environment Variable (Recommended)

```bash
# Set the auth token
export VPO_AUTH_TOKEN="your-secret-token-here"

# Start the server
vpo serve
```

### Option 2: Config File

Edit `~/.vpo/config.toml`:

```toml
[server]
auth_token = "your-secret-token-here"
```

Then start the server:

```bash
vpo serve
```

## Access the Web UI

1. Open `http://localhost:8321/` in your browser
2. Browser displays login dialog
3. Enter any username and your token as the password
4. Click OK - you now have access

## Access via API

```bash
# Using curl with Basic Auth
curl -u "user:your-secret-token-here" http://localhost:8321/api/jobs

# Or with explicit header
curl -H "Authorization: Basic $(echo -n 'user:your-secret-token-here' | base64)" \
     http://localhost:8321/api/jobs
```

## Disable Authentication

To run without authentication (e.g., localhost-only development):

1. Unset the environment variable: `unset VPO_AUTH_TOKEN`
2. Remove `auth_token` from config file (or leave it empty)
3. Restart the server

A warning will be logged indicating the server is running without authentication.

## Verify Authentication is Working

```bash
# Should return 401 Unauthorized
curl -I http://localhost:8321/api/jobs

# Should return 200 OK (health check is always open)
curl -I http://localhost:8321/health

# Should return 200 OK with valid credentials
curl -u "user:your-token" http://localhost:8321/api/jobs
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 on all requests | Check token matches exactly (case-sensitive) |
| Token not working | Ensure no trailing whitespace in env var or config |
| Browser not prompting | Clear browser cache or try incognito mode |
| Can't access health endpoint | `/health` should always work - check server is running |

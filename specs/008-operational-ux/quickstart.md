# Quickstart: Operational UX

**Feature**: 008-operational-ux
**Date**: 2025-11-22

This guide covers the new operational features for periodic library maintenance.

---

## Incremental Scanning

### Basic Usage

Incremental mode is now the **default** when prior scan data exists:

```bash
# First scan (full scan, creates database records)
vpo scan /media/movies

# Subsequent scans (incremental, skips unchanged files)
vpo scan /media/movies
```

### Force Full Rescan

When you need to rescan everything:

```bash
vpo scan --full /media/movies
```

### Handle Missing Files

By default, missing files are marked in the database. To delete their records:

```bash
vpo scan --prune /media/movies
```

### Verify Content Integrity

For paranoid mode using content hashes:

```bash
vpo scan --verify-hash /media/movies
```

---

## Job History

### List Recent Jobs

```bash
# Show last 20 jobs
vpo jobs list

# Filter by status
vpo jobs list --status failed

# Filter by type
vpo jobs list --type scan

# Show jobs from last 7 days
vpo jobs list --since 7d

# JSON output for scripting
vpo jobs list --json
```

### View Job Details

```bash
# Full job ID
vpo jobs show abc12345-6789-0abc-def0-123456789abc

# Short prefix (minimum 4 characters)
vpo jobs show abc1
```

---

## Configuration Profiles

### Create a Profile

Create a YAML file in `~/.vpo/profiles/`:

```yaml
# ~/.vpo/profiles/movies.yaml
name: movies
description: Settings for movie library

default_policy: ~/policies/movies-standard.yaml

behavior:
  warn_on_missing_features: false

logging:
  level: info
  file: ~/.vpo/logs/movies.log
```

### List Profiles

```bash
vpo profiles list
```

### Use a Profile

```bash
# Scan with profile settings
vpo scan --profile movies /media/movies

# Apply policy from profile
vpo apply --profile movies /media/movies/file.mkv
```

### Override Profile Settings

CLI flags always win:

```bash
# Use movies profile but override log level
vpo scan --profile movies --log-level debug /media/movies
```

---

## Structured Logging

### Configure in config.yaml

```yaml
# ~/.vpo/config.yaml
logging:
  level: info           # debug, info, warning, error
  file: ~/.vpo/vpo.log  # optional file output
  format: text          # text or json
  max_bytes: 10485760   # 10MB before rotation
  backup_count: 5       # keep 5 rotated logs
```

### Override via CLI

```bash
# Debug logging to file
vpo scan --log-level debug --log-file /tmp/debug.log /media/movies

# JSON format for log aggregation
vpo scan --log-json /media/movies
```

### JSON Log Format

When `format: json` or `--log-json`:

```json
{"timestamp": "2025-11-22T10:30:00Z", "level": "INFO", "message": "Scan started", "context": {"path": "/media/movies"}}
{"timestamp": "2025-11-22T10:30:01Z", "level": "DEBUG", "message": "Introspecting file", "context": {"file": "movie.mkv"}}
```

---

## Common Workflows

### Daily Library Maintenance

```bash
#!/bin/bash
# Run nightly via cron

# Incremental scan of all libraries
vpo scan --profile movies /media/movies
vpo scan --profile tv /media/tv

# Check for failures
vpo jobs list --status failed --since 1d
```

### Troubleshooting a Failed Job

```bash
# 1. Find the failed job
vpo jobs list --status failed

# 2. View details
vpo jobs show abc1

# 3. Enable debug logging and retry
vpo scan --log-level debug --log-file /tmp/debug.log /media/movies

# 4. Check the log
cat /tmp/debug.log
```

### Setting Up Multiple Profiles

```bash
# Create profile directory
mkdir -p ~/.vpo/profiles

# Create profiles for different libraries
cat > ~/.vpo/profiles/movies.yaml << 'EOF'
name: movies
description: 4K movie collection
default_policy: ~/policies/movies-4k.yaml
logging:
  file: ~/.vpo/logs/movies.log
EOF

cat > ~/.vpo/profiles/kids.yaml << 'EOF'
name: kids
description: Kid-friendly content
default_policy: ~/policies/kids-safe.yaml
behavior:
  warn_on_missing_features: false
EOF

# Verify profiles
vpo profiles list
```

---

## Migration Notes

### From Previous Versions

1. **Scanning behavior changed**: Scans are now incremental by default. Use `--full` if you need the old behavior.

2. **New database schema**: The database will auto-migrate to version 7 on first run. Backup `~/.vpo/library.db` if concerned.

3. **Config file additions**: New `logging` section available in config.yaml. Old configs continue to work.

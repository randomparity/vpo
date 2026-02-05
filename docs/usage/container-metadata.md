# Container Metadata Guide

**Purpose:**
This document explains how to read, write, and clear container-level metadata tags in VPO policies using `container_metadata` conditions and `set_container_metadata` actions.

---

## Overview

Container tags are key-value pairs stored in the file container itself — MKV global tags, MP4 metadata atoms, and similar structures in other formats. Common tags include `title`, `encoder`, `creation_time`, `description`, and `comment`.

VPO captures container tags automatically during scanning (from ffprobe `format.tags`). Tags are stored with these rules:

- **Keys normalized to lowercase** — `TITLE` and `Title` both become `title`
- **Values are strings** — stored as-is after whitespace trimming
- **Null when absent** — files with no container tags have `container_tags: null`

You can view, check, and modify container tags through policies, the CLI, and the web UI.

---

## Viewing Container Tags

### CLI

Use `vpo inspect` to see container tags:

```bash
vpo inspect /path/to/file.mkv
```

Output includes a "Container Tags" section when tags are present:

```
Container Tags:
  title: My Movie (2024)
  encoder: libmatroska v1.7.1
  creation_time: 2024-01-15T10:30:00.000000Z
```

JSON output (`--json`) includes tags in the `container_tags` field:

```bash
vpo inspect --json /path/to/file.mkv
```

```json
{
  "container_tags": {
    "title": "My Movie (2024)",
    "encoder": "libmatroska v1.7.1",
    "creation_time": "2024-01-15T10:30:00.000000Z"
  }
}
```

### Web UI

The file detail page shows container tags in the "File Information" section as a key-value table.

---

## Container Metadata Conditions

Use `container_metadata` conditions in conditional rules to check tag values.

### Syntax

```yaml
when:
  container_metadata:
    field: <tag_name>        # Required: tag name (e.g., title, encoder)
    operator: <operator>     # Optional: comparison operator (default: eq)
    value: <compare_value>   # Required for all operators except exists
```

### Operators

| Operator | Description | Value Required | Notes |
|----------|-------------|:--------------:|-------|
| `eq` | Equal (default) | Yes | Case-insensitive for strings |
| `neq` | Not equal | Yes | Case-insensitive for strings |
| `contains` | Substring match | Yes | Case-insensitive |
| `exists` | Tag exists | No | True if field is present with any value |
| `lt` | Less than | Yes | Numeric coercion |
| `lte` | Less than or equal | Yes | Numeric coercion |
| `gt` | Greater than | Yes | Numeric coercion |
| `gte` | Greater than or equal | Yes | Numeric coercion |

### Field Name Rules

Field names must match: `^[a-zA-Z][a-zA-Z0-9_]{0,63}$`

- Must start with a letter
- Can contain letters, digits, and underscores
- 1–64 characters
- Normalized to lowercase automatically

### Numeric Coercion

The `lt`, `lte`, `gt`, and `gte` operators attempt to parse tag values as numbers. If the tag value is not numeric, the condition evaluates to false. The `value` field in the condition must itself be a number (not a quoted string):

```yaml
# Correct
value: 5000

# Incorrect — will cause a validation error
value: "5000"
```

### Examples

**Check if a title tag exists:**

```yaml
when:
  container_metadata:
    field: title
    operator: exists
```

**Match an encoder string:**

```yaml
when:
  container_metadata:
    field: encoder
    operator: contains
    value: "libmatroska"
```

**Numeric comparison (e.g., a custom tag):**

```yaml
when:
  container_metadata:
    field: bitrate_override
    operator: gt
    value: 5000
```

---

## Set Container Metadata Action

Use `set_container_metadata` actions to write or clear container tags.

### Static Value

Set a tag to a fixed string:

```yaml
then:
  - set_container_metadata:
      field: title
      value: "My Library File"
```

### Dynamic Value from Plugin Metadata

Resolve a tag value from plugin metadata at runtime:

```yaml
then:
  - set_container_metadata:
      field: title
      from_plugin_metadata:
        plugin: radarr
        field: external_title
```

If the referenced plugin or field is not available for a file, the action is skipped silently.

### Clearing Tags

Set the value to an empty string to clear/delete a tag:

```yaml
then:
  - set_container_metadata:
      field: encoder
      value: ""
```

### Validation Rules

- **Field names** follow the same rules as conditions (letter start, alphanumeric + underscore, 1–64 chars)
- Either `value` or `from_plugin_metadata` must be specified, but not both
- Plugin-resolved values are truncated to 4096 characters with a warning

---

## Combining Conditions and Actions

A typical container metadata workflow uses multiple phases: clean stale tags, set new values, then audit.

```yaml
schema_version: 12
config:
  on_error: continue

phases:
  # Clean up stale encoder and spam tags
  - name: sanitize
    conditional:
      - name: clear-encoder
        when:
          container_metadata:
            field: encoder
            operator: exists
        then:
          - set_container_metadata:
              field: encoder
              value: ""

      - name: clear-spam-comments
        when:
          container_metadata:
            field: comment
            operator: contains
            value: "http"
        then:
          - set_container_metadata:
              field: comment
              value: ""

  # Set title from Radarr/Sonarr metadata
  - name: title
    depends_on: [sanitize]
    conditional:
      - name: set-title-from-radarr
        when:
          plugin_metadata:
            plugin: radarr
            field: external_title
            operator: exists
        then:
          - set_container_metadata:
              field: title
              from_plugin_metadata:
                plugin: radarr
                field: external_title

  # Audit: warn about files still missing titles
  - name: audit
    depends_on: [title]
    conditional:
      - name: warn-no-title
        when:
          not:
            container_metadata:
              field: title
              operator: exists
        then:
          - warn: "No container title set: {filename}"
```

For a complete working example, see [`examples/policies/container-metadata.yaml`](../../examples/policies/container-metadata.yaml).

---

## Executor Support

Container metadata changes are applied by different executors depending on the file format:

| Container | Executor | Tool | Notes |
|-----------|----------|------|-------|
| MKV (Matroska) | mkvpropedit | mkvpropedit | Sets tags via `--edit info --set`; clears via `--edit info --delete` |
| MP4 and other ffmpeg-supported formats | ffmpeg_metadata | ffmpeg | Sets/clears tags via `-metadata field=value` (empty value clears) |

Both executors support setting tags to a value and clearing tags (empty string). The executor is selected automatically based on the file's container format.

---

## Best Practices

1. **Clear before set for idempotent workflows** — Clear stale tags in an earlier phase, then set fresh values in a later phase. This ensures repeatable results regardless of prior state.
2. **Use `exists` checks before acting on tag values** — Don't assume a tag is present. Check with `operator: exists` first, or use the `exists` operator in a containing `and` condition.
3. **Combine with plugin metadata for dynamic titles** — Use `from_plugin_metadata` to pull titles from Radarr or Sonarr rather than hardcoding values.
4. **Always dry-run first** — Preview container metadata changes before applying:
   ```bash
   vpo process -p policy.yaml --dry-run /path/to/file.mkv
   ```
5. **Use `depends_on` for phase ordering** — When later phases depend on tags set by earlier phases, use `depends_on` to enforce execution order.

---

## Related docs

- [Policy Configuration Guide](policies.md)
- [Conditional Policies](conditional-policies.md) — Condition types and actions reference
- [Radarr Metadata Plugin](../../src/vpo/plugins/radarr_metadata/README.md)
- [Sonarr Metadata Plugin](../../src/vpo/plugins/sonarr_metadata/README.md)
- [Policy Editor](policy-editor.md) — Visual editor support for container metadata

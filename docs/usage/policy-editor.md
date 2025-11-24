# Policy Editor Usage Guide

**Feature**: Visual Policy Editor (024-policy-editor)
**Status**: Production Ready
**Version**: 1.0

## Overview

The Visual Policy Editor provides a web-based interface for creating and modifying VPO policy files without manually editing YAML. The editor preserves unknown fields and comments during round-trip operations, ensuring safe editing of complex policies.

## Accessing the Editor

### Starting the Web Server

```bash
# Start VPO web server
uv run vpo serve --port 8080

# Server will be available at http://localhost:8080
```

### Navigating to the Editor

1. Open your browser to `http://localhost:8080`
2. Navigate to the **Policies** page
3. Click on any policy name to view details
4. Click the **Edit** button to open the editor

## Editor Features

### 1. Track Ordering

Configure the order in which track types appear in processed files.

**Usage:**
- Use ↑ and ↓ buttons to reorder track types
- Track types include: Video, Audio (Main), Audio (Alternate), Audio (Commentary), Subtitles (Main), Subtitles (Forced), Subtitles (Commentary), Attachments

**Best Practices:**
- Place video tracks first
- Group similar track types together
- Place commentary tracks at the end for better playback experience

### 2. Audio Language Preferences

Specify preferred audio languages in priority order.

**Usage:**
- Enter ISO 639-2 language code (e.g., `eng`, `jpn`, `fra`)
- Click **Add** or press Enter
- Use ↑/↓ buttons to change priority order
- Use × button to remove a language

**Language Code Examples:**
- `eng` - English
- `jpn` - Japanese
- `fra` - French
- `deu` - German
- `spa` - Spanish
- `ita` - Italian
- `und` - Undetermined

**Validation:**
- Codes must be 2-3 lowercase letters
- Duplicates are not allowed
- At least one language required

### 3. Subtitle Language Preferences

Specify preferred subtitle languages in priority order.

**Usage:**
- Same as audio language preferences
- Use ISO 639-2 codes
- Order determines priority for subtitle selection

### 4. Default Flags

Configure which tracks are marked as default in processed files.

**Options:**
- **Set first video track as default** - Marks the first video track with default flag
- **Set preferred audio track as default** - Marks the highest-priority audio language as default
- **Set preferred subtitle track as default** - Marks the highest-priority subtitle language as default
- **Clear other default flags** - Removes default flags from other tracks

**Best Practices:**
- Enable "Clear other default flags" to avoid conflicts
- Set preferred audio as default for predictable playback
- Only set subtitle default if you want subtitles on by default

### 5. Commentary Detection

Configure patterns and settings for detecting commentary tracks.

**Commentary Patterns:**
- Enter regex patterns to match commentary track titles
- Examples: `commentary`, `director`, `cast`, `^Commentary$`
- Patterns are case-insensitive by default

**Transcription Settings:**
- **Enable commentary detection** - Use transcription analysis to detect commentary
- **Move commentary tracks to end** - Automatically reorder detected commentary tracks (requires detection enabled)

**Validation:**
- Patterns must be valid regular expressions
- "Move commentary tracks" requires "Enable commentary detection"

### 6. YAML Preview

Real-time preview of the policy file as YAML.

**Features:**
- Updates automatically as you edit (300ms debounce)
- Read-only view of generated YAML
- Shows exactly what will be saved
- Useful for verifying changes before saving

## Saving Changes

### Save Process

1. Make your desired changes in the form
2. Review the YAML preview
3. Click **Save Changes**
4. Wait for confirmation message

### Save Status Messages

- **"Saving..."** - Save in progress
- **"Policy saved successfully"** - Save completed
- **Error messages** - Validation or save errors

### Validation

The editor validates your changes before saving:

- **Track order** cannot be empty
- **Language codes** must be valid ISO 639-2 format
- **Commentary patterns** must be valid regex
- **Cross-field rules** (e.g., reorder requires detection enabled)

### Concurrent Modification Detection

If another user (or process) modifies the policy file while you're editing:

1. Your save will be rejected with a **409 Conflict** error
2. You'll see message: "Concurrent modification detected"
3. **Action**: Reload the page to get the latest version
4. Reapply your changes and save again

## Field Preservation

The editor preserves elements not exposed in the UI:

### Always Preserved

- **Unknown top-level fields** - Custom fields like `x_custom_field`
- **Transcode section** - Transcoding settings (not editable in UI)
- **YAML formatting** - Indentation, line breaks, key order

### Best-Effort Preservation

- **Comments** on unchanged fields are preserved
- **Comments** on edited fields may shift or be lost

### Example

**Before editing:**
```yaml
schema_version: 2
# This comment will be preserved
track_order:
  - video
  - audio_main

# Custom field (preserved)
x_my_setting: value
```

**After editing audio languages:**
```yaml
schema_version: 2
# This comment will be preserved
track_order:
  - video
  - audio_main

audio_language_preference:
  - fra  # Changed
  - eng

# Custom field (preserved)
x_my_setting: value
```

## Keyboard Shortcuts

- **Tab** - Navigate between fields
- **Enter** - Submit language/pattern input
- **Escape** - Close dropdowns/cancel inputs

## Unsaved Changes Warning

The editor warns you before navigating away with unsaved changes:

- **Browser warning** - "You have unsaved changes. Are you sure you want to leave?"
- **Cancel button** - Prompts for confirmation if changes exist

## Error Handling

### Common Errors

**"Invalid language code 'xx'"**
- Cause: Language code doesn't match ISO 639-2 format
- Solution: Use 2-3 lowercase letter codes (e.g., `eng`, `jpn`)

**"Track order cannot be empty"**
- Cause: All track types were removed
- Solution: Add at least one track type back

**"Invalid regex pattern"**
- Cause: Commentary pattern has invalid regex syntax
- Solution: Check pattern syntax (e.g., unmatched parentheses)

**"Reorder commentary requires detect commentary to be enabled"**
- Cause: Trying to enable reorder without detection
- Solution: Enable "Enable commentary detection" first

**"Concurrent modification detected"**
- Cause: Policy was modified since you loaded it
- Solution: Reload page, reapply changes, save again

**"Policy not found"**
- Cause: Policy file was deleted
- Solution: Return to policies list, create new policy

## Best Practices

### Editing Workflow

1. **Load** - Open policy in editor
2. **Review** - Check current settings
3. **Edit** - Make one logical set of changes
4. **Preview** - Verify YAML looks correct
5. **Save** - Save and wait for confirmation
6. **Test** - Test changes with `vpo apply --dry-run`

### Organization

- **Use descriptive language codes** - Stick to standard ISO codes
- **Order by priority** - Most preferred language first
- **Group related changes** - Don't mix unrelated edits
- **Test incrementally** - Save and test frequently

### Safety

- **Avoid concurrent editing** - One editor per policy at a time
- **Back up policies** - Copy policy files before major changes
- **Use dry-run** - Test with `--dry-run` before applying to library
- **Preserve unknown fields** - Don't manually edit while using UI

## Advanced Usage

### Editing Policies with Transcription

If your policy has a `transcription` section, you can:
- Enable/disable commentary detection
- Enable/disable automatic reordering
- Other transcription settings preserved but not editable in UI

### Editing Policies with Transcode

The `transcode` section is preserved but not editable in the UI.

To edit transcode settings:
1. Save your UI changes
2. Edit the YAML file manually for transcode section
3. Validate with `vpo apply --dry-run`

### Multiple Policies

You can edit multiple policies in separate browser tabs, but:
- **Don't edit the same policy in multiple tabs** (concurrent modification error)
- **Save frequently** to avoid losing work
- **Use different policies for different purposes** (e.g., TV vs Movies)

## Troubleshooting

### Changes Not Appearing in Preview

**Symptoms:** YAML preview doesn't update after editing

**Solutions:**
1. Wait 300ms (debounce delay)
2. Check browser console for JavaScript errors
3. Refresh page and try again

### Save Button Disabled

**Symptoms:** Can't click Save Changes button

**Causes:**
- No changes made (form is pristine)
- Save operation in progress
- Validation errors present

**Solutions:**
- Make at least one change
- Wait for current save to complete
- Fix validation errors shown

### Lost Comments

**Symptoms:** Comments disappeared from policy file

**Cause:** Comments on edited fields may be lost (best-effort preservation)

**Workaround:**
- Keep important comments on fields you don't edit via UI
- Add comments to unknown fields (always preserved)
- Re-add comments manually after UI edits if needed

## Related Documentation

- [Policy Schema Reference](../reference/policy-schema.md)
- [Policy Loader Documentation](../design/policy-loader.md)
- [Web UI Overview](../overview/web-ui.md)

## Support

For issues or questions:
- Check [GitHub Issues](https://github.com/randomparity/vpo/issues)
- Review [CLAUDE.md](../../CLAUDE.md) for development notes
- Consult [Quickstart Guide](../../specs/024-policy-editor/quickstart.md)

# Policy Editor Usage Guide

**Feature**: Visual Policy Editor (024-policy-editor, 036-v9-policy-editor, 037-user-defined-phases)
**Status**: Production Ready
**Version**: 3.0 (V3-V13 Schema Support)

## Overview

The Visual Policy Editor provides a web-based interface for creating and modifying VPO policy files without manually editing YAML. The editor creates V13 policies using the **phased format** (the only supported format). Features include video/audio transcoding, track filtering, conditional rules, audio synthesis, container conversion, and user-defined phases. The editor preserves unknown fields and comments during round-trip operations, ensuring safe editing of complex policies.

**Note:** All policies must use the V13 phased format with `phases` and optional `config` sections. Flat policy format is no longer supported.

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
3. Click the **Edit** button next to any policy to open the editor

### Creating a New Policy

1. Navigate to the **Policies** page
2. Click the **+ Create New Policy** button in the header
3. Enter a policy name (letters, numbers, dashes, underscores only)
4. Optionally add a description
5. Click **Create Policy** to create and open the editor
6. The new policy is created with schema version 13 and sensible defaults

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

## Advanced Settings (V3-V10 Schema Features)

The **Advanced Settings** accordion contains configuration for policy schema versions V3-V10. These settings are organized in collapsible sections.

### 7. Video Transcoding (V6+)

Configure video transcoding settings for converting video tracks.

**Enable Video Transcoding:**
- Toggle to enable video transcoding
- Shows/hides all video transcode options

**Target Codec:**
- Select target codec: `hevc`, `h264`, `av1`, `vp9`
- Determines the output video codec

**Skip Conditions:**
Configure conditions to skip transcoding:
- **Codec matches** - Skip if source matches these codecs (comma-separated)
- **Resolution within** - Skip if source resolution ≤ selected (1080p, 720p, 480p)
- **Bitrate under** - Skip if source bitrate under threshold (e.g., `15M`, `8M`)

**Quality Settings:**
- **Mode** - `crf` (constant rate factor) or `cbr` (constant bitrate)
- **CRF Value** - Quality level for CRF mode (0-51, lower = better)
- **Preset** - Encoding speed preset (ultrafast to veryslow)
- **Target Bitrate** - Bitrate for CBR mode (e.g., `8M`)

**Scaling:**
- **Max Resolution** - Maximum output resolution (1080p, 720p, 480p, or none)
- **Algorithm** - Scaling algorithm (lanczos, bilinear, bicubic, spline)

**Hardware Acceleration:**
- **Enabled** - `auto`, `true`, or `false`
- **Fallback to CPU** - Fall back to software encoding if HW unavailable

### 8. Audio Transcoding (V6+)

Configure audio transcoding settings.

**Enable Audio Transcoding:**
- Toggle to enable audio transcode section
- Shows/hides all audio transcode options

**Preserve Codecs:**
- List of codecs to never transcode (comma-separated)
- Example: `truehd, dts-hd, flac`
- Preserves high-quality lossless audio

**Transcode Target:**
- **Target Codec** - Codec for transcoded audio (aac, ac3, opus, flac)
- **Bitrate** - Target bitrate (e.g., `192k`, `256k`)

### 9. Track Filtering (V3+)

Configure which tracks to keep, remove, or filter.

**Keep Audio:**
- **Languages** - Keep only tracks with these languages (comma-separated ISO codes)
- **Fallback Mode** - Action when preferred languages not found:
  - `keep_original` - Keep original audio
  - `first_available` - Use first available track
  - `error` - Fail the operation
- **Minimum Tracks** - Minimum audio tracks to keep (0 = no minimum)
- **V10 Options:**
  - **Include Music** - Keep music-only tracks
  - **Include SFX** - Keep sound effects tracks
  - **Include Non-Speech** - Keep non-speech tracks

**Keep Subtitles:**
- **Languages** - Keep only subtitles with these languages
- **Preserve Forced** - Always keep forced subtitles
- **Remove All** - Remove all subtitle tracks

**Filter Attachments:**
- **Remove All** - Remove all attachment tracks (fonts, images, etc.)

### 10. Conditional Rules (V4+)

Define rules that apply different actions based on file conditions.

**Adding Rules:**
1. Click **+ Add Rule** to create a new conditional rule
2. Configure the condition (when)
3. Configure the action (then)
4. Optionally add an else action

**Condition Types:**
- **exists** - Check if a track type exists
- **count** - Check track count with operator (=, <, >, ≤, ≥)
- **and** - Combine multiple conditions (all must match)
- **or** - Combine multiple conditions (any must match)
- **not** - Negate a condition
- **audio_is_multi_language** - Check if file has audio in multiple languages

**Track Filters in Conditions:**
- **languages** - Match specific language codes
- **codecs** - Match specific codecs
- **is_default** - Match default tracks
- **is_commentary** - Match commentary tracks
- **is_hearing_impaired** - Match HI tracks

**Actions:**
- **skip_video** / **skip_audio** / **skip_subtitle** - Skip processing specific tracks
- **skip_file** - Skip the entire file
- **warn** - Log a warning message
- **fail** - Fail the operation with an error
- **set_forced** - Set/unset forced flag on matching tracks (V7+)
- **set_default** - Set/unset default flag on matching tracks (V7+)

### 11. Audio Synthesis (V5+)

Create new audio tracks from existing ones (e.g., stereo downmix from surround).

**Adding Synthesis Tracks:**
1. Click **+ Add Synthesis Track**
2. Configure the track settings
3. Click **× Remove** to delete unwanted tracks

**Track Configuration:**
- **Track Name** - Name for the synthesized track
- **Codec** - Output codec (aac, ac3, opus, flac)
- **Channels** - Channel count (2 = stereo, 6 = 5.1, 8 = 7.1)

**Source Preference:**
- Priority order for selecting source track:
  - `original_language` - Prefer original language
  - `most_channels` - Prefer highest channel count
  - `first_match` - Use first matching track

**Skip If Exists (V8+):**
- Skip creating track if similar already exists
- Match criteria: `channel_count`, `codec`, `language`

### 12. Container Settings (V3+)

Configure container format conversion.

**Target Container:**
- Select target format: `mkv` or `mp4`
- Empty = no container conversion

**On Incompatible Codec:**
- Action when source contains incompatible codecs:
  - `error` - Fail the operation (default)
  - `skip` - Skip the file
  - `transcode` - Transcode incompatible tracks

### 13. Workflow Configuration (V9+)

Configure how VPO processes files.

**Processing Phases:**
- **Analyze** - Analyze file and generate plan
- **Apply** - Apply metadata changes
- **Transcode** - Run video/audio transcoding

**Workflow Options:**
- **Auto Process** - Automatically process files after scan
- **On Error** - Error handling behavior:
  - `continue` - Continue with next file
  - `skip` - Skip the current file
  - `fail` - Stop processing

**Note:** For V11 policies, use the User-Defined Phases section instead. The V9 Workflow Configuration section is hidden for V11 policies.

### 14. User-Defined Phases (V11)

V11 introduces user-defined processing phases, replacing the fixed V9 workflow with customizable named phases. This section only appears for V11 policies.

**Creating Phases:**
1. Click **+ Add Phase** to create a new phase
2. Enter a descriptive phase name (e.g., "cleanup", "normalize", "compress")
3. Select which operations to enable for this phase
4. Drag phases to reorder execution sequence

**Phase Naming Rules:**
- Must start with a letter (a-z, A-Z)
- Can contain letters, numbers, hyphens, and underscores
- Maximum 64 characters
- Cannot use reserved names: `config`, `schema_version`, `phases`
- Each phase name must be unique within the policy

**Available Operations:**
Each phase can include any combination of these operations (executed in canonical order):

| Operation | Description |
|-----------|-------------|
| Track Actions | Pre-process audio/subtitle/video flags and titles (YAML only) |
| Container Conversion | Convert container format (mkv, mp4) |
| Keep Audio | Filter audio tracks by language |
| Keep Subtitles | Filter subtitle tracks by language |
| Filter Attachments | Remove attachments |
| Track Ordering | Reorder tracks by type |
| Default Flags | Set default track flags |
| Rules | Apply conditional logic |
| Audio Synthesis | Create synthesized audio tracks |
| Transcode | Transcode video/audio |
| Transcription | Transcription analysis |

**Operation Execution Order:**
Within each phase, operations execute in the canonical order shown above, regardless of the order you enable them. This ensures consistent and predictable behavior.

**Global Configuration:**
- **On Error** - How to handle errors during phase execution:
  - `skip` - Skip the current file and continue (default)
  - `continue` - Log error and continue with next phase
  - `fail` - Stop processing immediately

**Drag-and-Drop Reordering:**
- Drag the ⋮⋮ handle to reorder phases
- Visual indicators show insertion point during drag
- Phase order determines execution sequence

**Example V13 Policy Structure:**
```yaml
schema_version: 13
config:
  on_error: skip
phases:
  - name: cleanup
    keep_audio:
      languages: [eng, jpn]
    keep_subtitles:
      languages: [eng]
  - name: normalize
    track_order: [video, audio, subtitle]
    default_flags:
      set_first_video_default: true
  - name: compress
    transcode:
      video:
        to: hevc
        crf: 20
```

**CLI Integration:**
V11 policies can be executed with selective phase filtering:

```bash
# Execute all phases
vpo process -p policy.yaml /path/to/video.mkv

# Execute specific phases only
vpo process -p policy.yaml --phases cleanup,normalize /path/to/video.mkv

# Dry-run to preview changes
vpo process -p policy.yaml --dry-run /path/to/video.mkv
```

---

### 15. Container Metadata Conditions and Actions

The policy editor supports `container_metadata` conditions and `set_container_metadata` actions within conditional rules.

**Adding a Container Metadata Condition:**

1. In a conditional rule, select **container_metadata** as the condition type
2. Enter the **field name** (e.g., `title`, `encoder`) — validated against naming rules
3. Select an **operator** from the dropdown: eq, neq, contains, lt, lte, gt, gte, or exists
4. Enter a **value** to compare against (the value input is hidden when the operator is `exists`)

**Adding a Set Container Metadata Action:**

1. In a conditional rule's "then" or "else" actions, select **set_container_metadata**
2. Enter the **field name** to set (e.g., `title`, `encoder`)
3. Enter the **value** to set — leave empty to clear/delete the tag

**Notes:**
- Container metadata conditions and actions are available in V13 policies
- Field names follow standard validation: must start with a letter, contain only letters/digits/underscores, max 64 characters
- The value input dynamically shows or hides based on the selected operator

## Validation Features

The policy editor includes comprehensive validation to help you create correct policy configurations.

### Real-Time Validation

As you type, the editor provides immediate visual feedback:

- **Language codes**: Green border for valid codes, red border for invalid
- **Regex patterns**: Green border for valid patterns, red border for syntax errors
- Input fields show validation state with colored borders and aria-invalid attributes

### Test Policy (Dry-Run)

Before committing changes, you can validate your configuration without saving:

1. Make your desired changes
2. Click **Test Policy** button
3. See validation result:
   - **Success**: "Policy configuration is valid" message
   - **Failure**: Field-level error messages displayed

This is useful for:
- Checking complex pattern syntax
- Validating language code combinations
- Testing changes before committing to disk

### Field-Level Error Display

When validation fails, the editor shows detailed errors:

- **Error list**: All validation errors displayed together
- **Field highlighting**: Affected form sections have red borders
- **Auto-scroll**: First error field scrolled into view
- **Focus management**: Focusable element in error section receives focus

**Error Display Format:**
```text
2 validation errors found:
• audio_languages[0]: Invalid language code
• commentary_patterns[1]: Invalid regex pattern
```

## Saving Changes

### Save Process

1. Make your desired changes in the form
2. Review the YAML preview
3. Optionally click **Test Policy** to validate first
4. Click **Save Changes**
5. Wait for confirmation message

### Save Status Messages

- **"Saving..."** - Save in progress
- **"Saved: [change summary]"** - Save completed with diff summary
- **"Policy saved successfully"** - Save completed (no changes detected)
- **Error messages** - Validation or save errors

### Diff Summary

On successful save, the editor shows what changed:

- **Reordered fields**: "audio_languages: eng, jpn -> jpn, eng"
- **Added items**: "commentary_patterns: added director"
- **Removed items**: "audio_languages: removed fra"
- **Modified values**: "default_flags.clear_other_defaults: true -> false"

This helps you:
- Confirm intended changes were applied
- Understand exactly what was modified
- Review changes after save

### Validation

The editor validates your changes before saving:

- **Track order** cannot be empty
- **Language codes** must be valid ISO 639-2 format (2-3 lowercase letters)
- **Language lists** cannot be empty (at least one language required)
- **Commentary patterns** must be valid regular expressions
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
- **Advanced nested settings** - Subsection options not shown in the UI
- **YAML formatting** - Indentation, line breaks, key order

### Best-Effort Preservation

- **Comments** on unchanged fields are preserved
- **Comments** on edited fields may shift or be lost

### Example

**Before editing:**
```yaml
schema_version: 13
# This comment will be preserved
phases:
  - name: organize
    track_order:
      - video
      - audio_main

# Custom field (preserved)
x_my_setting: value
```

**After editing audio languages:**
```yaml
schema_version: 13
# This comment will be preserved
phases:
  - name: organize
    track_order:
      - video
      - audio_main
    keep_audio:
      languages: [fra, eng]  # Changed

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

### Validation Error Display

Validation errors are displayed with field-level detail:

1. **Error banner** appears at top of form with all errors listed
2. **Field sections** with errors are highlighted with red border
3. **Auto-scroll** brings the first error into view
4. Click the **×** button to dismiss errors and highlighting

### Common Errors

**"Invalid language code 'xx'"**
- Cause: Language code doesn't match ISO 639-2 format
- Solution: Use 2-3 lowercase letter codes (e.g., `eng`, `jpn`)

**"Language list cannot be empty"**
- Cause: All languages were removed from audio or subtitle preferences
- Solution: Add at least one language code

**"Track order cannot be empty"**
- Cause: All track types were removed
- Solution: Add at least one track type back

**"Invalid regex pattern"**
- Cause: Commentary pattern has invalid regex syntax
- Solution: Check pattern syntax (e.g., unmatched parentheses, unclosed brackets)

**"Reorder commentary requires detect commentary to be enabled"**
- Cause: Trying to enable reorder without detection
- Solution: Enable "Enable commentary detection" first

**"Validation failed"**
- Cause: Server-side validation found issues
- Solution: Review the field-level errors shown and fix each issue

**"Concurrent modification detected"**
- Cause: Policy was modified since you loaded it
- Solution: Reload page, reapply changes, save again

**"Policy not found"**
- Cause: Policy file was deleted
- Solution: Return to policies list, create new policy

**"Network error"**
- Cause: Server not responding or connection lost
- Solution: Check server is running, verify network connection

**"Phase name is required"** (V11)
- Cause: A phase was created without a name
- Solution: Enter a valid phase name starting with a letter

**"Phase name must start with a letter..."** (V11)
- Cause: Phase name doesn't match the naming pattern
- Solution: Use a name starting with a letter, containing only letters, numbers, hyphens, or underscores (max 64 chars)

**"'config' is a reserved name"** (V11)
- Cause: Trying to use a reserved word as phase name
- Solution: Choose a different name; `config`, `schema_version`, and `phases` are reserved

**"Phase 'name' already exists"** (V11)
- Cause: Duplicate phase name in the policy
- Solution: Use unique names for each phase

**"Invalid phase name(s): ..."** (CLI)
- Cause: `--phases` option specified names not in the policy
- Solution: Check available phase names with `vpo process -p policy.yaml --help` or review the policy file

## Best Practices

### Editing Workflow

1. **Load** - Open policy in editor
2. **Review** - Check current settings
3. **Edit** - Make one logical set of changes
4. **Preview** - Verify YAML looks correct
5. **Save** - Save and wait for confirmation
6. **Test** - Test changes with `vpo process --dry-run`

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

### Editing Policies with Transcode (V6+)

The Visual Policy Editor fully supports V6+ transcode configuration:

1. Enable video/audio transcoding in the **Advanced Settings** accordion
2. Configure codec, quality, and skip conditions
3. Preview changes in the YAML panel
4. Test with **Test Policy** before saving
5. Validate with `vpo process --dry-run` after saving

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

## Related docs

- [V11 Migration Guide](v11-migration.md) - Upgrading from V10 to V11 policies
- [Policies Guide](policies.md) - General policy configuration
- [Conditional Policies](conditional-policies.md) - Conditional rules
- [Container Metadata](container-metadata.md) - Reading, writing, and clearing container tags
- [Transcode Policy](transcode-policy.md) - Transcoding settings

## Support

For issues or questions:
- Check [GitHub Issues](https://github.com/randomparity/vpo/issues)
- Review [CLAUDE.md](../../CLAUDE.md) for development notes
- Consult [Quickstart Guide](../../specs/024-policy-editor/quickstart.md)

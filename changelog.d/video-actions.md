### Added

- **`video_actions` policy phase operation**: New pre-processing actions for video tracks (`clear_all_forced`, `clear_all_default`, `clear_all_titles`), mirroring the existing `audio_actions` and `subtitle_actions`. Use `video_actions` to clear encoder title strings or normalize flags on video tracks before other operations run.

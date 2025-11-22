# Research: Audio Transcription & Language Detection

**Feature**: 007-audio-transcription
**Date**: 2025-11-22

## Research Topics

### 1. Whisper Integration Patterns

**Decision**: Use `openai-whisper` package as optional dependency with lazy loading

**Rationale**:
- The `openai-whisper` package is the official OpenAI implementation, well-maintained and widely used
- Lazy loading ensures VPO starts quickly even without Whisper installed
- Optional dependency avoids forcing large ML model downloads on all users
- Whisper provides built-in language detection via `detect_language()` function

**Alternatives Considered**:
- `faster-whisper` (CTranslate2-based): Faster inference but less stable API, would add complexity
- `whisper.cpp` bindings: Better performance but requires separate binary installation
- Cloud APIs (AssemblyAI, Deepgram): Violates offline-first principle, would be separate plugins

**Implementation Notes**:
```python
# Lazy loading pattern
def get_whisper():
    try:
        import whisper
        return whisper
    except ImportError:
        raise PluginDependencyError(
            "Whisper plugin requires 'openai-whisper' package. "
            "Install with: pip install openai-whisper"
        )
```

### 2. Audio Extraction via ffmpeg

**Decision**: Use subprocess with pipe to stream audio directly to Whisper

**Rationale**:
- Avoids creating temporary files (disk I/O, cleanup concerns)
- ffmpeg is already a VPO dependency (used by ffprobe, transcode)
- Consistent with existing tool integration patterns in `executor/` module
- 16kHz mono WAV is Whisper's native format, minimizing conversion overhead

**Alternatives Considered**:
- Temporary file extraction: Simpler but wasteful for large files
- Direct container reading: Whisper doesn't support container formats natively
- PyAV/moviepy: Additional dependencies, less control over output format

**Implementation Notes**:
```python
# Stream audio from track to Whisper format
def extract_audio_stream(file_path: Path, track_index: int) -> bytes:
    cmd = [
        "ffmpeg", "-i", str(file_path),
        "-map", f"0:{track_index}",
        "-ac", "1",           # Mono
        "-ar", "16000",       # 16kHz (Whisper native)
        "-f", "wav",          # WAV format
        "-t", "60",           # Sample 60 seconds (configurable)
        "pipe:1"              # Output to stdout
    ]
    result = subprocess.run(cmd, capture_output=True, check=True)
    return result.stdout
```

### 3. Language Detection Confidence Scoring

**Decision**: Use Whisper's built-in language probability as confidence score

**Rationale**:
- Whisper returns language probabilities for 99 languages
- The highest probability is a natural confidence score (0.0-1.0)
- No additional processing needed; direct mapping to spec requirements
- Threshold-based decisions (e.g., 0.8 default) are straightforward

**Alternatives Considered**:
- Custom confidence calculation: Unnecessary complexity
- Multiple-model consensus: Performance cost, diminishing returns
- Transcript quality metrics: Requires full transcription, slow

**Implementation Notes**:
```python
# Whisper language detection returns dict of language -> probability
audio = whisper.load_audio(audio_path)
mel = whisper.log_mel_spectrogram(audio).to(model.device)
_, probs = model.detect_language(mel)

# Get top language and confidence
detected_lang = max(probs, key=probs.get)
confidence = probs[detected_lang]
```

### 4. Commentary Detection Heuristics

**Decision**: Two-tier detection: metadata keywords first, transcript keywords as fallback

**Rationale**:
- Metadata detection is fast and doesn't require transcription
- Most commentary tracks are labeled in track title/name
- Transcript-based detection is expensive but catches unlabeled commentary
- Keyword lists are configurable to handle different languages/conventions

**Alternatives Considered**:
- Transcript-only detection: Slow and wasteful if metadata is available
- ML-based classification: Overkill for this use case, training data scarce
- Audio analysis (speech patterns): Unreliable, high false positive rate

**Metadata Keywords** (case-insensitive):
```python
COMMENTARY_KEYWORDS = [
    "commentary", "director", "cast", "crew", "behind the scenes",
    "making of", "bts", "isolated", "alternate", "composer"
]
```

**Transcript Keywords** (if transcription enabled):
```python
COMMENTARY_TRANSCRIPT_PATTERNS = [
    r"we (decided|wanted|tried) to",
    r"during (filming|production|shooting)",
    r"this scene",
    r"on set",
    r"the director",
]
```

### 5. Database Schema for Transcription Results

**Decision**: New `transcription_results` table with foreign key to `tracks`

**Rationale**:
- One transcription result per track (unique constraint)
- Links to existing track via `track_id` foreign key
- Stores detected language, confidence, track type, timestamp
- Optional transcript sample for audit/debugging
- Follows existing schema patterns (files → tracks → transcription_results)

**Alternatives Considered**:
- JSON column in tracks table: Violates normalization, harder to query
- Separate database file: Unnecessary complexity
- In-memory cache only: Loses persistence requirement

**Schema**:
```sql
CREATE TABLE IF NOT EXISTS transcription_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL UNIQUE,
    detected_language TEXT,           -- ISO 639-1 code (e.g., "en", "fr")
    confidence_score REAL NOT NULL,   -- 0.0 to 1.0
    track_type TEXT NOT NULL DEFAULT 'main',  -- main, commentary, alternate
    transcript_sample TEXT,           -- Optional short sample
    plugin_name TEXT NOT NULL,        -- Which plugin produced result
    created_at TEXT NOT NULL,         -- ISO-8601 UTC
    updated_at TEXT NOT NULL,         -- ISO-8601 UTC
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transcription_track_id
    ON transcription_results(track_id);
CREATE INDEX IF NOT EXISTS idx_transcription_language
    ON transcription_results(detected_language);
```

### 6. TranscriptionPlugin Protocol Design

**Decision**: Follow existing `AnalyzerPlugin` pattern with transcription-specific methods

**Rationale**:
- Consistency with existing plugin architecture (Constitution XI)
- Protocol-based design allows duck typing and mock implementations
- Clear separation of capabilities (language detection vs full transcription)
- Matches existing patterns in `plugin/interfaces.py`

**Alternatives Considered**:
- ABC inheritance: Less flexible, requires explicit registration
- Function-based plugins: Loses type safety and discoverability
- Subprocess-based plugins: Unnecessary complexity for Python backends

**Protocol Definition**:
```python
@runtime_checkable
class TranscriptionPlugin(Protocol):
    """Protocol for transcription plugins."""

    name: str
    version: str

    def detect_language(
        self,
        audio_data: bytes,
        sample_rate: int = 16000
    ) -> TranscriptionResult:
        """Detect language from audio data."""
        ...

    def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str | None = None
    ) -> TranscriptionResult:
        """Full transcription with optional language hint."""
        ...

    def supports_feature(self, feature: str) -> bool:
        """Check if plugin supports a feature."""
        ...
```

### 7. Policy Integration

**Decision**: Add transcription policy options to existing `PolicySchema`

**Rationale**:
- Integrates naturally with existing policy workflow
- Users can combine transcription rules with other track rules
- Confidence threshold provides safety mechanism
- Commentary detection and reordering are opt-in

**New Policy Options**:
```yaml
audio:
  transcription:
    enabled: true                          # Enable transcription-based language detection
    update_language_from_transcription: true  # Actually update track language tags
    confidence_threshold: 0.8              # Minimum confidence to update
    detect_commentary: true                # Enable commentary detection
    reorder_commentary: true               # Move commentary tracks to end
```

### 8. Sampling Strategy for Long Audio

**Decision**: Sample first 60 seconds by default, configurable via config

**Rationale**:
- 60 seconds provides reliable language detection (Whisper documentation)
- Dramatically reduces processing time for feature-length audio
- Language typically consistent throughout a track
- Configurable for users who want higher accuracy

**Alternatives Considered**:
- Full track analysis: Too slow for large libraries
- Multiple samples (beginning, middle, end): Complexity with diminishing returns
- Dynamic sampling based on track length: Unpredictable performance

**Configuration**:
```yaml
transcription:
  sample_duration: 60  # seconds, 0 for full track
```

## Summary of Decisions

| Topic | Decision | Key Rationale |
|-------|----------|---------------|
| Whisper integration | `openai-whisper` with lazy loading | Official package, optional dependency |
| Audio extraction | ffmpeg pipe to stdout | No temp files, consistent with existing patterns |
| Confidence scoring | Whisper language probabilities | Built-in, direct mapping to spec |
| Commentary detection | Metadata first, transcript fallback | Fast path for common case |
| Database schema | New `transcription_results` table | Normalized, follows existing patterns |
| Plugin protocol | Protocol-based, similar to AnalyzerPlugin | Consistent architecture |
| Policy integration | New options in audio section | Natural extension |
| Sampling | 60 seconds default | Balance speed/accuracy |

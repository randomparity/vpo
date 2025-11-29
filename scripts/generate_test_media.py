#!/usr/bin/env python3
"""Test media file generation using ffmpeg.

This module provides utilities for generating test video files with specific
attributes (codec, resolution, audio tracks, subtitles) for integration testing.

Usage:
    # As a module in tests
    from scripts.generate_test_media import TestMediaGenerator, VideoSpec, SPECS

    generator = TestMediaGenerator()
    if generator.is_available:
        generator.generate(SPECS["basic_h264_stereo"], Path("/tmp/test.mkv"))

    # As CLI (for manual testing)
    python scripts/generate_test_media.py --spec basic_h264_stereo -o /tmp/out.mkv
    python scripts/generate_test_media.py --list  # List available specs
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 - subprocess is required for ffmpeg execution
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class AudioTrackSpec:
    """Specification for an audio track to generate.

    Attributes:
        codec: Audio codec (aac, ac3, flac, mp3).
        channels: Number of audio channels (1=mono, 2=stereo, 6=5.1).
        language: ISO 639-2/B language code (e.g., "eng", "jpn", "fra").
        title: Optional track title.
        is_default: Whether this track should be marked as default.
    """

    codec: Literal["aac", "ac3", "flac", "mp3"] = "aac"
    channels: int = 2
    language: str = "eng"
    title: str | None = None
    is_default: bool = False


@dataclass(frozen=True)
class SubtitleTrackSpec:
    """Specification for a subtitle track to generate.

    Attributes:
        language: ISO 639-2/B language code.
        title: Optional track title.
        is_default: Whether this track should be marked as default.
        is_forced: Whether this track should be marked as forced.
        content: SRT content for the subtitle file.
    """

    language: str = "eng"
    title: str | None = None
    is_default: bool = False
    is_forced: bool = False
    content: str = "1\n00:00:00,000 --> 00:00:01,000\nTest subtitle\n"


@dataclass(frozen=True)
class VideoSpec:
    """Complete specification for a test video file.

    Attributes:
        video_codec: Video codec (h264, hevc).
        width: Video width in pixels.
        height: Video height in pixels.
        duration_seconds: Duration of the video.
        frame_rate: Frame rate as string (e.g., "24", "30000/1001").
        video_bitrate: Optional target bitrate (e.g., "8M", "20M").
        audio_tracks: Tuple of audio track specifications.
        subtitle_tracks: Tuple of subtitle track specifications.
        container: Output container format.
    """

    video_codec: Literal["h264", "hevc"] = "h264"
    width: int = 1920
    height: int = 1080
    duration_seconds: float = 2.0
    frame_rate: str = "24"
    video_bitrate: str | None = None
    audio_tracks: tuple[AudioTrackSpec, ...] = field(
        default_factory=lambda: (AudioTrackSpec(),)
    )
    subtitle_tracks: tuple[SubtitleTrackSpec, ...] = ()
    container: Literal["mkv", "mp4"] = "mkv"


class TestMediaGenerator:
    """Generator for test media files using ffmpeg and mkvmerge.

    This class provides methods to generate video files with specific attributes
    for integration testing purposes. Files are generated using ffmpeg's test
    sources (testsrc for video, sine for audio).

    Example:
        generator = TestMediaGenerator()
        if generator.is_available:
            path = generator.generate(
                VideoSpec(video_codec="hevc", width=1920, height=1080),
                Path("/tmp/test.mkv")
            )
    """

    def __init__(
        self,
        ffmpeg_path: str | None = None,
        mkvmerge_path: str | None = None,
    ) -> None:
        """Initialize the generator.

        Args:
            ffmpeg_path: Optional explicit path to ffmpeg.
            mkvmerge_path: Optional explicit path to mkvmerge.
        """
        self._ffmpeg_path = (
            Path(ffmpeg_path) if ffmpeg_path else self._find_tool("ffmpeg")
        )
        self._mkvmerge_path = (
            Path(mkvmerge_path) if mkvmerge_path else self._find_tool("mkvmerge")
        )

    @staticmethod
    def _find_tool(name: str) -> Path | None:
        """Find a tool in system PATH."""
        result = shutil.which(name)
        return Path(result) if result else None

    @property
    def is_available(self) -> bool:
        """Check if ffmpeg is available for generation."""
        return self._ffmpeg_path is not None

    @property
    def has_mkvmerge(self) -> bool:
        """Check if mkvmerge is available for subtitle muxing."""
        return self._mkvmerge_path is not None

    def generate(self, spec: VideoSpec, output_path: Path) -> Path:
        """Generate a test video file from specification.

        Args:
            spec: Video specification defining the file attributes.
            output_path: Path where the file should be created.

        Returns:
            Path to the generated file.

        Raises:
            RuntimeError: If ffmpeg is not available or generation fails.
        """
        if not self.is_available:
            raise RuntimeError("ffmpeg is not available")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # If we have subtitles, generate to temp file first then mux
        if spec.subtitle_tracks:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Generate base video
                base_video = temp_path / "base_video.mkv"
                self._generate_base_video(spec, base_video)

                # Generate SRT files
                srt_files = []
                for i, sub_spec in enumerate(spec.subtitle_tracks):
                    srt_path = temp_path / f"subtitle_{i}.srt"
                    self._generate_srt_file(sub_spec, srt_path)
                    srt_files.append(srt_path)

                # Mux subtitles
                self._mux_subtitles(
                    base_video, srt_files, spec.subtitle_tracks, output_path
                )
        else:
            # No subtitles, generate directly
            self._generate_base_video(spec, output_path)

        return output_path

    def _generate_base_video(self, spec: VideoSpec, output_path: Path) -> None:
        """Generate the base video file without subtitles."""
        cmd = self._build_ffmpeg_command(spec, output_path)

        result = subprocess.run(  # nosec B603 - cmd is built from trusted spec
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    def _build_ffmpeg_command(self, spec: VideoSpec, output_path: Path) -> list[str]:
        """Build the ffmpeg command for generating a test file.

        Uses testsrc filter for video and sine filter for audio.
        """
        assert self._ffmpeg_path is not None

        cmd = [
            str(self._ffmpeg_path),
            "-y",  # Overwrite output
            "-hide_banner",
        ]

        # Video input: testsrc filter
        cmd.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"testsrc=duration={spec.duration_seconds}:size={spec.width}x{spec.height}:rate={spec.frame_rate}",
            ]
        )

        # Audio inputs: one sine source per track
        for i, audio in enumerate(spec.audio_tracks):
            # Different frequencies for each track to distinguish them
            frequency = 440 + (i * 220)  # 440Hz, 660Hz, 880Hz, etc.
            cmd.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"sine=frequency={frequency}:duration={spec.duration_seconds}:sample_rate=48000",
                ]
            )

        # Map video
        cmd.extend(["-map", "0:v"])

        # Map audio tracks
        for i in range(len(spec.audio_tracks)):
            cmd.extend(["-map", f"{i + 1}:a"])

        # Video codec settings
        video_encoder = "libx264" if spec.video_codec == "h264" else "libx265"
        cmd.extend(["-c:v", video_encoder, "-preset", "ultrafast"])

        if spec.video_bitrate:
            cmd.extend(["-b:v", spec.video_bitrate])
        else:
            cmd.extend(["-crf", "28"])  # Fast, small files

        # Audio codec settings for each track
        for i, audio in enumerate(spec.audio_tracks):
            cmd.extend([f"-c:a:{i}", self._get_audio_encoder(audio.codec)])

            # Set bitrate for lossy codecs
            if audio.codec in ("aac", "ac3", "mp3"):
                bitrate = "384k" if audio.channels > 2 else "128k"
                cmd.extend([f"-b:a:{i}", bitrate])

            # Set channels
            cmd.extend([f"-ac:{i}", str(audio.channels)])

            # Set metadata
            cmd.extend([f"-metadata:s:a:{i}", f"language={audio.language}"])
            if audio.title:
                cmd.extend([f"-metadata:s:a:{i}", f"title={audio.title}"])

            # Set disposition (default flag)
            disposition = "default" if audio.is_default else "0"
            cmd.extend([f"-disposition:a:{i}", disposition])

        # Output path
        cmd.append(str(output_path))

        return cmd

    @staticmethod
    def _get_audio_encoder(codec: str) -> str:
        """Get the ffmpeg encoder name for an audio codec."""
        return {
            "aac": "aac",
            "ac3": "ac3",
            "flac": "flac",
            "mp3": "libmp3lame",
        }[codec]

    def _generate_srt_file(self, spec: SubtitleTrackSpec, path: Path) -> None:
        """Generate an SRT subtitle file."""
        path.write_text(spec.content, encoding="utf-8")

    def _mux_subtitles(
        self,
        video_path: Path,
        srt_files: list[Path],
        subtitle_specs: tuple[SubtitleTrackSpec, ...],
        output_path: Path,
    ) -> None:
        """Mux subtitle files into the video using mkvmerge."""
        if not self.has_mkvmerge:
            raise RuntimeError("mkvmerge is not available for subtitle muxing")

        assert self._mkvmerge_path is not None

        cmd = [
            str(self._mkvmerge_path),
            "--output",
            str(output_path),
            str(video_path),
        ]

        for srt_path, sub_spec in zip(srt_files, subtitle_specs):
            cmd.extend(
                [
                    "--language",
                    f"0:{sub_spec.language}",
                ]
            )
            if sub_spec.title:
                cmd.extend(["--track-name", f"0:{sub_spec.title}"])
            if sub_spec.is_default:
                cmd.extend(["--default-track-flag", "0:1"])
            else:
                cmd.extend(["--default-track-flag", "0:0"])
            if sub_spec.is_forced:
                cmd.extend(["--forced-display-flag", "0:1"])
            cmd.append(str(srt_path))

        result = subprocess.run(  # nosec B603 - cmd is built from trusted spec
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # mkvmerge returns 0 for success, 1 for warnings, 2 for errors
        if result.returncode >= 2:
            raise RuntimeError(f"mkvmerge failed: {result.stderr}")


# =============================================================================
# Pre-defined Specifications
# =============================================================================

SPECS: dict[str, VideoSpec] = {
    # Tier 1: Basic smoke test files
    "basic_h264_stereo": VideoSpec(
        video_codec="h264",
        width=1280,
        height=720,
        audio_tracks=(
            AudioTrackSpec(codec="aac", channels=2, language="eng", is_default=True),
        ),
    ),
    "basic_hevc_1080p": VideoSpec(
        video_codec="hevc",
        width=1920,
        height=1080,
        audio_tracks=(
            AudioTrackSpec(codec="aac", channels=2, language="eng", is_default=True),
        ),
    ),
    "basic_mp4": VideoSpec(
        video_codec="h264",
        width=1280,
        height=720,
        container="mp4",
        audio_tracks=(
            AudioTrackSpec(codec="aac", channels=2, language="eng", is_default=True),
        ),
    ),
    # Tier 2: Multi-track files for filtering/reordering tests
    "multi_audio": VideoSpec(
        video_codec="h264",
        width=1280,
        height=720,
        audio_tracks=(
            AudioTrackSpec(
                codec="aac",
                channels=6,
                language="eng",
                title="English 5.1",
                is_default=True,
            ),
            AudioTrackSpec(
                codec="ac3", channels=2, language="jpn", title="Japanese Stereo"
            ),
            AudioTrackSpec(
                codec="aac", channels=2, language="fra", title="French Stereo"
            ),
        ),
    ),
    "multi_subtitle": VideoSpec(
        video_codec="h264",
        width=1280,
        height=720,
        audio_tracks=(
            AudioTrackSpec(codec="aac", channels=2, language="eng", is_default=True),
        ),
        subtitle_tracks=(
            SubtitleTrackSpec(language="eng", title="English", is_default=True),
            SubtitleTrackSpec(language="jpn", title="Japanese"),
            SubtitleTrackSpec(language="eng", title="English (Forced)", is_forced=True),
        ),
    ),
    "commentary": VideoSpec(
        video_codec="h264",
        width=1280,
        height=720,
        audio_tracks=(
            AudioTrackSpec(
                codec="aac",
                channels=2,
                language="eng",
                title="English Stereo",
                is_default=True,
            ),
            AudioTrackSpec(
                codec="aac", channels=2, language="eng", title="Director's Commentary"
            ),
        ),
    ),
    "lossless_audio": VideoSpec(
        video_codec="hevc",
        width=1920,
        height=1080,
        audio_tracks=(
            AudioTrackSpec(
                codec="flac",
                channels=6,
                language="eng",
                title="English Lossless",
                is_default=True,
            ),
            AudioTrackSpec(
                codec="aac", channels=2, language="eng", title="English AAC"
            ),
        ),
    ),
    # Tier 3: Transcode skip condition test files
    "hevc_1080p_low_bitrate": VideoSpec(
        video_codec="hevc",
        width=1920,
        height=1080,
        video_bitrate="8M",  # Under 15M threshold
        audio_tracks=(
            AudioTrackSpec(codec="aac", channels=2, language="eng", is_default=True),
        ),
    ),
    "hevc_1080p_high_bitrate": VideoSpec(
        video_codec="hevc",
        width=1920,
        height=1080,
        video_bitrate="20M",  # Over 15M threshold
        audio_tracks=(
            AudioTrackSpec(codec="aac", channels=2, language="eng", is_default=True),
        ),
    ),
    "hevc_4k": VideoSpec(
        video_codec="hevc",
        width=3840,
        height=2160,
        audio_tracks=(
            AudioTrackSpec(codec="aac", channels=2, language="eng", is_default=True),
        ),
    ),
    "h264_1080p": VideoSpec(
        video_codec="h264",
        width=1920,
        height=1080,
        audio_tracks=(
            AudioTrackSpec(codec="aac", channels=2, language="eng", is_default=True),
        ),
    ),
    # Tier 4: Edge case test files
    "no_audio": VideoSpec(
        video_codec="h264",
        width=1280,
        height=720,
        audio_tracks=(),  # No audio
    ),
    "und_language": VideoSpec(
        video_codec="h264",
        width=1280,
        height=720,
        audio_tracks=(
            AudioTrackSpec(codec="aac", channels=2, language="und", is_default=True),
        ),
    ),
}


# =============================================================================
# CLI Interface
# =============================================================================


def main() -> None:
    """Command-line interface for test media generation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate test video files for integration testing"
    )
    parser.add_argument(
        "--spec",
        choices=list(SPECS.keys()),
        help="Pre-defined specification to use",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available specifications",
    )

    args = parser.parse_args()

    if args.list:
        print("Available specifications:")
        for name, spec in SPECS.items():
            print(f"  {name}:")
            print(f"    Video: {spec.video_codec} {spec.width}x{spec.height}")
            print(f"    Audio: {len(spec.audio_tracks)} track(s)")
            print(f"    Subs:  {len(spec.subtitle_tracks)} track(s)")
            print()
        return

    if not args.spec or not args.output:
        parser.error("--spec and --output are required (unless using --list)")

    generator = TestMediaGenerator()
    if not generator.is_available:
        print("Error: ffmpeg is not available")
        raise SystemExit(1)

    spec = SPECS[args.spec]
    print(f"Generating {args.spec} -> {args.output}")
    generator.generate(spec, args.output)
    print("Done!")


if __name__ == "__main__":
    main()

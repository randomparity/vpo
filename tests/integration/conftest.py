"""Integration test fixtures for policy module with real video files.

This module provides pytest fixtures for:
- Tool availability detection (ffmpeg, ffprobe, mkvpropedit, mkvmerge)
- Test media generation using ffmpeg
- Pre-generated video file fixtures
- Factory fixtures for custom video generation
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# Add scripts directory to path for importing generator
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from generate_test_media import SPECS, TestMediaGenerator, VideoSpec  # noqa: E402

if TYPE_CHECKING:
    from _pytest.config import Config


# =============================================================================
# Tool Availability Fixtures
# =============================================================================


def _tool_available(name: str) -> bool:
    """Check if an external tool is available in PATH."""
    return shutil.which(name) is not None


@pytest.fixture(scope="session")
def ffmpeg_available() -> bool:
    """Check if ffmpeg is available."""
    return _tool_available("ffmpeg")


@pytest.fixture(scope="session")
def ffprobe_available() -> bool:
    """Check if ffprobe is available."""
    return _tool_available("ffprobe")


@pytest.fixture(scope="session")
def mkvpropedit_available() -> bool:
    """Check if mkvpropedit is available."""
    return _tool_available("mkvpropedit")


@pytest.fixture(scope="session")
def mkvmerge_available() -> bool:
    """Check if mkvmerge is available."""
    return _tool_available("mkvmerge")


# =============================================================================
# Custom Pytest Markers
# =============================================================================


def pytest_configure(config: Config) -> None:
    """Register custom markers for tool requirements."""
    config.addinivalue_line(
        "markers",
        "requires_ffmpeg: mark test as requiring ffmpeg",
    )
    config.addinivalue_line(
        "markers",
        "requires_ffprobe: mark test as requiring ffprobe",
    )
    config.addinivalue_line(
        "markers",
        "requires_mkvtools: mark test as requiring mkvpropedit and mkvmerge",
    )
    config.addinivalue_line(
        "markers",
        "requires_all_tools: mark test as requiring ffmpeg, ffprobe, and mkvtools",
    )


# =============================================================================
# Generator Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def test_media_generator(ffmpeg_available: bool) -> TestMediaGenerator | None:
    """Provide a test media generator instance.

    Returns None if ffmpeg is not available.
    """
    if not ffmpeg_available:
        return None
    return TestMediaGenerator()


# =============================================================================
# Pre-generated Video Fixtures (Module Scope)
# =============================================================================


@pytest.fixture(scope="module")
def generated_basic_h264(
    test_media_generator: TestMediaGenerator | None,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path | None:
    """Generate a basic H.264 720p test file.

    Returns None if generation tools unavailable.
    """
    if test_media_generator is None:
        return None

    output_dir = tmp_path_factory.mktemp("videos")
    output_path = output_dir / "basic_h264.mkv"
    return test_media_generator.generate(SPECS["basic_h264_stereo"], output_path)


@pytest.fixture(scope="module")
def generated_basic_hevc(
    test_media_generator: TestMediaGenerator | None,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path | None:
    """Generate a basic HEVC 1080p test file."""
    if test_media_generator is None:
        return None

    output_dir = tmp_path_factory.mktemp("videos")
    output_path = output_dir / "basic_hevc.mkv"
    return test_media_generator.generate(SPECS["basic_hevc_1080p"], output_path)


@pytest.fixture(scope="module")
def generated_multi_audio(
    test_media_generator: TestMediaGenerator | None,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path | None:
    """Generate a file with multiple audio tracks."""
    if test_media_generator is None:
        return None

    output_dir = tmp_path_factory.mktemp("videos")
    output_path = output_dir / "multi_audio.mkv"
    return test_media_generator.generate(SPECS["multi_audio"], output_path)


@pytest.fixture(scope="module")
def generated_multi_subtitle(
    test_media_generator: TestMediaGenerator | None,
    mkvmerge_available: bool,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path | None:
    """Generate a file with multiple subtitle tracks."""
    if test_media_generator is None or not mkvmerge_available:
        return None

    output_dir = tmp_path_factory.mktemp("videos")
    output_path = output_dir / "multi_subtitle.mkv"
    return test_media_generator.generate(SPECS["multi_subtitle"], output_path)


@pytest.fixture(scope="module")
def generated_commentary(
    test_media_generator: TestMediaGenerator | None,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path | None:
    """Generate a file with commentary audio track."""
    if test_media_generator is None:
        return None

    output_dir = tmp_path_factory.mktemp("videos")
    output_path = output_dir / "commentary.mkv"
    return test_media_generator.generate(SPECS["commentary"], output_path)


@pytest.fixture(scope="module")
def generated_lossless_audio(
    test_media_generator: TestMediaGenerator | None,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path | None:
    """Generate a file with lossless (FLAC) audio."""
    if test_media_generator is None:
        return None

    output_dir = tmp_path_factory.mktemp("videos")
    output_path = output_dir / "lossless_audio.mkv"
    return test_media_generator.generate(SPECS["lossless_audio"], output_path)


@pytest.fixture(scope="module")
def generated_hevc_low_bitrate(
    test_media_generator: TestMediaGenerator | None,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path | None:
    """Generate a HEVC file with low bitrate (for skip condition testing)."""
    if test_media_generator is None:
        return None

    output_dir = tmp_path_factory.mktemp("videos")
    output_path = output_dir / "hevc_low_bitrate.mkv"
    return test_media_generator.generate(SPECS["hevc_1080p_low_bitrate"], output_path)


@pytest.fixture(scope="module")
def generated_hevc_high_bitrate(
    test_media_generator: TestMediaGenerator | None,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path | None:
    """Generate a HEVC file with high bitrate (for skip condition testing)."""
    if test_media_generator is None:
        return None

    output_dir = tmp_path_factory.mktemp("videos")
    output_path = output_dir / "hevc_high_bitrate.mkv"
    return test_media_generator.generate(SPECS["hevc_1080p_high_bitrate"], output_path)


@pytest.fixture(scope="module")
def generated_hevc_4k(
    test_media_generator: TestMediaGenerator | None,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path | None:
    """Generate a 4K HEVC file (for scaling tests)."""
    if test_media_generator is None:
        return None

    output_dir = tmp_path_factory.mktemp("videos")
    output_path = output_dir / "hevc_4k.mkv"
    return test_media_generator.generate(SPECS["hevc_4k"], output_path)


@pytest.fixture(scope="module")
def generated_h264_1080p(
    test_media_generator: TestMediaGenerator | None,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path | None:
    """Generate an H.264 1080p file (for codec mismatch tests)."""
    if test_media_generator is None:
        return None

    output_dir = tmp_path_factory.mktemp("videos")
    output_path = output_dir / "h264_1080p.mkv"
    return test_media_generator.generate(SPECS["h264_1080p"], output_path)


# =============================================================================
# Factory Fixture for Custom Specs
# =============================================================================


@pytest.fixture
def generate_video(
    test_media_generator: TestMediaGenerator | None,
    tmp_path: Path,
) -> Callable[[VideoSpec, str], Path | None]:
    """Factory fixture for generating videos with custom specs.

    Returns a callable that can generate videos on demand.
    Skips the test if ffmpeg is not available.

    Usage:
        def test_custom_video(generate_video):
            video_path = generate_video(
                VideoSpec(video_codec="hevc", width=1280, height=720),
                "custom.mkv"
            )
            assert video_path.exists()
    """

    def _generate(spec: VideoSpec, filename: str) -> Path | None:
        if test_media_generator is None:
            pytest.skip("ffmpeg not available")
        output_path = tmp_path / filename
        return test_media_generator.generate(spec, output_path)

    return _generate


# =============================================================================
# Helper Fixtures
# =============================================================================


@pytest.fixture
def skip_without_ffmpeg(ffmpeg_available: bool) -> None:
    """Skip test if ffmpeg is not available."""
    if not ffmpeg_available:
        pytest.skip("ffmpeg not available")


@pytest.fixture
def skip_without_ffprobe(ffprobe_available: bool) -> None:
    """Skip test if ffprobe is not available."""
    if not ffprobe_available:
        pytest.skip("ffprobe not available")


@pytest.fixture
def skip_without_mkvtools(
    mkvpropedit_available: bool,
    mkvmerge_available: bool,
) -> None:
    """Skip test if mkvpropedit or mkvmerge is not available."""
    if not mkvpropedit_available:
        pytest.skip("mkvpropedit not available")
    if not mkvmerge_available:
        pytest.skip("mkvmerge not available")


@pytest.fixture
def skip_without_all_tools(
    ffmpeg_available: bool,
    ffprobe_available: bool,
    mkvpropedit_available: bool,
    mkvmerge_available: bool,
) -> None:
    """Skip test if any required tool is not available."""
    if not ffmpeg_available:
        pytest.skip("ffmpeg not available")
    if not ffprobe_available:
        pytest.skip("ffprobe not available")
    if not mkvpropedit_available:
        pytest.skip("mkvpropedit not available")
    if not mkvmerge_available:
        pytest.skip("mkvmerge not available")

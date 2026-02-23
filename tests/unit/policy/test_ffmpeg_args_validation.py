"""Tests for ffmpeg_args validation in VideoTranscodeConfigModel."""

import pytest
from pydantic import ValidationError

from vpo.policy.pydantic_models.transcode import (
    MAX_FFMPEG_ARG_LENGTH,
    MAX_FFMPEG_ARGS_COUNT,
    VideoTranscodeConfigModel,
)


class TestFfmpegArgsValidation:
    """Tests for ffmpeg_args field validation."""

    def test_valid_args_pass(self):
        """Valid FFmpeg arguments are accepted."""
        expected_args = ["-max_muxing_queue_size", "9999", "-preset", "slow"]
        model = VideoTranscodeConfigModel(
            to="hevc",
            ffmpeg_args=expected_args,
        )
        assert model.ffmpeg_args == expected_args

    def test_none_args_pass(self):
        """None ffmpeg_args is accepted."""
        model = VideoTranscodeConfigModel(
            to="hevc",
            ffmpeg_args=None,
        )
        assert model.ffmpeg_args is None

    def test_empty_list_pass(self):
        """Empty list is accepted."""
        model = VideoTranscodeConfigModel(
            to="hevc",
            ffmpeg_args=[],
        )
        assert model.ffmpeg_args == []

    @pytest.mark.parametrize(
        "pattern",
        [
            ";",
            "|",
            "&",
            "$(",
            "`",
            "${",
            ">",
            "<",
            "\\n",
            "\n",
        ],
    )
    def test_forbidden_pattern_rejected(self, pattern: str):
        """Each forbidden shell metacharacter is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VideoTranscodeConfigModel(
                to="hevc",
                ffmpeg_args=[f"-flag{pattern}value"],
            )
        assert "forbidden character" in str(exc_info.value).lower()

    def test_semicolon_in_arg_rejected(self):
        """Semicolon (command separator) is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VideoTranscodeConfigModel(
                to="hevc",
                ffmpeg_args=["-preset", "slow; rm -rf /"],
            )
        assert "forbidden character" in str(exc_info.value).lower()

    def test_pipe_in_arg_rejected(self):
        """Pipe character is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VideoTranscodeConfigModel(
                to="hevc",
                ffmpeg_args=["-vf", "scale=1920:1080|crop=100:100"],
            )
        assert "forbidden character" in str(exc_info.value).lower()

    def test_command_substitution_rejected(self):
        """Command substitution $() is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VideoTranscodeConfigModel(
                to="hevc",
                ffmpeg_args=["-metadata", "title=$(whoami)"],
            )
        assert "forbidden character" in str(exc_info.value).lower()

    def test_backtick_rejected(self):
        """Backtick command substitution is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VideoTranscodeConfigModel(
                to="hevc",
                ffmpeg_args=["-metadata", "title=`whoami`"],
            )
        assert "forbidden character" in str(exc_info.value).lower()

    def test_count_limit_exceeded(self):
        """Argument count exceeding limit is rejected."""
        too_many_args = ["-flag"] * (MAX_FFMPEG_ARGS_COUNT + 1)
        with pytest.raises(ValidationError) as exc_info:
            VideoTranscodeConfigModel(
                to="hevc",
                ffmpeg_args=too_many_args,
            )
        assert "count exceeds limit" in str(exc_info.value).lower()

    def test_count_at_limit_passes(self):
        """Argument count at exactly the limit is accepted."""
        args_at_limit = ["-flag"] * MAX_FFMPEG_ARGS_COUNT
        model = VideoTranscodeConfigModel(
            to="hevc",
            ffmpeg_args=args_at_limit,
        )
        assert len(model.ffmpeg_args) == MAX_FFMPEG_ARGS_COUNT

    def test_length_limit_exceeded(self):
        """Individual argument exceeding length limit is rejected."""
        long_arg = "x" * (MAX_FFMPEG_ARG_LENGTH + 1)
        with pytest.raises(ValidationError) as exc_info:
            VideoTranscodeConfigModel(
                to="hevc",
                ffmpeg_args=[long_arg],
            )
        assert "length limit" in str(exc_info.value).lower()

    def test_length_at_limit_passes(self):
        """Argument at exactly the length limit is accepted."""
        arg_at_limit = "x" * MAX_FFMPEG_ARG_LENGTH
        model = VideoTranscodeConfigModel(
            to="hevc",
            ffmpeg_args=[arg_at_limit],
        )
        assert len(model.ffmpeg_args[0]) == MAX_FFMPEG_ARG_LENGTH

    def test_non_string_arg_rejected(self):
        """Non-string arguments are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VideoTranscodeConfigModel(
                to="hevc",
                ffmpeg_args=["-preset", 123],  # type: ignore
            )
        # Pydantic catches this as a type error before our validator runs
        assert "string" in str(exc_info.value).lower()

    def test_multiple_valid_args(self):
        """Multiple valid arguments work correctly."""
        model = VideoTranscodeConfigModel(
            to="hevc",
            ffmpeg_args=[
                "-max_muxing_queue_size",
                "9999",
                "-movflags",
                "+faststart",
                "-threads",
                "4",
            ],
        )
        assert len(model.ffmpeg_args) == 6

    def test_redirect_operators_rejected(self):
        """Redirect operators > and < are rejected."""
        with pytest.raises(ValidationError):
            VideoTranscodeConfigModel(
                to="hevc",
                ffmpeg_args=["-y", "> /tmp/output.txt"],
            )

        with pytest.raises(ValidationError):
            VideoTranscodeConfigModel(
                to="hevc",
                ffmpeg_args=["< /etc/passwd"],
            )

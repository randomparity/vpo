"""Video transcode decision logic.

This module determines whether video transcoding is needed based on codec,
resolution, and policy settings.
"""

import logging

from vpo.core.codecs import video_codec_matches
from vpo.policy.types import TranscodePolicyConfig

logger = logging.getLogger(__name__)


def should_transcode_video(
    policy: TranscodePolicyConfig,
    current_codec: str | None,
    current_width: int | None,
    current_height: int | None,
) -> tuple[bool, bool, int | None, int | None]:
    """Determine if video transcoding is needed.

    Args:
        policy: Transcode policy configuration.
        current_codec: Current video codec (from ffprobe).
        current_width: Current video width.
        current_height: Current video height.

    Returns:
        Tuple of (needs_transcode, needs_scale, target_width, target_height).
    """
    needs_transcode = False
    needs_scale = False
    target_width = None
    target_height = None

    # Check codec compliance using centralized alias matching
    if policy.target_video_codec:
        target_codec = policy.target_video_codec.casefold()
        if current_codec and not video_codec_matches(current_codec, target_codec):
            needs_transcode = True
            logger.debug(
                "Video transcode needed: %s -> %s", current_codec, target_codec
            )

    # Check resolution limits
    max_dims = policy.get_max_dimensions()
    if max_dims and current_width and current_height:
        max_width, max_height = max_dims
        if current_width > max_width or current_height > max_height:
            needs_scale = True
            # Calculate target dimensions maintaining aspect ratio
            width_ratio = max_width / current_width
            height_ratio = max_height / current_height
            scale_ratio = min(width_ratio, height_ratio)

            target_width = int(current_width * scale_ratio)
            target_height = int(current_height * scale_ratio)

            # Ensure even dimensions (required by most codecs)
            target_width = target_width - (target_width % 2)
            target_height = target_height - (target_height % 2)

            logger.debug(
                "Video scale needed: %dx%d -> %dx%d",
                current_width,
                current_height,
                target_width,
                target_height,
            )

    # If we need to scale, we also need to transcode
    if needs_scale:
        needs_transcode = True

    return needs_transcode, needs_scale, target_width, target_height

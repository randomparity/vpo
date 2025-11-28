"""CLI commands for video transcoding."""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import click

from video_policy_orchestrator.db.models import (
    Job,
    JobStatus,
    JobType,
    get_file_by_path,
    insert_job,
)
from video_policy_orchestrator.executor.transcode import (
    should_transcode_video,
)
from video_policy_orchestrator.introspector import FFprobeIntrospector
from video_policy_orchestrator.metadata.parser import parse_filename
from video_policy_orchestrator.metadata.templates import parse_template
from video_policy_orchestrator.policy.loader import load_policy
from video_policy_orchestrator.policy.models import TranscodePolicyConfig

logger = logging.getLogger(__name__)

# Video file extensions
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}


def _discover_files(paths: tuple[Path, ...], recursive: bool) -> list[Path]:
    """Discover video files from paths.

    Args:
        paths: Paths to files or directories.
        recursive: Whether to search directories recursively.

    Returns:
        List of video file paths.
    """
    files = []
    for path in paths:
        if path.is_file():
            if path.suffix.lower() in VIDEO_EXTENSIONS:
                files.append(path)
        elif path.is_dir():
            if recursive:
                for video_path in path.rglob("*"):
                    if video_path.suffix.lower() in VIDEO_EXTENSIONS:
                        files.append(video_path)
            else:
                for video_path in path.iterdir():
                    if (
                        video_path.is_file()
                        and video_path.suffix.lower() in VIDEO_EXTENSIONS
                    ):
                        files.append(video_path)
    return sorted(set(files))


def _build_policy_from_options(
    policy: TranscodePolicyConfig | None,
    codec: str | None,
    crf: int | None,
    bitrate: str | None,
    max_resolution: str | None,
) -> TranscodePolicyConfig:
    """Build policy from CLI options, merging with policy file if provided.

    Args:
        policy: Base policy from file (optional).
        codec: Override video codec.
        crf: Override CRF value.
        bitrate: Override bitrate.
        max_resolution: Override max resolution.

    Returns:
        Merged TranscodePolicyConfig.
    """
    if policy is None:
        policy = TranscodePolicyConfig()

    # Apply CLI overrides
    overrides = {}
    if codec:
        overrides["target_video_codec"] = codec
    if crf is not None:
        overrides["target_crf"] = crf
    if bitrate:
        overrides["target_bitrate"] = bitrate
    if max_resolution:
        overrides["max_resolution"] = max_resolution

    if overrides:
        # Create new config with overrides
        return TranscodePolicyConfig(
            target_video_codec=overrides.get(
                "target_video_codec", policy.target_video_codec
            ),
            target_crf=overrides.get("target_crf", policy.target_crf),
            target_bitrate=overrides.get("target_bitrate", policy.target_bitrate),
            max_resolution=overrides.get("max_resolution", policy.max_resolution),
            max_width=policy.max_width,
            max_height=policy.max_height,
            audio_preserve_codecs=policy.audio_preserve_codecs,
            audio_transcode_to=policy.audio_transcode_to,
            audio_transcode_bitrate=policy.audio_transcode_bitrate,
            audio_downmix=policy.audio_downmix,
            destination=policy.destination,
            destination_fallback=policy.destination_fallback,
        )

    return policy


@click.command("transcode")
@click.argument(
    "paths", nargs=-1, type=click.Path(exists=True, path_type=Path), required=True
)
@click.option(
    "--policy",
    "-p",
    "policy_path",
    type=click.Path(exists=True, path_type=Path),
    help="Path to policy YAML file with transcode settings.",
)
@click.option(
    "--codec",
    "-c",
    type=click.Choice(["hevc", "h264", "vp9", "av1"], case_sensitive=False),
    help="Target video codec (overrides policy).",
)
@click.option(
    "--crf",
    type=click.IntRange(0, 51),
    help="Target CRF quality (0-51, lower=better). Overrides policy.",
)
@click.option(
    "--bitrate",
    "-b",
    help="Target bitrate (e.g., '5M', '2500k'). Overrides policy.",
)
@click.option(
    "--max-resolution",
    "-r",
    type=click.Choice(
        ["480p", "720p", "1080p", "1440p", "4k", "8k"], case_sensitive=False
    ),
    help="Maximum resolution (scales down if larger). Overrides policy.",
)
@click.option(
    "--recursive",
    "-R",
    is_flag=True,
    help="Process directories recursively.",
)
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    help="Show what would be done without making changes.",
)
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(path_type=Path),
    help="Output directory for transcoded files. Defaults to same directory.",
)
@click.pass_context
def transcode_command(
    ctx: click.Context,
    paths: tuple[Path, ...],
    policy_path: Path | None,
    codec: str | None,
    crf: int | None,
    bitrate: str | None,
    max_resolution: str | None,
    recursive: bool,
    dry_run: bool,
    output_dir: Path | None,
) -> None:
    """Queue files for transcoding.

    Files are added to the job queue and processed by `vpo jobs start`.
    Use --dry-run to preview what would be done.

    Examples:

        # Queue single file with policy
        vpo transcode --policy hevc.yaml movie.mkv

        # Queue with inline settings
        vpo transcode --codec hevc --crf 20 movie.mkv

        # Queue directory recursively
        vpo transcode --policy hevc.yaml --recursive /videos/

        # Preview without queueing
        vpo transcode --dry-run --codec hevc movie.mkv
    """
    conn = ctx.obj.get("db_conn")
    if conn is None:
        raise click.ClickException("Failed to connect to database.")

    # Load policy if provided
    transcode_policy: TranscodePolicyConfig | None = None
    policy_name: str | None = None
    if policy_path:
        try:
            schema = load_policy(policy_path)
            transcode_policy = schema.transcode
            policy_name = policy_path.name
            if transcode_policy is None:
                raise click.ClickException(
                    f"Policy file has no transcode settings: {policy_path}"
                )
        except Exception as e:
            raise click.ClickException(f"Failed to load policy: {e}")

    # Build final policy from options
    final_policy = _build_policy_from_options(
        transcode_policy, codec, crf, bitrate, max_resolution
    )

    # Validate we have some transcode settings
    if not final_policy.has_video_settings:
        raise click.ClickException(
            "No transcode settings specified. Use --policy or --codec/--crf/--bitrate."
        )

    # Discover files
    files = _discover_files(paths, recursive)
    if not files:
        click.echo("No video files found.")
        return

    click.echo(f"Found {len(files)} video file(s)")

    # Get introspector for file analysis
    introspector = FFprobeIntrospector()

    # Process each file
    queued = 0
    skipped = 0
    errors = 0

    for file_path in files:
        try:
            # Introspect file
            result = introspector.get_file_info(file_path)
            if not result.success:
                click.echo(f"  [ERROR] {file_path.name}: {result.error}")
                errors += 1
                continue

            # Get video track info
            video_track = next(
                (t for t in result.tracks if t.track_type == "video"), None
            )
            if not video_track:
                click.echo(f"  [SKIP] {file_path.name}: No video track")
                skipped += 1
                continue

            # Check if transcode needed
            needs_transcode, needs_scale, target_w, target_h = should_transcode_video(
                final_policy,
                video_track.codec,
                video_track.width,
                video_track.height,
            )

            if not needs_transcode:
                click.echo(f"  [SKIP] {file_path.name}: Already compliant")
                skipped += 1
                continue

            if dry_run:
                # Show what would be done
                actions = []
                if final_policy.target_video_codec:
                    actions.append(
                        f"{video_track.codec} -> {final_policy.target_video_codec}"
                    )
                if needs_scale:
                    src = f"{video_track.width}x{video_track.height}"
                    dst = f"{target_w}x{target_h}"
                    actions.append(f"{src} -> {dst}")
                click.echo(f"  [QUEUE] {file_path.name}: {', '.join(actions)}")

                # Show destination if configured
                if final_policy.destination:
                    metadata = parse_filename(file_path)
                    metadata_dict = metadata.as_dict()
                    template = parse_template(final_policy.destination)
                    fallback = final_policy.destination_fallback or "Unknown"
                    base_dir = output_dir or file_path.parent
                    dest = template.render_path(base_dir, metadata_dict, fallback)
                    click.echo(f"          Destination: {dest}/")

                queued += 1
            else:
                # Queue the job
                # Look up or create file record
                file_record = get_file_by_path(conn, str(file_path.resolve()))
                # file_id is None if file not scanned yet - job uses file_path
                file_id = file_record.id if file_record else None

                # Create job
                job = Job(
                    id=str(uuid.uuid4()),
                    file_id=file_id,
                    file_path=str(file_path.resolve()),
                    job_type=JobType.TRANSCODE,
                    status=JobStatus.QUEUED,
                    priority=100,
                    policy_name=policy_name,
                    policy_json=json.dumps(
                        {
                            "target_video_codec": final_policy.target_video_codec,
                            "target_crf": final_policy.target_crf,
                            "target_bitrate": final_policy.target_bitrate,
                            "max_resolution": final_policy.max_resolution,
                            "max_width": final_policy.max_width,
                            "max_height": final_policy.max_height,
                            "audio_preserve_codecs": list(
                                final_policy.audio_preserve_codecs
                            ),
                            "audio_transcode_to": final_policy.audio_transcode_to,
                            "audio_bitrate": final_policy.audio_transcode_bitrate,
                            "audio_downmix": final_policy.audio_downmix,
                            "output_dir": str(output_dir) if output_dir else None,
                            "destination": final_policy.destination,
                            "destination_base": str(output_dir) if output_dir else None,
                            "destination_fallback": final_policy.destination_fallback,
                        }
                    ),
                    progress_percent=0.0,
                    progress_json=None,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                insert_job(conn, job)

                actions = []
                if final_policy.target_video_codec:
                    actions.append(
                        f"{video_track.codec} -> {final_policy.target_video_codec}"
                    )
                if needs_scale:
                    src = f"{video_track.width}x{video_track.height}"
                    dst = f"{target_w}x{target_h}"
                    actions.append(f"{src} -> {dst}")
                click.echo(f"  [QUEUED] {file_path.name}: {', '.join(actions)}")
                queued += 1

        except Exception as e:
            click.echo(f"  [ERROR] {file_path.name}: {e}")
            errors += 1
            continue

    # Summary
    click.echo()
    if dry_run:
        msg = f"Dry run complete: {queued} would be queued, "
        msg += f"{skipped} skipped, {errors} errors"
        click.echo(msg)
    else:
        click.echo(f"Queued {queued} job(s), {skipped} skipped, {errors} errors")
        if queued > 0:
            click.echo("Run 'vpo jobs start' to process the queue.")

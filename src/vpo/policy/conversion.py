"""Conversion functions from Pydantic models to frozen dataclasses.

This module contains all _convert_*() functions that transform validated
Pydantic models into the frozen dataclasses defined in types.py.
"""

from vpo.policy.pydantic_models import (
    ActionModel,
    AudioIsMultiLanguageModel,
    AudioSynthesisModel,
    AudioTranscodeConfigModel,
    ChannelPreferenceModel,
    ComparisonModel,
    ConditionalRuleModel,
    ConditionModel,
    ContainerMetadataConditionModel,
    CountConditionModel,
    ExistsConditionModel,
    HardwareAccelConfigModel,
    IsDubbedConditionModel,
    IsOriginalConditionModel,
    PhaseModel,
    PluginMetadataConditionModel,
    PolicyModel,
    PreferenceCriterionModel,
    QualitySettingsModel,
    ScalingSettingsModel,
    SkipConditionModel,
    SkipIfExistsModel,
    SynthesisTrackDefinitionModel,
    TitleMatchModel,
    VideoTranscodeConfigModel,
)
from vpo.policy.types import (
    AndCondition,
    AttachmentFilterConfig,
    AudioActionsConfig,
    AudioFilterConfig,
    AudioIsMultiLanguageCondition,
    AudioSynthesisConfig,
    AudioTranscodeConfig,
    CodecTranscodeMapping,
    Comparison,
    ComparisonOperator,
    Condition,
    ConditionalAction,
    ConditionalRule,
    ContainerConfig,
    ContainerMetadataCondition,
    CountCondition,
    DefaultFlagsConfig,
    ExistsCondition,
    FailAction,
    FileTimestampConfig,
    GlobalConfig,
    HardwareAccelConfig,
    HardwareAccelMode,
    IsDubbedCondition,
    IsOriginalCondition,
    LanguageFallbackConfig,
    NotCondition,
    OnErrorMode,
    OrCondition,
    PhaseDefinition,
    PhaseSkipCondition,
    PluginMetadataCondition,
    PluginMetadataOperator,
    PluginMetadataReference,
    PolicySchema,
    QualityMode,
    QualitySettings,
    RunIfCondition,
    ScaleAlgorithm,
    ScalingSettings,
    SetContainerMetadataAction,
    SetDefaultAction,
    SetForcedAction,
    SetLanguageAction,
    SkipAction,
    SkipCondition,
    SkipIfExistsCriteria,
    SkipType,
    SubtitleActionsConfig,
    SubtitleFilterConfig,
    SynthesisTrackDefinitionRef,
    TitleMatch,
    TrackFilters,
    TrackType,
    TranscriptionPolicyOptions,
    VideoTranscodeConfig,
    WarnAction,
)

# Module-level constant for on_error mode conversion (used in multiple places)
_ON_ERROR_MAP = {
    "skip": OnErrorMode.SKIP,
    "continue": OnErrorMode.CONTINUE,
    "fail": OnErrorMode.FAIL,
}

# =============================================================================
# V4 Conversion Functions for Conditional Rules
# =============================================================================


def _convert_comparison(model: ComparisonModel) -> Comparison:
    """Convert ComparisonModel to Comparison dataclass."""
    op_map = {
        "eq": ComparisonOperator.EQ,
        "lt": ComparisonOperator.LT,
        "lte": ComparisonOperator.LTE,
        "gt": ComparisonOperator.GT,
        "gte": ComparisonOperator.GTE,
    }
    for op_name, op_enum in op_map.items():
        val = getattr(model, op_name)
        if val is not None:
            return Comparison(operator=op_enum, value=val)
    # Should never happen due to validation
    raise ValueError("No comparison operator found")


def _convert_title_match(model: TitleMatchModel) -> TitleMatch:
    """Convert TitleMatchModel to TitleMatch dataclass."""
    return TitleMatch(contains=model.contains, regex=model.regex)


def _convert_track_filters(
    *,
    language: str | list[str] | None = None,
    codec: str | list[str] | None = None,
    is_default: bool | None = None,
    is_forced: bool | None = None,
    channels: int | ComparisonModel | None = None,
    width: int | ComparisonModel | None = None,
    height: int | ComparisonModel | None = None,
    title: str | TitleMatchModel | None = None,
    not_commentary: bool | None = None,
) -> TrackFilters:
    """Convert filter fields to TrackFilters dataclass."""
    # Normalize language to tuple
    lang_tuple: str | tuple[str, ...] | None = None
    if language is not None:
        if isinstance(language, list):
            lang_tuple = tuple(language)
        else:
            lang_tuple = language

    # Normalize codec to tuple
    codec_tuple: str | tuple[str, ...] | None = None
    if codec is not None:
        if isinstance(codec, list):
            codec_tuple = tuple(codec)
        else:
            codec_tuple = codec

    # Convert channels comparison
    channels_val: int | Comparison | None = None
    if channels is not None:
        if isinstance(channels, ComparisonModel):
            channels_val = _convert_comparison(channels)
        else:
            channels_val = channels

    # Convert width comparison
    width_val: int | Comparison | None = None
    if width is not None:
        if isinstance(width, ComparisonModel):
            width_val = _convert_comparison(width)
        else:
            width_val = width

    # Convert height comparison
    height_val: int | Comparison | None = None
    if height is not None:
        if isinstance(height, ComparisonModel):
            height_val = _convert_comparison(height)
        else:
            height_val = height

    # Convert title match
    title_val: str | TitleMatch | None = None
    if title is not None:
        if isinstance(title, TitleMatchModel):
            title_val = _convert_title_match(title)
        else:
            title_val = title

    return TrackFilters(
        language=lang_tuple,
        codec=codec_tuple,
        is_default=is_default,
        is_forced=is_forced,
        channels=channels_val,
        width=width_val,
        height=height_val,
        title=title_val,
        not_commentary=not_commentary,
    )


def _convert_exists_condition(model: ExistsConditionModel) -> ExistsCondition:
    """Convert ExistsConditionModel to ExistsCondition dataclass."""
    filters = _convert_track_filters(
        language=model.language,
        codec=model.codec,
        is_default=model.is_default,
        is_forced=model.is_forced,
        channels=model.channels,
        width=model.width,
        height=model.height,
        title=model.title,
        not_commentary=model.not_commentary,
    )
    return ExistsCondition(track_type=model.track_type, filters=filters)


def _convert_count_condition(model: CountConditionModel) -> CountCondition:
    """Convert CountConditionModel to CountCondition dataclass."""
    filters = _convert_track_filters(
        language=model.language,
        codec=model.codec,
        is_default=model.is_default,
        is_forced=model.is_forced,
        channels=model.channels,
        width=model.width,
        height=model.height,
        title=model.title,
        not_commentary=model.not_commentary,
    )

    op_map = {
        "eq": ComparisonOperator.EQ,
        "lt": ComparisonOperator.LT,
        "lte": ComparisonOperator.LTE,
        "gt": ComparisonOperator.GT,
        "gte": ComparisonOperator.GTE,
    }
    for op_name, op_enum in op_map.items():
        val = getattr(model, op_name)
        if val is not None:
            return CountCondition(
                track_type=model.track_type,
                filters=filters,
                operator=op_enum,
                value=val,
            )

    # Should never happen due to validation
    raise ValueError("No count comparison operator found")


def _convert_audio_is_multi_language_condition(
    model: AudioIsMultiLanguageModel,
) -> AudioIsMultiLanguageCondition:
    """Convert AudioIsMultiLanguageModel to AudioIsMultiLanguageCondition."""
    return AudioIsMultiLanguageCondition(
        track_index=model.track_index,
        threshold=model.threshold,
        primary_language=model.primary_language,
    )


def _convert_plugin_metadata_condition(
    model: PluginMetadataConditionModel,
) -> PluginMetadataCondition:
    """Convert PluginMetadataConditionModel to PluginMetadataCondition."""
    # Convert operator string to enum
    op_map = {
        "eq": PluginMetadataOperator.EQ,
        "neq": PluginMetadataOperator.NEQ,
        "contains": PluginMetadataOperator.CONTAINS,
        "lt": PluginMetadataOperator.LT,
        "lte": PluginMetadataOperator.LTE,
        "gt": PluginMetadataOperator.GT,
        "gte": PluginMetadataOperator.GTE,
        "exists": PluginMetadataOperator.EXISTS,
    }
    return PluginMetadataCondition(
        plugin=model.plugin,
        field=model.field,
        value=model.value,
        operator=op_map[model.operator],
    )


def _convert_container_metadata_condition(
    model: ContainerMetadataConditionModel,
) -> ContainerMetadataCondition:
    """Convert ContainerMetadataConditionModel to ContainerMetadataCondition."""
    op_map = {
        "eq": PluginMetadataOperator.EQ,
        "neq": PluginMetadataOperator.NEQ,
        "contains": PluginMetadataOperator.CONTAINS,
        "lt": PluginMetadataOperator.LT,
        "lte": PluginMetadataOperator.LTE,
        "gt": PluginMetadataOperator.GT,
        "gte": PluginMetadataOperator.GTE,
        "exists": PluginMetadataOperator.EXISTS,
    }
    return ContainerMetadataCondition(
        field=model.field,
        value=model.value,
        operator=op_map[model.operator],
    )


def _convert_is_original_condition(
    model: IsOriginalConditionModel | bool,
) -> IsOriginalCondition:
    """Convert is_original Pydantic model to domain condition.

    Handles two forms:
    1. Simple boolean: is_original: true
    2. Full object: is_original: { value: true, min_confidence: 0.8 }
    """
    if isinstance(model, bool):
        return IsOriginalCondition(value=model)

    return IsOriginalCondition(
        value=model.value,
        min_confidence=model.min_confidence,
        language=model.language,
    )


def _convert_is_dubbed_condition(
    model: IsDubbedConditionModel | bool,
) -> IsDubbedCondition:
    """Convert is_dubbed Pydantic model to domain condition.

    Handles two forms:
    1. Simple boolean: is_dubbed: true
    2. Full object: is_dubbed: { value: true, min_confidence: 0.8, language: eng }
    """
    if isinstance(model, bool):
        return IsDubbedCondition(value=model)

    return IsDubbedCondition(
        value=model.value,
        min_confidence=model.min_confidence,
        language=model.language,
    )


def _convert_condition(model: ConditionModel) -> Condition:
    """Convert ConditionModel to Condition type."""
    if model.exists is not None:
        return _convert_exists_condition(model.exists)

    if model.count is not None:
        return _convert_count_condition(model.count)

    if model.audio_is_multi_language is not None:
        return _convert_audio_is_multi_language_condition(model.audio_is_multi_language)

    if model.plugin_metadata is not None:
        return _convert_plugin_metadata_condition(model.plugin_metadata)

    if model.container_metadata is not None:
        return _convert_container_metadata_condition(model.container_metadata)

    if model.is_original is not None:
        return _convert_is_original_condition(model.is_original)

    if model.is_dubbed is not None:
        return _convert_is_dubbed_condition(model.is_dubbed)

    if model.all_of is not None:
        return AndCondition(
            conditions=tuple(_convert_condition(c) for c in model.all_of)
        )

    if model.any_of is not None:
        return OrCondition(
            conditions=tuple(_convert_condition(c) for c in model.any_of)
        )

    if model.not_ is not None:
        return NotCondition(inner=_convert_condition(model.not_))

    # Should never happen due to validation
    raise ValueError("No condition type found")


def _convert_action(model: ActionModel) -> tuple[ConditionalAction, ...]:
    """Convert ActionModel to tuple of ConditionalAction.

    A single ActionModel can contain multiple actions (e.g., both skip and warn).
    """
    actions: list[ConditionalAction] = []

    if model.skip_video_transcode is True:
        actions.append(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE))

    if model.skip_audio_transcode is True:
        actions.append(SkipAction(skip_type=SkipType.AUDIO_TRANSCODE))

    if model.skip_track_filter is True:
        actions.append(SkipAction(skip_type=SkipType.TRACK_FILTER))

    if model.warn is not None:
        actions.append(WarnAction(message=model.warn))

    if model.fail is not None:
        actions.append(FailAction(message=model.fail))

    if model.set_forced is not None:
        actions.append(
            SetForcedAction(
                track_type=model.set_forced.track_type,
                language=model.set_forced.language,
                value=model.set_forced.value,
            )
        )

    if model.set_default is not None:
        actions.append(
            SetDefaultAction(
                track_type=model.set_default.track_type,
                language=model.set_default.language,
                value=model.set_default.value,
            )
        )

    if model.set_language is not None:
        from_plugin_ref = None
        if model.set_language.from_plugin_metadata is not None:
            from_plugin_ref = PluginMetadataReference(
                plugin=model.set_language.from_plugin_metadata.plugin,
                field=model.set_language.from_plugin_metadata.field,
            )
        actions.append(
            SetLanguageAction(
                track_type=model.set_language.track_type,
                new_language=model.set_language.new_language,
                from_plugin_metadata=from_plugin_ref,
                match_language=model.set_language.match_language,
            )
        )

    if model.set_container_metadata is not None:
        from_plugin_ref = None
        if model.set_container_metadata.from_plugin_metadata is not None:
            from_plugin_ref = PluginMetadataReference(
                plugin=model.set_container_metadata.from_plugin_metadata.plugin,
                field=model.set_container_metadata.from_plugin_metadata.field,
            )
        actions.append(
            SetContainerMetadataAction(
                field=model.set_container_metadata.field,
                value=model.set_container_metadata.value,
                from_plugin_metadata=from_plugin_ref,
            )
        )

    return tuple(actions)


def _convert_actions(
    models: ActionModel | list[ActionModel] | None,
) -> tuple[ConditionalAction, ...] | None:
    """Convert action model(s) to tuple of ConditionalAction."""
    if models is None:
        return None

    if isinstance(models, list):
        actions: list[ConditionalAction] = []
        for m in models:
            actions.extend(_convert_action(m))
        return tuple(actions)

    return _convert_action(models)


def _convert_conditional_rule(model: ConditionalRuleModel) -> ConditionalRule:
    """Convert ConditionalRuleModel to ConditionalRule dataclass."""
    then_actions = _convert_actions(model.then)
    if then_actions is None:
        then_actions = ()

    else_actions = _convert_actions(model.else_)

    return ConditionalRule(
        name=model.name,
        when=_convert_condition(model.when),
        then_actions=then_actions,
        else_actions=else_actions,
    )


def _convert_conditional_rules(
    models: list[ConditionalRuleModel] | None,
) -> tuple[ConditionalRule, ...]:
    """Convert list of ConditionalRuleModel to tuple of ConditionalRule."""
    if models is None:
        return ()
    return tuple(_convert_conditional_rule(m) for m in models)


# =============================================================================
# V5 Conversion Functions for Audio Synthesis
# =============================================================================


def _convert_preference_criterion(
    model: PreferenceCriterionModel,
) -> dict:
    """Convert PreferenceCriterionModel to dict for storage."""
    result: dict = {}

    if model.language is not None:
        if isinstance(model.language, list):
            result["language"] = tuple(model.language)
        else:
            result["language"] = model.language

    if model.not_commentary is not None:
        result["not_commentary"] = model.not_commentary

    if model.channels is not None:
        if isinstance(model.channels, ChannelPreferenceModel):
            if model.channels.max:
                result["channels"] = "max"
            elif model.channels.min:
                result["channels"] = "min"
        else:
            result["channels"] = model.channels

    if model.codec is not None:
        if isinstance(model.codec, list):
            result["codec"] = tuple(model.codec)
        else:
            result["codec"] = model.codec

    return result


def _convert_skip_if_exists(
    model: SkipIfExistsModel | None,
) -> SkipIfExistsCriteria | None:
    """Convert SkipIfExistsModel to SkipIfExistsCriteria dataclass."""
    if model is None:
        return None

    # Normalize codec to tuple
    codec: str | tuple[str, ...] | None = None
    if model.codec is not None:
        if isinstance(model.codec, list):
            codec = tuple(model.codec)
        else:
            codec = model.codec

    # Convert channels comparison
    channels: int | Comparison | None = None
    if model.channels is not None:
        if isinstance(model.channels, ComparisonModel):
            channels = _convert_comparison(model.channels)
        else:
            channels = model.channels

    # Normalize language to tuple
    language: str | tuple[str, ...] | None = None
    if model.language is not None:
        if isinstance(model.language, list):
            language = tuple(model.language)
        else:
            language = model.language

    return SkipIfExistsCriteria(
        codec=codec,
        channels=channels,
        language=language,
        not_commentary=model.not_commentary,
    )


def _convert_synthesis_track_definition(
    model: SynthesisTrackDefinitionModel,
) -> SynthesisTrackDefinitionRef:
    """Convert SynthesisTrackDefinitionModel to SynthesisTrackDefinitionRef."""
    # Convert source preferences to tuple of dicts
    source_prefer = tuple(_convert_preference_criterion(p) for p in model.source.prefer)

    # Convert create_if condition if present
    create_if: Condition | None = None
    if model.create_if is not None:
        create_if = _convert_condition(model.create_if)

    # Convert skip_if_exists criteria if present (V8+)
    skip_if_exists = _convert_skip_if_exists(model.skip_if_exists)

    return SynthesisTrackDefinitionRef(
        name=model.name,
        codec=model.codec,
        channels=model.channels,
        source_prefer=source_prefer,
        bitrate=model.bitrate,
        create_if=create_if,
        skip_if_exists=skip_if_exists,
        title=model.title,
        language=model.language,
        position=model.position,
    )


def _convert_audio_synthesis(
    model: AudioSynthesisModel | None,
) -> AudioSynthesisConfig | None:
    """Convert AudioSynthesisModel to AudioSynthesisConfig."""
    if model is None:
        return None

    tracks = tuple(_convert_synthesis_track_definition(t) for t in model.tracks)

    return AudioSynthesisConfig(tracks=tracks)


# =============================================================================
# V6 Conversion Functions for Conditional Video Transcoding
# =============================================================================


def _convert_skip_condition(model: SkipConditionModel | None) -> SkipCondition | None:
    """Convert SkipConditionModel to SkipCondition dataclass."""
    if model is None:
        return None

    return SkipCondition(
        codec_matches=tuple(model.codec_matches) if model.codec_matches else None,
        resolution_within=model.resolution_within,
        bitrate_under=model.bitrate_under,
    )


def _convert_quality_settings(
    model: QualitySettingsModel | None,
) -> QualitySettings | None:
    """Convert QualitySettingsModel to QualitySettings dataclass."""
    if model is None:
        return None

    # Convert mode string to enum
    mode_map = {
        "crf": QualityMode.CRF,
        "bitrate": QualityMode.BITRATE,
        "constrained_quality": QualityMode.CONSTRAINED_QUALITY,
    }

    return QualitySettings(
        mode=mode_map[model.mode],
        crf=model.crf,
        bitrate=model.bitrate,
        min_bitrate=model.min_bitrate,
        max_bitrate=model.max_bitrate,
        preset=model.preset,
        tune=model.tune,
        two_pass=model.two_pass,
    )


def _convert_scaling_settings(
    model: ScalingSettingsModel | None,
) -> ScalingSettings | None:
    """Convert ScalingSettingsModel to ScalingSettings dataclass."""
    if model is None:
        return None

    # Convert algorithm string to enum
    algo_map = {
        "lanczos": ScaleAlgorithm.LANCZOS,
        "bicubic": ScaleAlgorithm.BICUBIC,
        "bilinear": ScaleAlgorithm.BILINEAR,
    }

    return ScalingSettings(
        max_resolution=model.max_resolution,
        max_width=model.max_width,
        max_height=model.max_height,
        algorithm=algo_map[model.algorithm],
        upscale=model.upscale,
    )


def _convert_hardware_accel_config(
    model: HardwareAccelConfigModel | None,
) -> HardwareAccelConfig | None:
    """Convert HardwareAccelConfigModel to HardwareAccelConfig dataclass."""
    if model is None:
        return None

    # Convert enabled string to enum
    mode_map = {
        "auto": HardwareAccelMode.AUTO,
        "nvenc": HardwareAccelMode.NVENC,
        "qsv": HardwareAccelMode.QSV,
        "vaapi": HardwareAccelMode.VAAPI,
        "none": HardwareAccelMode.NONE,
    }

    mode = mode_map.get(model.enabled)
    if mode is None:
        raise ValueError(
            f"Invalid hardware acceleration mode: '{model.enabled}'. "
            f"Must be one of: {', '.join(sorted(mode_map.keys()))}"
        )

    return HardwareAccelConfig(
        enabled=mode,
        fallback_to_cpu=model.fallback_to_cpu,
    )


def _convert_video_transcode_config(
    model: VideoTranscodeConfigModel | None,
) -> VideoTranscodeConfig | None:
    """Convert VideoTranscodeConfigModel to VideoTranscodeConfig dataclass."""
    if model is None:
        return None

    return VideoTranscodeConfig(
        target_codec=model.target_codec,
        skip_if=_convert_skip_condition(model.skip_if),
        quality=_convert_quality_settings(model.quality),
        scaling=_convert_scaling_settings(model.scaling),
        hardware_acceleration=_convert_hardware_accel_config(
            model.hardware_acceleration
        ),
        ffmpeg_args=tuple(model.ffmpeg_args) if model.ffmpeg_args else None,
    )


def _convert_audio_transcode_config(
    model: AudioTranscodeConfigModel | None,
) -> AudioTranscodeConfig | None:
    """Convert AudioTranscodeConfigModel to AudioTranscodeConfig dataclass."""
    if model is None:
        return None

    return AudioTranscodeConfig(
        preserve_codecs=tuple(model.preserve_codecs),
        transcode_to=model.transcode_to,
        transcode_bitrate=model.transcode_bitrate,
    )


# =============================================================================
# Conversion Functions
# =============================================================================


def _convert_phase_model(phase: PhaseModel) -> PhaseDefinition:
    """Convert PhaseModel to PhaseDefinition dataclass."""
    # Convert container
    container: ContainerConfig | None = None
    if phase.container is not None:
        codec_mappings: dict[str, CodecTranscodeMapping] | None = None
        if phase.container.codec_mappings is not None:
            codec_mappings = {
                codec: CodecTranscodeMapping(
                    codec=mapping.codec,
                    bitrate=mapping.bitrate,
                    action=mapping.action,
                )
                for codec, mapping in phase.container.codec_mappings.items()
            }
        container = ContainerConfig(
            target=phase.container.target,
            on_incompatible_codec=phase.container.on_incompatible_codec,
            codec_mappings=codec_mappings,
        )

    # Convert audio_filter
    audio_filter: AudioFilterConfig | None = None
    if phase.audio_filter is not None:
        fallback: LanguageFallbackConfig | None = None
        if phase.audio_filter.fallback is not None:
            fallback = LanguageFallbackConfig(mode=phase.audio_filter.fallback.mode)
        audio_filter = AudioFilterConfig(
            languages=tuple(phase.audio_filter.languages),
            fallback=fallback,
            minimum=phase.audio_filter.minimum,
            keep_music_tracks=phase.audio_filter.keep_music_tracks,
            exclude_music_from_language_filter=phase.audio_filter.exclude_music_from_language_filter,
            keep_sfx_tracks=phase.audio_filter.keep_sfx_tracks,
            exclude_sfx_from_language_filter=phase.audio_filter.exclude_sfx_from_language_filter,
            keep_non_speech_tracks=phase.audio_filter.keep_non_speech_tracks,
            exclude_non_speech_from_language_filter=phase.audio_filter.exclude_non_speech_from_language_filter,
        )

    # Convert subtitle_filter
    subtitle_filter: SubtitleFilterConfig | None = None
    if phase.subtitle_filter is not None:
        languages = None
        if phase.subtitle_filter.languages is not None:
            languages = tuple(phase.subtitle_filter.languages)
        subtitle_filter = SubtitleFilterConfig(
            languages=languages,
            preserve_forced=phase.subtitle_filter.preserve_forced,
            remove_all=phase.subtitle_filter.remove_all,
        )

    # Convert attachment_filter
    attachment_filter: AttachmentFilterConfig | None = None
    if phase.attachment_filter is not None:
        attachment_filter = AttachmentFilterConfig(
            remove_all=phase.attachment_filter.remove_all,
        )

    # Convert track_order
    track_order: tuple[TrackType, ...] | None = None
    if phase.track_order is not None:
        track_order = tuple(TrackType(t) for t in phase.track_order)

    # Convert default_flags
    default_flags: DefaultFlagsConfig | None = None
    if phase.default_flags is not None:
        pf = phase.default_flags
        preferred_codec: tuple[str, ...] | None = None
        if pf.preferred_audio_codec is not None:
            preferred_codec = tuple(pf.preferred_audio_codec)
        default_flags = DefaultFlagsConfig(
            set_first_video_default=pf.set_first_video_default,
            set_preferred_audio_default=pf.set_preferred_audio_default,
            set_preferred_subtitle_default=pf.set_preferred_subtitle_default,
            clear_other_defaults=pf.clear_other_defaults,
            set_subtitle_default_when_audio_differs=pf.set_subtitle_default_when_audio_differs,
            set_subtitle_forced_when_audio_differs=pf.set_subtitle_forced_when_audio_differs,
            preferred_audio_codec=preferred_codec,
        )

    # Convert conditional rules
    conditional: tuple[ConditionalRule, ...] | None = None
    if phase.conditional is not None:
        conditional = _convert_conditional_rules(phase.conditional)

    # Convert audio_synthesis
    audio_synthesis: AudioSynthesisConfig | None = None
    if phase.audio_synthesis is not None:
        audio_synthesis = _convert_audio_synthesis(phase.audio_synthesis)

    # Convert transcode (V6-style)
    transcode: VideoTranscodeConfig | None = None
    audio_transcode: AudioTranscodeConfig | None = None
    if phase.transcode is not None:
        transcode = _convert_video_transcode_config(phase.transcode.video)
        audio_transcode = _convert_audio_transcode_config(phase.transcode.audio)

    # Convert transcription
    transcription: TranscriptionPolicyOptions | None = None
    if phase.transcription is not None:
        transcription = TranscriptionPolicyOptions(
            enabled=phase.transcription.enabled,
            update_language_from_transcription=phase.transcription.update_language_from_transcription,
            confidence_threshold=phase.transcription.confidence_threshold,
            detect_commentary=phase.transcription.detect_commentary,
            reorder_commentary=phase.transcription.reorder_commentary,
        )

    # Convert file_timestamp
    file_timestamp: FileTimestampConfig | None = None
    if phase.file_timestamp is not None:
        file_timestamp = FileTimestampConfig(
            mode=phase.file_timestamp.mode,
            fallback=phase.file_timestamp.fallback,
            date_source=phase.file_timestamp.date_source,
        )

    # Convert audio_actions
    audio_actions: AudioActionsConfig | None = None
    if phase.audio_actions is not None:
        audio_actions = AudioActionsConfig(
            clear_all_forced=phase.audio_actions.clear_all_forced,
            clear_all_default=phase.audio_actions.clear_all_default,
            clear_all_titles=phase.audio_actions.clear_all_titles,
        )

    # Convert subtitle_actions
    subtitle_actions: SubtitleActionsConfig | None = None
    if phase.subtitle_actions is not None:
        subtitle_actions = SubtitleActionsConfig(
            clear_all_forced=phase.subtitle_actions.clear_all_forced,
            clear_all_default=phase.subtitle_actions.clear_all_default,
            clear_all_titles=phase.subtitle_actions.clear_all_titles,
        )

    # Convert skip_when condition
    skip_when: PhaseSkipCondition | None = None
    if phase.skip_when is not None:
        skip_when = PhaseSkipCondition(
            video_codec=(
                tuple(phase.skip_when.video_codec)
                if phase.skip_when.video_codec
                else None
            ),
            audio_codec_exists=phase.skip_when.audio_codec_exists,
            subtitle_language_exists=phase.skip_when.subtitle_language_exists,
            container=(
                tuple(phase.skip_when.container) if phase.skip_when.container else None
            ),
            resolution=phase.skip_when.resolution,
            resolution_under=phase.skip_when.resolution_under,
            file_size_under=phase.skip_when.file_size_under,
            file_size_over=phase.skip_when.file_size_over,
            duration_under=phase.skip_when.duration_under,
            duration_over=phase.skip_when.duration_over,
        )

    # Convert depends_on
    depends_on: tuple[str, ...] | None = None
    if phase.depends_on is not None:
        depends_on = tuple(phase.depends_on)

    # Convert run_if condition
    run_if: RunIfCondition | None = None
    if phase.run_if is not None:
        run_if = RunIfCondition(
            phase_modified=phase.run_if.phase_modified,
            phase_completed=phase.run_if.phase_completed,
        )

    # Convert on_error override
    on_error: OnErrorMode | None = None
    if phase.on_error is not None:
        on_error = _ON_ERROR_MAP[phase.on_error]

    return PhaseDefinition(
        name=phase.name,
        container=container,
        audio_filter=audio_filter,
        subtitle_filter=subtitle_filter,
        attachment_filter=attachment_filter,
        track_order=track_order,
        default_flags=default_flags,
        conditional=conditional,
        audio_synthesis=audio_synthesis,
        transcode=transcode,
        audio_transcode=audio_transcode,
        transcription=transcription,
        file_timestamp=file_timestamp,
        audio_actions=audio_actions,
        subtitle_actions=subtitle_actions,
        skip_when=skip_when,
        depends_on=depends_on,
        run_if=run_if,
        on_error=on_error,
    )


def _convert_to_policy_schema(model: PolicyModel) -> PolicySchema:
    """Convert PolicyModel to PolicySchema dataclass."""
    # Convert global config
    global_config = GlobalConfig(
        audio_language_preference=tuple(model.config.audio_language_preference),
        subtitle_language_preference=tuple(model.config.subtitle_language_preference),
        commentary_patterns=tuple(model.config.commentary_patterns),
        on_error=_ON_ERROR_MAP[model.config.on_error],
    )

    # Convert phases
    phases = tuple(_convert_phase_model(p) for p in model.phases)

    return PolicySchema(
        schema_version=12,
        config=global_config,
        phases=phases,
        description=model.description,
        category=model.category,
    )

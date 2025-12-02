"""Unit tests for tool requirements checking."""

from datetime import datetime, timezone

from video_policy_orchestrator.tools.models import (
    FFmpegCapabilities,
    FFmpegInfo,
    FFprobeInfo,
    MkvmergeInfo,
    MkvpropeditInfo,
    ToolRegistry,
    ToolStatus,
)
from video_policy_orchestrator.tools.requirements import (
    ALL_REQUIREMENTS,
    CAPABILITY_REQUIREMENTS,
    CORE_REQUIREMENTS,
    FFMPEG_VERSION_REQUIREMENTS,
    MKV_REQUIREMENTS,
    NON_MKV_REQUIREMENTS,
    TRANSCRIPTION_REQUIREMENTS,
    VERSION_RECOMMENDATIONS,
    RequirementCheckResult,
    RequirementLevel,
    RequirementsReport,
    ToolRequirement,
    check_core_requirements,
    check_mkv_requirements,
    check_non_mkv_requirements,
    check_requirement,
    check_requirements,
    get_missing_tool_hints,
    get_upgrade_suggestions,
)

# =============================================================================
# Test Fixtures
# =============================================================================


def make_available_tool(info_class, version: str, version_tuple: tuple[int, ...]):
    """Create an available tool info instance."""
    info = info_class()
    info.status = ToolStatus.AVAILABLE
    info.version = version
    info.version_tuple = version_tuple
    info.detected_at = datetime.now(timezone.utc)
    return info


def make_missing_tool(info_class):
    """Create a missing tool info instance."""
    info = info_class()
    info.status = ToolStatus.MISSING
    info.status_message = f"{info.name} not found in PATH"
    return info


def make_full_registry() -> ToolRegistry:
    """Create a registry with all tools available."""
    return ToolRegistry(
        ffmpeg=make_available_tool(FFmpegInfo, "6.1.1", (6, 1, 1)),
        ffprobe=make_available_tool(FFprobeInfo, "6.1.1", (6, 1, 1)),
        mkvmerge=make_available_tool(MkvmergeInfo, "81.0", (81, 0)),
        mkvpropedit=make_available_tool(MkvpropeditInfo, "81.0", (81, 0)),
    )


def make_empty_registry() -> ToolRegistry:
    """Create a registry with no tools available."""
    return ToolRegistry(
        ffmpeg=make_missing_tool(FFmpegInfo),
        ffprobe=make_missing_tool(FFprobeInfo),
        mkvmerge=make_missing_tool(MkvmergeInfo),
        mkvpropedit=make_missing_tool(MkvpropeditInfo),
    )


# =============================================================================
# ToolRequirement Tests
# =============================================================================


class TestToolRequirement:
    """Tests for ToolRequirement dataclass."""

    def test_default_level_is_required(self):
        """Default requirement level should be REQUIRED."""
        req = ToolRequirement(
            tool_name="test",
            feature_name="Test Feature",
            description="Test description",
        )
        assert req.level == RequirementLevel.REQUIRED

    def test_min_version_defaults_to_none(self):
        """min_version should default to None (any version)."""
        req = ToolRequirement(
            tool_name="test",
            feature_name="Test Feature",
            description="Test description",
        )
        assert req.min_version is None

    def test_capability_check_defaults_to_none(self):
        """capability_check should default to None."""
        req = ToolRequirement(
            tool_name="test",
            feature_name="Test Feature",
            description="Test description",
        )
        assert req.capability_check is None


# =============================================================================
# RequirementsReport Tests
# =============================================================================


class TestRequirementsReport:
    """Tests for RequirementsReport dataclass."""

    def test_all_satisfied_when_all_pass(self):
        """all_satisfied is True when all requirements pass."""
        req = ToolRequirement(
            tool_name="test",
            feature_name="Test",
            description="Test",
        )
        results = [
            RequirementCheckResult(requirement=req, satisfied=True),
            RequirementCheckResult(requirement=req, satisfied=True),
        ]
        report = RequirementsReport(results=results)
        assert report.all_satisfied is True

    def test_all_satisfied_false_when_one_fails(self):
        """all_satisfied is False when any requirement fails."""
        req = ToolRequirement(
            tool_name="test",
            feature_name="Test",
            description="Test",
        )
        results = [
            RequirementCheckResult(requirement=req, satisfied=True),
            RequirementCheckResult(requirement=req, satisfied=False),
        ]
        report = RequirementsReport(results=results)
        assert report.all_satisfied is False

    def test_required_satisfied_ignores_recommended(self):
        """required_satisfied ignores RECOMMENDED failures."""
        required_req = ToolRequirement(
            tool_name="test",
            feature_name="Required Test",
            description="Test",
            level=RequirementLevel.REQUIRED,
        )
        recommended_req = ToolRequirement(
            tool_name="test",
            feature_name="Recommended Test",
            description="Test",
            level=RequirementLevel.RECOMMENDED,
        )
        results = [
            RequirementCheckResult(requirement=required_req, satisfied=True),
            RequirementCheckResult(requirement=recommended_req, satisfied=False),
        ]
        report = RequirementsReport(results=results)
        assert report.required_satisfied is True
        assert report.all_satisfied is False

    def test_required_satisfied_false_when_required_fails(self):
        """required_satisfied is False when a REQUIRED requirement fails."""
        req = ToolRequirement(
            tool_name="test",
            feature_name="Test",
            description="Test",
            level=RequirementLevel.REQUIRED,
        )
        results = [RequirementCheckResult(requirement=req, satisfied=False)]
        report = RequirementsReport(results=results)
        assert report.required_satisfied is False

    def test_get_unsatisfied_returns_failures_only(self):
        """get_unsatisfied() returns only failed requirements."""
        req1 = ToolRequirement(
            tool_name="test1", feature_name="Test1", description="Test1"
        )
        req2 = ToolRequirement(
            tool_name="test2", feature_name="Test2", description="Test2"
        )
        results = [
            RequirementCheckResult(requirement=req1, satisfied=True),
            RequirementCheckResult(requirement=req2, satisfied=False, message="Failed"),
        ]
        report = RequirementsReport(results=results)
        unsatisfied = report.get_unsatisfied()
        assert len(unsatisfied) == 1
        assert unsatisfied[0].requirement.tool_name == "test2"

    def test_get_unsatisfied_with_level_filter(self):
        """get_unsatisfied() filters by level."""
        required_req = ToolRequirement(
            tool_name="required",
            feature_name="Required",
            description="Test",
            level=RequirementLevel.REQUIRED,
        )
        recommended_req = ToolRequirement(
            tool_name="recommended",
            feature_name="Recommended",
            description="Test",
            level=RequirementLevel.RECOMMENDED,
        )
        results = [
            RequirementCheckResult(requirement=required_req, satisfied=False),
            RequirementCheckResult(requirement=recommended_req, satisfied=False),
        ]
        report = RequirementsReport(results=results)

        all_unsatisfied = report.get_unsatisfied()
        assert len(all_unsatisfied) == 2

        required_only = report.get_unsatisfied(RequirementLevel.REQUIRED)
        assert len(required_only) == 1
        assert required_only[0].requirement.tool_name == "required"

    def test_get_messages_returns_non_empty_messages(self):
        """get_messages() returns only non-empty messages."""
        req1 = ToolRequirement(
            tool_name="test1", feature_name="Test1", description="Test1"
        )
        req2 = ToolRequirement(
            tool_name="test2", feature_name="Test2", description="Test2"
        )
        results = [
            RequirementCheckResult(
                requirement=req1, satisfied=False, message="Error message"
            ),
            RequirementCheckResult(requirement=req2, satisfied=False, message=""),
        ]
        report = RequirementsReport(results=results)
        messages = report.get_messages()
        assert len(messages) == 1
        assert messages[0] == "Error message"

    def test_empty_report_all_satisfied(self):
        """Empty report should have all_satisfied=True."""
        report = RequirementsReport(results=[])
        assert report.all_satisfied is True
        assert report.required_satisfied is True


# =============================================================================
# check_requirement Tests
# =============================================================================


class TestCheckRequirement:
    """Tests for check_requirement() function."""

    def test_missing_tool_returns_unsatisfied(self):
        """Requirement fails when tool is missing."""
        registry = make_empty_registry()
        req = ToolRequirement(
            tool_name="ffprobe",
            feature_name="Test Feature",
            description="Test description",
            install_hint="Install ffmpeg",
        )
        result = check_requirement(registry, req)
        assert result.satisfied is False
        assert result.current_version is None
        assert "not found" in result.message
        assert "Install ffmpeg" in result.message

    def test_available_tool_returns_satisfied(self):
        """Requirement passes when tool is available."""
        registry = make_full_registry()
        req = ToolRequirement(
            tool_name="ffprobe",
            feature_name="Test Feature",
            description="Test description",
        )
        result = check_requirement(registry, req)
        assert result.satisfied is True
        assert result.current_version == "6.1.1"
        assert result.message == ""

    def test_version_below_minimum_returns_unsatisfied(self):
        """Requirement fails when version < min_version."""
        registry = make_full_registry()
        req = ToolRequirement(
            tool_name="ffmpeg",
            feature_name="Modern FFmpeg",
            description="FFmpeg 7.0+ required",
            min_version=(7, 0),
            install_hint="Upgrade ffmpeg",
        )
        result = check_requirement(registry, req)
        assert result.satisfied is False
        assert result.current_version == "6.1.1"
        assert "6.1.1 < required 7.0" in result.message

    def test_version_meets_minimum_returns_satisfied(self):
        """Requirement passes when version >= min_version."""
        registry = make_full_registry()
        req = ToolRequirement(
            tool_name="ffmpeg",
            feature_name="Modern FFmpeg",
            description="FFmpeg 5.0+ required",
            min_version=(5, 0),
        )
        result = check_requirement(registry, req)
        assert result.satisfied is True
        assert result.current_version == "6.1.1"

    def test_version_exactly_meets_minimum(self):
        """Requirement passes when version equals min_version exactly."""
        registry = ToolRegistry(
            ffmpeg=make_available_tool(FFmpegInfo, "5.0", (5, 0)),
            ffprobe=make_available_tool(FFprobeInfo, "5.0", (5, 0)),
            mkvmerge=make_available_tool(MkvmergeInfo, "70.0", (70, 0)),
            mkvpropedit=make_available_tool(MkvpropeditInfo, "70.0", (70, 0)),
        )
        req = ToolRequirement(
            tool_name="ffmpeg",
            feature_name="Test",
            description="Test",
            min_version=(5, 0),
        )
        result = check_requirement(registry, req)
        assert result.satisfied is True

    def test_capability_check_missing_returns_unsatisfied(self):
        """Requirement fails when capability check fails."""
        # Create ffmpeg with no MKV muxer support
        ffmpeg = make_available_tool(FFmpegInfo, "6.1.1", (6, 1, 1))
        ffmpeg.capabilities = FFmpegCapabilities(muxers=set())  # No matroska

        registry = ToolRegistry(
            ffmpeg=ffmpeg,
            ffprobe=make_available_tool(FFprobeInfo, "6.1.1", (6, 1, 1)),
            mkvmerge=make_available_tool(MkvmergeInfo, "81.0", (81, 0)),
            mkvpropedit=make_available_tool(MkvpropeditInfo, "81.0", (81, 0)),
        )
        req = ToolRequirement(
            tool_name="ffmpeg",
            feature_name="MKV Muxing",
            description="FFmpeg must support MKV output",
            capability_check="can_remux_to_mkv",
            install_hint="Rebuild ffmpeg with libmatroska",
        )
        result = check_requirement(registry, req)
        assert result.satisfied is False
        assert "MKV Muxing" in result.message

    def test_capability_check_present_returns_satisfied(self):
        """Requirement passes when capability check passes."""
        # Create ffmpeg with MKV muxer support
        ffmpeg = make_available_tool(FFmpegInfo, "6.1.1", (6, 1, 1))
        ffmpeg.capabilities = FFmpegCapabilities(muxers={"matroska"})

        registry = ToolRegistry(
            ffmpeg=ffmpeg,
            ffprobe=make_available_tool(FFprobeInfo, "6.1.1", (6, 1, 1)),
            mkvmerge=make_available_tool(MkvmergeInfo, "81.0", (81, 0)),
            mkvpropedit=make_available_tool(MkvpropeditInfo, "81.0", (81, 0)),
        )
        req = ToolRequirement(
            tool_name="ffmpeg",
            feature_name="MKV Muxing",
            description="FFmpeg must support MKV output",
            capability_check="can_remux_to_mkv",
        )
        result = check_requirement(registry, req)
        assert result.satisfied is True

    def test_unknown_tool_returns_unsatisfied(self):
        """Requirement fails for unknown tool name."""
        registry = make_full_registry()
        req = ToolRequirement(
            tool_name="unknown_tool",
            feature_name="Unknown",
            description="Unknown tool",
        )
        result = check_requirement(registry, req)
        assert result.satisfied is False
        assert "not found" in result.message


# =============================================================================
# check_requirements Tests
# =============================================================================


class TestCheckRequirements:
    """Tests for check_requirements() function."""

    def test_defaults_to_all_requirements(self):
        """Without requirements arg, uses ALL_REQUIREMENTS."""
        registry = make_full_registry()
        # Add matroska support for capability check
        registry.ffmpeg.capabilities = FFmpegCapabilities(muxers={"matroska"})

        report = check_requirements(registry)
        # Should have checked all requirements
        assert len(report.results) == len(ALL_REQUIREMENTS)

    def test_custom_requirements_list(self):
        """Can pass custom requirements list."""
        registry = make_full_registry()
        custom_reqs = [
            ToolRequirement(
                tool_name="ffprobe",
                feature_name="Custom",
                description="Custom requirement",
            )
        ]
        report = check_requirements(registry, custom_reqs)
        assert len(report.results) == 1
        assert report.results[0].requirement.feature_name == "Custom"

    def test_returns_report_with_all_results(self):
        """Returns report containing all check results."""
        registry = make_full_registry()
        report = check_requirements(registry, CORE_REQUIREMENTS + MKV_REQUIREMENTS)
        assert len(report.results) == len(CORE_REQUIREMENTS) + len(MKV_REQUIREMENTS)


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for check_core/mkv/non_mkv_requirements()."""

    def test_check_core_requirements(self):
        """check_core_requirements() checks ffprobe."""
        registry = make_full_registry()
        report = check_core_requirements(registry)
        assert len(report.results) == len(CORE_REQUIREMENTS)
        assert report.all_satisfied is True

    def test_check_core_requirements_fails_without_ffprobe(self):
        """check_core_requirements() fails without ffprobe."""
        registry = make_full_registry()
        registry.ffprobe = make_missing_tool(FFprobeInfo)
        report = check_core_requirements(registry)
        assert report.all_satisfied is False

    def test_check_mkv_requirements(self):
        """check_mkv_requirements() checks mkvpropedit and mkvmerge."""
        registry = make_full_registry()
        report = check_mkv_requirements(registry)
        assert len(report.results) == len(MKV_REQUIREMENTS)
        assert report.all_satisfied is True

    def test_check_mkv_requirements_fails_without_mkvpropedit(self):
        """check_mkv_requirements() fails without mkvpropedit."""
        registry = make_full_registry()
        registry.mkvpropedit = make_missing_tool(MkvpropeditInfo)
        report = check_mkv_requirements(registry)
        assert report.all_satisfied is False

    def test_check_non_mkv_requirements(self):
        """check_non_mkv_requirements() checks ffmpeg."""
        registry = make_full_registry()
        report = check_non_mkv_requirements(registry)
        assert len(report.results) == len(NON_MKV_REQUIREMENTS)
        assert report.all_satisfied is True

    def test_check_non_mkv_requirements_fails_without_ffmpeg(self):
        """check_non_mkv_requirements() fails without ffmpeg."""
        registry = make_full_registry()
        registry.ffmpeg = make_missing_tool(FFmpegInfo)
        report = check_non_mkv_requirements(registry)
        assert report.all_satisfied is False


# =============================================================================
# Hint Function Tests
# =============================================================================


class TestHintFunctions:
    """Tests for get_upgrade_suggestions() and get_missing_tool_hints()."""

    def test_get_upgrade_suggestions_with_old_tools(self):
        """get_upgrade_suggestions() returns messages for old tools."""
        # Create registry with old tool versions
        registry = ToolRegistry(
            ffmpeg=make_available_tool(FFmpegInfo, "4.0", (4, 0)),
            ffprobe=make_available_tool(FFprobeInfo, "4.0", (4, 0)),
            mkvmerge=make_available_tool(MkvmergeInfo, "60.0", (60, 0)),
            mkvpropedit=make_available_tool(MkvpropeditInfo, "60.0", (60, 0)),
        )
        suggestions = get_upgrade_suggestions(registry)
        assert len(suggestions) >= 1
        # Should suggest upgrading ffmpeg and mkvmerge
        messages_text = " ".join(suggestions)
        assert "ffmpeg" in messages_text.lower() or "mkvmerge" in messages_text.lower()

    def test_get_upgrade_suggestions_with_modern_tools(self):
        """get_upgrade_suggestions() returns empty for modern tools."""
        # Create registry with new tool versions
        registry = ToolRegistry(
            ffmpeg=make_available_tool(FFmpegInfo, "7.0", (7, 0)),
            ffprobe=make_available_tool(FFprobeInfo, "7.0", (7, 0)),
            mkvmerge=make_available_tool(MkvmergeInfo, "85.0", (85, 0)),
            mkvpropedit=make_available_tool(MkvpropeditInfo, "85.0", (85, 0)),
        )
        suggestions = get_upgrade_suggestions(registry)
        assert len(suggestions) == 0

    def test_get_missing_tool_hints_with_all_tools(self):
        """get_missing_tool_hints() returns empty when all tools present."""
        registry = make_full_registry()
        hints = get_missing_tool_hints(registry)
        assert len(hints) == 0

    def test_get_missing_tool_hints_with_missing_tools(self):
        """get_missing_tool_hints() returns hints for missing tools."""
        registry = make_empty_registry()
        hints = get_missing_tool_hints(registry)
        assert len(hints) == 4
        assert "ffmpeg" in hints
        assert "ffprobe" in hints
        assert "mkvmerge" in hints
        assert "mkvpropedit" in hints
        # Check hints contain URLs
        assert "ffmpeg.org" in hints["ffmpeg"]
        assert "mkvtoolnix" in hints["mkvmerge"]

    def test_get_missing_tool_hints_partial_missing(self):
        """get_missing_tool_hints() returns hints only for missing tools."""
        registry = make_full_registry()
        registry.ffmpeg = make_missing_tool(FFmpegInfo)
        registry.mkvmerge = make_missing_tool(MkvmergeInfo)
        hints = get_missing_tool_hints(registry)
        assert len(hints) == 2
        assert "ffmpeg" in hints
        assert "mkvmerge" in hints
        assert "ffprobe" not in hints
        assert "mkvpropedit" not in hints


# =============================================================================
# Predefined Requirements Tests
# =============================================================================


class TestPredefinedRequirements:
    """Tests for the predefined requirement lists."""

    def test_core_requirements_has_ffprobe(self):
        """CORE_REQUIREMENTS includes ffprobe."""
        tool_names = [r.tool_name for r in CORE_REQUIREMENTS]
        assert "ffprobe" in tool_names

    def test_mkv_requirements_has_mkvtools(self):
        """MKV_REQUIREMENTS includes mkvpropedit and mkvmerge."""
        tool_names = [r.tool_name for r in MKV_REQUIREMENTS]
        assert "mkvpropedit" in tool_names
        assert "mkvmerge" in tool_names

    def test_non_mkv_requirements_has_ffmpeg(self):
        """NON_MKV_REQUIREMENTS includes ffmpeg."""
        tool_names = [r.tool_name for r in NON_MKV_REQUIREMENTS]
        assert "ffmpeg" in tool_names

    def test_version_recommendations_are_recommended_level(self):
        """VERSION_RECOMMENDATIONS all have RECOMMENDED level."""
        for req in VERSION_RECOMMENDATIONS:
            assert req.level == RequirementLevel.RECOMMENDED

    def test_capability_requirements_check_capabilities(self):
        """CAPABILITY_REQUIREMENTS all have capability_check."""
        for req in CAPABILITY_REQUIREMENTS:
            assert req.capability_check is not None

    def test_all_requirements_combines_all_lists(self):
        """ALL_REQUIREMENTS contains all other requirement lists."""
        expected_count = (
            len(CORE_REQUIREMENTS)
            + len(MKV_REQUIREMENTS)
            + len(NON_MKV_REQUIREMENTS)
            + len(VERSION_RECOMMENDATIONS)
            + len(CAPABILITY_REQUIREMENTS)
            + len(FFMPEG_VERSION_REQUIREMENTS)
            + len(TRANSCRIPTION_REQUIREMENTS)
        )
        assert len(ALL_REQUIREMENTS) == expected_count

    def test_all_requirements_have_descriptions(self):
        """All predefined requirements have non-empty descriptions."""
        for req in ALL_REQUIREMENTS:
            assert req.description, f"{req.feature_name} missing description"

    def test_all_requirements_have_feature_names(self):
        """All predefined requirements have non-empty feature names."""
        for req in ALL_REQUIREMENTS:
            assert req.feature_name, f"{req.tool_name} missing feature name"

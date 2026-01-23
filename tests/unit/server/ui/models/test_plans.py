"""Unit tests for plan view models."""

from __future__ import annotations

from unittest.mock import MagicMock

from vpo.server.ui.models.plans import PlanDetailContext


class TestPlanDetailContextSafeBackUrl:
    """Tests for PlanDetailContext._is_safe_back_url open redirect protection."""

    def test_rejects_external_url_referer(self) -> None:
        """External URLs should be rejected."""
        # Full external URL
        assert PlanDetailContext._is_safe_back_url("https://evil.com/plans") is None
        assert PlanDetailContext._is_safe_back_url("http://evil.com/plans/123") is None

        # External URL that contains our paths
        assert (
            PlanDetailContext._is_safe_back_url("https://evil.com/fake/plans") is None
        )

    def test_rejects_protocol_relative_url(self) -> None:
        """Protocol-relative URLs should be rejected."""
        assert PlanDetailContext._is_safe_back_url("//evil.com/plans") is None
        assert PlanDetailContext._is_safe_back_url("//evil.com/approvals") is None

        # Even with valid path prefix
        assert PlanDetailContext._is_safe_back_url("//plans.example.com/") is None

    def test_accepts_valid_internal_paths(self) -> None:
        """Valid internal paths should be accepted."""
        # Plans paths
        assert PlanDetailContext._is_safe_back_url("/plans") == "/plans"
        assert PlanDetailContext._is_safe_back_url("/plans/") == "/plans/"
        assert PlanDetailContext._is_safe_back_url("/plans/123") == "/plans/123"
        assert (
            PlanDetailContext._is_safe_back_url("/plans?status=pending")
            == "/plans"  # Query stripped
        )

        # Approvals paths
        assert PlanDetailContext._is_safe_back_url("/approvals") == "/approvals"

        # Library paths
        assert PlanDetailContext._is_safe_back_url("/library") == "/library"
        assert PlanDetailContext._is_safe_back_url("/library/123") == "/library/123"

        # Jobs paths
        assert PlanDetailContext._is_safe_back_url("/jobs") == "/jobs"
        assert PlanDetailContext._is_safe_back_url("/jobs/abc-123") == "/jobs/abc-123"

    def test_extracts_path_from_full_url(self) -> None:
        """Full URLs with localhost should extract the path."""
        # Valid internal full URLs
        assert (
            PlanDetailContext._is_safe_back_url("http://localhost:8080/plans/123")
            == "/plans/123"
        )
        assert (
            PlanDetailContext._is_safe_back_url("http://127.0.0.1:8080/approvals")
            == "/approvals"
        )

    def test_rejects_invalid_paths(self) -> None:
        """Paths that don't match allowed prefixes should be rejected."""
        assert PlanDetailContext._is_safe_back_url("/admin") is None
        assert PlanDetailContext._is_safe_back_url("/settings") is None
        assert PlanDetailContext._is_safe_back_url("/") is None
        assert PlanDetailContext._is_safe_back_url("/api/plans") is None

    def test_rejects_empty_and_none(self) -> None:
        """Empty and None values should be rejected."""
        assert PlanDetailContext._is_safe_back_url(None) is None
        assert PlanDetailContext._is_safe_back_url("") is None

    def test_rejects_malformed_urls(self) -> None:
        """Malformed URLs should be rejected gracefully."""
        # These should not raise exceptions
        assert PlanDetailContext._is_safe_back_url("javascript:alert(1)") is None
        assert PlanDetailContext._is_safe_back_url("data:text/html,<script>") is None

    def test_rejects_paths_not_starting_with_slash(self) -> None:
        """Relative paths without leading slash should be rejected."""
        assert PlanDetailContext._is_safe_back_url("plans") is None
        assert PlanDetailContext._is_safe_back_url("plans/123") is None


class TestPlanDetailContextFromPlanAndRequest:
    """Tests for PlanDetailContext.from_plan_and_request."""

    def _make_mock_plan(self):
        """Create a minimal mock plan for testing."""
        from unittest.mock import MagicMock

        plan = MagicMock()
        plan.id = "test-uuid-1234"
        plan.id_short = "test-uui"
        plan.file_id = 1
        plan.file_path = "/path/to/file.mkv"
        plan.filename = "file.mkv"
        plan.file_deleted = False
        plan.policy_name = "test-policy"
        plan.policy_version = 1
        plan.action_count = 3
        plan.requires_remux = False
        plan.status = "pending"
        plan.status_badge = {"class": "status-pending", "label": "Pending"}
        plan.created_at = "2024-01-01T00:00:00Z"
        plan.updated_at = "2024-01-01T00:00:00Z"
        plan.actions = []
        plan.job_id = None
        return plan

    def test_uses_default_when_referer_is_none(self) -> None:
        """Default back_url should be used when referer is None."""
        from vpo.server.ui.models.plans import PlanDetailItem

        # Create a mock PlanDetailItem
        plan = MagicMock(spec=PlanDetailItem)
        ctx = PlanDetailContext.from_plan_and_request(plan, None)
        assert ctx.back_url == "/plans"

    def test_uses_default_for_external_referer(self) -> None:
        """Default back_url should be used for external referers."""
        from vpo.server.ui.models.plans import PlanDetailItem

        plan = MagicMock(spec=PlanDetailItem)
        ctx = PlanDetailContext.from_plan_and_request(plan, "https://evil.com/plans")
        assert ctx.back_url == "/plans"

    def test_uses_safe_path_from_valid_referer(self) -> None:
        """Valid referer should have its path extracted and used."""
        from vpo.server.ui.models.plans import PlanDetailItem

        plan = MagicMock(spec=PlanDetailItem)

        ctx = PlanDetailContext.from_plan_and_request(
            plan, "http://localhost:8080/approvals"
        )
        assert ctx.back_url == "/approvals"

        ctx = PlanDetailContext.from_plan_and_request(
            plan, "http://localhost:8080/plans?status=pending"
        )
        assert ctx.back_url == "/plans"

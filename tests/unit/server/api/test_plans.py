"""Unit tests for plan API endpoints."""

from __future__ import annotations

from vpo.server.api.plans import BulkActionResponse


class TestBulkActionResponse:
    """Tests for BulkActionResponse dataclass."""

    def test_to_dict_success_only(self) -> None:
        """Response with only success field."""
        response = BulkActionResponse(success=True)
        result = response.to_dict()
        assert result == {"success": True}

    def test_to_dict_with_approved(self) -> None:
        """Response with approved count."""
        response = BulkActionResponse(success=True, approved=5)
        result = response.to_dict()
        assert result == {"success": True, "approved": 5}

    def test_to_dict_with_rejected(self) -> None:
        """Response with rejected count."""
        response = BulkActionResponse(success=True, rejected=3)
        result = response.to_dict()
        assert result == {"success": True, "rejected": 3}

    def test_to_dict_with_failures(self) -> None:
        """Response with failed count and errors."""
        errors = [
            {"plan_id": "uuid1", "error": "Not found"},
            {"plan_id": "uuid2", "error": "Already approved"},
        ]
        response = BulkActionResponse(success=True, approved=3, failed=2, errors=errors)
        result = response.to_dict()
        assert result == {
            "success": True,
            "approved": 3,
            "failed": 2,
            "errors": errors,
        }

    def test_to_dict_excludes_zero_counts(self) -> None:
        """Zero counts should not be included in output."""
        response = BulkActionResponse(success=True, approved=0, rejected=5, failed=0)
        result = response.to_dict()
        assert "approved" not in result
        assert "rejected" in result
        assert "failed" not in result


# Note: Full integration tests for the bulk API endpoints would require
# setting up aiohttp test client and mocking the database. Those tests
# should be added to the integration test suite.

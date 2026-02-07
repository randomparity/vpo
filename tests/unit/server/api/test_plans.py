"""Unit tests for plan API endpoints."""

from __future__ import annotations

from vpo.server.api.plans import BulkActionResponse


class TestBulkActionResponse:
    """Tests for BulkActionResponse dataclass."""

    def test_to_dict_success_only(self) -> None:
        """Response with only success field includes all fields with defaults."""
        response = BulkActionResponse(success=True)
        result = response.to_dict()
        assert result == {
            "success": True,
            "approved": 0,
            "rejected": 0,
            "failed": 0,
            "errors": [],
        }

    def test_to_dict_with_approved(self) -> None:
        """Response with approved count."""
        response = BulkActionResponse(success=True, approved=5)
        result = response.to_dict()
        assert result["approved"] == 5
        assert result["rejected"] == 0
        assert result["failed"] == 0
        assert result["errors"] == []

    def test_to_dict_with_rejected(self) -> None:
        """Response with rejected count."""
        response = BulkActionResponse(success=True, rejected=3)
        result = response.to_dict()
        assert result["rejected"] == 3
        assert result["approved"] == 0

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
            "rejected": 0,
            "failed": 2,
            "errors": errors,
        }

    def test_to_dict_always_includes_all_fields(self) -> None:
        """All fields are always present regardless of value."""
        response = BulkActionResponse(success=True, approved=0, rejected=5, failed=0)
        result = response.to_dict()
        assert "approved" in result
        assert "rejected" in result
        assert "failed" in result
        assert "errors" in result
        assert result["approved"] == 0
        assert result["rejected"] == 5
        assert result["failed"] == 0

    def test_to_dict_none_errors_becomes_empty_list(self) -> None:
        """None errors are normalized to empty list."""
        response = BulkActionResponse(success=True, errors=None)
        result = response.to_dict()
        assert result["errors"] == []


# Note: Full integration tests for the bulk API endpoints would require
# setting up aiohttp test client and mocking the database. Those tests
# should be added to the integration test suite.

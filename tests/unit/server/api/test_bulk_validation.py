"""Tests for BulkActionRequest Pydantic validation.

Verifies that the Pydantic model used for bulk plan approve/reject
correctly validates plan_ids: non-empty list, max 100, valid UUIDs.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from vpo.server.api.plans import MAX_BULK_BATCH_SIZE, BulkActionRequest


class TestBulkActionRequest:
    """Tests for BulkActionRequest Pydantic model."""

    def test_valid_single_uuid(self):
        """Accepts a single valid UUID."""
        plan_id = str(uuid.uuid4())
        req = BulkActionRequest(plan_ids=[plan_id])
        assert req.plan_ids == [plan_id]

    def test_valid_multiple_uuids(self):
        """Accepts multiple valid UUIDs."""
        ids = [str(uuid.uuid4()) for _ in range(5)]
        req = BulkActionRequest(plan_ids=ids)
        assert req.plan_ids == ids

    def test_rejects_empty_list(self):
        """Empty plan_ids list is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BulkActionRequest(plan_ids=[])
        assert "plan_ids" in str(exc_info.value)

    def test_rejects_oversized_list(self):
        """List exceeding MAX_BULK_BATCH_SIZE is rejected."""
        ids = [str(uuid.uuid4()) for _ in range(MAX_BULK_BATCH_SIZE + 1)]
        with pytest.raises(ValidationError) as exc_info:
            BulkActionRequest(plan_ids=ids)
        assert "plan_ids" in str(exc_info.value)

    def test_accepts_max_size_list(self):
        """List of exactly MAX_BULK_BATCH_SIZE is accepted."""
        ids = [str(uuid.uuid4()) for _ in range(MAX_BULK_BATCH_SIZE)]
        req = BulkActionRequest(plan_ids=ids)
        assert len(req.plan_ids) == MAX_BULK_BATCH_SIZE

    def test_rejects_invalid_uuid(self):
        """Invalid UUID string is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BulkActionRequest(plan_ids=["not-a-uuid"])
        assert "Invalid plan ID format" in str(exc_info.value)

    def test_rejects_mixed_valid_invalid(self):
        """Mix of valid and invalid UUIDs is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BulkActionRequest(plan_ids=[str(uuid.uuid4()), "bad"])
        assert "Invalid plan ID format" in str(exc_info.value)

    def test_rejects_missing_field(self):
        """Missing plan_ids field is rejected."""
        with pytest.raises(ValidationError):
            BulkActionRequest()  # type: ignore[call-arg]

    def test_rejects_non_list(self):
        """Non-list plan_ids is rejected."""
        with pytest.raises(ValidationError):
            BulkActionRequest(plan_ids="not-a-list")  # type: ignore[arg-type]

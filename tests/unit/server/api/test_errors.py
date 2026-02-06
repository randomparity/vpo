"""Unit tests for server/api/errors.py."""

from __future__ import annotations

import json

from vpo.server.api.errors import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    NOT_FOUND,
    api_error,
)


class TestApiError:
    """Tests for the api_error helper function."""

    def test_returns_json_response_with_error_and_code(self):
        """Response body contains error message and code."""
        resp = api_error("Bad input", code=INVALID_REQUEST)

        body = json.loads(resp.body)
        assert body == {"error": "Bad input", "code": "INVALID_REQUEST"}

    def test_default_status_is_400(self):
        """Default HTTP status code is 400."""
        resp = api_error("Bad input", code=INVALID_REQUEST)

        assert resp.status == 400

    def test_custom_status_code(self):
        """Accepts custom HTTP status codes."""
        resp = api_error("Not found", code=NOT_FOUND, status=404)

        assert resp.status == 404

    def test_includes_details_when_provided(self):
        """Details field is included when passed."""
        resp = api_error(
            "Server error",
            code=INTERNAL_ERROR,
            status=500,
            details="Connection refused",
        )

        body = json.loads(resp.body)
        assert body == {
            "error": "Server error",
            "code": "INTERNAL_ERROR",
            "details": "Connection refused",
        }

    def test_omits_details_when_none(self):
        """Details field is absent when not provided."""
        resp = api_error("Bad input", code=INVALID_REQUEST)

        body = json.loads(resp.body)
        assert "details" not in body

    def test_details_can_be_list(self):
        """Details can be a list (e.g., validation errors)."""
        errors = [{"field": "name", "message": "required"}]
        resp = api_error("Validation failed", code=INVALID_REQUEST, details=errors)

        body = json.loads(resp.body)
        assert body["details"] == errors

    def test_details_can_be_dict(self):
        """Details can be a dict."""
        resp = api_error("Error", code=INTERNAL_ERROR, details={"key": "value"})

        body = json.loads(resp.body)
        assert body["details"] == {"key": "value"}

    def test_content_type_is_json(self):
        """Response content type is application/json."""
        resp = api_error("Bad input", code=INVALID_REQUEST)

        assert resp.content_type == "application/json"

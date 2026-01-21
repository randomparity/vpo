"""Tests for core validation utilities."""

from vpo.core.validation import is_valid_uuid


class TestIsValidUuid:
    """Tests for is_valid_uuid function."""

    def test_valid_uuid_lowercase(self):
        """is_valid_uuid returns True for valid lowercase UUID."""
        assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_valid_uuid_uppercase(self):
        """is_valid_uuid returns True for valid uppercase UUID."""
        assert is_valid_uuid("550E8400-E29B-41D4-A716-446655440000") is True

    def test_valid_uuid_mixed_case(self):
        """is_valid_uuid returns True for valid mixed case UUID."""
        assert is_valid_uuid("550E8400-e29b-41D4-a716-446655440000") is True

    def test_valid_uuid_v4(self):
        """is_valid_uuid returns True for UUIDv4."""
        assert is_valid_uuid("f47ac10b-58cc-4372-a567-0e02b2c3d479") is True

    def test_valid_uuid_v1(self):
        """is_valid_uuid returns True for UUIDv1."""
        assert is_valid_uuid("6ba7b810-9dad-11d1-80b4-00c04fd430c8") is True

    def test_invalid_empty_string(self):
        """is_valid_uuid returns False for empty string."""
        assert is_valid_uuid("") is False

    def test_invalid_short_string(self):
        """is_valid_uuid returns False for too-short string."""
        assert is_valid_uuid("550e8400-e29b-41d4") is False

    def test_invalid_long_string(self):
        """is_valid_uuid returns False for too-long string."""
        assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000-extra") is False

    def test_invalid_missing_dashes(self):
        """is_valid_uuid returns False for UUID without dashes."""
        # Test UUID without dashes (32 hex chars in a row)
        no_dashes = "550e8400e29b41d4a716446655440000"  # pragma: allowlist secret
        assert is_valid_uuid(no_dashes) is False

    def test_invalid_wrong_dash_positions(self):
        """is_valid_uuid returns False for wrong dash positions."""
        assert is_valid_uuid("550e-8400-e29b-41d4-a716-446655440000") is False

    def test_invalid_non_hex_characters(self):
        """is_valid_uuid returns False for non-hex characters."""
        assert is_valid_uuid("550e8400-e29b-41d4-a716-44665544000g") is False
        assert is_valid_uuid("550e8400-e29b-41d4-a716-44665544000z") is False

    def test_invalid_with_braces(self):
        """is_valid_uuid returns False for UUID with braces."""
        assert is_valid_uuid("{550e8400-e29b-41d4-a716-446655440000}") is False

    def test_invalid_with_urn_prefix(self):
        """is_valid_uuid returns False for UUID with URN prefix."""
        assert is_valid_uuid("urn:uuid:550e8400-e29b-41d4-a716-446655440000") is False

    def test_invalid_whitespace(self):
        """is_valid_uuid returns False for UUID with whitespace."""
        assert is_valid_uuid(" 550e8400-e29b-41d4-a716-446655440000") is False
        assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000 ") is False

    def test_invalid_random_string(self):
        """is_valid_uuid returns False for random string."""
        assert is_valid_uuid("not-a-uuid-at-all") is False
        assert is_valid_uuid("hello world") is False

    def test_nil_uuid_valid(self):
        """is_valid_uuid returns True for nil UUID."""
        assert is_valid_uuid("00000000-0000-0000-0000-000000000000") is True

    def test_max_uuid_valid(self):
        """is_valid_uuid returns True for all-f UUID."""
        assert is_valid_uuid("ffffffff-ffff-ffff-ffff-ffffffffffff") is True

"""Unit tests for security headers configuration."""

from vpo.server.ui.routes import SECURITY_HEADERS


class TestSecurityHeaders:
    """Tests for SECURITY_HEADERS configuration."""

    def test_security_headers_includes_csp(self) -> None:
        """Test that SECURITY_HEADERS includes Content-Security-Policy."""
        assert "Content-Security-Policy" in SECURITY_HEADERS

    def test_csp_includes_default_src(self) -> None:
        """Test that CSP includes default-src directive."""
        csp = SECURITY_HEADERS.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp

    def test_csp_blocks_object_src(self) -> None:
        """Test that CSP blocks object/embed elements."""
        csp = SECURITY_HEADERS.get("Content-Security-Policy", "")
        assert "object-src 'none'" in csp

    def test_csp_restricts_frame_ancestors(self) -> None:
        """Test that CSP restricts framing to same origin."""
        csp = SECURITY_HEADERS.get("Content-Security-Policy", "")
        assert "frame-ancestors 'self'" in csp

    def test_security_headers_includes_required_headers(self) -> None:
        """Test that all required security headers are present."""
        required = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Referrer-Policy",
            "Content-Security-Policy",
        ]
        for header in required:
            assert header in SECURITY_HEADERS, f"Missing header: {header}"

    def test_x_content_type_options_nosniff(self) -> None:
        """Test X-Content-Type-Options is set to nosniff."""
        assert SECURITY_HEADERS.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options_sameorigin(self) -> None:
        """Test X-Frame-Options is set to SAMEORIGIN."""
        assert SECURITY_HEADERS.get("X-Frame-Options") == "SAMEORIGIN"

    def test_csp_no_unsafe_inline_script(self) -> None:
        """Test that CSP script-src does not allow unsafe-inline."""
        csp = SECURITY_HEADERS.get("Content-Security-Policy", "")
        # Extract script-src directive
        for directive in csp.split(";"):
            if "script-src" in directive:
                assert "'unsafe-inline'" not in directive
                break

    def test_csp_no_unsafe_inline_style(self) -> None:
        """Test that CSP style-src does not allow unsafe-inline."""
        csp = SECURITY_HEADERS.get("Content-Security-Policy", "")
        # Extract style-src directive
        for directive in csp.split(";"):
            if "style-src" in directive:
                assert "'unsafe-inline'" not in directive
                break

    def test_csp_includes_base_uri(self) -> None:
        """Test that CSP includes base-uri directive."""
        csp = SECURITY_HEADERS.get("Content-Security-Policy", "")
        assert "base-uri 'self'" in csp

    def test_csp_includes_form_action(self) -> None:
        """Test that CSP includes form-action directive."""
        csp = SECURITY_HEADERS.get("Content-Security-Policy", "")
        assert "form-action 'self'" in csp

    def test_permissions_policy_header(self) -> None:
        """Test that Permissions-Policy header is present."""
        assert "Permissions-Policy" in SECURITY_HEADERS
        policy = SECURITY_HEADERS["Permissions-Policy"]
        assert "camera=()" in policy
        assert "microphone=()" in policy
        assert "geolocation=()" in policy
        assert "payment=()" in policy

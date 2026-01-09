"""Tests for vpo package."""


def test_package_imports():
    """Test that the package can be imported successfully."""
    import vpo

    assert vpo is not None


def test_package_version():
    """Test that the package has a version string."""
    from vpo import __version__

    assert __version__ == "0.1.0"

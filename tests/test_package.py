"""Tests for video_policy_orchestrator package."""


def test_package_imports():
    """Test that the package can be imported successfully."""
    import video_policy_orchestrator

    assert video_policy_orchestrator is not None


def test_package_version():
    """Test that the package has a version string."""
    from video_policy_orchestrator import __version__

    assert __version__ == "0.1.0"

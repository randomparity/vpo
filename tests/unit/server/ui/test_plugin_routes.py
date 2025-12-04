"""Unit tests for plugin data browser route handlers and models."""

from video_policy_orchestrator.server.ui.models import (
    FilePluginDataResponse,
    PluginDataContext,
    PluginFileItem,
    PluginFilesResponse,
    PluginInfo,
    PluginListResponse,
)


class TestPluginInfo:
    """Tests for PluginInfo dataclass."""

    def test_plugin_info_to_dict(self) -> None:
        """Test PluginInfo serializes correctly to dictionary."""
        info = PluginInfo(
            name="whisper-transcriber",
            version="1.0.0",
            enabled=True,
            is_builtin=True,
            events=["file.scanned"],
        )

        data = info.to_dict()

        assert data["name"] == "whisper-transcriber"
        assert data["version"] == "1.0.0"
        assert data["enabled"] is True
        assert data["is_builtin"] is True
        assert data["events"] == ["file.scanned"]

    def test_plugin_info_with_multiple_events(self) -> None:
        """Test PluginInfo with multiple events."""
        info = PluginInfo(
            name="multi-plugin",
            version="2.0.0",
            enabled=False,
            is_builtin=False,
            events=["file.scanned", "plan.before_execute", "plan.after_execute"],
        )

        data = info.to_dict()
        assert len(data["events"]) == 3


class TestPluginListResponse:
    """Tests for PluginListResponse dataclass."""

    def test_plugin_list_response_to_dict(self) -> None:
        """Test PluginListResponse serializes correctly."""
        plugins = [
            PluginInfo(
                name="plugin-a",
                version="1.0.0",
                enabled=True,
                is_builtin=True,
                events=["file.scanned"],
            ),
            PluginInfo(
                name="plugin-b",
                version="2.0.0",
                enabled=False,
                is_builtin=False,
                events=[],
            ),
        ]

        response = PluginListResponse(plugins=plugins, total=2)
        data = response.to_dict()

        assert len(data["plugins"]) == 2
        assert data["total"] == 2
        assert data["plugins"][0]["name"] == "plugin-a"
        assert data["plugins"][1]["name"] == "plugin-b"

    def test_plugin_list_response_empty(self) -> None:
        """Test PluginListResponse with no plugins."""
        response = PluginListResponse(plugins=[], total=0)
        data = response.to_dict()

        assert data["plugins"] == []
        assert data["total"] == 0


class TestPluginFileItem:
    """Tests for PluginFileItem dataclass."""

    def test_plugin_file_item_to_dict(self) -> None:
        """Test PluginFileItem serializes correctly."""
        item = PluginFileItem(
            id=123,
            filename="test.mkv",
            path="/path/to/test.mkv",
            scan_status="ok",
            plugin_data={"language": "en", "confidence": 0.95},
        )

        data = item.to_dict()

        assert data["id"] == 123
        assert data["filename"] == "test.mkv"
        assert data["path"] == "/path/to/test.mkv"
        assert data["scan_status"] == "ok"
        assert data["plugin_data"] == {"language": "en", "confidence": 0.95}

    def test_plugin_file_item_with_empty_plugin_data(self) -> None:
        """Test PluginFileItem with empty plugin data."""
        item = PluginFileItem(
            id=1,
            filename="test.mkv",
            path="/test.mkv",
            scan_status="ok",
            plugin_data={},
        )

        data = item.to_dict()
        assert data["plugin_data"] == {}


class TestPluginFilesResponse:
    """Tests for PluginFilesResponse dataclass."""

    def test_plugin_files_response_to_dict(self) -> None:
        """Test PluginFilesResponse serializes correctly."""
        files = [
            PluginFileItem(
                id=1,
                filename="file1.mkv",
                path="/path/file1.mkv",
                scan_status="ok",
                plugin_data={"language": "en"},
            ),
            PluginFileItem(
                id=2,
                filename="file2.mkv",
                path="/path/file2.mkv",
                scan_status="ok",
                plugin_data={"language": "fr"},
            ),
        ]

        response = PluginFilesResponse(
            plugin_name="whisper-transcriber",
            files=files,
            total=10,
            limit=50,
            offset=0,
        )
        data = response.to_dict()

        assert data["plugin_name"] == "whisper-transcriber"
        assert len(data["files"]) == 2
        assert data["total"] == 10
        assert data["limit"] == 50
        assert data["offset"] == 0


class TestFilePluginDataResponse:
    """Tests for FilePluginDataResponse dataclass."""

    def test_file_plugin_data_response_to_dict(self) -> None:
        """Test FilePluginDataResponse serializes correctly."""
        response = FilePluginDataResponse(
            file_id=123,
            filename="test.mkv",
            plugin_data={
                "whisper-transcriber": {"language": "en"},
                "other-plugin": {"processed": True},
            },
        )
        data = response.to_dict()

        assert data["file_id"] == 123
        assert data["filename"] == "test.mkv"
        assert len(data["plugin_data"]) == 2
        assert data["plugin_data"]["whisper-transcriber"] == {"language": "en"}

    def test_file_plugin_data_response_empty_data(self) -> None:
        """Test FilePluginDataResponse with no plugin data."""
        response = FilePluginDataResponse(
            file_id=1,
            filename="test.mkv",
            plugin_data={},
        )
        data = response.to_dict()

        assert data["plugin_data"] == {}


class TestPluginDataContext:
    """Tests for PluginDataContext dataclass."""

    def test_plugin_data_context_to_dict(self) -> None:
        """Test PluginDataContext serializes correctly."""
        context = PluginDataContext(
            file_id=123,
            filename="test.mkv",
            file_path="/path/to/test.mkv",
            plugin_data={
                "whisper-transcriber": {"language": "en", "confidence": 0.95},
            },
            plugin_count=1,
        )
        data = context.to_dict()

        assert data["file_id"] == 123
        assert data["filename"] == "test.mkv"
        assert data["file_path"] == "/path/to/test.mkv"
        assert data["plugin_count"] == 1
        assert "whisper-transcriber" in data["plugin_data"]

    def test_plugin_data_context_multiple_plugins(self) -> None:
        """Test PluginDataContext with multiple plugins."""
        context = PluginDataContext(
            file_id=1,
            filename="test.mkv",
            file_path="/test.mkv",
            plugin_data={
                "plugin-a": {"field": "value"},
                "plugin-b": {"other": 123},
                "plugin-c": {"flag": True},
            },
            plugin_count=3,
        )
        data = context.to_dict()

        assert data["plugin_count"] == 3
        assert len(data["plugin_data"]) == 3


class TestFileDetailItemPluginMetadata:
    """Tests for FileDetailItem plugin_metadata field."""

    def test_file_detail_item_has_plugin_data_true(self) -> None:
        """Test has_plugin_data returns True when metadata present."""
        from video_policy_orchestrator.server.ui.models import (
            FileDetailItem,
        )

        item = FileDetailItem(
            id=1,
            path="/test.mkv",
            filename="test.mkv",
            directory="/",
            extension=".mkv",
            container_format="matroska",
            size_bytes=1000,
            size_human="1 KB",
            modified_at="2024-01-01T00:00:00Z",
            scanned_at="2024-01-01T00:00:00Z",
            scan_status="ok",
            scan_error=None,
            scan_job_id=None,
            video_tracks=[],
            audio_tracks=[],
            subtitle_tracks=[],
            other_tracks=[],
            plugin_metadata={"plugin": {"data": "value"}},
        )

        assert item.has_plugin_data is True
        assert item.plugin_count == 1

    def test_file_detail_item_has_plugin_data_false(self) -> None:
        """Test has_plugin_data returns False when no metadata."""
        from video_policy_orchestrator.server.ui.models import (
            FileDetailItem,
        )

        item = FileDetailItem(
            id=1,
            path="/test.mkv",
            filename="test.mkv",
            directory="/",
            extension=".mkv",
            container_format="matroska",
            size_bytes=1000,
            size_human="1 KB",
            modified_at="2024-01-01T00:00:00Z",
            scanned_at="2024-01-01T00:00:00Z",
            scan_status="ok",
            scan_error=None,
            scan_job_id=None,
            video_tracks=[],
            audio_tracks=[],
            subtitle_tracks=[],
            other_tracks=[],
            plugin_metadata=None,
        )

        assert item.has_plugin_data is False
        assert item.plugin_count == 0

    def test_file_detail_item_to_dict_includes_plugin_metadata(self) -> None:
        """Test to_dict includes plugin metadata fields."""
        from video_policy_orchestrator.server.ui.models import (
            FileDetailItem,
        )

        item = FileDetailItem(
            id=1,
            path="/test.mkv",
            filename="test.mkv",
            directory="/",
            extension=".mkv",
            container_format="matroska",
            size_bytes=1000,
            size_human="1 KB",
            modified_at="2024-01-01T00:00:00Z",
            scanned_at="2024-01-01T00:00:00Z",
            scan_status="ok",
            scan_error=None,
            scan_job_id=None,
            video_tracks=[],
            audio_tracks=[],
            subtitle_tracks=[],
            other_tracks=[],
            plugin_metadata={"plugin": {"data": "value"}},
        )

        data = item.to_dict()
        assert "plugin_metadata" in data
        assert "has_plugin_data" in data
        assert "plugin_count" in data
        assert data["has_plugin_data"] is True
        assert data["plugin_count"] == 1

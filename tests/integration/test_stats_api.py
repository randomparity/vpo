"""Integration tests for stats API endpoints.

Tests the /api/stats/* endpoints including trends and encoder tracking.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from aiohttp.test_utils import AioHTTPTestCase

from vpo.db.schema import initialize_database
from vpo.server.app import create_app

if TYPE_CHECKING:
    from aiohttp import web


class TestStatsTrendsEndpoint(AioHTTPTestCase):
    """Integration tests for /api/stats/trends endpoint."""

    async def get_application(self) -> web.Application:
        """Create application with test database."""
        # Create temp db file
        self._db_path = Path(f"/tmp/vpo_test_{uuid4().hex}.db")
        conn = sqlite3.connect(str(self._db_path))
        initialize_database(conn)
        conn.close()
        return create_app(db_path=self._db_path, auth_token=None)

    async def tearDownAsync(self) -> None:
        """Clean up test database."""
        await super().tearDownAsync()
        if hasattr(self, "_db_path") and self._db_path.exists():
            self._db_path.unlink()

    def _insert_test_stats(
        self,
        file_id: str,
        policy_name: str,
        processed_at: datetime,
        success: bool = True,
        encoder_type: str | None = None,
    ) -> int:
        """Insert test processing stats record.

        Returns the file_id (integer) for use in processing_stats.
        """
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()

        # Insert a file record with correct schema
        file_path = f"/test/file_{file_id}.mkv"
        cursor.execute(
            """
            INSERT INTO files (
                path, filename, directory, extension,
                size_bytes, modified_at, scanned_at, scan_status
            ) VALUES (?, 'file.mkv', '/test', '.mkv', 1000000, ?, ?, 'completed')
            """,
            (file_path, processed_at.isoformat(), processed_at.isoformat()),
        )
        db_file_id = cursor.lastrowid

        stats_id = uuid4().hex
        cursor.execute(
            """
            INSERT INTO processing_stats (
                id, file_id, policy_name, processed_at, success,
                size_before, size_after, size_change, duration_seconds,
                encoder_type
            ) VALUES (?, ?, ?, ?, ?, 1000000, 800000, 200000, 10.5, ?)
            """,
            (
                stats_id,
                db_file_id,
                policy_name,
                processed_at.isoformat(),
                1 if success else 0,
                encoder_type,
            ),
        )
        conn.commit()
        conn.close()
        return db_file_id

    async def test_trends_endpoint_returns_json(self) -> None:
        """Trends endpoint returns valid JSON array."""
        async with self.client.get("/api/stats/trends") as response:
            assert response.status == 200
            data = await response.json()
            assert isinstance(data, list)

    async def test_trends_with_data(self) -> None:
        """Trends endpoint returns aggregated data."""
        file_id = uuid4().hex
        now = datetime.now(timezone.utc)

        # Insert test data
        self._insert_test_stats(file_id, "test.yaml", now, success=True)
        self._insert_test_stats(
            uuid4().hex, "test.yaml", now - timedelta(hours=1), success=True
        )
        self._insert_test_stats(
            uuid4().hex, "test.yaml", now - timedelta(hours=2), success=False
        )

        async with self.client.get("/api/stats/trends?since=24h") as response:
            assert response.status == 200
            data = await response.json()
            assert len(data) >= 1

            # Check structure of response
            if data:
                point = data[0]
                assert "date" in point
                assert "files_processed" in point
                assert "success_count" in point
                assert "fail_count" in point

    async def test_trends_respects_since_parameter(self) -> None:
        """Trends endpoint respects the since filter."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(days=60)  # Beyond 30d filter

        # Insert old and new data
        self._insert_test_stats(uuid4().hex, "test.yaml", now, success=True)
        self._insert_test_stats(uuid4().hex, "test.yaml", old_time, success=True)

        # Query for last 7 days - should only get the recent one
        async with self.client.get("/api/stats/trends?since=7d") as response:
            assert response.status == 200
            data = await response.json()

            # Count total records using correct field name
            total_count = sum(point["files_processed"] for point in data)
            assert total_count == 1

    async def test_trends_groups_by_day(self) -> None:
        """Trends endpoint groups data by day."""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)

        # Insert data for two different days
        self._insert_test_stats(uuid4().hex, "test.yaml", now, success=True)
        self._insert_test_stats(uuid4().hex, "test.yaml", yesterday, success=True)

        async with self.client.get("/api/stats/trends?since=7d&group_by=day") as resp:
            assert resp.status == 200
            data = await resp.json()

            # Should have at least 2 different dates
            dates = {point["date"] for point in data}
            assert len(dates) >= 2

    async def test_trends_groups_by_week(self) -> None:
        """Trends endpoint groups data by week."""
        now = datetime.now(timezone.utc)

        # Insert data
        self._insert_test_stats(uuid4().hex, "test.yaml", now, success=True)

        async with self.client.get("/api/stats/trends?since=30d&group_by=week") as resp:
            assert resp.status == 200
            data = await resp.json()

            # Should have at least 1 data point with week format
            assert len(data) >= 1
            if data:
                # Week format should contain 'W' for week number
                assert "W" in data[0]["date"]

    async def test_trends_groups_by_month(self) -> None:
        """Trends endpoint groups data by month."""
        now = datetime.now(timezone.utc)

        # Insert data
        self._insert_test_stats(uuid4().hex, "test.yaml", now, success=True)

        # Use 30d since that's the max supported value
        async with self.client.get(
            "/api/stats/trends?since=30d&group_by=month"
        ) as resp:
            assert resp.status == 200
            data = await resp.json()

            # Should have at least 1 data point
            assert len(data) >= 1
            if data:
                # Month format should be YYYY-MM
                assert len(data[0]["date"]) == 7  # e.g., "2026-01"
                assert "-" in data[0]["date"]

    async def test_trends_invalid_since_format(self) -> None:
        """Trends endpoint handles invalid since parameter."""
        async with self.client.get("/api/stats/trends?since=invalid") as response:
            assert response.status == 400


class TestStatsEncoderTypeEndpoint(AioHTTPTestCase):
    """Integration tests for encoder type in stats endpoints."""

    async def get_application(self) -> web.Application:
        """Create application with test database."""
        self._db_path = Path(f"/tmp/vpo_test_{uuid4().hex}.db")
        conn = sqlite3.connect(str(self._db_path))
        initialize_database(conn)
        conn.close()
        return create_app(db_path=self._db_path, auth_token=None)

    async def tearDownAsync(self) -> None:
        """Clean up test database."""
        await super().tearDownAsync()
        if hasattr(self, "_db_path") and self._db_path.exists():
            self._db_path.unlink()

    def _insert_test_stats_with_encoder(self, encoder_type: str | None) -> None:
        """Insert test processing stats with encoder type."""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()

        file_id = uuid4().hex
        now = datetime.now(timezone.utc)
        file_path = f"/test/file_{file_id}.mkv"

        cursor.execute(
            """
            INSERT INTO files (
                path, filename, directory, extension,
                size_bytes, modified_at, scanned_at, scan_status
            ) VALUES (?, 'file.mkv', '/test', '.mkv', 1000000, ?, ?, 'completed')
            """,
            (file_path, now.isoformat(), now.isoformat()),
        )
        db_file_id = cursor.lastrowid

        stats_id = uuid4().hex
        cursor.execute(
            """
            INSERT INTO processing_stats (
                id, file_id, policy_name, processed_at, success,
                size_before, size_after, size_change, duration_seconds,
                encoder_type
            ) VALUES (?, ?, 'test.yaml', ?, 1, 1000000, 800000, 200000, 10.5, ?)
            """,
            (stats_id, db_file_id, now.isoformat(), encoder_type),
        )
        conn.commit()
        conn.close()

    async def test_summary_includes_encoder_counts(self) -> None:
        """Stats summary includes hardware/software encoder counts."""
        # Insert mix of encoder types
        self._insert_test_stats_with_encoder("hardware")
        self._insert_test_stats_with_encoder("hardware")
        self._insert_test_stats_with_encoder("software")
        self._insert_test_stats_with_encoder(None)  # Unknown

        async with self.client.get("/api/stats/summary") as response:
            assert response.status == 200
            data = await response.json()

            assert "hardware_encodes" in data
            assert "software_encodes" in data
            assert data["hardware_encodes"] == 2
            assert data["software_encodes"] == 1

    async def test_recent_includes_encoder_type(self) -> None:
        """Recent stats include encoder type field."""
        self._insert_test_stats_with_encoder("hardware")

        async with self.client.get("/api/stats/recent") as response:
            assert response.status == 200
            data = await response.json()

            assert len(data) >= 1
            assert "encoder_type" in data[0]
            assert data[0]["encoder_type"] == "hardware"

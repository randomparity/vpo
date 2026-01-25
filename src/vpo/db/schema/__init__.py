"""Database schema management for Video Policy Orchestrator.

This package provides schema definition, version management, and migrations
for the VPO SQLite database.

Module organization:
- definition.py: Schema DDL and creation (SCHEMA_VERSION, SCHEMA_SQL, create_schema)
- version.py: Version query helper (get_schema_version)
- initialize.py: Database initialization orchestration (initialize_database)
- migrations/: All schema migration functions

Usage:
    from vpo.db.schema import initialize_database, SCHEMA_VERSION
    from vpo.db.schema import create_schema, get_schema_version
"""

from .definition import SCHEMA_SQL, SCHEMA_VERSION, create_schema
from .initialize import initialize_database
from .migrations import (
    migrate_v1_to_v2,
    migrate_v2_to_v3,
    migrate_v3_to_v4,
    migrate_v4_to_v5,
    migrate_v5_to_v6,
    migrate_v6_to_v7,
    migrate_v7_to_v8,
    migrate_v8_to_v9,
    migrate_v9_to_v10,
    migrate_v10_to_v11,
    migrate_v11_to_v12,
    migrate_v12_to_v13,
    migrate_v13_to_v14,
    migrate_v14_to_v15,
    migrate_v15_to_v16,
    migrate_v16_to_v17,
    migrate_v17_to_v18,
    migrate_v18_to_v19,
    migrate_v19_to_v20,
    migrate_v20_to_v21,
    migrate_v21_to_v22,
    migrate_v22_to_v23,
    migrate_v23_to_v24,
)
from .version import get_schema_version

__all__ = [
    # Constants
    "SCHEMA_VERSION",
    "SCHEMA_SQL",
    # Core functions
    "create_schema",
    "get_schema_version",
    "initialize_database",
    # Migrations (exported for testing)
    "migrate_v1_to_v2",
    "migrate_v2_to_v3",
    "migrate_v3_to_v4",
    "migrate_v4_to_v5",
    "migrate_v5_to_v6",
    "migrate_v6_to_v7",
    "migrate_v7_to_v8",
    "migrate_v8_to_v9",
    "migrate_v9_to_v10",
    "migrate_v10_to_v11",
    "migrate_v11_to_v12",
    "migrate_v12_to_v13",
    "migrate_v13_to_v14",
    "migrate_v14_to_v15",
    "migrate_v15_to_v16",
    "migrate_v16_to_v17",
    "migrate_v17_to_v18",
    "migrate_v18_to_v19",
    "migrate_v19_to_v20",
    "migrate_v20_to_v21",
    "migrate_v21_to_v22",
    "migrate_v22_to_v23",
    "migrate_v23_to_v24",
]

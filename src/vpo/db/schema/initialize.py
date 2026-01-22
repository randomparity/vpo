"""Database initialization for Video Policy Orchestrator.

This module provides the main entry point for database initialization,
orchestrating schema creation and migrations.
"""

import sqlite3

from .definition import SCHEMA_VERSION, create_schema
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
)
from .version import get_schema_version


def initialize_database(conn: sqlite3.Connection) -> None:
    """Initialize the database with schema, creating tables if needed.

    Args:
        conn: An open database connection.
    """
    current_version = get_schema_version(conn)

    if current_version is None:
        create_schema(conn)
    elif current_version < SCHEMA_VERSION:
        # Run migrations sequentially
        if current_version == 1:
            migrate_v1_to_v2(conn)
            current_version = 2
        if current_version == 2:
            migrate_v2_to_v3(conn)
            current_version = 3
        if current_version == 3:
            migrate_v3_to_v4(conn)
            current_version = 4
        if current_version == 4:
            migrate_v4_to_v5(conn)
            current_version = 5
        if current_version == 5:
            migrate_v5_to_v6(conn)
            current_version = 6
        if current_version == 6:
            migrate_v6_to_v7(conn)
            current_version = 7
        if current_version == 7:
            migrate_v7_to_v8(conn)
            current_version = 8
        if current_version == 8:
            migrate_v8_to_v9(conn)
            current_version = 9
        if current_version == 9:
            migrate_v9_to_v10(conn)
            current_version = 10
        if current_version == 10:
            migrate_v10_to_v11(conn)
            current_version = 11
        if current_version == 11:
            migrate_v11_to_v12(conn)
            current_version = 12
        if current_version == 12:
            migrate_v12_to_v13(conn)
            current_version = 13
        if current_version == 13:
            migrate_v13_to_v14(conn)
            current_version = 14
        if current_version == 14:
            migrate_v14_to_v15(conn)
            current_version = 15
        if current_version == 15:
            migrate_v15_to_v16(conn)
            current_version = 16
        if current_version == 16:
            migrate_v16_to_v17(conn)
            current_version = 17
        if current_version == 17:
            migrate_v17_to_v18(conn)
            current_version = 18
        if current_version == 18:
            migrate_v18_to_v19(conn)
            current_version = 19
        if current_version == 19:
            migrate_v19_to_v20(conn)
            current_version = 20
        if current_version == 20:
            migrate_v20_to_v21(conn)

"""Database migrations for Video Policy Orchestrator.

This package contains all schema migrations organized by version ranges.
Each migration function is idempotent and safe to run multiple times.

Modules:
- v01_to_v05: Core schema migrations (v1→v5)
- v06_to_v10: Jobs and indexing migrations (v6→v10)
- v11_to_v15: Language analysis migrations (v11→v15)
- v16_to_v20: Stats and classification migrations (v16→v20)
- v21_to_v25: Enhanced statistics migrations (v21→v25)
"""

from .v01_to_v05 import (
    migrate_v1_to_v2,
    migrate_v2_to_v3,
    migrate_v3_to_v4,
    migrate_v4_to_v5,
)
from .v06_to_v10 import (
    migrate_v5_to_v6,
    migrate_v6_to_v7,
    migrate_v7_to_v8,
    migrate_v8_to_v9,
    migrate_v9_to_v10,
)
from .v11_to_v15 import (
    migrate_v10_to_v11,
    migrate_v11_to_v12,
    migrate_v12_to_v13,
    migrate_v13_to_v14,
    migrate_v14_to_v15,
)
from .v16_to_v20 import (
    migrate_v15_to_v16,
    migrate_v16_to_v17,
    migrate_v17_to_v18,
    migrate_v18_to_v19,
    migrate_v19_to_v20,
)
from .v21_to_v25 import (
    migrate_v20_to_v21,
)

__all__ = [
    # v1 to v5
    "migrate_v1_to_v2",
    "migrate_v2_to_v3",
    "migrate_v3_to_v4",
    "migrate_v4_to_v5",
    # v5 to v10
    "migrate_v5_to_v6",
    "migrate_v6_to_v7",
    "migrate_v7_to_v8",
    "migrate_v8_to_v9",
    "migrate_v9_to_v10",
    # v10 to v15
    "migrate_v10_to_v11",
    "migrate_v11_to_v12",
    "migrate_v12_to_v13",
    "migrate_v13_to_v14",
    "migrate_v14_to_v15",
    # v15 to v20
    "migrate_v15_to_v16",
    "migrate_v16_to_v17",
    "migrate_v17_to_v18",
    "migrate_v18_to_v19",
    "migrate_v19_to_v20",
    # v20 to v25
    "migrate_v20_to_v21",
]

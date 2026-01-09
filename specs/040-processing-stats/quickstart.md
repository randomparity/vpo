# Quickstart: Processing Statistics and Metrics Tracking

This guide provides a quick reference for implementing the processing statistics feature.

## Implementation Order

### Phase 1: Foundation (Database + Core)

1. **Schema Migration** (`db/schema.py`)
   ```python
   # Add to SCHEMA_SQL
   PROCESSING_STATS_SQL = """
   CREATE TABLE IF NOT EXISTS processing_stats (...);
   CREATE TABLE IF NOT EXISTS action_results (...);
   CREATE TABLE IF NOT EXISTS performance_metrics (...);
   """

   # Add migration function
   def migrate_v17_to_v18(conn): ...

   # Update initialize_database()
   if current_version == 17:
       migrate_v17_to_v18(conn)
       current_version = 18
   ```

2. **Data Types** (`db/types.py`)
   ```python
   @dataclass
   class ProcessingStatsRecord:
       id: str  # UUIDv4
       file_id: int
       processed_at: str
       # ... (see data-model.md for full spec)

   @dataclass
   class ActionResultRecord: ...

   @dataclass
   class PerformanceMetricsRecord: ...
   ```

3. **CRUD Queries** (`db/queries.py`)
   ```python
   def insert_processing_stats(conn, stats: ProcessingStatsRecord) -> str: ...
   def insert_action_result(conn, result: ActionResultRecord) -> int: ...
   def insert_performance_metric(conn, metric: PerformanceMetricsRecord) -> int: ...
   def get_processing_stats_by_id(conn, stats_id: str) -> ProcessingStatsRecord | None: ...
   def get_processing_stats_for_file(conn, file_id: int) -> list[ProcessingStatsRecord]: ...
   def delete_processing_stats_before(conn, before_date: str) -> int: ...
   ```

### Phase 2: Statistics Capture

4. **Extend Workflow Processor** (`workflow/v11_processor.py`)
   ```python
   def process_file(self, file_path: Path) -> FileProcessingResult:
       # Capture before state
       size_before = file_path.stat().st_size
       tracks_before = self._count_tracks(file_path)
       hash_before = self._compute_hash(file_path)

       # Process file (existing logic)
       result = self._process_phases(file_path)

       # Capture after state
       size_after = file_path.stat().st_size
       tracks_after = self._count_tracks(file_path)
       hash_after = self._compute_hash(file_path)

       # Persist statistics
       stats = ProcessingStatsRecord(
           id=str(uuid.uuid4()),
           file_id=file_id,
           processed_at=datetime.now(timezone.utc).isoformat(),
           policy_name=self.policy_name,
           size_before=size_before,
           size_after=size_after,
           # ...
       )
       insert_processing_stats(self.conn, stats)

       return result
   ```

5. **Capture Per-Action Results**
   ```python
   # In phase executor, wrap each action
   for action in planned_actions:
       start_time = time.perf_counter()
       try:
           result = execute_action(action)
           success = True
       except Exception as e:
           success = False
           message = str(e)

       action_result = ActionResultRecord(
           stats_id=stats_id,
           action_type=action.type,
           track_type=action.track_type,
           before_state=json.dumps(action.before_state),
           after_state=json.dumps(action.after_state),
           success=success,
           duration_ms=int((time.perf_counter() - start_time) * 1000),
       )
       insert_action_result(conn, action_result)
   ```

### Phase 3: Aggregate Queries

6. **View Queries** (`db/views.py` or `db/stats.py`)
   ```python
   def get_stats_summary(
       conn,
       since: str | None = None,
       until: str | None = None,
   ) -> StatsSummary:
       """Get aggregate statistics."""
       query = """
           SELECT
               COUNT(*) as total_files,
               SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
               SUM(size_before) as total_before,
               SUM(size_after) as total_after,
               SUM(size_change) as total_saved,
               AVG(duration_seconds) as avg_duration,
               -- ... more aggregates
           FROM processing_stats
           WHERE 1=1
       """
       # Add time filters if provided
       # Execute and return StatsSummary dataclass

   def get_policy_stats(conn, policy_name: str | None = None) -> list[PolicyStats]: ...
   def get_file_processing_history(conn, file_id: int) -> list[FileProcessingHistory]: ...
   ```

### Phase 4: CLI Command

7. **Create CLI Module** (`cli/stats.py`)
   ```python
   import click
   from vpo.db import get_connection
   from vpo.db.views import get_stats_summary

   @click.group()
   def stats():
       """View and manage processing statistics."""
       pass

   @stats.command()
   @click.option('--since', help='Start date (ISO-8601)')
   @click.option('--format', type=click.Choice(['table', 'json', 'csv']))
   def summary(since, format):
       """Display aggregate processing statistics."""
       conn = get_connection()
       summary = get_stats_summary(conn, since=since)
       # Format and output

   @stats.command()
   def policy(): ...

   @stats.command()
   def file(): ...

   @stats.command()
   def purge(): ...
   ```

8. **Register Command** (`cli/__init__.py`)
   ```python
   from vpo.cli.stats import stats
   cli.add_command(stats)
   ```

### Phase 5: Web UI

9. **API Routes** (`server/routes.py`)
   ```python
   routes.add_route('GET', '/api/stats/summary', get_stats_summary_handler)
   routes.add_route('GET', '/api/stats/policies', get_policy_stats_handler)
   routes.add_route('GET', '/api/stats/policies/{name}', get_policy_stats_by_name_handler)
   routes.add_route('GET', '/api/stats/files/{file_id}', get_file_stats_handler)
   routes.add_route('DELETE', '/api/stats/purge', purge_stats_handler)
   ```

10. **Dashboard Template** (`server/ui/templates/stats.html`)
    ```html
    {% extends "base.html" %}
    {% block content %}
    <div class="stats-dashboard">
        <div class="summary-cards">...</div>
        <div class="policy-table">...</div>
        <div class="recent-runs">...</div>
    </div>
    {% endblock %}
    ```

## Testing Checklist

- [ ] Unit tests for ProcessingStatsRecord validation
- [ ] Unit tests for aggregate query functions
- [ ] Integration test: process file → verify stats recorded
- [ ] Integration test: CLI stats summary command
- [ ] Integration test: API /api/stats/summary endpoint
- [ ] Test purge with various filters
- [ ] Test with large dataset (10k+ records) for performance

## Key Files to Modify

| File | Changes |
|------|---------|
| `db/schema.py` | Add tables, migration |
| `db/types.py` | Add dataclasses |
| `db/queries.py` | Add CRUD operations |
| `db/views.py` | Add aggregate queries |
| `workflow/v11_processor.py` | Capture statistics |
| `cli/stats.py` | New file |
| `cli/__init__.py` | Register command |
| `server/routes.py` | Add API endpoints |
| `server/ui/templates/stats.html` | New file |

## Common Patterns

### ISO-8601 Timestamps
```python
from datetime import datetime, timezone
timestamp = datetime.now(timezone.utc).isoformat()
```

### UUID Generation
```python
import uuid
stats_id = str(uuid.uuid4())
```

### File Hash (partial)
```python
import hashlib

def compute_partial_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute hash of first 1MB + last 1MB + file size."""
    hasher = hashlib.sha256()
    size = path.stat().st_size
    hasher.update(str(size).encode())

    with open(path, 'rb') as f:
        hasher.update(f.read(chunk_size))
        if size > chunk_size * 2:
            f.seek(-chunk_size, 2)
            hasher.update(f.read(chunk_size))

    return hasher.hexdigest()
```

### Track Counting
```python
def count_tracks(tracks: list[TrackInfo]) -> dict[str, int]:
    """Count tracks by type."""
    counts = {'audio': 0, 'subtitle': 0, 'attachment': 0}
    for track in tracks:
        if track.track_type in counts:
            counts[track.track_type] += 1
    return counts
```

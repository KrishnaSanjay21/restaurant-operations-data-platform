# Historical replay

Start the state machine with an explicit source, `start_date`, `end_date`, and a
unique execution name such as `replay-2024-q1-001`. The execution name becomes the
batch ID. Use smaller windows for the high-volume 311 source.

After the run:

```sql
select batch_id, source_name, source_count, loaded_count, rejected_count, status
from restaurant_ops.raw.load_audit
where batch_id = 'replay-2024-q1-001';
```

Then execute `dbt build` and compare model row counts before and after the replay.
Business-key uniqueness tests provide duplicate protection; the audit table proves
which batch changed the warehouse.


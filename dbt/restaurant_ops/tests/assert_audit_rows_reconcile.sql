select batch_id, source_name
from {{ source('raw', 'load_audit') }}
where status = 'SUCCESS'
  and source_count <> loaded_count


select violation_code, violation_description, critical_flag
from {{ ref('stg_inspections') }}
where violation_code is not null
qualify row_number() over (
    partition by violation_code order by record_date desc nulls last, loaded_at desc
) = 1


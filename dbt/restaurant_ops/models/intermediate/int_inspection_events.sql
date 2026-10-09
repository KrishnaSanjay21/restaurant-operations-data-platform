{{ config(materialized='incremental', unique_key='inspection_key', incremental_strategy='merge') }}

select
    inspection_key,
    restaurant_id,
    location_key,
    inspection_date,
    inspection_type,
    max(action) as action,
    max(score) as score,
    max(grade) as grade,
    max(grade_date) as grade_date,
    count(distinct case when violation_code is not null then violation_key end) as violation_count,
    count(distinct case when critical_flag = 'Critical' then violation_key end) as critical_violation_count,
    max(record_date) as source_record_date,
    max(loaded_at) as loaded_at
from {{ ref('stg_inspections') }}
{% if is_incremental() %}
where loaded_at > (select coalesce(max(loaded_at), '1900-01-01'::timestamp_ntz) from {{ this }})
{% endif %}
group by 1, 2, 3, 4, 5


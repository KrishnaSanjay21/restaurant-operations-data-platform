{{ config(materialized='incremental', unique_key='violation_key', incremental_strategy='merge') }}

select distinct
    violation_key,
    inspection_key,
    restaurant_id,
    location_key,
    violation_code,
    violation_description,
    critical_flag,
    inspection_date as violation_date,
    loaded_at
from {{ ref('stg_inspections') }}
where violation_code is not null
{% if is_incremental() %}
  and loaded_at > (select coalesce(max(loaded_at), '1900-01-01'::timestamp_ntz) from {{ this }})
{% endif %}


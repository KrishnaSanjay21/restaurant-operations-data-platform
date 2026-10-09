select
    source_row_key,
    inspection_key,
    violation_key,
    restaurant_id,
    nullif(trim(restaurant_name), '') as restaurant_name,
    upper(nullif(trim(borough), '')) as borough,
    building,
    street,
    address_normalized,
    zipcode,
    phone,
    cuisine_description,
    inspection_date,
    action,
    violation_code,
    violation_description,
    critical_flag,
    score,
    grade,
    grade_date,
    record_date,
    inspection_type,
    latitude,
    longitude,
    location_key,
    _batch_id as batch_id,
    _retrieved_at as retrieved_at,
    _loaded_at as loaded_at
from {{ source('raw', 'inspections') }}
qualify row_number() over (
    partition by source_row_key
    order by _loaded_at desc
) = 1


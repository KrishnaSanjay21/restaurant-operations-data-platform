select
    complaint_id,
    created_date,
    closed_date,
    agency,
    agency_name,
    complaint_type,
    descriptor,
    location_type,
    incident_zip,
    incident_address,
    address_normalized,
    street_name,
    city,
    status,
    resolution_description,
    upper(nullif(trim(borough), '')) as borough,
    latitude,
    longitude,
    open_data_channel_type,
    location_key,
    _batch_id as batch_id,
    _retrieved_at as retrieved_at,
    _loaded_at as loaded_at
from {{ source('raw', 'complaints') }}
qualify row_number() over (
    partition by complaint_id
    order by _loaded_at desc
) = 1


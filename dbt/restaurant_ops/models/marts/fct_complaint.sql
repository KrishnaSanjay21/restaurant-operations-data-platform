{{ config(materialized='incremental', unique_key='complaint_id', incremental_strategy='merge') }}

select
    complaint_id,
    restaurant_id,
    location_key,
    to_date(created_date) as complaint_date,
    created_date,
    closed_date,
    complaint_type,
    descriptor,
    location_type,
    status,
    resolution_description,
    borough,
    incident_zip,
    latitude,
    longitude,
    open_data_channel_type,
    restaurant_match_method,
    loaded_at
from {{ ref('int_complaints_enriched') }}
{% if is_incremental() %}
where loaded_at > (select coalesce(max(loaded_at), '1900-01-01'::timestamp_ntz) from {{ this }})
{% endif %}


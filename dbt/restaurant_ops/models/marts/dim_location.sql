with locations as (
    select distinct
        location_key, borough, address_normalized, zipcode as postal_code,
        latitude, longitude, 'RESTAURANT' as source_type
    from {{ ref('stg_inspections') }}
    union all
    select distinct
        location_key, borough, address_normalized, incident_zip as postal_code,
        latitude, longitude, 'COMPLAINT' as source_type
    from {{ ref('stg_complaints') }}
), ranked as (
    select *, row_number() over (
        partition by location_key order by iff(source_type = 'RESTAURANT', 0, 1)
    ) as row_num
    from locations
)
select * exclude row_num from ranked where row_num = 1


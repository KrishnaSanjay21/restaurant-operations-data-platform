select * exclude row_num
from (
    select
        restaurant_id,
        restaurant_name,
        cuisine_description,
        phone,
        location_key,
        borough,
        building,
        street,
        address_normalized,
        zipcode,
        latitude,
        longitude,
        record_date,
        row_number() over (
            partition by restaurant_id order by record_date desc nulls last, loaded_at desc
        ) as row_num
    from {{ ref('stg_inspections') }}
)
where row_num = 1


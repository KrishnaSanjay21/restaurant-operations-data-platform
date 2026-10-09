with restaurant_addresses as (
    select * exclude row_num
    from (
        select
            restaurant_id,
            address_normalized,
            zipcode,
            row_number() over (
                partition by address_normalized, zipcode order by record_date desc nulls last
            ) as row_num
        from {{ ref('stg_inspections') }}
        where address_normalized is not null and zipcode is not null
    )
    where row_num = 1
)

select
    c.*,
    r.restaurant_id,
    iff(r.restaurant_id is not null, 'EXACT_ADDRESS_ZIP', 'UNMATCHED') as restaurant_match_method
from {{ ref('stg_complaints') }} c
left join restaurant_addresses r
    on c.address_normalized = r.address_normalized
   and c.incident_zip = r.zipcode


{{ config(materialized='table') }}

with bounds as (
    select min(event_date) as min_date, max(event_date) as max_date
    from (
        select inspection_date as event_date from {{ ref('stg_inspections') }}
        union all select to_date(created_date) from {{ ref('stg_complaints') }}
        union all select weather_date from {{ ref('stg_weather') }}
    )
), dates as (
    select dateadd(day, seq4(), min_date) as date_key
    from bounds, table(generator(rowcount => 15000))
    qualify date_key <= max_date
)
select
    date_key,
    year(date_key) as year,
    quarter(date_key) as quarter,
    month(date_key) as month,
    monthname(date_key) as month_name,
    weekofyear(date_key) as week_of_year,
    dayofweek(date_key) as day_of_week,
    dayname(date_key) as day_name,
    dayofweek(date_key) in (0, 6) as is_weekend
from dates


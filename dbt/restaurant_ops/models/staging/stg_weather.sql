select
    weather_key,
    station_id,
    weather_date,
    temperature_max_f,
    temperature_min_f,
    precipitation_in,
    snowfall_in,
    snow_depth_in,
    average_wind_mph,
    _batch_id as batch_id,
    _retrieved_at as retrieved_at,
    _loaded_at as loaded_at
from {{ source('raw', 'weather') }}
qualify row_number() over (
    partition by weather_key
    order by _loaded_at desc
) = 1


{{ config(materialized='incremental', unique_key='weather_key', incremental_strategy='merge') }}

select * from {{ ref('stg_weather') }}
{% if is_incremental() %}
where loaded_at > (select coalesce(max(loaded_at), '1900-01-01'::timestamp_ntz) from {{ this }})
{% endif %}


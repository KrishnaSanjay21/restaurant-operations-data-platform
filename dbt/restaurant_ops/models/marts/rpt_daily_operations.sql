select
    d.date_key,
    count(distinct i.inspection_key) as inspections,
    coalesce(sum(i.violation_count), 0) as violations,
    coalesce(sum(i.critical_violation_count), 0) as critical_violations,
    count(distinct c.complaint_id) as complaints,
    count(distinct iff(c.complaint_type = 'Food Poisoning', c.complaint_id, null)) as food_poisoning_complaints,
    max(w.temperature_max_f) as temperature_max_f,
    max(w.precipitation_in) as precipitation_in,
    max(w.snowfall_in) as snowfall_in
from {{ ref('dim_date') }} d
left join {{ ref('fct_inspection') }} i on d.date_key = i.inspection_date
left join {{ ref('fct_complaint') }} c on d.date_key = c.complaint_date
left join {{ ref('fct_weather') }} w on d.date_key = w.weather_date
group by 1


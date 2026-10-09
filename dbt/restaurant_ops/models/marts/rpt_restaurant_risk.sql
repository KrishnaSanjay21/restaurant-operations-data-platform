with inspection_metrics as (
    select
        restaurant_id,
        count(*) as inspection_count,
        sum(violation_count) as violation_count,
        sum(critical_violation_count) as critical_violation_count,
        avg(score) as average_inspection_score,
        max(inspection_date) as latest_inspection_date,
        max_by(grade, inspection_date) as latest_grade
    from {{ ref('fct_inspection') }}
    group by 1
), complaint_metrics as (
    select
        restaurant_id,
        count(*) as matched_complaint_count,
        count_if(complaint_type = 'Food Poisoning') as food_poisoning_complaints,
        count_if(complaint_type = 'Rodent') as rodent_complaints
    from {{ ref('fct_complaint') }}
    where restaurant_id is not null
    group by 1
), scored as (
    select
        r.restaurant_id,
        r.restaurant_name,
        r.cuisine_description,
        r.borough,
        r.zipcode,
        r.location_key,
        coalesce(i.inspection_count, 0) as inspection_count,
        coalesce(i.violation_count, 0) as violation_count,
        coalesce(i.critical_violation_count, 0) as critical_violation_count,
        round(i.average_inspection_score, 2) as average_inspection_score,
        i.latest_inspection_date,
        i.latest_grade,
        coalesce(c.matched_complaint_count, 0) as matched_complaint_count,
        coalesce(c.food_poisoning_complaints, 0) as food_poisoning_complaints,
        coalesce(c.rodent_complaints, 0) as rodent_complaints,
        round(
            coalesce(i.average_inspection_score, 0) * 2
            + coalesce(i.critical_violation_count, 0) * 3
            + coalesce(c.matched_complaint_count, 0) * 2,
            2
        ) as risk_score
    from {{ ref('dim_restaurant') }} r
    left join inspection_metrics i using (restaurant_id)
    left join complaint_metrics c using (restaurant_id)
)
select *, case
    when risk_score >= 80 then 'CRITICAL'
    when risk_score >= 50 then 'HIGH'
    when risk_score >= 25 then 'MEDIUM'
    else 'LOW'
end as risk_tier
from scored


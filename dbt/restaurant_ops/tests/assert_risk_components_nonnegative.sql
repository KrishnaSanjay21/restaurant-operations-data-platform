select restaurant_id
from {{ ref('rpt_restaurant_risk') }}
where risk_score < 0
   or inspection_count < 0
   or violation_count < 0
   or critical_violation_count < 0
   or matched_complaint_count < 0


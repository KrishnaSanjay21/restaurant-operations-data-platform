select inspection_key, score
from {{ ref('fct_inspection') }}
where score < 0


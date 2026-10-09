# Data dictionary

| Model | Grain | Primary key | Purpose |
|---|---|---|---|
| `dim_restaurant` | One restaurant | `restaurant_id` | Latest NYC CAMIS attributes |
| `dim_location` | One normalized address | `location_key` | Conformed inspection/complaint geography |
| `dim_date` | One calendar day | `date_key` | Shared time filtering |
| `dim_violation` | One violation code | `violation_code` | Violation descriptions and criticality |
| `fct_inspection` | One inspection event | `inspection_key` | Grade, score, and violation totals |
| `fct_violation` | One violation within an inspection | `violation_key` | Repeat and critical violation analysis |
| `fct_complaint` | One 311 service request | `complaint_id` | Complaint volume and conservative location match |
| `fct_weather` | One station/day | `weather_key` | Daily operational weather context |
| `rpt_restaurant_risk` | One restaurant | `restaurant_id` | Prioritization metrics and transparent risk tier |
| `rpt_daily_operations` | One calendar day | `date_key` | Inspection, complaint, and weather trend |

`restaurant_match_method = EXACT_ADDRESS_ZIP` means the complaint address and ZIP
matched a known restaurant exactly after normalization. `UNMATCHED` rows remain in
the fact table and are never silently attributed.

NYC placeholder inspection dates earlier than 2000-01-01 are routed to the reject
dataset and excluded from time-series reporting.


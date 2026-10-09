# KPI dictionary

| KPI | Formula | Interpretation |
|---|---|---|
| Inspections | Distinct `inspection_key` | Completed inspection events in filter context |
| Violations | Sum of `violation_count` | Violations recorded during inspections |
| Critical violation rate | Critical violations / all violations | Share classified as critical; blank when no violations |
| Repeat violators | Restaurants with the same violation code on 2+ inspection dates | Persistent control opportunity |
| Complaints | Distinct `complaint_id` | Selected DOHMH 311 volume |
| Complaint match rate | Complaints matched by exact address+ZIP / all complaints | Attribution coverage, not model accuracy |
| Average inspection score | Average non-null inspection score | NYC score; higher values generally indicate more issues |
| Risk score | `2×avg score + 3×critical violations + 2×matched complaints` | Portfolio heuristic for prioritization; not an official NYC rating |
| Risk tier | Low `<25`, Medium `25–49.99`, High `50–79.99`, Critical `≥80` | Operational queue derived from risk score |
| Freshness lag | Current timestamp − latest source load timestamp | Pipeline health indicator |


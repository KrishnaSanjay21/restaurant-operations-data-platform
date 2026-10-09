# Dashboard design specification

## Operations Overview

- KPI row: restaurants, inspections, violations, 311 complaints, priority restaurants.
- Monthly dual-line trend: inspection and complaint volume.
- Complaint mix bar chart and freshness status card.
- Filters: date, borough, cuisine, and risk tier.

## Restaurant Priorities

- Ranked risk table with restaurant, borough, cuisine, latest grade, critical
  violations, complaints, score, and tier.
- Repeat-violation bar chart and drill-through inspection history.
- Conditional colors: Low blue, Medium teal, High amber, Critical red.

The risk score is labeled as a portfolio prioritization heuristic, not an official
NYC risk designation. Complaints are only attributed when normalized address and
ZIP match exactly; unmatched complaints remain visible at area level.


# Power BI dashboard

Open `RestaurantOperations.pbip` after running the local pipeline. The semantic
model imports the governed CSV evidence exports in `../dashboard` through the
`DataRoot` Power Query parameter. If the repository moves, change `DataRoot` in
Power BI Desktop and refresh.

Pages:

1. **Operations Overview** — restaurants, inspections, violations, complaints,
   priority count, monthly activity, and complaint mix.
2. **Restaurant Priorities** — highest-risk restaurants and recurring violation
   codes for field follow-up.

The included PNG is a portable dashboard preview. The PBIP is source-controlled;
publishing and scheduled refresh must be configured in the user’s own Power BI
workspace and are not claimed by this repository.


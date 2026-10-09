# Published data sources

| Source | Dataset | Use | Access |
|---|---|---|---|
| NYC Department of Health | DOHMH New York City Restaurant Inspection Results (`43nn-pn8j`) | Restaurant, inspection, grade, score, and violation history | Socrata API |
| NYC 311 | 311 Service Requests from 2010 to Present (`erm2-nwe9`) | Selected DOHMH food, vendor, poisoning, and rodent complaints | Socrata API |
| NOAA NCEI | Daily Summaries, Central Park station `USW00094728` | Temperature, precipitation, snow, and wind controls | Access Data Service |

The portfolio profile requests all currently available inspection rows and up to
the 275,000 most recent relevant complaints from 2010 onward. Counts vary as the public datasets
are updated, so every run records its observed counts in
`artifacts/record_counts.json`. NOAA data is public and token-free through the
Access Data Service used here.

Sources:

- https://data.cityofnewyork.us/Health/DOHMH-New-York-City-Restaurant-Inspection-Results/43nn-pn8j/
- https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9/data
- https://www.ncei.noaa.gov/access/services/data/v1


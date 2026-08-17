# Data provenance

Snapshot date: 2026-08-16.

## Observed source data used by the model

- `chicago_candidate_licenses_snapshot.csv`: City of Chicago, **Business
  Licenses - Current Active**, dataset `uupf-x98q`. The snapshot contains
  active Commercial Garage and Filling Station licenses inside the study box.
  Source: https://data.cityofchicago.org/d/uupf-x98q
- `chicago_community_areas_2025.geojson`: City of Chicago, **Boundaries -
  Community Areas**, dataset `igwz-8jzy`. Source boundaries were last updated
  2025-04-22. Source: https://data.cityofchicago.org/d/igwz-8jzy
- `chicago_acs_2023_community_areas.csv`: City of Chicago, **ACS 5-Year Data by
  Community Area**, dataset `t68z-cikk`, based on the 2023 ACS. Source:
  https://data.cityofchicago.org/d/t68z-cikk

## Source-calibrated assumptions

- The site-cost envelope is a teaching proxy for a multi-port charging site.
  It is broadly compared with U.S. Department of Energy Alternative Fuels Data
  Center equipment and installation ranges, but the model's site-specific
  values are not quotes or engineering estimates. Source:
  https://afdc.energy.gov/fuels/electricity-infrastructure-development
- The DOE Alternative Fueling Station Locator is the appropriate future source
  for existing chargers and validation of candidate overlap. It is not used as
  an optimization input in this version. Source:
  https://afdc.energy.gov/stations/charging-networks

## Synthetic/modelled quantities

- The ACS density proxy is rescaled to a total of 23,248 demand units. These are
  not measured EV charging sessions or vehicles per day.
- Construction cost declines with great-circle distance from the Loop. The
  gradient is hypothetical.
- Capacity is 4,000 units for a garage and 2,200 for a filling station. These
  are normalized service units, not verified charger throughput.
- The farthest-first selection of 14 garages and 6 filling stations is a
  deterministic sampling rule used to keep the MILP small. A license confirms
  location/type only; it does not confirm EV readiness or grid capacity.
- Travel uses straight-line great-circle distance rather than road travel time.

# Optimal Siting of EV Charging Stations — Revised

Course project for Optimization Methods. The project uses a capacitated facility-location
MILP to screen which of 20 licensed Chicago garages or filling stations to use as candidate
EV charging sites.

## Run the project

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook notebooks/ev_charging_siting_full.ipynb
```

Run the notebook from top to bottom. CBC is bundled with PuLP; no separate solver install
is required. The delivered notebook was executed with Python 3.13.5 and contains all
outputs.

## Data boundary

The model deliberately separates three tiers:

- **Observed source data:** active City of Chicago business-license records provide the
  candidate coordinates and facility types; official City community-area boundaries
  define the study geometry; the City's 2023 ACS table supplies community population.
- **Source-derived proxy:** a 45-cell grid is clipped to the City boundary and weighted
  using ACS community population density. These weights are a spatial demand proxy, not
  observed EV charging sessions.
- **Synthetic scenario parameters:** total demand scale, construction cost, capacity,
  service radius and budget. Costs are only checked against the broad DOE/AFDC equipment
  and installation discussion; they are not bids or parcel-level estimates.

Exact snapshot names, URLs, access dates, row counts and caveats are recorded in
`data/SOURCES.md`. Distances are Haversine straight-line distances, not road-network travel
times.

## Corrected baseline

Under the stated synthetic parameters and a 5 km service radius, the lexicographic
minimum-cost solve builds 6 of 20 sites for $589,000, covers 100% of the model demand and
has a 2.276 km demand-weighted average straight-line assignment distance. CBC reports
`Optimal`, and explicit feasibility residual checks pass.

This is an illustrative screening result, not an investment recommendation. Candidate
ownership/access, utility interconnection, grid capacity, charger counts, measured EV
demand, equity criteria and road travel times require validation before deployment.

## Model and analyses

`src/model.py` exposes one `solve_model()` function. In `min_cost` mode it first minimizes
construction cost and then distance at that minimum cost. In `max_coverage` mode it
maximizes covered demand, minimizes cost at that coverage, and then minimizes distance.
This ordered solve removes arbitrary above-knee spending.

The notebook contains the formulation, data audit, baseline, feasibility validation,
budget/radius/capacity sensitivity, a separate weighted-distance experiment, balanced
scenario stability, low- versus knee-budget maps and `recommend(budget)` decision support.

## Project structure

```text
data/       official source snapshots and SOURCES.md
src/        deterministic data preparation, model, validation and plotting
notebooks/  complete executed notebook
figures/    revised presentation figures
ev_charging_siting.pptx    final presentation with speaker notes
```

The notebook does not need network access because the audited source snapshots are stored
in `data/`.

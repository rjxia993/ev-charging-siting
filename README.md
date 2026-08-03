# Optimal Siting of EV Charging Stations

Final project for the Optimization Methods course. A capacitated facility location model
that decides which of 20 candidate sites in Chicago should get a public EV charging
station, under a construction budget.

**Status: front half done, back half open.** See [Where the project stands](#where-the-project-stands).

---

## The problem in one paragraph

A city planner has a budget and a list of candidate sites, each with its own construction
cost and daily capacity. EV drivers are spread unevenly across the city. Build too few
stations and some drivers face a long drive; build too many and the budget is gone. The
model decides which sites to build and which station serves each area, so the city gets
the best coverage it can afford. It is a mixed integer program: binary build decisions
plus continuous assignment decisions, solved with PuLP and CBC.

## Quick start

```bash
pip install -r requirements.txt

python src/data_prep.py     # builds data/ (about 1 second)
python src/model.py         # baseline solve (about 2 seconds)
```

Then open `notebooks/01_data_and_model.ipynb` for the full walkthrough.

Expected baseline output, at a \$1.2M budget and a 5 km service radius:

```
stations built   : 6 of 20
construction cost: $643,000
demand covered   : 23,248 (100.0%)
average drive    : 2.59 km
```

## Repo layout

```
├── README.md
├── requirements.txt
├── data/                       generated, not committed
│   ├── sites.csv               candidate sites: id, lon, lat, cost, capacity
│   ├── demands.csv             demand points: id, lon, lat, weight
│   └── distance.npy            56 x 20 distance matrix in km
├── src/
│   ├── data_prep.py            builds the instance, documents every assumption
│   ├── model.py                solve_model(), the one function everything calls
│   └── plotting.py             plot_instance(), plot_solution(), plot_sweep()
├── notebooks/
│   ├── 01_data_and_model.ipynb DONE, front half walkthrough
│   └── 02_analysis.ipynb       SCAFFOLD, back half goes here
├── figures/                    saved figures for the report
└── docs/
    └── proposal.pdf            the approved one page proposal
```

The modeling code lives in `src/`, not in the notebooks. That way the notebooks stay
readable, and both people can work without fighting over merge conflicts in the same
`.ipynb`.

## The model

**Decision variables**

- `y_j` in {0, 1}: build a station at candidate site j, or not
- `x_ij` in [0, 1]: the fraction of demand at point i that is served by station j

**Objective**, in `min_cost` mode:

```
minimize   sum_j ( cost_j * y_j )  +  lambda * sum_ij ( weight_i * dist_ij * x_ij )
```

In `max_coverage` mode the budget is fixed and the objective becomes
`maximize sum_ij ( weight_i * x_ij )`, with demand allowed to go unserved.

**Constraints**

| Constraint | Meaning |
|---|---|
| `sum_j x_ij == 1` | every demand point is fully served (`<= 1` in coverage mode) |
| `x_ij <= y_j` | demand can only be assigned to a site that was built |
| `x_ij == 0 if dist_ij > radius` | nobody drives further than the service radius |
| `sum_i weight_i * x_ij <= cap_j * y_j` | a station cannot serve more than its capacity |
| `sum_j cost_j * y_j <= budget` | construction stays within budget |

## The one function you need

```python
from model import solve_model

res = solve_model(sites, demands, D,
                  budget=700_000,      # dollars
                  radius=5.0,          # km
                  lam=1.0,             # dollars per demand-km
                  mode="max_coverage", # or "min_cost"
                  capacity_scale=1.0)  # for the capacity sensitivity analysis

res["status"]        # "Optimal" when it worked
res["built"]         # [4, 8, 12, 14, 16, 18] site indices
res["total_cost"]    # construction cost of the plan
res["coverage_pct"]  # percent of demand served
res["avg_distance"]  # demand weighted average drive, km
res["assign"]        # {(i, j): fraction}
```

The entire back half is this function called in a loop with different arguments. You
should not need to modify the model.

## Data and assumptions

Real geography, assumed parameters. This is stated openly in the report rather than
presented as measured data.

**Real**: the 20 candidate coordinates are actual Chicago parking garages and fuel
stations (Millennium Park garage, Wicker Park, Logan Square, Pilsen, and so on).
Distances are great circle distances computed from those coordinates.

**Assumed**:

| Parameter | Value | Reasoning |
|---|---|---|
| Demand weight | about 900 near the Loop down to about 120 at the edge, 15% noise | density and daytime population are highest downtown |
| Construction cost | about \$210k downtown down to about \$60k at the edge | land prices fall with distance from the center |
| Capacity | 4000 per day for garages, 2200 for fuel stations | garages have room for more charging ports |

To pull the candidate sites live from OpenStreetMap instead of using the hard coded list,
call `data_prep.pull_sites_from_osm()`. It returns the same columns, so nothing else
changes. It needs internet and `osmnx`.

### Why capacity is set high

Total capacity is about 2.8 times total demand, so roughly a third of the sites is enough
to serve the whole area. This is deliberate. An earlier version used capacities about
8 times smaller, and the model became infeasible at reasonable budgets: nearly every site
had to be built, so there was no real choice left and the sensitivity curves came out
flat. If you change the capacity assumption, re run the feasibility check at the end of
notebook 01 before trusting any results.

## Where the project stands

**Done (front half)**

- Study area, 20 candidate sites, 56 demand points on a grid
- Cost, demand, and capacity assumptions, each documented with reasoning
- Haversine distance matrix
- `solve_model()` with both objective modes
- Baseline solve, verified sensible: 6 stations, \$643k, 100 percent coverage, 2.59 km
  average drive
- Feasibility limits mapped: a 3 km radius is infeasible, 4 km and up works
- Instance map and solution map

**Open (back half), scaffolded in `notebooks/02_analysis.ipynb`**

1. Compare `min_cost` against `max_coverage` at the same budget
2. Budget sweep and the coverage curve. A quick check gives 34 percent coverage at
   \$200k rising to 100 percent at \$700k, then flat. That knee is the headline result
3. Service radius sweep, 3 to 8 km
4. Capacity sweep via `capacity_scale`, 0.5 to 1.5
5. Maps: a low budget plan next to a high budget plan
6. `recommend(budget)` decision support tool, partly written
7. Write up the conclusions

## Notes for whoever picks this up

- Run `notebooks/01_data_and_model.ipynb` top to bottom first. If it runs clean, the
  handoff worked and you can start immediately.
- Everything is seeded (`SEED = 42` in `data_prep.py`), so results are reproducible.
- Keep working in `02_analysis.ipynb`. Do not edit `01`, and do not edit `src/model.py`
  unless something is genuinely broken.
- Save figures to `figures/` so the report can pull them in.
- If a solve comes back `Infeasible`, it is almost always the radius being too small or
  the budget being below the minimum needed to serve everyone. Check with an unlimited
  budget first to separate the two.

## Requirements

Python 3.9 or newer. See `requirements.txt`. The solver is CBC, which ships with PuLP,
so there is nothing extra to install.

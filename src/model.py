"""
The capacitated facility location model.

solve_model() is the only function the rest of the project needs. The whole
back half (budget sweep, radius and capacity sensitivity, maps, the decision
support tool) is built by calling it repeatedly with different arguments, so
it is written as a function and not as a top to bottom script.

Run a baseline from the repo root:

    python src/model.py
"""
import numpy as np
import pulp


def solve_model(sites, demands, D, budget, radius, lam=1.0,
                mode="min_cost", capacity_scale=1.0, msg=False):
    """Solve the capacitated facility location model.

    Parameters
    ----------
    sites : DataFrame
        Needs columns site_id, cost, capacity.
    demands : DataFrame
        Needs columns demand_id, weight.
    D : ndarray
        Distance matrix in km. D[i, j] is demand point i to site j.
    budget : float
        Total construction budget in dollars.
    radius : float
        Maximum acceptable driving distance in km. Demand cannot be assigned
        to a site further away than this.
    lam : float
        Converts one demand-km of travel into dollars. Only used in min_cost
        mode, where it sets the balance between building and driving.
    mode : {"min_cost", "max_coverage"}
        min_cost     : every demand point must be served, minimize
                       construction cost plus weighted travel cost.
        max_coverage : the budget is fixed, cover as much demand as possible.
                       Demand is allowed to go unserved.
    capacity_scale : float
        Multiplies every site capacity. Used by the capacity sensitivity
        analysis, so the caller does not have to edit the data.
    msg : bool
        Pass True to see the CBC solver log.

    Returns
    -------
    dict with keys:
        status        : solver status string, "Optimal" when it worked
        objective     : optimal objective value, None if not solved
        built         : list of integer site indices that were built
        assign        : {(i, j): fraction} for every positive assignment
        total_cost    : construction cost of the built sites
        covered       : total demand served
        coverage_pct  : covered as a percent of total demand
        avg_distance  : demand weighted average driving distance in km
    """
    I = range(len(demands))
    J = range(len(sites))
    w = demands["weight"].values
    f = sites["cost"].values
    cap = sites["capacity"].values * capacity_scale

    sense = pulp.LpMinimize if mode == "min_cost" else pulp.LpMaximize
    prob = pulp.LpProblem("facility_location", sense)

    # decision variables
    y = {j: pulp.LpVariable(f"y_{j}", cat="Binary") for j in J}
    x = {(i, j): pulp.LpVariable(f"x_{i}_{j}", lowBound=0, upBound=1)
         for i in I for j in J}

    # objective
    if mode == "min_cost":
        prob += (pulp.lpSum(f[j] * y[j] for j in J)
                 + lam * pulp.lpSum(w[i] * D[i, j] * x[i, j] for i in I for j in J))
    else:
        prob += pulp.lpSum(w[i] * x[i, j] for i in I for j in J)

    # demand satisfaction
    for i in I:
        if mode == "min_cost":
            prob += pulp.lpSum(x[i, j] for j in J) == 1
        else:
            prob += pulp.lpSum(x[i, j] for j in J) <= 1

    # linking and service radius
    for i in I:
        for j in J:
            if D[i, j] > radius:
                prob += x[i, j] == 0
            else:
                prob += x[i, j] <= y[j]

    # capacity
    for j in J:
        prob += pulp.lpSum(w[i] * x[i, j] for i in I) <= cap[j] * y[j]

    # budget
    prob += pulp.lpSum(f[j] * y[j] for j in J) <= budget

    prob.solve(pulp.PULP_CBC_CMD(msg=msg))
    status = pulp.LpStatus[prob.status]

    if status != "Optimal":
        return {"status": status, "objective": None, "built": [], "assign": {},
                "total_cost": None, "covered": 0.0, "coverage_pct": 0.0,
                "avg_distance": None}

    built = [j for j in J if y[j].value() > 0.5]
    assign = {(i, j): x[i, j].value()
              for i in I for j in J if x[i, j].value() > 1e-6}
    covered = sum(w[i] * v for (i, j), v in assign.items())
    dist_weighted = sum(w[i] * D[i, j] * v for (i, j), v in assign.items())

    return {
        "status": status,
        "objective": pulp.value(prob.objective),
        "built": built,
        "assign": assign,
        "total_cost": float(sum(f[j] for j in built)),
        "covered": covered,
        "coverage_pct": 100 * covered / w.sum(),
        "avg_distance": dist_weighted / covered if covered > 0 else None,
    }


def summarize(res, sites, label=""):
    """Print a short readable summary of one solve."""
    head = f"[{label}] " if label else ""
    print(f"{head}status: {res['status']}")
    if res["status"] != "Optimal":
        return
    print(f"  stations built   : {len(res['built'])} of {len(sites)}")
    print(f"  construction cost: ${res['total_cost']:,.0f}")
    print(f"  demand covered   : {res['covered']:,.0f} ({res['coverage_pct']:.1f}%)")
    print(f"  average drive    : {res['avg_distance']:.2f} km")
    print(f"  objective        : {res['objective']:,.0f}")


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from data_prep import load_all, build_all

    try:
        sites, demands, D = load_all()
    except FileNotFoundError:
        print("data/ not found, building it first")
        sites, demands, D = build_all()

    BUDGET, RADIUS = 1_200_000, 5.0
    res = solve_model(sites, demands, D, budget=BUDGET, radius=RADIUS)
    summarize(res, sites, label=f"baseline, budget ${BUDGET:,}, radius {RADIUS} km")
    print("\nbuilt sites:")
    print(sites.iloc[res["built"]][["site_id", "amenity", "cost", "capacity"]]
          .to_string(index=False))

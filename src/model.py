"""Capacitated facility-location MILP with lexicographic objectives."""
from __future__ import annotations

import numpy as np
import pulp


def solve_model(sites, demands, D, budget, radius, lam=1.0,
                mode="min_cost", capacity_scale=1.0, msg=False):
    """Solve the facility-location model.

    ``min_cost`` serves all demand, first minimizing construction cost and then
    assignment distance among equally cheap plans.

    ``max_coverage`` maximizes served demand, then minimizes construction cost
    at that coverage, then minimizes distance. This removes the former
    above-knee degeneracy that could spend money without improving coverage.

    ``weighted_cost`` retains the original construction-plus-travel objective
    for a separate trade-off analysis; it does not define the minimum-cost knee.
    """
    if mode not in {"min_cost", "max_coverage", "weighted_cost"}:
        raise ValueError("mode must be min_cost, max_coverage, or weighted_cost")

    I, J = range(len(demands)), range(len(sites))
    weights = demands["weight"].to_numpy(float)
    costs = sites["cost"].to_numpy(float)
    capacities = sites["capacity"].to_numpy(float) * capacity_scale
    sense = pulp.LpMaximize if mode == "max_coverage" else pulp.LpMinimize
    problem = pulp.LpProblem("facility_location", sense)
    y = {j: pulp.LpVariable(f"y_{j}", cat="Binary") for j in J}
    x = {(i, j): pulp.LpVariable(f"x_{i}_{j}", lowBound=0, upBound=1)
         for i in I for j in J}

    coverage = pulp.lpSum(weights[i] * x[i, j] for i in I for j in J)
    capex = pulp.lpSum(costs[j] * y[j] for j in J)
    travel = pulp.lpSum(weights[i] * D[i, j] * x[i, j] for i in I for j in J)

    for i in I:
        assigned = pulp.lpSum(x[i, j] for j in J)
        problem += assigned <= 1 if mode == "max_coverage" else assigned == 1
    for i in I:
        for j in J:
            problem += x[i, j] == 0 if D[i, j] > radius else x[i, j] <= y[j]
    for j in J:
        problem += pulp.lpSum(weights[i] * x[i, j] for i in I) <= capacities[j] * y[j]
    problem += capex <= budget

    solver = pulp.PULP_CBC_CMD(msg=msg)
    phases = []

    def run_phase(name, objective, phase_sense):
        problem.sense = phase_sense
        problem.setObjective(objective)
        problem.solve(solver)
        status = pulp.LpStatus[problem.status]
        phases.append({"phase": name, "status": status,
                       "objective": pulp.value(objective) if status == "Optimal" else None})
        return status

    if mode == "min_cost":
        status = run_phase("minimize construction cost", capex, pulp.LpMinimize)
        if status == "Optimal":
            best_cost = float(pulp.value(capex))
            problem += capex <= best_cost + 0.5
            status = run_phase("minimize distance at minimum cost", travel, pulp.LpMinimize)
    elif mode == "max_coverage":
        status = run_phase("maximize covered demand", coverage, pulp.LpMaximize)
        if status == "Optimal":
            best_coverage = float(pulp.value(coverage))
            problem += coverage >= best_coverage - 1e-5
            status = run_phase("minimize cost at maximum coverage", capex, pulp.LpMinimize)
        if status == "Optimal":
            best_cost = float(pulp.value(capex))
            problem += capex <= best_cost + 0.5
            status = run_phase(
                "minimize distance at maximum coverage and minimum cost",
                travel, pulp.LpMinimize,
            )
    else:
        status = run_phase("minimize weighted cost", capex + lam * travel, pulp.LpMinimize)

    if status != "Optimal":
        return {"status": status, "objective": None, "built": [], "assign": {},
                "total_cost": None, "covered": 0.0, "coverage_pct": 0.0,
                "avg_distance": None, "travel_demand_km": None, "phases": phases,
                "mode": mode}

    built = [j for j in J if y[j].value() > 0.5]
    assign = {(i, j): x[i, j].value() for i in I for j in J
              if x[i, j].value() is not None and x[i, j].value() > 1e-7}
    covered = sum(weights[i] * value for (i, j), value in assign.items())
    travel_value = sum(weights[i] * D[i, j] * value for (i, j), value in assign.items())
    total_cost = float(sum(costs[j] for j in built))
    primary = covered if mode == "max_coverage" else (
        total_cost if mode == "min_cost" else total_cost + lam * travel_value
    )
    return {
        "status": status,
        "objective": primary,
        "built": built,
        "assign": assign,
        "total_cost": total_cost,
        "covered": covered,
        "coverage_pct": 100 * covered / weights.sum(),
        "avg_distance": travel_value / covered if covered > 0 else None,
        "travel_demand_km": travel_value,
        "phases": phases,
        "mode": mode,
    }


def validate_solution(res, sites, demands, D, budget, radius, capacity_scale=1.0,
                      require_full=False, tol=1e-4):
    """Return maximum residuals and raise if a reported optimum is infeasible."""
    if res["status"] != "Optimal":
        raise ValueError(f"cannot validate non-optimal result: {res['status']}")
    weights = demands.weight.to_numpy(float)
    assigned = np.zeros(len(demands))
    load = np.zeros(len(sites))
    radius_violation = 0.0
    for (i, j), value in res["assign"].items():
        assigned[i] += value
        load[j] += weights[i] * value
        if D[i, j] > radius + tol:
            radius_violation = max(radius_violation, D[i, j] - radius)
    capacity = sites.capacity.to_numpy(float) * capacity_scale
    report = {
        "budget_excess": max(0.0, res["total_cost"] - budget),
        "assignment_excess": max(0.0, float(assigned.max() - 1)),
        "full_service_shortfall": max(0.0, float(1 - assigned.min())) if require_full else 0.0,
        "capacity_excess": max(0.0, float((load - capacity).max())),
        "radius_excess_km": radius_violation,
    }
    if max(report.values()) > tol:
        raise AssertionError(f"solution validation failed: {report}")
    return report


def summarize(res, sites, label=""):
    prefix = f"[{label}] " if label else ""
    print(f"{prefix}status: {res['status']}")
    if res["status"] != "Optimal":
        return
    print(f"  stations built   : {len(res['built'])} of {len(sites)}")
    print(f"  construction cost: ${res['total_cost']:,.0f}")
    print(f"  demand covered   : {res['covered']:,.0f} ({res['coverage_pct']:.1f}%)")
    print(f"  avg straight-line assignment distance: {res['avg_distance']:.2f} km")
    print(f"  primary objective: {res['objective']:,.2f}")

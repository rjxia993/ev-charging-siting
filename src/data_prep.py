"""Build the Chicago EV-charging siting teaching instance.

Observed source data: candidate coordinates and facility types come from the
City of Chicago Business Licenses - Current Active snapshot (uupf-x98q).
Demand spatial shape uses 2023 ACS community-area population density from the
City of Chicago (t68z-cikk) and official boundaries (igwz-8jzy).

Model assumptions: total demand is scaled to 23,248 units; site-specific costs
and capacities are scenario parameters; distances are great-circle rather than
road-network distances. These assumptions must not be described as measured EV
sessions, engineering bids, or verified site throughput.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

WEST, EAST = -87.72, -87.60
SOUTH, NORTH = 41.85, 41.95
CENTER = (-87.6298, 41.8781)
NX, NY = 8, 7
DECAY_KM = 4.5
SEED = 42
TARGET_TOTAL_DEMAND = 23_248

SOURCE_FILES = {
    "candidate_licenses": "chicago_candidate_licenses_snapshot.csv",
    "community_boundaries": "chicago_community_areas_2025.geojson",
    "acs_population": "chicago_acs_2023_community_areas.csv",
}


def haversine_km(lon1, lat1, lon2, lat2):
    """Great-circle distance in kilometres; supports scalars and arrays."""
    earth_radius_km = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlam = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlam / 2) ** 2
    return 2 * earth_radius_km * np.arcsin(np.sqrt(a))


def _farthest_first(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    """Deterministically choose a geographically spread subset."""
    frame = frame.reset_index(drop=True).copy()
    lon = frame.longitude.to_numpy(float)
    lat = frame.latitude.to_numpy(float)
    start = int(np.argmin(haversine_km(CENTER[0], CENTER[1], lon, lat)))
    chosen = [start]
    min_dist = haversine_km(lon[start], lat[start], lon, lat)
    while len(chosen) < min(n, len(frame)):
        min_dist[chosen] = -1
        nxt = int(np.argmax(min_dist))
        chosen.append(nxt)
        min_dist = np.minimum(min_dist, haversine_km(lon[nxt], lat[nxt], lon, lat))
    return frame.iloc[chosen].copy()


def build_sites(source_csv: str | os.PathLike) -> pd.DataFrame:
    """Select 20 real licensed facilities; attach synthetic cost/capacity."""
    raw = pd.read_csv(source_csv)
    raw = raw.dropna(subset=["latitude", "longitude", "license_description"])
    raw = raw.drop_duplicates(subset=["address", "license_description"])
    garages = _farthest_first(raw[raw.license_description == "Commercial Garage"], 14)
    filling = _farthest_first(raw[raw.license_description == "Filling Station"], 6)
    chosen = pd.concat([garages, filling], ignore_index=True)
    chosen = chosen.sort_values(["latitude", "longitude"]).reset_index(drop=True)

    sites = pd.DataFrame({
        "site_id": [f"S{k:02d}" for k in range(len(chosen))],
        "source_license_number": chosen.license_number.astype(str),
        "name": chosen.doing_business_as_name.fillna(chosen.legal_name).astype(str),
        "address": chosen.address.astype(str),
        "lon": chosen.longitude.astype(float),
        "lat": chosen.latitude.astype(float),
        "amenity": np.where(
            chosen.license_description.eq("Commercial Garage"), "parking", "fuel"
        ),
        "source_type": chosen.license_description.astype(str),
    })

    distance_from_loop = haversine_km(
        CENTER[0], CENTER[1], sites.lon.to_numpy(), sites.lat.to_numpy()
    )
    # Assumed multi-port site cost proxy; these are not observed bids.
    sites["cost"] = np.round(
        60_000 + 150_000 * np.exp(-distance_from_loop / DECAY_KM), -3
    ).astype(int)
    # Synthetic service-capacity units, deliberately stress-tested later.
    sites["capacity"] = np.where(sites.amenity.eq("parking"), 4000, 2200)
    return sites


def _point_in_ring(lon: float, lat: float, ring) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat):
            x_at_lat = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_at_lat:
                inside = not inside
        j = i
    return inside


def _point_in_geometry(lon: float, lat: float, geometry: dict) -> bool:
    polygons = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        polygons = [polygons]
    for polygon in polygons:
        if not polygon or not _point_in_ring(lon, lat, polygon[0]):
            continue
        if any(_point_in_ring(lon, lat, hole) for hole in polygon[1:]):
            continue
        return True
    return False


def build_demands(boundaries_geojson: str | os.PathLike,
                  acs_csv: str | os.PathLike) -> pd.DataFrame:
    """Build 56 grid points with ACS population-density proxy weights."""
    with open(boundaries_geojson, encoding="utf-8") as stream:
        geo = json.load(stream)
    acs = pd.read_csv(acs_csv)
    acs["community_key"] = acs.community_area.str.upper().str.strip()
    population = acs.set_index("community_key").total_population.to_dict()

    gx = np.linspace(WEST + 0.006, EAST - 0.006, NX)
    gy = np.linspace(SOUTH + 0.006, NORTH - 0.006, NY)
    xx, yy = np.meshgrid(gx, gy)
    rows = []
    for k, (lon, lat) in enumerate(zip(xx.ravel(), yy.ravel())):
        match = next((feature for feature in geo["features"]
                      if _point_in_geometry(float(lon), float(lat), feature["geometry"])), None)
        # The rectangular study box includes a few cells in Lake Michigan.
        # Clip those cells to the official City boundary instead of inventing
        # demand outside a Chicago community area.
        if match is None:
            continue
        props = match["properties"]
        community = str(props["community"]).upper().strip()
        pop = float(population[community])
        area = float(props["shape_area"])
        rows.append((f"D{k:02d}", lon, lat, community, pop, pop / area))

    demands = pd.DataFrame(rows, columns=[
        "demand_id", "lon", "lat", "community_area", "acs_population", "density_proxy"
    ])
    scaled = demands.density_proxy / demands.density_proxy.sum() * TARGET_TOTAL_DEMAND
    weights = pd.Series(np.maximum(1, np.floor(scaled).astype(int)))
    remainder = TARGET_TOTAL_DEMAND - int(weights.sum())
    order = np.argsort(-(scaled - np.floor(scaled)).to_numpy())
    weights.iloc[order[:remainder]] += 1
    demands["weight"] = weights.to_numpy(int)
    return demands


def build_distance_matrix(demands: pd.DataFrame, sites: pd.DataFrame) -> np.ndarray:
    matrix = np.zeros((len(demands), len(sites)))
    for i in range(len(demands)):
        matrix[i, :] = haversine_km(
            demands.lon.iloc[i], demands.lat.iloc[i], sites.lon.to_numpy(), sites.lat.to_numpy()
        )
    return matrix


def build_all(data_dir="data", save=True):
    data_dir = Path(data_dir)
    sites = build_sites(data_dir / SOURCE_FILES["candidate_licenses"])
    demands = build_demands(
        data_dir / SOURCE_FILES["community_boundaries"],
        data_dir / SOURCE_FILES["acs_population"],
    )
    distances = build_distance_matrix(demands, sites)
    if save:
        data_dir.mkdir(parents=True, exist_ok=True)
        sites.to_csv(data_dir / "sites.csv", index=False)
        demands.to_csv(data_dir / "demands.csv", index=False)
        np.save(data_dir / "distance.npy", distances)
    return sites, demands, distances


def load_all(data_dir="data"):
    data_dir = Path(data_dir)
    return (
        pd.read_csv(data_dir / "sites.csv"),
        pd.read_csv(data_dir / "demands.csv"),
        np.load(data_dir / "distance.npy"),
    )


if __name__ == "__main__":
    sites, demands, distances = build_all()
    print(f"candidate sites  : {len(sites)} (City license records)")
    print(f"demand points    : {len(demands)} (ACS density proxy; scaled total)")
    print(f"distance matrix  : {distances.shape}, {distances.min():.2f}-{distances.max():.2f} km")
    print(f"total demand     : {demands.weight.sum():,} synthetic model units")
    print(f"total capacity   : {sites.capacity.sum():,} synthetic model units")
    print(f"cost to build all: ${sites.cost.sum():,} assumed")

"""
Build the problem instance: candidate sites, demand points, and the distance
matrix for the EV charging station siting model (Chicago).

Run from the repo root:

    python src/data_prep.py

This writes data/sites.csv, data/demands.csv, and data/distance.npy.
"""
import os
import numpy as np
import pandas as pd

# ----------------------------------------------------------------------
# Study area: near north and west side of Chicago
# ----------------------------------------------------------------------
WEST, EAST = -87.72, -87.60
SOUTH, NORTH = 41.85, 41.95
CENTER = (-87.6298, 41.8781)      # the Loop

# grid resolution for demand points
NX, NY = 8, 7

# how fast demand and land price fall off with distance from the Loop
DECAY_KM = 4.5

SEED = 42

# ----------------------------------------------------------------------
# Candidate sites.
#
# These are real Chicago parking garages and fuel stations. They are hard
# coded so the pipeline runs with no network access. To pull them live from
# OpenStreetMap instead, use pull_sites_from_osm() below.
# ----------------------------------------------------------------------
CANDIDATES = [
    (-87.6270, 41.8827, "parking"),   # Millennium Park garage
    (-87.6195, 41.8853, "parking"),   # Grant Park North
    (-87.6338, 41.8919, "parking"),   # River North
    (-87.6410, 41.8994, "fuel"),      # Near North, Clybourn
    (-87.6553, 41.9120, "parking"),   # Lincoln Park south
    (-87.6722, 41.9105, "fuel"),      # Bucktown
    (-87.6769, 41.9089, "parking"),   # Wicker Park
    (-87.6866, 41.8956, "fuel"),      # Humboldt Park east
    (-87.7013, 41.9033, "parking"),   # Humboldt Park
    (-87.6644, 41.8836, "fuel"),      # West Loop
    (-87.6520, 41.8781, "parking"),   # Greektown
    (-87.6412, 41.8674, "fuel"),      # University Village
    (-87.6280, 41.8598, "parking"),   # Chinatown north
    (-87.6720, 41.8570, "fuel"),      # Pilsen
    (-87.7085, 41.8721, "parking"),   # Lawndale
    (-87.7136, 41.9250, "fuel"),      # Logan Square west
    (-87.6900, 41.9290, "parking"),   # Logan Square
    (-87.6641, 41.9455, "fuel"),      # Lakeview west
    (-87.6480, 41.9380, "parking"),   # Lakeview
    (-87.6350, 41.9210, "fuel"),      # Old Town
]


def haversine_km(lon1, lat1, lon2, lat2):
    """Great circle distance in km. Works with scalars or arrays.

    Degrees of longitude and latitude are not the same length, so a plain
    Euclidean distance on raw coordinates would be wrong.
    """
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlam = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlam / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def pull_sites_from_osm(n_sites=20, seed=SEED):
    """Pull real parking and fuel locations from OpenStreetMap.

    Needs internet and `pip install osmnx`. Returns the same columns as
    build_sites(), so it is a drop in replacement for CANDIDATES.
    """
    import osmnx as ox

    tags = {"amenity": ["fuel", "parking"]}
    gdf = ox.features_from_bbox((WEST, SOUTH, EAST, NORTH), tags)
    gdf = gdf[gdf.geometry.notna()].copy()
    # parking lots come back as polygons, so take the centroid
    pts = gdf.to_crs(3857).geometry.centroid.to_crs(4326)
    out = pd.DataFrame({"lon": pts.x.values, "lat": pts.y.values,
                        "amenity": gdf["amenity"].values})
    out = out.sample(n_sites, random_state=seed).reset_index(drop=True)
    out.insert(0, "site_id", [f"S{k:02d}" for k in range(len(out))])
    return out


def build_sites(candidates=None):
    """Candidate sites with assumed construction cost and capacity.

    ASSUMPTIONS (state these in the report):
      - Construction cost decays with distance from the Loop, reflecting land
        prices: about $210k downtown down to about $60k at the edge.
      - Capacity is 4000 vehicles/day for parking garages, which have room for
        more ports, and 2200 for fuel stations. Total capacity across all 20
        sites is about 2.8x total demand, so roughly a third of the sites is
        enough to serve the area. That is deliberate: it leaves the model a
        real choice about WHICH sites to build, which is what the budget sweep
        explores. If capacity is set much tighter, nearly every site has to be
        built and the sensitivity curves go flat.
    """
    rows = candidates if candidates is not None else CANDIDATES
    sites = pd.DataFrame(rows, columns=["lon", "lat", "amenity"])
    sites.insert(0, "site_id", [f"S{k:02d}" for k in range(len(sites))])

    d = haversine_km(CENTER[0], CENTER[1], sites["lon"].values, sites["lat"].values)
    sites["cost"] = np.round(60_000 + 150_000 * np.exp(-d / DECAY_KM), -3).astype(int)
    sites["capacity"] = np.where(sites["amenity"] == "parking", 4000, 2200)
    return sites


def build_demands(seed=SEED):
    """Demand points on a grid, with an assumed demand weight.

    ASSUMPTION: the weight stands for EV drivers per day in that grid cell. It
    decays with distance from the Loop, since density and daytime population
    are highest downtown. Range is about 900 near the Loop down to about 120 at
    the edge, with 15 percent noise so cells are not identical.
    """
    rng = np.random.default_rng(seed)
    gx = np.linspace(WEST + 0.006, EAST - 0.006, NX)
    gy = np.linspace(SOUTH + 0.006, NORTH - 0.006, NY)
    XX, YY = np.meshgrid(gx, gy)

    demands = pd.DataFrame({"lon": XX.ravel(), "lat": YY.ravel()})
    demands.insert(0, "demand_id", [f"D{k:02d}" for k in range(len(demands))])

    d = haversine_km(CENTER[0], CENTER[1], demands["lon"].values, demands["lat"].values)
    demands["weight"] = np.round(
        (120 + 780 * np.exp(-d / DECAY_KM)) * rng.uniform(0.85, 1.15, len(demands))
    ).astype(int)
    return demands


def build_distance_matrix(demands, sites):
    """D[i, j] = km from demand point i to candidate site j."""
    D = np.zeros((len(demands), len(sites)))
    for i in range(len(demands)):
        D[i, :] = haversine_km(demands.lon.iloc[i], demands.lat.iloc[i],
                               sites["lon"].values, sites["lat"].values)
    return D


def build_all(data_dir="data", save=True):
    """Build everything and optionally write it to disk."""
    sites = build_sites()
    demands = build_demands()
    D = build_distance_matrix(demands, sites)
    if save:
        os.makedirs(data_dir, exist_ok=True)
        sites.to_csv(os.path.join(data_dir, "sites.csv"), index=False)
        demands.to_csv(os.path.join(data_dir, "demands.csv"), index=False)
        np.save(os.path.join(data_dir, "distance.npy"), D)
    return sites, demands, D


def load_all(data_dir="data"):
    """Load a previously built instance."""
    sites = pd.read_csv(os.path.join(data_dir, "sites.csv"))
    demands = pd.read_csv(os.path.join(data_dir, "demands.csv"))
    D = np.load(os.path.join(data_dir, "distance.npy"))
    return sites, demands, D


if __name__ == "__main__":
    sites, demands, D = build_all()
    print(f"candidate sites  : {len(sites)}")
    print(f"demand points    : {len(demands)}")
    print(f"distance matrix  : {D.shape}, {D.min():.2f} to {D.max():.2f} km")
    print(f"total demand     : {demands['weight'].sum():,}")
    print(f"total capacity   : {sites['capacity'].sum():,}")
    print(f"cost range       : ${sites['cost'].min():,} to ${sites['cost'].max():,}")
    print(f"cost to build all: ${sites['cost'].sum():,}")
    print("\nwrote data/sites.csv, data/demands.csv, data/distance.npy")

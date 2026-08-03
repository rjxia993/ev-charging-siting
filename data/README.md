# data/

These files are generated, not committed. Rebuild them from the repo root with:

    python src/data_prep.py

| File | Contents |
|---|---|
| `sites.csv` | candidate sites: `site_id, lon, lat, amenity, cost, capacity` |
| `demands.csv` | demand points: `demand_id, lon, lat, weight` |
| `distance.npy` | 56 x 20 matrix, distance in km from demand i to site j |

Everything is seeded, so rebuilding gives identical files.

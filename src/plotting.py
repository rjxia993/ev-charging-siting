"""
Map and chart helpers.

plot_instance() is finished and used in notebook 01.
plot_solution() is finished and is what the back half needs for the maps.
"""
import matplotlib.pyplot as plt

CENTER = (-87.6298, 41.8781)   # the Loop


def plot_instance(sites, demands, ax=None, annotate=True):
    """The problem before optimizing: all candidate sites and all demand."""
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 7))

    ax.scatter(demands.lon, demands.lat, s=demands.weight / 6, c="tab:blue",
               alpha=0.45, label="demand point (size = weight)")
    ax.scatter(sites.lon, sites.lat, s=90, c="tab:red", marker="^",
               edgecolors="black", label="candidate site")
    ax.scatter(*CENTER, s=140, c="gold", marker="*", edgecolors="black",
               label="the Loop")
    if annotate:
        for _, r in sites.iterrows():
            ax.annotate(r.site_id, (r.lon, r.lat), fontsize=6.5,
                        xytext=(3, 4), textcoords="offset points")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_title("Candidate sites and demand points")
    ax.legend(fontsize=8)
    return ax


def plot_solution(res, sites, demands, ax=None, title=None, annotate=False):
    """The solved plan: chosen sites, rejected sites, and assignment lines.

    Line width is scaled by how much demand travels along it, so the busy
    routes stand out.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 7))

    if res["status"] != "Optimal":
        ax.set_title(f"{title or 'solution'}: {res['status']}")
        return ax

    built = set(res["built"])
    w = demands["weight"].values
    max_flow = max((w[i] * v for (i, j), v in res["assign"].items()), default=1)

    # assignment lines first, so the markers sit on top
    for (i, j), v in res["assign"].items():
        flow = w[i] * v
        ax.plot([demands.lon.iloc[i], sites.lon.iloc[j]],
                [demands.lat.iloc[i], sites.lat.iloc[j]],
                color="grey", alpha=0.55, lw=0.4 + 2.6 * flow / max_flow,
                zorder=1)

    # demand points
    ax.scatter(demands.lon, demands.lat, s=demands.weight / 8, c="tab:blue",
               alpha=0.45, zorder=2, label="demand point")

    # rejected then chosen sites
    rej = sites[~sites.index.isin(built)]
    sel = sites[sites.index.isin(built)]
    ax.scatter(rej.lon, rej.lat, s=55, c="lightgrey", marker="^",
               edgecolors="grey", zorder=3, label="site not built")
    ax.scatter(sel.lon, sel.lat, s=150, c="tab:red", marker="^",
               edgecolors="black", zorder=4, label="station built")
    if annotate:
        for _, r in sel.iterrows():
            ax.annotate(r.site_id, (r.lon, r.lat), fontsize=7, weight="bold",
                        xytext=(4, 5), textcoords="offset points")

    if title is None:
        title = (f"{len(res['built'])} stations, ${res['total_cost']:,.0f}, "
                 f"{res['coverage_pct']:.0f}% covered")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_title(title)
    ax.legend(fontsize=8, loc="upper right")
    return ax


def plot_sweep(df, xcol, ycol, xlabel=None, ylabel=None, title=None,
               ax=None, marker="o", color="tab:blue"):
    """Generic sweep chart, for the budget, radius, and capacity analyses."""
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 5))
    ax.plot(df[xcol], df[ycol], marker=marker, color=color)
    ax.set_xlabel(xlabel or xcol)
    ax.set_ylabel(ylabel or ycol)
    if title:
        ax.set_title(title)
    ax.grid(alpha=0.3)
    return ax

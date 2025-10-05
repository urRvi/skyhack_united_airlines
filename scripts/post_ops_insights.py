from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from src.config import OUTPUTS

OUT = OUTPUTS
FIG = OUT.parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)


def _to_num(s):
    return pd.to_numeric(s, errors="coerce")


def _ensure_cols(df):
    """Derive a few convenience columns if missing."""
    if "difficult" not in df.columns:
        if "fds_bucket" in df.columns:
            df["difficult"] = (
                df["fds_bucket"].astype(str).str.lower() == "difficult"
            ).astype(int)
        else:
            
            q80 = _to_num(df.get("fds")).quantile(0.80)
            df["difficult"] = (_to_num(df.get("fds")) >= q80).astype(int)

    ap_col = "scheduled_arrival_airport_code"
    if ap_col not in df.columns and "scheduled_arrival_station_code" in df.columns:
        ap_col = "scheduled_arrival_station_code"
    df.rename(columns={ap_col: "arr_ap"}, inplace=True)

    if "scheduled_departure_datetime_local" in df.columns:
        dt = pd.to_datetime(df["scheduled_departure_datetime_local"], errors="coerce")
    else:
        dt = pd.to_datetime(df["scheduled_departure_date_local"], errors="coerce")
    df["dep_date"] = dt.dt.date
    df["dep_month"] = dt.dt.to_period("M").astype(str)
    return df
def _corr(a, b):
    a = _to_num(a)
    b = _to_num(b)
    if a.notna().sum() < 3 or b.notna().sum() < 3:
        return np.nan
    if a.var() == 0 or b.var() == 0:
        return np.nan
    return a.corr(b, method="spearman")


fs_path = OUT / "flight_scores.csv"
assert fs_path.exists(), f"Missing: {fs_path}. Run scripts/run_all.py first."

df = pd.read_csv(
    fs_path,
    low_memory=False,
    parse_dates=[
        "scheduled_departure_datetime_local",
        "scheduled_arrival_datetime_local",
    ],
    infer_datetime_format=True,
)
df = _ensure_cols(df)

by_mo = (
    df.groupby(["arr_ap", "dep_month"], dropna=False)
    .agg(
        flights=("flight_number", "count"),
        pct_difficult=("difficult", "mean"),
        mean_fds=("fds", "mean"),
    )
    .reset_index()
)
g = (
    by_mo.groupby("arr_ap", dropna=False)
    .agg(
        flights=("flights", "sum"),
        mean_fds=("mean_fds", "mean"),
        pct_difficult=("pct_difficult", "mean"),
        mo_count=("dep_month", "nunique"),
        fds_cv=(
            "mean_fds",
            lambda x: (
                float(np.std(x, ddof=0) / (np.mean(x) + 1e-6)) if len(x) > 1 else np.nan
            ),
        ),
        diff_cv=(
            "pct_difficult",
            lambda x: (
                float(np.std(x, ddof=0) / (np.mean(x) + 1e-6)) if len(x) > 1 else np.nan
            ),
        ),
    )
    .reset_index()
)
g["consistency_score"] = (g["pct_difficult"].fillna(0)) * (
    1 - g["diff_cv"].fillna(0).clip(lower=0, upper=1)
)
g = g.sort_values(
    ["consistency_score", "pct_difficult", "flights"], ascending=[False, False, False]
)

g.to_csv(OUT / "destination_consistency.csv", index=False)

top = g.head(15).sort_values("pct_difficult")
plt.figure(figsize=(7, 4))
plt.barh(top["arr_ap"], top["pct_difficult"] * 100.0)
plt.xlabel("% of flights Difficult")
plt.title("Destinations with consistently higher difficulty")
plt.tight_layout()
plt.savefig(FIG / "top_difficult_destinations.png", dpi=160)
plt.close()


candidate_drivers = [
    "turn_slack",
    "dep_delay_rate_roll28",
    "arr_delay_rate_roll28",
    "route_delay_rate_roll28",
    "route_cxl_rate_roll28",
    "taxi_out_delta",
    "arrivals_same_hour",
    "ssr_rate",
    "transfer_checked_ratio",
    "special_bag_ratio",
    "is_peak_season",
    "red_eye",
    "bank_window",
    "dep_hub_flag",
    "arr_hub_flag",
    "type_diff_rate",
    "total_seats",
]
present = [c for c in candidate_drivers if c in df.columns]
drv_rows = []

focus_aps = g.head(20)["arr_ap"].tolist()
for ap in focus_aps:
    sub = df[df["arr_ap"] == ap]
    for feat in present:
        val = _corr(sub[feat], sub["difficult"])
        drv_rows.append({"arr_ap": ap, "feature": feat, "spearman_with_difficult": val})

drivers = (
    pd.DataFrame(drv_rows)
    .dropna()
    .sort_values(["arr_ap", "spearman_with_difficult"], ascending=[True, False])
)
drivers.to_csv(OUT / "destination_drivers.csv", index=False)

try:
    topA = g.head(10)["arr_ap"].tolist()
    piv = drivers[drivers["arr_ap"].isin(topA)].pivot_table(
        index="arr_ap", columns="feature", values="spearman_with_difficult"
    )
    if not piv.empty:
        plt.figure(figsize=(min(10, 1.2 + 0.6 * len(present)), 0.7 + 0.5 * len(topA)))
        im = plt.imshow(piv.fillna(0).to_numpy(), aspect="auto")
        plt.colorbar(im, fraction=0.046, pad=0.04)
        plt.yticks(range(len(piv.index)), piv.index)
        plt.xticks(range(len(piv.columns)), piv.columns, rotation=60, ha="right")
        plt.title("Driver strength (Spearman corr with Difficult)")
        plt.tight_layout()
        plt.savefig(FIG / "driver_heatmap.png", dpi=160)
        plt.close()
except Exception:
    pass
def reco_lines():
    yield "# Operational Recommendations\n"
    yield "These are mapped from statistical drivers to concrete actions.\n\n"
    mapping = [
        (
            "turn_slack",
            "Pad scheduled ground time on affected turns; pre-position ramp/cleaning; gate change to shorten taxi path.",
        ),
        (
            "dep_delay_rate_roll28",
            "Pre-departure buffers and extra pushback crews during peak; de-peaking banks by 5–10 min.",
        ),
        (
            "arr_delay_rate_roll28",
            "Tighten inbound connection protection; proactive reaccom for misconnect risk.",
        ),
        (
            "route_delay_rate_roll28",
            "Publish playbook for chronic routes (ATC flow times, taxi congestion); set dynamic crew show times.",
        ),
        (
            "route_cxl_rate_roll28",
            "Stage spare aircraft/crews; swap to higher reliability fleets.",
        ),
        (
            "taxi_out_delta",
            "Shift push windows; request alternate taxi routes; avoid far-end gates at peak.",
        ),
        (
            "arrivals_same_hour",
            "Add gate/ramp staffing in that hour; de-peak schedule; prioritize quick-turn gates.",
        ),
        (
            "ssr_rate",
            "Pre-board teams and wheelchairs staged; add aisle chairs; extend boarding window by 5 min.",
        ),
        (
            "transfer_checked_ratio",
            "Extra transfer-bag runners & belt capacity; SLA for cross-belt moves.",
        ),
        (
            "special_bag_ratio",
            "Dedicated oversize belt staffing; early callouts to baggage.",
        ),
        ("is_peak_season", "Seasonal staffing rosters; temporary schedule buffers."),
        ("red_eye", "Crew/cleaning overlap; quiet-hour taxi coordination."),
        ("dep_hub_flag", "Hub control-tower alerting & stand re-assignment rules."),
        (
            "type_diff_rate",
            "Targeted training/briefings for the aircraft type; ensure jet-bridge fit/spares.",
        ),
        ("total_seats", "Adjust boarding groups and door staffing for larger gauge."),
    ]
    yield "## Global actions by driver\n"
    for feat, action in mapping:
        yield f"- **{feat}** → {action}\n"
    yield "\n## Destination-specific priorities (top 10)\n"
    for ap in g.head(10)["arr_ap"]:
        topdrv = (
            drivers[drivers["arr_ap"] == ap]
            .sort_values("spearman_with_difficult", ascending=False)
            .head(3)["feature"]
            .tolist()
        )
        yield f"- **{ap}**: focus on {', '.join(topdrv)}\n"


(OUT / "ops_recos.md").write_text("".join(reco_lines()), encoding="utf-8")
print("Wrote:")
print(" -", OUT / "destination_consistency.csv")
print(" -", OUT / "destination_drivers.csv")
print(" -", OUT / "ops_recos.md")
print("Also charts (if data available) under:", FIG)

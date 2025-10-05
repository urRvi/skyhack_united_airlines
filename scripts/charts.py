from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))


from src import load, features, labeler
from src.config import OUTPUTS

FIGDIR = OUTPUTS.parent / "figures"
FIGDIR.mkdir(parents=True, exist_ok=True)

def savefig(name):
    plt.tight_layout()
    out = FIGDIR / name
    plt.savefig(out, dpi=160, bbox_inches="tight")
    plt.close()
    print("Saved", out)

def main():
    flights, pnrfl, bags = load.load_all()
    df = features.merge_all(flights, pnrfl, bags)
    df = labeler.add_difficulty_label(df)
    df = features.add_airport_equipment_flags(df)
    df = features.add_airport_route_rollups(df)
    dd = pd.to_numeric(df.get("actual_departure_delay_minutes"), errors="coerce")
    avg_delay = float(dd.mean()) if dd.notna().any() else np.nan
    pct_late = float((dd > 0).mean() * 100.0) if dd.notna().any() else np.nan

    plt.figure(figsize=(4.5,3.2))
    xs = ["Avg dep delay (min)", "% flights late"]
    ys = [avg_delay, pct_late]
    plt.bar(xs, ys)
    plt.title("Delays summary")
    savefig("eda_delay_summary.png")
    if "turn_slack" in df.columns:
        ts = pd.to_numeric(df["turn_slack"], errors="coerce").dropna()
        if len(ts) > 0:
            plt.figure(figsize=(5,3.2))
            plt.hist(ts, bins=40)
            plt.title("Turn slack (planned - typical minutes)")
            plt.xlabel("Minutes")
            plt.ylabel("Flights")
            savefig("turn_slack_hist.png")

            lt0 = int((ts < 0).sum())
            le5 = int((ts <= 5).sum())
            plt.figure(figsize=(4.5,3.2))
            plt.bar(["< 0", "≤ 5"], [lt0, le5])
            plt.title("Flights with tight turns")
            savefig("turn_slack_counts.png")

    if "transfer_checked_ratio" in df.columns:
        tcr = (df
               .assign(route=df["scheduled_departure_airport_code"]+"→"+df["scheduled_arrival_airport_code"])
               .groupby("route")["transfer_checked_ratio"].median().dropna()
               .sort_values(ascending=False).head(10))
        if not tcr.empty:
            plt.figure(figsize=(7,4))
            tcr.sort_values().plot(kind="barh")
            plt.xlabel("Median transfer/checked ratio")
            plt.title("Routes with highest transfer bag pressure (median)")
            savefig("bags_route_transfer_ratio_top10.png")

    if {"pnr_rows","difficult"}.issubset(df.columns) and df["pnr_rows"].notna().any():
        tmp = df.copy()
        tmp = tmp[pd.to_numeric(tmp["pnr_rows"], errors="coerce").notna()]
        if len(tmp) > 0:
            tmp["load_bin"] = pd.qcut(tmp["pnr_rows"].astype(float), q=min(8, tmp["pnr_rows"].nunique()), duplicates="drop")
            by = tmp.groupby("load_bin").agg(mean_diff=("difficult","mean"),
                                             mean_load=("pnr_rows","mean")).reset_index()
            plt.figure(figsize=(5.5,3.2))
            plt.plot(by["mean_load"], by["mean_diff"], marker="o")
            plt.xlabel("Avg passengers (bin)")
            plt.ylabel("Share difficult")
            plt.title("Passenger load vs. difficulty (binned)")
            savefig("load_vs_difficult.png")

    if {"ssr_wch","pnr_rows","difficult"}.issubset(df.columns):
        tmp = df.copy()
        tmp["ssr_dense"] = (pd.to_numeric(tmp["ssr_wch"], errors="coerce")
                            / tmp["pnr_rows"].replace(0, np.nan)).fillna(0)
        tmp = tmp[tmp["pnr_rows"].notna()]
        if len(tmp) > 0:
            tmp["load_bin"] = pd.qcut(tmp["pnr_rows"].astype(float), q=min(5, tmp["pnr_rows"].nunique()), duplicates="drop")
            g = (tmp.groupby("load_bin").agg(mean_ssr=("ssr_dense","mean"),
                                             mean_diff=("difficult","mean")))
            plt.figure(figsize=(5.5,3.2))
            plt.plot(g["mean_ssr"], g["mean_diff"], marker="o")
            plt.xlabel("SSR density (per PNR row)")
            plt.ylabel("Share difficult")
            plt.title("SSR vs difficulty (controls for load)")
            savefig("ssr_vs_difficult_by_load.png")

    fi_path = OUTPUTS / "feature_importance.csv"
    if fi_path.exists():
        fi = pd.read_csv(fi_path)
        if not fi.empty and "importance_gain" in fi.columns:
            top = fi.sort_values("importance_gain", ascending=False).head(15)
            plt.figure(figsize=(7,4))
            plt.barh(top["feature"][::-1], top["importance_gain"][::-1])
            plt.title("Feature importance (top 15)")
            savefig("feature_importance_top15.png")

    fs_path = OUTPUTS / "flight_scores.csv"
    if fs_path.exists():
        fs = pd.read_csv(fs_path)
        if "fds" in fs.columns:
            plt.figure(figsize=(6,3.2))
            plt.hist(fs["fds"].dropna(), bins=30)
            plt.title("Flight Difficulty Score distribution")
            plt.xlabel("FDS (0–100)")
            plt.ylabel("Flights")
            savefig("fds_distribution.png")
        if "fds_bucket" in fs.columns:
            counts = fs["fds_bucket"].value_counts().reindex(["Easy","Medium","Difficult"])
            plt.figure(figsize=(5,3.2))
            counts.plot(kind="bar")
            plt.title("FDS buckets")
            savefig("fds_buckets.png")

if __name__ == "__main__":
    main()

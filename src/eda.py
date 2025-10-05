import pandas as pd
import numpy as np
from .config import OUTPUTS

def _write_one_row(path, **kwargs):
    """Write a single-row CSV (values may be NaN)."""
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{**kwargs}]).to_csv(path, index=False)

def _safe_corr(a, b):
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    if a.size < 2 or b.size < 2:
        return np.nan
    if a.std(ddof=0) == 0 or b.std(ddof=0) == 0:
        return np.nan
    return float(a.corr(b))

def eda_deliverables(df: pd.DataFrame):
    """
    Writes all hackathon EDA CSVs into OUTPUTS:
      - eda_delay_summary.csv
      - eda_turn_slack_counts.csv
      - eda_bag_ratio.csv
      - eda_pax_corr.csv
      - eda_ssr_vs_delay_by_load.csv
    Always emits at least one row per file.
    """
    OUT = OUTPUTS
    OUT.mkdir(parents=True, exist_ok=True)

    dd = pd.to_numeric(df.get("actual_departure_delay_minutes", pd.Series(dtype=float)), errors="coerce")
    if dd.notna().any():
        _write_one_row(
            OUT / "eda_delay_summary.csv",
            avg_dep_delay_min=float(dd.mean()),
            pct_departure_late=float((dd > 0).mean() * 100.0),
        )
    else:
        _write_one_row(OUT / "eda_delay_summary.csv",
                       avg_dep_delay_min=np.nan, pct_departure_late=np.nan)
    if "turn_slack" in df.columns:
        _write_one_row(
            OUT / "eda_turn_slack_counts.csv",
            turn_slack_lt_0=int((df["turn_slack"] < 0).sum()),
            turn_slack_le_5=int((df["turn_slack"] <= 5).sum()),
            total_flights=int(len(df)),
        )
    else:
        _write_one_row(
            OUT / "eda_turn_slack_counts.csv",
            turn_slack_lt_0=0, turn_slack_le_5=0, total_flights=int(len(df)),
        )
    ratio = df.get("transfer_checked_ratio")
    if ratio is None or not pd.to_numeric(ratio, errors="coerce").dropna().size:
        ratio = df.get("special_bag_ratio")
    if ratio is not None:
        clean = pd.to_numeric(ratio, errors="coerce").dropna()
        avg_ratio = float(clean.mean()) if clean.size else np.nan
    else:
        avg_ratio = np.nan
    _write_one_row(OUT / "eda_bag_ratio.csv", avg_transfer_to_checked_bag_ratio=avg_ratio)

    if {"pnr_rows","difficult"}.issubset(df.columns) and df["pnr_rows"].nunique() > 1:
        corr = _safe_corr(df["pnr_rows"], df["difficult"])
        _write_one_row(OUT / "eda_pax_corr.csv", corr_pnr_rows_vs_difficult=corr)
    else:
        _write_one_row(OUT / "eda_pax_corr.csv", corr_pnr_rows_vs_difficult=np.nan)

    if {"ssr_wch","pnr_rows","difficult"}.issubset(df.columns) and df["pnr_rows"].nunique() > 1:
        tmp = df.copy()
        tmp["ssr_dense"] = (tmp["ssr_wch"] / tmp["pnr_rows"].replace(0, np.nan)).fillna(0)
        try:
            tmp["load_bin"] = pd.qcut(tmp["pnr_rows"], q=5, duplicates="drop")
            res = (
                tmp.groupby("load_bin", observed=False, dropna=False)
                   .apply(lambda g: pd.Series({
                       "mean_difficult": g["difficult"].mean(),
                       "mean_ssr_dense": g["ssr_dense"].mean(),
                       "corr_ssr_dense_difficult": _safe_corr(g["ssr_dense"], g["difficult"]),
                   }), include_groups=False)
                   .reset_index()
            )
        except ValueError:
            res = pd.DataFrame(columns=["load_bin","mean_difficult","mean_ssr_dense","corr_ssr_dense_difficult"])
    else:
        res = pd.DataFrame(columns=["load_bin","mean_difficult","mean_ssr_dense","corr_ssr_dense_difficult"])

    res.to_csv(OUT / "eda_ssr_vs_delay_by_load.csv", index=False)
    print("EDA outputs saved to", OUT)

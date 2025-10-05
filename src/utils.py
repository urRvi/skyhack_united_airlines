import pandas as pd
import re

def to_datetime(s):
    return pd.to_datetime(s, errors="coerce")

def add_time_parts(df, col, prefix):
    t = to_datetime(df[col])
    df[f"{prefix}_hour"]  = t.dt.hour
    df[f"{prefix}_dow"]   = t.dt.dayofweek
    df[f"{prefix}_month"] = t.dt.month
    return df

def bank_window(hour: int) -> int:
    if 6 <= hour <= 9:   return 1
    if 17 <= hour <= 21: return 2
    return 0

def lc_map(cols):
    """lowercase -> original column map"""
    return {c.lower(): c for c in cols}

def find_col(df, patterns):
    """find first column matching any regex pattern (case-insensitive)"""
    cmap = lc_map(df.columns)
    for pat in patterns:
        rgx = re.compile(pat, re.I)
        for lc, orig in cmap.items():
            if rgx.search(lc):
                return orig
    return None

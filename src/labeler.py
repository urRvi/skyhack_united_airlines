import pandas as pd
from .config import DELAY_THRESHOLD_MIN

def _series_or_zeros(df: pd.DataFrame, colname: str):
    if colname in df.columns:
        return pd.to_numeric(df[colname], errors="coerce").fillna(0)
    return pd.Series(0, index=df.index, dtype="float64")

def _ensure_delay_minutes(df: pd.DataFrame) -> pd.DataFrame:
    """Create actual_departure_delay_minutes / actual_arrival_delay_minutes if missing."""
    out = df.copy()
    # Departure delay
    if "actual_departure_delay_minutes" not in out.columns:
        sdt = pd.to_datetime(out.get("scheduled_departure_datetime_local"), errors="coerce")
        adt = pd.to_datetime(out.get("actual_departure_datetime_local"), errors="coerce")
        dep_delay = (adt - sdt).dt.total_seconds() / 60.0
        out["actual_departure_delay_minutes"] = pd.to_numeric(dep_delay, errors="coerce")
    # Arrival delay (optional)
    if "actual_arrival_delay_minutes" not in out.columns:
        sat = pd.to_datetime(out.get("scheduled_arrival_datetime_local"), errors="coerce")
        aat = pd.to_datetime(out.get("actual_arrival_datetime_local"), errors="coerce")
        arr_delay = (aat - sat).dt.total_seconds() / 60.0
        out["actual_arrival_delay_minutes"] = pd.to_numeric(arr_delay, errors="coerce")
    return out

def add_difficulty_label(flights: pd.DataFrame) -> pd.DataFrame:
    df = _ensure_delay_minutes(flights)

    delay = _series_or_zeros(df, "actual_departure_delay_minutes")
    cxl   = _series_or_zeros(df, "cancellation_flag")
    div   = _series_or_zeros(df, "diversion_flag")

    df["difficult"] = ((delay >= DELAY_THRESHOLD_MIN) | (cxl == 1) | (div == 1)).astype(int)
    return df

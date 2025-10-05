import pandas as pd, numpy as np
from .config import OUTPUTS

def score_and_write(model, feature_cols, df: pd.DataFrame):
    X = df[feature_cols].fillna(0.0).values
    proba = model.predict_proba(X)[:, 1]
    fds = (proba * 100.0).clip(0, 100)
    bucket = pd.cut(fds, bins=[-1, 33.33, 66.66, 100.0], labels=["Low","Medium","High"])

    out = df.copy()
    out["fds"] = fds
    out["fds_bucket"] = bucket.astype(str)

    cols = [
        "company_id","flight_number",
        "scheduled_departure_airport_code","scheduled_arrival_airport_code",
        "scheduled_departure_datetime_local","scheduled_arrival_datetime_local",
        "fds","fds_bucket"
    ]
    for c in cols:
        if c not in out.columns: out[c] = ""
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    out[cols + [c for c in out.columns if c not in cols]].to_csv(OUTPUTS / "flight_scores.csv", index=False)
    return OUTPUTS / "flight_scores.csv"

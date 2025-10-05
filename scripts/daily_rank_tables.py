from pathlib import Path
import pandas as pd

from src.config import OUTPUTS 

OUT = OUTPUTS
INP = OUT / "flight_scores.csv"
assert INP.exists(), f"Not found: {INP}"

df = pd.read_csv(INP, low_memory=False, parse_dates=["scheduled_departure_datetime_local"])
df["dep_date"] = df["scheduled_departure_datetime_local"].dt.date
df["rank_in_day"] = (
    df.groupby("dep_date")["fds"]
      .rank(ascending=False, method="first")
      .astype(int)
)
cols = ["dep_date","rank_in_day","company_id","flight_number",
        "scheduled_departure_airport_code","scheduled_arrival_airport_code",
        "fds","fds_bucket"]
df.sort_values(["dep_date","rank_in_day"])[cols] \
  .to_csv(OUT / "daily_rankings.csv", index=False)

(df.sort_values(["dep_date","rank_in_day"])
   .groupby("dep_date")
   .head(10)[cols]
   .to_csv(OUT / "daily_rankings_top10.csv", index=False))
bucket_counts = (df.groupby(["dep_date","fds_bucket"]).size()
                   .unstack(fill_value=0)
                   .reset_index())
bucket_counts.to_csv(OUT / "daily_bucket_counts.csv", index=False)

print("Wrote:")
print(" -", OUT / "daily_rankings.csv")
print(" -", OUT / "daily_rankings_top10.csv")
print(" -", OUT / "daily_bucket_counts.csv")

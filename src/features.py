# src/features.py
import pandas as pd, numpy as np, re
import duckdb
from .config import FLIGHT_KEYS, AP_FILE
from .utils import add_time_parts, bank_window

# Join keys for non-flight tables (no datetime needed)
KEY4 = FLIGHT_KEYS[:4]  # company_id, flight_number, dep_code, arr_code


# ---------- utilities ----------
def _find_col(df, patterns):
    cols = {c.lower(): c for c in df.columns}
    for pat in patterns:
        rgx = re.compile(pat, re.I)
        for lc, orig in cols.items():
            if rgx.search(lc):
                return orig
    return None


def ensure_keys(d: pd.DataFrame, what: str, require_datetime: bool = True) -> pd.DataFrame:
    """
    Normalize to canonical columns and types:
      company_id, flight_number,
      scheduled_departure_airport_code, scheduled_arrival_airport_code,
      scheduled_departure_datetime_local (only when require_datetime=True)

    Also normalizes casing/whitespace so joins are reliable.
    """
    df = d.copy()

    # company_id
    if "company_id" not in df.columns:
        c = _find_col(df, [r"^company[_ ]?id$", r"^airline[_ ]?id$", r"^carrier(_id)?$"])
        if c: df["company_id"] = df[c]

    # flight_number
    if "flight_number" not in df.columns:
        c = _find_col(df, [r"^flight[_ ]?number$", r"^flight(no)?$", r"^flt[_ ]?num(ber)?$"])
        if c: df["flight_number"] = df[c]

    # dep airport code (accept station_code)
    if "scheduled_departure_airport_code" not in df.columns:
        if "scheduled_departure_station_code" in df.columns:
            df["scheduled_departure_airport_code"] = df["scheduled_departure_station_code"]
        else:
            c = _find_col(df, [r"(scheduled|sched|plan)?[_ ]?(dep|origin|org)[_ ]?(airport|station)?[_ ]?(iata|code)?$"])
            if c: df["scheduled_departure_airport_code"] = df[c]

    # arr airport code (accept station_code)
    if "scheduled_arrival_airport_code" not in df.columns:
        if "scheduled_arrival_station_code" in df.columns:
            df["scheduled_arrival_airport_code"] = df["scheduled_arrival_station_code"]
        else:
            c = _find_col(df, [r"(scheduled|sched|plan)?[_ ]?(arr|dest|destination)[_ ]?(airport|station)?[_ ]?(iata|code)?$"])
            if c: df["scheduled_arrival_airport_code"] = df[c]

    # flight times – only required for Flight Level
    if require_datetime and "scheduled_departure_datetime_local" not in df.columns:
        c = _find_col(df, [r"scheduled.*dep.*(datetime|date[_ ]?time|time).*local"])
        if c: df["scheduled_departure_datetime_local"] = df[c]
    if require_datetime and "scheduled_arrival_datetime_local" not in df.columns:
        c = _find_col(df, [r"scheduled.*arr.*(datetime|date[_ ]?time|time).*local"])
        if c: df["scheduled_arrival_datetime_local"] = df[c]

    # aircraft type mapping
    if "aircraft_type" not in df.columns:
        c = _find_col(df, [r"^fleet[_ ]?type$", r"^aircraft$"])
        if c: df["aircraft_type"] = df[c]

    # ---- normalize key types/casing to make joins reliable
    for c in ["company_id", "flight_number"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    for c in ["scheduled_departure_airport_code", "scheduled_arrival_airport_code"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip().str.upper()

    if require_datetime:
        for c in ["scheduled_departure_datetime_local", "scheduled_arrival_datetime_local"]:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce")

    # validate
    need = FLIGHT_KEYS if require_datetime else KEY4
    missing = [k for k in need if k not in df.columns]
    if missing:
        raise KeyError(f"{what}: missing required key columns {missing}. Available: {list(df.columns)}")
    return df

def agg_pnr_to_flight(pnr_fl: pd.DataFrame) -> pd.DataFrame:
    df = ensure_keys(pnr_fl, "PNR+Flight", require_datetime=False)

    total_pax_col = "total_pax" if "total_pax" in df.columns else None
    child_flag    = "is_child" if "is_child" in df.columns else None
    infant_cnt    = "lap_child_count" if "lap_child_count" in df.columns else None

    ssr_cols  = [c for c in df.columns if re.search(r"(ssr|wheelchair|wch)", c, re.I)]
    umnr_cols = [c for c in df.columns if re.search(r"(umnr|unaccompanied)", c, re.I)]

    if infant_cnt is None: df["__infants__"] = 0; infant_cnt = "__infants__"
    if child_flag is None: df["__is_child__"] = 0; child_flag = "__is_child__"

    df["__ssr_wch__"] = df[ssr_cols[0]] if ssr_cols else 0
    df["__umnr__"]    = df[umnr_cols[0]] if umnr_cols else 0

    g = (df.groupby(KEY4, dropna=False)
           .agg(
               pnr_rows=("flight_number","count"),
               pax_proxy=(total_pax_col, "sum") if total_pax_col else ("flight_number","count"),
               children=(child_flag,"sum"),
               infants=(infant_cnt,"sum"),
               ssr_wch=("__ssr_wch__","sum"),
               umnr=("__umnr__","sum"),
           ).reset_index())
    g["ssr_rate"] = (g["ssr_wch"] / g["pnr_rows"].replace(0, np.nan)).fillna(0)
    return g


def agg_bag_to_flight(bag: pd.DataFrame) -> pd.DataFrame:
    df = ensure_keys(bag, "Bag", require_datetime=False)
    if "bag_count" not in df.columns:
        df["bag_count"] = df.select_dtypes(include=[np.number]).sum(axis=1)
    if "special_bag_flag" not in df.columns:
        df["special_bag_flag"] = 0

    transfer_cols = [c for c in df.columns if "transfer" in c.lower() and "bag" in c.lower()]
    checked_cols  = [c for c in df.columns if "checked"  in c.lower() and "bag" in c.lower()]

    g = (df.groupby(KEY4, dropna=False)
           .agg(total_bags=("bag_count","sum"),
                special_bags=("special_bag_flag","sum"))
           .reset_index())
    g["special_bag_ratio"] = (g["special_bags"] / g["total_bags"].replace(0, np.nan)).fillna(0)

    if transfer_cols and checked_cols:
        tmp = (df.groupby(KEY4, dropna=False)
                 .agg(transfer_bags=(transfer_cols[0],"sum"),
                      checked_bags=(checked_cols[0],"sum")).reset_index())
        g = g.merge(tmp, on=KEY4, how="left")
        g["transfer_checked_ratio"] = (g["transfer_bags"] / g["checked_bags"].replace(0, np.nan)).fillna(0)
    else:
        g["transfer_checked_ratio"] = np.nan
    return g
def add_time_features(flights: pd.DataFrame) -> pd.DataFrame:
    df = flights.copy()
    df = add_time_parts(df, "scheduled_departure_datetime_local", "dep")
    df = add_time_parts(df, "scheduled_arrival_datetime_local", "arr")
    df["red_eye"] = ((df["dep_hour"]>=22) | (df["dep_hour"]<=5)).astype(int)
    df["bank_window"] = df["dep_hour"].apply(bank_window)
    vol_by_month = df.groupby(df["dep_month"])["flight_number"].count()
    top_months = set(vol_by_month.sort_values(ascending=False).head(4).index.tolist())
    df["is_peak_season"] = df["dep_month"].isin(top_months).astype(int)
    df["route_ab"] = df["scheduled_departure_airport_code"] + "→" + df["scheduled_arrival_airport_code"]
    return df


def add_turn_features(flights: pd.DataFrame) -> pd.DataFrame:
    df = flights.copy()
    numeric_cols = ["planned_ground_time_minutes", "scheduled_ground_time_minutes", "actual_ground_time_minutes"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "planned_ground_time_minutes" in df.columns:
        df["planned_turn_minutes"] = df["planned_ground_time_minutes"]
    elif "scheduled_ground_time_minutes" in df.columns:
        df["planned_turn_minutes"] = df["scheduled_ground_time_minutes"]
    else:
        df["planned_turn_minutes"] = np.nan

    if "actual_ground_time_minutes" in df.columns:
        std = (df.assign(dep_hour=df.get("dep_hour", pd.to_datetime(df["scheduled_departure_datetime_local"]).dt.hour))
                 .groupby(["aircraft_type","scheduled_departure_airport_code","dep_hour"], dropna=False)
                 ["actual_ground_time_minutes"].median()
                 .rename("std_turn_minutes").reset_index())
        df = df.merge(std, on=["aircraft_type","scheduled_departure_airport_code","dep_hour"], how="left")
    else:
        df["std_turn_minutes"] = np.nan

    df["turn_slack"] = df["planned_turn_minutes"] - df["std_turn_minutes"]
    return df


def add_airport_equipment_flags(flights: pd.DataFrame) -> pd.DataFrame:
    df = flights.copy()
    con = duckdb.connect()
    ap = con.execute(f"SELECT * FROM read_csv_auto('{AP_FILE.as_posix()}', header=True)").df()
    ap = ap.rename(columns={k:k.strip() for k in ap.columns}).drop_duplicates(subset=["airport_iata_code"])
    df = df.merge(ap.add_prefix("dep_"), left_on="scheduled_departure_airport_code", right_on="dep_airport_iata_code", how="left")
    df = df.merge(ap.add_prefix("arr_"), left_on="scheduled_arrival_airport_code",   right_on="arr_airport_iata_code", how="left")
    df["intl_flag"] = (df["dep_iso_country_code"] != df["arr_iso_country_code"]).astype(int)

    dep_counts = df.groupby("scheduled_departure_airport_code")["flight_number"].count()
    cutoff = dep_counts.quantile(0.95)
    hubs = set(dep_counts[dep_counts >= cutoff].index)
    df["dep_hub_flag"] = df["scheduled_departure_airport_code"].isin(hubs).astype(int)
    df["arr_hub_flag"] = df["scheduled_arrival_airport_code"].isin(hubs).astype(int)

    if "aircraft_type" in df.columns and "difficult" in df.columns:
        if "dep_month" not in df.columns:
            df["dep_month"] = pd.to_datetime(df["scheduled_departure_datetime_local"]).dt.month
        tmp = (df.sort_values("scheduled_departure_datetime_local")
                 .groupby(["aircraft_type", "dep_month"], as_index=False)
                 .agg(type_diff_rate=("difficult","mean")))
        df = df.merge(tmp, on=["aircraft_type","dep_month"], how="left")
    else:
        df["type_diff_rate"] = np.nan
    return df


def add_airport_route_rollups(flights: pd.DataFrame) -> pd.DataFrame:
    """
    Rolling difficulty rates by dep/arr airport-hour and by route.
    Taxi-out deltas are included only if 'actual_taxi_out_minutes' exists.
    """
    df = flights.copy()
    assert "difficult" in df.columns, "Run labeler.add_difficulty_label first."
    df = df.sort_values("scheduled_departure_datetime_local").reset_index(drop=True)

    df["dep_date"] = pd.to_datetime(df["scheduled_departure_datetime_local"]).dt.date
    df["dep_hour"] = pd.to_datetime(df["scheduled_departure_datetime_local"]).dt.hour
    df["arr_hour"] = pd.to_datetime(df["scheduled_arrival_datetime_local"]).dt.hour

    has_taxi_out = "actual_taxi_out_minutes" in df.columns
    grp = ["scheduled_departure_airport_code", "dep_hour"]

    dep_agg = {"dep_count": ("flight_number", "count"), "diff_sum": ("difficult", "sum")}
    if has_taxi_out:
        dep_agg["taxi_out_avg"] = ("actual_taxi_out_minutes", "mean")

    tmp = (df.groupby(grp + ["dep_date"], as_index=False).agg(**dep_agg).sort_values("dep_date"))

    tmp["dep_delay_rate_roll28"] = (
        tmp.groupby(grp)["diff_sum"].transform(lambda s: s.rolling(28, min_periods=7).sum())
        / tmp.groupby(grp)["dep_count"].transform(lambda s: s.rolling(28, min_periods=7).sum())
    )

    if has_taxi_out:
        tmp["taxi_out_roll7"] = tmp.groupby(grp)["taxi_out_avg"].transform(lambda s: s.rolling(7, min_periods=3).mean())
        tmp["taxi_out_long"] = tmp.groupby(grp)["taxi_out_avg"].transform(lambda s: s.rolling(90, min_periods=30).median())
        tmp["taxi_out_delta"] = tmp["taxi_out_roll7"] - tmp["taxi_out_long"]
    else:
        tmp["taxi_out_delta"] = np.nan

    df = df.merge(
        tmp[["scheduled_departure_airport_code","dep_hour","dep_date","dep_delay_rate_roll28","taxi_out_delta"]],
        on=["scheduled_departure_airport_code","dep_hour","dep_date"], how="left"
    )

    agrp = ["scheduled_arrival_airport_code","arr_hour"]
    atmp = (df.groupby(agrp + ["dep_date"], as_index=False)
              .agg(arr_count=("flight_number","count"), arr_diff_sum=("difficult","sum"))
              .sort_values("dep_date"))
    atmp["arr_delay_rate_roll28"] = (
        atmp.groupby(agrp)["arr_diff_sum"].transform(lambda s: s.rolling(28, min_periods=7).sum())
        / atmp.groupby(agrp)["arr_count"].transform(lambda s: s.rolling(28, min_periods=7).sum())
    )
    df = df.merge(
        atmp[["scheduled_arrival_airport_code","arr_hour","dep_date","arr_delay_rate_roll28"]],
        on=["scheduled_arrival_airport_code","arr_hour","dep_date"], how="left"
    )

    if "cancellation_flag" not in df.columns:
        df["cancellation_flag"] = 0

    rgrp = ["scheduled_departure_airport_code","scheduled_arrival_airport_code"]
    rtmp = (df.groupby(rgrp + ["dep_date"], as_index=False)
              .agg(route_count=("flight_number","count"),
                   route_diff_sum=("difficult","sum"),
                   route_cxl=("cancellation_flag","sum"))
              .sort_values("dep_date"))
    rtmp["route_delay_rate_roll28"] = (
        rtmp.groupby(rgrp)["route_diff_sum"].transform(lambda s: s.rolling(28, min_periods=7).sum())
        / rtmp.groupby(rgrp)["route_count"].transform(lambda s: s.rolling(28, min_periods=7).sum())
    )
    rtmp["route_cxl_rate_roll28"] = (
        rtmp.groupby(rgrp)["route_cxl"].transform(lambda s: s.rolling(28, min_periods=7).sum())
        / rtmp.groupby(rgrp)["route_count"].transform(lambda s: s.rolling(28, min_periods=7).sum())
    )
    df = df.merge(
        rtmp[rgrp + ["dep_date","route_delay_rate_roll28","route_cxl_rate_roll28"]],
        on=rgrp + ["dep_date"], how="left"
    )
    arrivals = (df[["scheduled_arrival_airport_code","scheduled_arrival_datetime_local"]]
                .rename(columns={"scheduled_arrival_airport_code":"ap",
                                 "scheduled_arrival_datetime_local":"arr_time"}))
    arrivals["arr_hour"] = pd.to_datetime(arrivals["arr_time"]).dt.floor("h")
    same_hour = arrivals.groupby(["ap","arr_hour"]).size().rename("arrivals_same_hour").reset_index()
    df = df.merge(
        same_hour,
        left_on=["scheduled_departure_airport_code",
                 pd.to_datetime(df["scheduled_departure_datetime_local"]).dt.floor("h")],
        right_on=["ap","arr_hour"], how="left"
    ).drop(columns=["ap","arr_hour"])
    df["arrivals_same_hour"] = df["arrivals_same_hour"].fillna(0).astype(int)

    return df

def merge_all(flights, pnr_fl, bags):
    flights = ensure_keys(flights, "Flight Level", require_datetime=True)
    pax = agg_pnr_to_flight(pnr_fl)
    bag = agg_bag_to_flight(bags)

    df = flights.merge(pax, on=KEY4, how="left")
    df = df.merge(bag, on=KEY4, how="left")

    df = add_time_features(df)
    df = add_turn_features(df)
    return df
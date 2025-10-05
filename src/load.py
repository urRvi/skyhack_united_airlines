from __future__ import annotations
from pathlib import Path
import pandas as pd

try:
    from .config import DATA_DIR as _DATA_DIR 
    DATA_DIR = Path(_DATA_DIR)
except Exception:
    DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _norm(s: str) -> str:
    """normalize a filename for fuzzy matching"""
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _find_file(candidates: list[str]) -> Path:
    """Find a CSV in DATA_DIR whose normalized name contains any of the candidate keys."""
    files = list(DATA_DIR.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {DATA_DIR}")

    norm_to_path = { _norm(p.name): p for p in files }
    for key in candidates:
        k = _norm(key)
        for n, p in norm_to_path.items():
            if k in n:
                return p
   
    names = "\n  - ".join(str(p.name) for p in files)
    raise FileNotFoundError(
        "Could not find a matching CSV for any of: "
        f"{candidates} in {DATA_DIR}\nAvailable:\n  - {names}"
    )


def _read_csv(path: Path) -> pd.DataFrame:
    """Read CSV permissively, keeping strings; dates are parsed later in features/labeler."""
    try:
        return pd.read_csv(path, dtype="object", low_memory=False, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, dtype="object", low_memory=False, encoding="latin-1")


def load_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Returns:
        flights, pnr_flight, bags  (as DataFrames)
    Looks for your actual filenames case/spacing-independently, e.g.:
      - 'Flight Level Data.csv'
      - 'PNR+Flight+Level+Data.csv'
      - 'Bag+Level+Data.csv'
    """
    flights_path = _find_file([
        "Flight Level Data",
        "FlightLevelData",
        "flights"
    ])
    pnrfl_path = _find_file([
        "PNR+Flight+Level+Data",
        "PNR Flight Level",
        "PNRFlight"
    ])
    bag_path = _find_file([
        "Bag+Level+Data",
        "Bag Level Data",
        "bags"
    ])

    flights = _read_csv(flights_path)
    pnr_fl  = _read_csv(pnrfl_path)
    bags    = _read_csv(bag_path)

    # helpful for debugging
    flights.attrs["source_path"] = str(flights_path)
    pnr_fl.attrs["source_path"]  = str(pnrfl_path)
    bags.attrs["source_path"]    = str(bag_path)

    return flights, pnr_fl, bags


__all__ = ["DATA_DIR", "load_all"]

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ARTIFACTS = ROOT / "artifacts"
PLOTS = ARTIFACTS / "eda_plots"
OUTPUTS = ARTIFACTS / "outputs"
FLIGHT_FILE = DATA / "Flight Level Data.csv"
PNRFL_FILE  = DATA / "PNR+Flight+Level+Data.csv"
PNRRMK_FILE = DATA / "PNR Remark Level Data.csv"   
BAG_FILE    = DATA / "Bag+Level+Data.csv"
AP_FILE     = DATA / "Airports Data.csv"
FLIGHT_KEYS = [
    "company_id",
    "flight_number",
    "scheduled_departure_airport_code",
    "scheduled_arrival_airport_code",
    "scheduled_departure_datetime_local",
]

DELAY_THRESHOLD_MIN = 45
RANDOM_STATE = 42

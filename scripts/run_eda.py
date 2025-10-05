import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import load, features, labeler, eda

# load
flights = load.load_flight_level()
pnrfl   = load.load_pnr_flight()
bags    = load.load_bag_level()

# features
df = features.merge_all(flights, pnrfl, bags)
df = labeler.add_difficulty_label(df)
df = features.add_airport_route_rollups(df)
df = features.add_airport_equipment_flags(df)

# EDA deliverables
eda.eda_deliverables(df)
print("EDA complete.")

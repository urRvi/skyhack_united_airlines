import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import load, features, labeler, train, score

# 1) load
flights = load.load_flight_level()
pnrfl   = load.load_pnr_flight()
bags    = load.load_bag_level()

# 2) features
df = features.merge_all(flights, pnrfl, bags)
df = labeler.add_difficulty_label(df)
df = features.add_airport_route_rollups(df)
df = features.add_airport_equipment_flags(df)

# 3) train
model, feat_cols = train.train_and_save(df)

# 4) score
out_path = score.score_and_write(model, feat_cols, df)
print(f"Wrote {out_path}")

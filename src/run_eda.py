from src import load, features, labeler
from src.eda import eda_deliverables  
from src.config import OUTPUTS

if __name__ == "__main__":
    flights, pnrfl, bags = load.load_all()

    # Merge & feature build
    df = features.merge_all(flights, pnrfl, bags)
    df = labeler.add_difficulty_label(df)
    df = features.add_airport_equipment_flags(df)
    df = features.add_airport_route_rollups(df)

    # EDA outputs
    eda_deliverables(df)
    print("EDA complete. Outputs in:", OUTPUTS)

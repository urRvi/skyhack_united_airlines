import pandas as pd, numpy as np
from dataclasses import dataclass
from sklearn.model_selection import TimeSeriesSplit
from sklearn.calibration import CalibratedClassifierCV
from xgboost import XGBClassifier
from .config import OUTPUTS, RANDOM_STATE

OUTPUTS.mkdir(parents=True, exist_ok=True)

@dataclass
class ConstantProbModel:
    """Fallback model when labels are all one class."""
    p: float = 0.5
    def predict_proba(self, X):
        import numpy as np
        n = X.shape[0]
        return np.column_stack([1 - self.p * np.ones(n), self.p * np.ones(n)])
    @property
    def base_estimator(self): 
        return self

def _select_features(df: pd.DataFrame):
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    drop = [
        "difficult",
        "actual_departure_delay_minutes",
        "actual_arrival_delay_minutes",
        "cancellation_flag",
        "diversion_flag",
    ]
    time_cols = [c for c in df.columns if c.endswith("_datetime_local")]

    return [c for c in num_cols if c not in drop and c not in time_cols]

def train_and_save(df: pd.DataFrame):
    feature_cols = _select_features(df)
    X = df[feature_cols].fillna(0.0).values
    y = df["difficult"].astype(int).values

    pos = int(y.sum())
    neg = int((y == 0).sum())
    prior = y.mean() if len(y) else 0.5
    if pos == 0 or neg == 0:
        prior = float(prior if 0 < prior < 1 else 0.5)
        const_model = ConstantProbModel(p=prior)
        pd.DataFrame({"feature": feature_cols, "importance_gain": 0.0}).to_csv(
            OUTPUTS / "feature_importance.csv", index=False
        )
        return const_model, feature_cols

    spw = max(1.0, neg / max(1, pos))  # scale_pos_weight

    base = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        random_state=RANDOM_STATE,
        n_jobs=4,
        base_score=float(min(max(prior, 1e-6), 1-1e-6)),  
        scale_pos_weight=spw,
        tree_method="hist",          
    )

    tscv = TimeSeriesSplit(n_splits=4)
    model = CalibratedClassifierCV(base, method="isotonic", cv=tscv)
    model.fit(X, y)
    try:
        importances = pd.DataFrame({
            "feature": feature_cols,
            "importance_gain": model.base_estimator.feature_importances_
        }).sort_values("importance_gain", ascending=False)
    except Exception:
        importances = pd.DataFrame({"feature": feature_cols, "importance_gain": 0.0})

    importances.to_csv(OUTPUTS / "feature_importance.csv", index=False)
    return model, feature_cols

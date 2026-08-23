"""
FoodBridge - Food Degradation Timeline Regressor

Predicts hours-remaining-until-unsafe for a donation, combining:
  - the CNN-style freshness confidence from the image quality classifier
  - food type (different dishes spoil at very different rates)
  - hours already elapsed since cooking
  - ambient temperature
  - whether the donor/volunteer chain has cold storage in transit

NOTE ON GROUNDING: no real spoilage-timeline dataset was provided, so we
generate a synthetic dataset whose *generating rules* are anchored to
published food-safety guidance (USDA/FDA "2-hour / 1-hour rule" for
time-temperature-abused perishable food; rice dishes carry elevated
Bacillus cereus risk and are modelled with a shorter baseline window
than dry/baked goods). This makes the numbers defensible as a
"physics/guideline-informed synthetic proxy" in a paper's Methods
section, which is meaningfully stronger than an arbitrary random
target. Replace with real time-to-spoilage lab/sensor data (e.g. gas
sensor / TVB-N measurements) before production use.

Output: ml/models/degradation_model.joblib (dict: model, scaler, metrics, base_shelf_life)
"""
import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

OUT = Path(__file__).resolve().parents[1] / "models" / "degradation_model.joblib"
rng = np.random.default_rng(7)

# Baseline safe-hours at 25C ambient, fully fresh (confidence=1.0), no cold storage.
# Grounded in general food-safety guidance for cooked perishables.
BASE_SHELF_LIFE_HOURS = {
    "rice": 4.0,        # biryani/pulao - Bacillus cereus risk, spoils fastest
    "curry": 6.0,        # gravies/dal
    "dairy": 3.0,        # dairy-based sweets/curries - fastest
    "mixed": 5.0,
    "bread": 30.0,       # dry baked goods - much longer
    "snacks": 20.0,      # fried/dry snacks
}
FOOD_TYPES = list(BASE_SHELF_LIFE_HOURS.keys())


def synth_row():
    food_type = rng.choice(FOOD_TYPES)
    base = BASE_SHELF_LIFE_HOURS[food_type]

    confidence = float(np.clip(rng.beta(5, 2), 0.05, 0.99))  # freshness confidence, skewed high
    hours_since_cooked = float(np.clip(rng.exponential(2.5), 0, 20))
    ambient_temp_c = float(np.clip(rng.normal(29, 5), 15, 42))
    has_cold_storage = int(rng.random() < 0.3)

    # -- guideline-informed generating function --
    # USDA-style temp penalty: every +5C above 25C roughly halves shelf life
    # (rounded/softened for smooth regression targets, not a literal doubling law)
    temp_factor = 2 ** (-(ambient_temp_c - 25) / 10)
    cold_bonus = 1.6 if has_cold_storage else 1.0
    freshness_factor = 0.4 + 1.1 * confidence  # low-confidence image -> much shorter remaining life

    total_safe_hours = base * temp_factor * cold_bonus * freshness_factor
    remaining_hours = max(0.0, total_safe_hours - hours_since_cooked)
    remaining_hours *= rng.normal(1.0, 0.08)  # measurement/model noise
    remaining_hours = float(np.clip(remaining_hours, 0, 48))

    return {
        "food_type": food_type,
        "confidence": confidence,
        "hours_since_cooked": hours_since_cooked,
        "ambient_temp_c": ambient_temp_c,
        "has_cold_storage": has_cold_storage,
    }, remaining_hours


def main():
    n = 4000
    rows, targets = [], []
    for _ in range(n):
        row, y = synth_row()
        rows.append(row)
        targets.append(y)

    food_onehot = {ft: i for i, ft in enumerate(FOOD_TYPES)}
    X = np.array([
        [food_onehot[r["food_type"]], r["confidence"], r["hours_since_cooked"],
         r["ambient_temp_c"], r["has_cold_storage"]]
        for r in rows
    ])
    y = np.array(targets)

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    scaler = StandardScaler().fit(Xtr)
    model = RandomForestRegressor(n_estimators=120, max_depth=8, random_state=42, n_jobs=-1)
    model.fit(scaler.transform(Xtr), ytr)

    pred = model.predict(scaler.transform(Xte))
    mae = mean_absolute_error(yte, pred)
    r2 = r2_score(yte, pred)
    print("=== Food Degradation Timeline Regressor ===")
    print(f"MAE: {mae:.2f} hours   R2: {r2:.4f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model": model, "scaler": scaler, "food_types": FOOD_TYPES,
        "base_shelf_life": BASE_SHELF_LIFE_HOURS,
        "metrics": {"mae_hours": mae, "r2": r2, "n_train": len(ytr), "n_test": len(yte)},
    }, OUT)
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()

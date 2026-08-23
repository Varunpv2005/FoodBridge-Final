"""
FoodBridge - NGO Feedback Sentiment Model
NOTE ON ARCHITECTURE: the product scenario describes a fine-tuned BERT
transformer. This training environment has no internet access to
Hugging Face Hub (only PyPI/npm registries are reachable), so we train
a strong classical NLP pipeline instead: TF-IDF (word 1-2 grams) +
Linear SVM (calibrated for probabilities). This is a legitimate,
citable substitute for a paper (a common ablation baseline against
BERT) and is trivially swappable for a real `bert-base-uncased`
fine-tune once you have GPU + internet -- see README "Swapping in BERT".

Input : ml/data/FoodBridge_XAI_Large_Datasets.xlsx (NGO_Feedback_Sentiment)
Output: ml/models/sentiment_model.joblib (dict: pipeline, label_encoder, metrics)
"""
import pandas as pd
import joblib
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, f1_score
from sklearn.preprocessing import LabelEncoder

DATA = Path(__file__).resolve().parents[1] / "data" / "FoodBridge_XAI_Large_Datasets.xlsx"
OUT = Path(__file__).resolve().parents[1] / "models" / "sentiment_model.joblib"


def main():
    xl = pd.ExcelFile(DATA)
    df = xl.parse("NGO_Feedback_Sentiment").dropna(subset=["comment_text", "sentiment_label"])

    le = LabelEncoder()
    y = le.fit_transform(df["sentiment_label"])
    X = df["comment_text"].astype(str)

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=5000, sublinear_tf=True)),
        ("clf", CalibratedClassifierCV(LinearSVC(class_weight="balanced", random_state=42), cv=3)),
    ])
    pipe.fit(Xtr, ytr)

    pred = pipe.predict(Xte)
    acc = accuracy_score(yte, pred)
    f1 = f1_score(yte, pred, average="macro")
    print("=== NGO Feedback Sentiment Model (TF-IDF + Linear SVM) ===")
    print(f"Accuracy: {acc:.4f}  Macro-F1: {f1:.4f}")
    print(classification_report(yte, pred, target_names=le.classes_))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "pipeline": pipe,
        "label_encoder": le,
        "metrics": {"accuracy": acc, "macro_f1": f1, "n_train": len(ytr), "n_test": len(yte)},
    }, OUT)
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()

"""Train a simple local Arabic intent-classifier baseline. Synthetic toy data only."""
from pathlib import Path
import pandas as pd
import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, f1_score

BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "seed_messages.csv"
OUT = BASE / "results"
OUT.mkdir(exist_ok=True)
(BASE / "models").mkdir(exist_ok=True)
df = pd.read_csv(DATA).dropna(subset=["message", "intent"])
assert df["intent"].value_counts().min() >= 5
x_train, x_test, y_train, y_test = train_test_split(
    df["message"], df["intent"], test_size=0.25, stratify=df["intent"], random_state=42
)
model = Pipeline([
    ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)),
    ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced")),
])
model.fit(x_train, y_train)
pred = model.predict(x_test)
report = classification_report(y_test, pred, digits=3, zero_division=0)
macro_f1 = f1_score(y_test, pred, average="macro")
print("Synthetic-data holdout (not a real-world performance estimate)")
print(report)
print("macro-F1:", round(macro_f1, 3))
joblib.dump(model, BASE / "models" / "intent_baseline.joblib")
pd.DataFrame({"message": x_test.values, "true_intent": y_test.values, "predicted_intent": pred}).to_csv(
    OUT / "test_predictions.csv", index=False, encoding="utf-8-sig"
)
(OUT / "evaluation.txt").write_text(
    "Warning: this test uses synthetic seed messages only; do not report as deployed accuracy.\n\n" + report + "\nmacro_F1=" + str(round(macro_f1, 3)),
    encoding="utf-8",
)
print("Saved models/intent_baseline.joblib, results/evaluation.txt, results/test_predictions.csv")

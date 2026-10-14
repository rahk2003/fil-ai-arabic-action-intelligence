"""Select and train an improved classical model on the synthetic prototype data.

The original 24-row holdout is preserved for a controlled comparison. Model
selection uses a validation split made only from the original 72 training rows.
All resulting metrics remain synthetic-data diagnostics.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fil_ai.normalization import normalize_arabic  # noqa: E402

SEED = 42


def remove_holdout(full: pd.DataFrame, holdout: pd.DataFrame) -> pd.DataFrame:
    remaining = Counter(zip(holdout["message"], holdout["true_intent"]))
    keep = []
    for row in full.itertuples(index=False):
        key = (row.message, row.intent)
        if remaining[key] > 0:
            remaining[key] -= 1
            keep.append(False)
        else:
            keep.append(True)
    if any(remaining.values()):
        raise ValueError("The preserved holdout is not a subset of seed_messages.csv")
    return full.loc[keep].reset_index(drop=True)


def vectors(kind: str):
    word = TfidfVectorizer(preprocessor=normalize_arabic, analyzer="word", ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    char = TfidfVectorizer(preprocessor=normalize_arabic, analyzer="char_wb", ngram_range=(2, 5), min_df=1, sublinear_tf=True)
    if kind == "word":
        return word
    if kind == "char":
        return char
    return FeatureUnion([("word", word), ("char", char)])


def candidates() -> dict[str, Pipeline]:
    return {
        "word_lr": Pipeline([("features", vectors("word")), ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced", C=2.0, random_state=SEED))]),
        "char_lr": Pipeline([("features", vectors("char")), ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced", C=2.0, random_state=SEED))]),
        "word_char_lr": Pipeline([("features", vectors("combined")), ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced", C=2.0, random_state=SEED))]),
        "char_svm": Pipeline([("features", vectors("char")), ("classifier", LinearSVC(class_weight="balanced", C=1.0, random_state=SEED))]),
        "word_char_svm": Pipeline([("features", vectors("combined")), ("classifier", LinearSVC(class_weight="balanced", C=1.0, random_state=SEED))]),
    }


def main() -> None:
    full = pd.read_csv(ROOT / "data/seed_messages.csv").dropna(subset=["message", "intent"])
    holdout = pd.read_csv(ROOT / "results/baseline/original/test_predictions.csv")
    development = remove_holdout(full, holdout)
    x_train, x_validation, y_train, y_validation = train_test_split(
        development["message"], development["intent"], test_size=0.25,
        stratify=development["intent"], random_state=SEED,
    )
    results = []
    model_candidates = candidates()
    for name, model in model_candidates.items():
        model.fit(x_train, y_train)
        prediction = model.predict(x_validation)
        results.append({
            "model": name,
            "validation_accuracy": accuracy_score(y_validation, prediction),
            "validation_macro_f1": f1_score(y_validation, prediction, average="macro", zero_division=0),
        })
    validation = pd.DataFrame(results).sort_values(["validation_macro_f1", "validation_accuracy", "model"], ascending=[False, False, True])
    selected_name = str(validation.iloc[0]["model"])
    selected = candidates()[selected_name]
    selected.fit(development["message"], development["intent"])
    test_prediction = selected.predict(holdout["message"])
    test_accuracy = accuracy_score(holdout["true_intent"], test_prediction)
    test_macro_f1 = f1_score(holdout["true_intent"], test_prediction, average="macro", zero_division=0)

    model_path = ROOT / "models/intent_classical_v2.joblib"
    joblib.dump(selected, model_path)
    results_dir = ROOT / "results/classical_v2"
    results_dir.mkdir(parents=True, exist_ok=True)
    validation.to_csv(results_dir / "validation_results.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({"message": holdout["message"], "true_intent": holdout["true_intent"], "predicted_intent": test_prediction}).to_csv(results_dir / "test_predictions.csv", index=False, encoding="utf-8-sig")
    manifest = {
        "model": selected_name,
        "model_path": str(model_path.relative_to(ROOT)),
        "data_source": "96 manually authored synthetic messages",
        "development_rows": len(development),
        "selection_train_rows": len(x_train),
        "selection_validation_rows": len(x_validation),
        "preserved_test_rows": len(holdout),
        "random_seed": SEED,
        "test_accuracy": round(float(test_accuracy), 6),
        "test_macro_f1": round(float(test_macro_f1), 6),
        "warning": "Synthetic-only experiment; not a real-world performance estimate.",
    }
    (results_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

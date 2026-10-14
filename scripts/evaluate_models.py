"""Compare available local intent models on the same preserved holdout."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LABELS = ["new_task", "reschedule", "cancellation", "info_only"]


def main() -> None:
    holdout = pd.read_csv(ROOT / "results/baseline/original/test_predictions.csv")
    models = {
        "baseline_v1": ROOT / "models/baseline_v1/intent_baseline.joblib",
        "classical_v2": ROOT / "models/intent_classical_v2.joblib",
    }
    rows, report_sections = [], []
    output = ROOT / "results/evaluation"
    output.mkdir(parents=True, exist_ok=True)
    for name, path in models.items():
        if not path.is_file():
            rows.append({"model": name, "status": "Not evaluated", "accuracy": None, "macro_f1": None, "weighted_f1": None})
            continue
        model = joblib.load(path)
        prediction = model.predict(holdout["message"])
        metrics = {
            "model": name,
            "status": "evaluated_on_preserved_synthetic_holdout",
            "accuracy": accuracy_score(holdout["true_intent"], prediction),
            "macro_f1": f1_score(holdout["true_intent"], prediction, average="macro", zero_division=0),
            "weighted_f1": f1_score(holdout["true_intent"], prediction, average="weighted", zero_division=0),
        }
        rows.append(metrics)
        report = pd.DataFrame(classification_report(holdout["true_intent"], prediction, labels=LABELS, output_dict=True, zero_division=0)).T
        report.to_csv(output / f"{name}_classification_report.csv", encoding="utf-8-sig")
        matrix = pd.DataFrame(confusion_matrix(holdout["true_intent"], prediction, labels=LABELS), index=LABELS, columns=LABELS)
        matrix.to_csv(output / f"{name}_confusion_matrix.csv", encoding="utf-8-sig")
        pd.DataFrame({"message": holdout["message"], "true_intent": holdout["true_intent"], "predicted_intent": prediction}).query("true_intent != predicted_intent").to_csv(output / f"{name}_errors.csv", index=False, encoding="utf-8-sig")
        report_sections.append(f"- **{name}** — accuracy {metrics['accuracy']:.3f}, macro-F1 {metrics['macro_f1']:.3f}, weighted-F1 {metrics['weighted_f1']:.3f}")
    comparison = pd.DataFrame(rows)
    comparison.to_csv(ROOT / "results/model_comparison.csv", index=False, encoding="utf-8-sig")
    transformer_status = "Not evaluated — no human-verified in-domain training set or fine-tuned checkpoint."
    report_text = "# FI'L AI Model Comparison\n\nAll evaluated models below use the exact same 24-row preserved synthetic holdout. These numbers do not measure real-world performance.\n\n" + "\n".join(report_sections) + f"\n\n- **CAMeLBERT classifier** — {transformer_status}\n\nModel selection for classical_v2 used a separate validation subset of the original training portion. The preserved holdout was not used to select the feature/model family.\n\n## Unavailable controlled metrics\n\n- Performance by Arabic writing style: **Not evaluated** — style is not annotated in the seed data.\n- Extraction precision/recall/F1 and datetime exact match: **Not evaluated** — no reviewed extraction test set exists.\n- Context matching precision/recall/F1: **Not evaluated** — no labeled message-pair test set exists.\n"
    (ROOT / "reports/model_comparison.md").write_text(report_text, encoding="utf-8")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()

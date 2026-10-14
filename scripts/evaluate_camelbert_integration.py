"""Compare the baseline and local CAMeLBERT on the same synthetic holdout.

This is evaluation only: no model is trained and no corrections are hard-coded.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fil_ai.config import INTENTS  # noqa: E402
from fil_ai.inference import ModelRegistry  # noqa: E402

KNOWN_FAILURES = [
    {"message": "بكرة الدوام أون لاين", "expected_intent": "info_only"},
    {"message": "تم اعتماد التقرير النهائي", "expected_intent": "info_only"},
]


def evaluate(input_path: Path, output_dir: Path, device: str) -> dict[str, object]:
    frame = pd.read_csv(input_path)
    required = {"message", "true_intent"}
    if not required.issubset(frame.columns):
        raise ValueError(f"{input_path} must contain {sorted(required)}")
    if not set(frame["true_intent"]).issubset(INTENTS):
        raise ValueError("Evaluation data contains unsupported labels")

    registry = ModelRegistry(
        ROOT / "models/intent_baseline.joblib",
        ROOT / "models/FIL_AI_CAMeLBERT",
        transformer_device=device,
    )
    predictions: dict[str, list[str]] = {"baseline": [], "camelbert": []}
    scores: dict[str, list[float | None]] = {"baseline": [], "camelbert": []}
    latencies: dict[str, list[float]] = {"baseline": [], "camelbert": []}
    identifiers: dict[str, str] = {}

    for model_key in ("baseline", "camelbert"):
        model = registry.get(model_key)
        identifiers[model_key] = model.name
        for message in frame["message"].astype(str):
            result = model.predict(message)
            predictions[model_key].append(result.label)
            scores[model_key].append(result.confidence)
            latencies[model_key].append(result.inference_latency_ms)

    detailed = frame[["message", "true_intent"]].copy()
    for model_key in ("baseline", "camelbert"):
        detailed[f"{model_key}_prediction"] = predictions[model_key]
        detailed[f"{model_key}_uncalibrated_score"] = scores[model_key]
        detailed[f"{model_key}_latency_ms"] = latencies[model_key]
        detailed[f"{model_key}_correct"] = detailed[f"{model_key}_prediction"] == detailed["true_intent"]

    metrics = []
    for model_key in ("baseline", "camelbert"):
        precision, recall, f1, _ = precision_recall_fscore_support(
            detailed["true_intent"],
            predictions[model_key],
            labels=list(INTENTS),
            average="macro",
            zero_division=0,
        )
        _, _, weighted_f1, _ = precision_recall_fscore_support(
            detailed["true_intent"],
            predictions[model_key],
            labels=list(INTENTS),
            average="weighted",
            zero_division=0,
        )
        metrics.append(
            {
                "model": model_key,
                "model_identifier": identifiers[model_key],
                "accuracy": accuracy_score(detailed["true_intent"], predictions[model_key]),
                "macro_precision": precision,
                "macro_recall": recall,
                "macro_f1": f1,
                "weighted_f1": weighted_f1,
                "mean_inference_latency_ms": sum(latencies[model_key]) / len(latencies[model_key]),
                "rows": len(detailed),
                "data_provenance": "synthetic_holdout",
            }
        )

    known_rows = []
    for case in KNOWN_FAILURES:
        row = dict(case)
        for model_key in ("baseline", "camelbert"):
            result = registry.get(model_key).predict(case["message"])
            row[f"{model_key}_prediction"] = result.label
            row[f"{model_key}_uncalibrated_score"] = result.confidence
            row[f"{model_key}_latency_ms"] = result.inference_latency_ms
        row["category"] = "known_info_only_false_positive"
        row["hard_coded_correction"] = False
        known_rows.append(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    detailed.to_csv(output_dir / "same_holdout_predictions.csv", index=False)
    pd.DataFrame(metrics).to_csv(output_dir / "same_holdout_metrics.csv", index=False)
    pd.DataFrame(known_rows).to_csv(output_dir / "known_failure_cases.csv", index=False)
    summary = {
        "checkpoint": str(ROOT / "models/FIL_AI_CAMeLBERT"),
        "id2label": registry.get("camelbert").id2label,
        "runtime_device": registry.get("camelbert").device,
        "evaluation_set": str(input_path),
        "evaluation_rows": len(detailed),
        "evaluation_provenance": "synthetic",
        "independent_test": False,
        "leakage_warning": (
            "This 24-row set overlaps the 500-message CAMeLBERT fine-tuning corpus; "
            "95.8% is not an independent generalization estimate."
        ),
        "real_world_accuracy_claim": False,
        "reported_external_synthetic_accuracy": 0.896,
        "reported_external_baseline_accuracy": 0.72,
        "reported_external_metric_note": (
            "User-reported Colab test accuracy; not assumed to be the same split as this holdout."
        ),
        "metrics": metrics,
    }
    (output_dir / "integration_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "results/test_predictions.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/camelbert")
    parser.add_argument("--device", choices=["auto", "cpu", "mps"], default="auto")
    args = parser.parse_args()
    summary = evaluate(args.input, args.output_dir, args.device)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

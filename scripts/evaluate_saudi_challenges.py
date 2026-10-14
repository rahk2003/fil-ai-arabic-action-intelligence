"""Run both real local classifiers on the curated Saudi Arabic challenge set.

The set is synthetic and rows marked needs_context are never scored. This script
does not train, modify, or hard-code either model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fil_ai.inference import ModelRegistry  # noqa: E402


def evaluate(input_path: Path, output_dir: Path, device: str) -> dict[str, object]:
    frame = pd.read_csv(input_path, keep_default_na=False)
    registry = ModelRegistry(
        ROOT / "models/intent_baseline.joblib",
        ROOT / "models/FIL_AI_CAMeLBERT",
        transformer_device=device,
    )
    for model_key in ("baseline", "camelbert"):
        predictions: list[str] = []
        scores: list[float | None] = []
        latencies: list[float] = []
        for message in frame["message"].astype(str):
            result = registry.get(model_key).predict(message)
            predictions.append(result.label)
            scores.append(result.confidence)
            latencies.append(result.inference_latency_ms)
        frame[f"{model_key}_prediction"] = predictions
        frame[f"{model_key}_uncalibrated_score"] = scores
        frame[f"{model_key}_latency_ms"] = latencies
        frame[f"{model_key}_correct"] = [
            prediction == reference if reference else "not_scored"
            for prediction, reference in zip(predictions, frame["reference_intent"])
        ]

    scored = frame[frame["reference_intent"] != ""].copy()
    metrics: dict[str, object] = {}
    for model_key in ("baseline", "camelbert"):
        predicted = scored[f"{model_key}_prediction"]
        metrics[model_key] = {
            "identifier": registry.get(model_key).name,
            "accuracy": accuracy_score(scored["reference_intent"], predicted),
            "macro_f1": f1_score(scored["reference_intent"], predicted, average="macro", zero_division=0),
            "scored_rows": len(scored),
            "mean_latency_ms": float(frame[f"{model_key}_latency_ms"].mean()),
        }
    summary = {
        "data_provenance": "synthetic_demo_challenge_set",
        "human_verified": False,
        "scored_rows": len(scored),
        "needs_context_rows": int((frame["reference_intent"] == "").sum()),
        "metrics": metrics,
        "limitations": [
            "Small curated synthetic challenge set; not a real-world accuracy estimate.",
            "Rows requiring conversation context are excluded from accuracy and F1.",
            "This set must remain outside training and requires independent human review.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_dir / "saudi_challenge_predictions.csv", index=False)
    (output_dir / "saudi_challenge_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "data/evaluation/saudi_challenge_set.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/camelbert")
    parser.add_argument("--device", choices=["auto", "cpu", "mps"], default="auto")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.input, args.output_dir, args.device), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

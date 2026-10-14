"""Compare lexical and local embedding matching on one labeled pair set.

The benchmark is tiny and synthetic/derived from user-provided demo examples. It
is a workflow diagnostic, not a real-world accuracy estimate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fil_ai.context import similarity  # noqa: E402
from fil_ai.semantic import get_semantic_matcher  # noqa: E402

DATA = ROOT / "data/evaluation/context_pair_benchmark.csv"
OUTPUT = ROOT / "results/context_matching"


def metrics(truth: list[int], predictions: list[int]) -> dict[str, float]:
    precision, recall, f1, _ = precision_recall_fscore_support(truth, predictions, average="binary", zero_division=0)
    return {"accuracy": accuracy_score(truth, predictions), "precision": precision, "recall": recall, "f1": f1}


def main() -> None:
    frame = pd.read_csv(DATA)
    matcher = get_semantic_matcher(
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        str(ROOT / "models/embedding_cache"),
        True,
        True,
    )
    if not matcher.ensure_loaded():
        raise SystemExit(matcher.warning or "Embedding model unavailable")
    frame["lexical_score"] = [similarity(left, right) for left, right in zip(frame.previous_message, frame.followup_message)]
    frame["embedding_score"] = [
        matcher.similarities(followup, [previous])[0]
        for previous, followup in zip(frame.previous_message, frame.followup_message)
    ]
    validation = frame[frame.split == "validation"]
    thresholds = [round(value / 100, 2) for value in range(20, 81, 5)]
    embedding_threshold = max(thresholds, key=lambda threshold: (metrics(validation.related.tolist(), (validation.embedding_score >= threshold).astype(int).tolist())["f1"], threshold))
    lexical_threshold = 0.20
    frame["lexical_prediction"] = (frame.lexical_score >= lexical_threshold).astype(int)
    frame["embedding_prediction"] = (frame.embedding_score >= embedding_threshold).astype(int)
    validation = frame[frame.split == "validation"]
    test = frame[frame.split == "test"]
    summary = {
        "model": matcher.status(),
        "data_provenance": "tiny synthetic benchmark from user-provided capstone examples plus explicitly labeled cross-pairs",
        "real_world_accuracy_claim": False,
        "validation_rows": len(validation), "test_rows": len(test),
        "thresholds": {"lexical": lexical_threshold, "embeddings": embedding_threshold},
        "validation": {
            "lexical": metrics(validation.related.tolist(), validation.lexical_prediction.tolist()),
            "embeddings": metrics(validation.related.tolist(), validation.embedding_prediction.tolist()),
        },
        "test": {
            "lexical": metrics(test.related.tolist(), test.lexical_prediction.tolist()),
            "embeddings": metrics(test.related.tolist(), test.embedding_prediction.tolist()),
        },
        "false_matches_test": {
            "lexical": int(((test.related == 0) & (test.lexical_prediction == 1)).sum()),
            "embeddings": int(((test.related == 0) & (test.embedding_prediction == 1)).sum()),
        },
        "limitations": [
            "Only 12 synthetic/derived pairs are available; four validation rows are insufficient for stable threshold tuning.",
            "Related pairs are adjacent-message examples, so recency and user confirmation remain required in production.",
            "Cosine similarity never commits or merges a task by itself.",
        ],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT / "pair_predictions.csv", index=False)
    (OUTPUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

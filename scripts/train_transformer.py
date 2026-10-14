"""Fine-tune CAMeLBERT only on explicitly human-verified FI'L AI labels.

This script intentionally refuses to train on unreviewed MASSIVE candidates.
For an 8 GB Mac, use the supplied Colab notebook unless a small verified dataset
and a compatible local PyTorch installation are available.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

MODEL_ID = "CAMeL-Lab/bert-base-arabic-camelbert-da"
LABELS = ["new_task", "reschedule", "cancellation", "info_only"]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=root / "data/annotation/annotation_template.csv")
    parser.add_argument("--output", type=Path, default=root / "models/camelbert_fil_ai")
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    args = parser.parse_args()
    import pandas as pd
    if not args.data.is_file():
        raise SystemExit(f"Missing annotated dataset: {args.data}")
    frame = pd.read_csv(args.data)
    required = {"message", "intent", "label_status"}
    if not required.issubset(frame.columns):
        raise SystemExit(f"Annotated CSV must contain {sorted(required)}")
    verified = frame[frame["label_status"].eq("human_verified") & frame["intent"].isin(LABELS)].dropna(subset=["message", "intent"])
    counts = verified["intent"].value_counts().reindex(LABELS, fill_value=0)
    if len(verified) < 80 or int(counts.min()) < 10:
        raise SystemExit(
            "Training blocked: need at least 80 human-verified in-domain rows and 10 per class. "
            f"Found {len(verified)} rows with counts {counts.to_dict()}. Unreviewed MASSIVE labels are never accepted."
        )
    try:
        import numpy as np
        import torch
        from datasets import Dataset
        from sklearn.model_selection import train_test_split
        from transformers import AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding, EarlyStoppingCallback, Trainer, TrainingArguments
    except ImportError as error:
        raise SystemExit("Install requirements-transformer.txt under Python 3.11/3.12 or use notebooks/train_camelbert_colab.ipynb") from error
    seed = 42
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    train, validation = train_test_split(verified, test_size=0.2, stratify=verified["intent"], random_state=seed)
    label2id = {label: index for index, label in enumerate(LABELS)}
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    def tokenize(batch):
        encoded = tokenizer(batch["message"], truncation=True, max_length=128)
        encoded["labels"] = [label2id[label] for label in batch["intent"]]
        return encoded
    train_ds = Dataset.from_pandas(train[["message", "intent"]], preserve_index=False).map(tokenize, batched=True)
    validation_ds = Dataset.from_pandas(validation[["message", "intent"]], preserve_index=False).map(tokenize, batched=True)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID, num_labels=4, label2id=label2id, id2label={v: k for k, v in label2id.items()})
    args.output.mkdir(parents=True, exist_ok=True)
    training_args = TrainingArguments(output_dir=str(args.output), learning_rate=args.learning_rate, per_device_train_batch_size=args.batch_size, per_device_eval_batch_size=args.batch_size, gradient_accumulation_steps=4, num_train_epochs=args.epochs, eval_strategy="epoch", save_strategy="epoch", load_best_model_at_end=True, metric_for_best_model="eval_loss", greater_is_better=False, seed=seed, report_to=[])
    trainer = Trainer(model=model, args=training_args, train_dataset=train_ds, eval_dataset=validation_ds, processing_class=tokenizer, data_collator=DataCollatorWithPadding(tokenizer), callbacks=[EarlyStoppingCallback(early_stopping_patience=2)])
    trainer.train()
    metrics = trainer.evaluate()
    trainer.save_model(args.output / "best")
    tokenizer.save_pretrained(args.output / "best")
    (args.output / "training_manifest.json").write_text(json.dumps({"model_id": MODEL_ID, "verified_rows": len(verified), "validation_metrics": metrics, "labels": LABELS, "seed": seed}, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

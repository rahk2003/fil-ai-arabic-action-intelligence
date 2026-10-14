# Training Guide

Use Python 3.12 on macOS; Python 3.14 currently lacks several required ML packages in this project.

```bash
python3.12 -m venv .venv312
source .venv312/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt -r requirements-data.txt
python scripts/download_massive.py
python scripts/explore_dataset.py
python scripts/prepare_massive_candidates.py
python scripts/train_classical.py
python scripts/evaluate_models.py
pytest -q
```

The classical script preserves the original holdout, selects on validation only, and labels all output synthetic-only. Do not promote `intent_classical_v2.joblib` unless the controlled evaluation and regression suite justify it.

For CAMeLBERT, review `data/annotation/annotation_template.csv`, mark only genuinely reviewed rows `human_verified`, and use the Colab notebook or:

```bash
python -m pip install -r requirements-transformer.txt
python scripts/train_transformer.py --data data/annotation/annotation_template.csv
```

The script refuses to train below its minimum verified-label threshold and refuses unreviewed rows. The intended configuration is max length 128, learning rate 2e-5, 4 epochs, gradient accumulation, early stopping, and best-checkpoint loading. No private data is uploaded automatically.

"""Explore downloaded MASSIVE ar-SA Parquet files without changing labels."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fil_ai.normalization import normalize_arabic  # noqa: E402

RAW = ROOT / "data/raw/amazon_massive"
RESULTS = ROOT / "results/data"
REPORT = ROOT / "reports/dataset_exploration.md"


def distribution_png(distribution: pd.DataFrame, path: Path) -> None:
    scenario = distribution.groupby("scenario", as_index=False)["count"].sum().sort_values("count", ascending=False)
    image = Image.new("RGB", (1100, 650), "white")
    draw = ImageDraw.Draw(image)
    font, title = ImageFont.load_default(size=15), ImageFont.load_default(size=22)
    draw.text((40, 25), "Amazon MASSIVE ar-SA - examples by scenario", fill="#172033", font=title)
    maximum = max(1, int(scenario["count"].max()))
    for index, row in enumerate(scenario.itertuples(index=False)):
        y, bar = 80 + index * 30, int(700 * row.count / maximum)
        draw.text((40, y), str(row.scenario), fill="#172033", font=font)
        draw.rectangle((260, y, 260 + bar, y + 19), fill="#3157d5")
        draw.text((270 + bar, y), str(row.count), fill="#172033", font=font)
    image.save(path)


def main() -> None:
    files = {split: RAW / f"{split}.parquet" for split in ("train", "validation", "test")}
    missing = [str(path) for path in files.values() if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing MASSIVE files. Run scripts/download_massive.py first: {missing}")
    RESULTS.mkdir(parents=True, exist_ok=True)
    frames, split_counts = [], {}
    for split, path in files.items():
        frame = pd.read_parquet(path)
        frame["source_split"] = split
        frames.append(frame)
        split_counts[split] = len(frame)
    data = pd.concat(frames, ignore_index=True)
    required = {"id", "locale", "scenario", "intent", "utt", "annot_utt"}
    missing_columns = required.difference(data.columns)
    if missing_columns:
        raise SystemExit(f"Unexpected MASSIVE schema; missing {sorted(missing_columns)}")
    distribution = data.groupby(["source_split", "scenario", "intent"], dropna=False).size().rename("count").reset_index()
    distribution.to_csv(RESULTS / "intent_distribution.csv", index=False, encoding="utf-8-sig")
    normalized = data["utt"].fillna("").map(lambda x: normalize_arabic(x, remove_punctuation=True))
    duplicate_groups = int((normalized.value_counts() > 1).sum())
    duplicate_rows = int(normalized.duplicated(keep=False).sum())
    missing_values = {column: int(value) for column, value in data.isna().sum().items()}
    slot_examples = data[data["annot_utt"].fillna("").str.contains(r"\[(?:date|time)\s*:", regex=True)]
    summary = {
        "source": "AmazonScience/massive", "source_url": "https://huggingface.co/datasets/AmazonScience/massive",
        "license": "CC BY 4.0", "locale": "ar-SA", "split_counts": split_counts,
        "total_rows": len(data), "columns": list(data.columns), "scenarios": int(data["scenario"].nunique()),
        "intents": int(data["intent"].nunique()), "missing_values": missing_values,
        "normalized_duplicate_groups": duplicate_groups, "normalized_duplicate_rows": duplicate_rows,
        "date_or_time_annotated_rows": len(slot_examples),
        "warning": "MASSIVE labels are virtual-assistant intents, not FI'L AI workplace-action labels.",
    }
    (RESULTS / "dataset_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    distribution_png(distribution, RESULTS / "dataset_distribution.png")
    samples = data[["source_split", "utt", "scenario", "intent"]].drop_duplicates("intent").head(20)
    sample_lines = "\n".join(f"| {r.source_split} | {str(r.utt).replace('|', '/')} | {r.scenario} | {r.intent} |" for r in samples.itertuples(index=False))
    missing_lines = "\n".join(f"| {column} | {count} |" for column, count in missing_values.items())
    REPORT.write_text(f"""# Amazon MASSIVE ar-SA Dataset Exploration

## Verified source

- Official repository: https://huggingface.co/datasets/AmazonScience/massive
- Locale: `ar-SA`; license: **CC BY 4.0**
- Rows: train {split_counts['train']:,}, validation/dev {split_counts['validation']:,}, test {split_counts['test']:,}; total {len(data):,}
- Original split membership, scenario, intent, utterance, and slot annotations are preserved.

MASSIVE contains localized single-shot virtual-assistant utterances across 60 intents and 18 scenarios. It is not a corpus of real workplace messages and its labels must not be silently converted into FI'L AI's four intents.

## Schema

`{', '.join(data.columns)}`

## Quality checks

- Unique scenarios: {data['scenario'].nunique()}; unique intents: {data['intent'].nunique()}
- Normalized duplicate groups: {duplicate_groups}; rows involved: {duplicate_rows}
- Rows with explicit date/time slot annotations: {len(slot_examples):,}

| Column | Missing |
| --- | ---: |
{missing_lines}

## Representative samples

| Split | Utterance | Scenario | Original intent |
| --- | --- | --- | --- |
{sample_lines}

The date/time spans are directly useful for extraction research. Scheduling/reminder examples are only annotation candidates for FI'L AI; supervised four-label use requires human review.
""", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

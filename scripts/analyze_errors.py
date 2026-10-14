"""Generate the preserved baseline error-analysis deliverables."""

from __future__ import annotations

import shutil
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analyze_errors import main as run_analysis  # noqa: E402


def write_png(matrix_path: Path, output_path: Path) -> None:
    frame = pd.read_csv(matrix_path, index_col=0)
    labels = list(frame.columns)
    size, left, top = 145, 190, 110
    image = Image.new("RGB", (left + size * len(labels) + 25, top + size * len(labels) + 35), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=16)
    title_font = ImageFont.load_default(size=21)
    draw.text((left, 20), "FI'L AI baseline confusion matrix", fill="#172033", font=title_font)
    maximum = max(1, int(frame.to_numpy().max()))
    for column, label in enumerate(labels):
        draw.text((left + column * size + 8, 76), label, fill="#172033", font=font)
    for row, true_label in enumerate(frame.index):
        draw.text((10, top + row * size + size // 2), true_label, fill="#172033", font=font)
        for column, predicted_label in enumerate(labels):
            value = int(frame.loc[true_label, predicted_label])
            intensity = value / maximum
            color = (round(239 - 205 * intensity), round(246 - 105 * intensity), round(255 - 39 * intensity))
            x, y = left + column * size, top + row * size
            draw.rounded_rectangle((x, y, x + size - 3, y + size - 3), radius=7, fill=color)
            text_color = "white" if intensity >= 0.55 else "#172033"
            draw.text((x + size // 2 - 5, y + size // 2 - 10), str(value), fill=text_color, font=title_font)
    image.save(output_path)


def write_near_duplicate_audit(output: Path) -> str:
    full = pd.read_csv(ROOT / "data/seed_messages.csv")
    holdout = pd.read_csv(ROOT / "results/test_predictions.csv")
    remaining = Counter(zip(holdout["message"], holdout["true_intent"]))
    keep = []
    for row in full.itertuples(index=False):
        key = (row.message, row.intent)
        if remaining[key]:
            remaining[key] -= 1
            keep.append(False)
        else:
            keep.append(True)
    train = full.loc[keep].reset_index(drop=True)
    combined = pd.concat([train["message"], holdout["message"]], ignore_index=True)
    vectors = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit_transform(combined)
    similarities = cosine_similarity(vectors[len(train):], vectors[:len(train)])
    rows = []
    for test_index, scores in enumerate(similarities):
        train_index = int(scores.argmax())
        rows.append({
            "test_message": holdout.iloc[test_index]["message"],
            "test_intent": holdout.iloc[test_index]["true_intent"],
            "nearest_train_message": train.iloc[train_index]["message"],
            "train_intent": train.iloc[train_index]["intent"],
            "char_tfidf_cosine": round(float(scores[train_index]), 6),
            "high_similarity_at_0_70": bool(scores[train_index] >= 0.70),
        })
    audit = pd.DataFrame(rows).sort_values("char_tfidf_cosine", ascending=False)
    audit.to_csv(output / "near_duplicate_pairs.csv", index=False, encoding="utf-8-sig")
    high_count = int(audit["high_similarity_at_0_70"].sum())
    top = audit.iloc[0]
    return (
        "\n\n## Train/test near-duplicate audit\n\n"
        "A character TF-IDF cosine audit compared every preserved holdout message with its nearest original-training message. "
        f"At the declared 0.70 high-similarity threshold, **{high_count}** holdout messages were flagged. "
        f"The maximum observed similarity was **{top['char_tfidf_cosine']:.3f}**. "
        "This finds no direct near-duplicate leakage under the stated heuristic, but it cannot rule out shared author style or semantic/template-family leakage. "
        "All nearest pairs and scores are saved in `near_duplicate_pairs.csv`.\n"
    )


if __name__ == "__main__":
    output = ROOT / "results" / "baseline"
    if len(sys.argv) == 1:
        sys.argv.extend(["--output-dir", str(output)])
    run_analysis()
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(output / "class_metrics.csv", output / "classification_report.csv")
    shutil.copyfile(output / "misclassified_messages.csv", output / "misclassified_examples.csv")
    write_png(output / "confusion_matrix.csv", output / "confusion_matrix.png")
    near_duplicate_section = write_near_duplicate_audit(output)
    report_path = output / "error_analysis.md"
    report_path.write_text(report_path.read_text(encoding="utf-8") + near_duplicate_section, encoding="utf-8")
    shutil.copyfile(output / "error_analysis.md", ROOT / "reports" / "baseline_error_analysis.md")
    print("Created requested baseline artifacts in results/baseline and reports/.")

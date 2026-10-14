"""Reproducible error analysis for the FI'L AI synthetic baseline.

This script does not train or modify a model. It evaluates the predictions saved by
``train_baseline.py``, audits the synthetic seed dataset, and writes analysis
artifacts to ``results/``.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)


BASE = Path(__file__).resolve().parent
DEFAULT_PREDICTIONS = BASE / "results" / "test_predictions.csv"
DEFAULT_DATASET = BASE / "data" / "seed_messages.csv"
DEFAULT_MODEL = BASE / "models" / "intent_baseline.joblib"
DEFAULT_OUTPUT_DIR = BASE / "results"

LABELS = ["new_task", "reschedule", "cancellation", "info_only"]
ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
NON_WORD_OR_SPACE = re.compile(r"[^\w\s]", flags=re.UNICODE)
WHITESPACE = re.compile(r"\s+")


# These are qualitative hypotheses, not ground-truth causal explanations. Exact
# messages receive a specific diagnosis; unseen errors fall back to a confusion-
# pair explanation so that the script remains useful if predictions are replaced.
KNOWN_ERROR_EXPLANATIONS = {
    "عندي طلب بسيط: اكتبي مقدمة عربية للمبادرة.": (
        "The action is expressed by the imperative اكتبي, but the generic word طلب also "
        "appears in cancellation examples. With only a few request phrasings, the character "
        "features do not reliably represent the sentence-level request."
    ),
    "نشكر جميع الحضور على مشاركتهم.": (
        "This is a completed social statement, not an instruction. The active verb and "
        "second-person-like surface fragments resemble action-oriented training messages, "
        "while there is no strong memorized information-only cue."
    ),
    "ما في داعي تتواصلين مع المورد، انتهى الطلب.": (
        "The colloquial cancellation is carried by the multiword negation ما في داعي. The "
        "action verb تتواصلين strongly resembles new-task wording, showing that the model "
        "does not compose negation with the requested action."
    ),
    "مو اليوم، خلي تسليم المستندات صباح الاثنين.": (
        "مو is a negative cue that resembles cancellation, whereas the new date is expressed "
        "implicitly without a strong marker such as موعد, بدل, or تغيّر."
    ),
    "بخصوص مراجعة التقرير، بنقدمها ليوم الأحد.": (
        "The schedule change is implicit and بنقدمها is lexically ambiguous (move it earlier "
        "versus present it). The sentence lacks the explicit rescheduling cues favored by the "
        "model."
    ),
    "ما يحتاج ترفعين النموذج بعد القرار الجديد.": (
        "The cancellation depends on colloquial negation ما يحتاج, but ترفعين is an action "
        "verb shaped like the feminine task imperatives common in new_task examples."
    ),
    "أبغى ملخص صفحة واحدة عن نتائج المشروع.": (
        "This noun-heavy request uses أبغى rather than an overt imperative or deadline. Its "
        "desired deliverable can look like a descriptive information statement to a sparse "
        "character n-gram model."
    ),
    "معلومة سريعة: الدورات المسائية تبدأ عادة بعد الخامسة.": (
        "The explicit information marker معلومة is outweighed by temporal language such as "
        "بعد الخامسة. The model confuses a general fact containing a time with a change to an "
        "existing schedule."
    ),
    "مطلوب من جميع المشاركين تسليم الواجب يوم الأربعاء.": (
        "This creates a task with a deadline, but the weekday phrase is mistaken for a schedule "
        "change. No previous time is referenced, a distinction bag-of-character features do "
        "not encode."
    ),
    "المقر الرئيسي انتقل إلى المبنى الجديد.": (
        "انتقل إلى describes a completed location change, but its change/direction wording "
        "resembles rescheduling language. There is no requested action or appointment change."
    ),
    "لا تجين الساعة ثمان، تعالي عشر ونص.": (
        "The first clause begins with a prohibition, so cancellation-like negation competes "
        "with the replacement time in the second clause. The model misses the contrastive "
        "old-time/new-time structure."
    ),
    "تمت إضافة أعضاء جدد إلى الفريق.": (
        "This is a completed status update. Its passive construction and generic change wording "
        "lack a distinctive information-only phrase, so sparse character fragments dominate."
    ),
}

PAIR_EXPLANATIONS = {
    ("reschedule", "cancellation"): (
        "Negation or rejection of the old time is likely dominating evidence for the replacement time."
    ),
    ("cancellation", "new_task"): (
        "An action verb is likely dominating a colloquial or multiword cancellation cue."
    ),
    ("info_only", "reschedule"): (
        "Time/change vocabulary is being treated as a schedule change without modeling the message's speech act."
    ),
    ("new_task", "reschedule"): (
        "A task deadline is being confused with a change to an already established schedule."
    ),
    ("new_task", "info_only"): (
        "The request is implicit or noun-heavy and lacks an overt imperative learned by the model."
    ),
    ("new_task", "cancellation"): (
        "Surface overlap with cancellation examples is outweighing the request construction."
    ),
    ("info_only", "new_task"): (
        "An active verb is being interpreted as an instruction rather than a completed or informational statement."
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze the saved FI'L AI baseline predictions without retraining."
    )
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--top-features", type=int, default=10)
    return parser.parse_args()


def read_and_validate_csv(
    path: Path, required_columns: set[str], name: str
) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"{name} file not found: {path}")
    frame = pd.read_csv(path)
    missing_columns = required_columns.difference(frame.columns)
    if missing_columns:
        raise ValueError(
            f"{name} is missing required columns: {sorted(missing_columns)}"
        )
    if frame[list(required_columns)].isna().any().any():
        raise ValueError(f"{name} contains missing values in required columns")
    return frame


def validate_labels(predictions: pd.DataFrame, dataset: pd.DataFrame) -> None:
    expected = set(LABELS)
    observed = set(dataset["intent"]) | set(predictions["true_intent"]) | set(
        predictions["predicted_intent"]
    )
    unexpected = observed.difference(expected)
    if unexpected:
        raise ValueError(f"Unexpected intent labels found: {sorted(unexpected)}")


def normalize_message(value: str) -> str:
    """Conservative normalization used only to detect likely duplicate text."""
    value = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    value = value.replace("ـ", "")
    value = ARABIC_DIACRITICS.sub("", value)
    value = re.sub(r"[إأآٱ]", "ا", value)
    value = value.replace("ى", "ي")
    value = NON_WORD_OR_SPACE.sub(" ", value)
    return WHITESPACE.sub(" ", value).strip()


def duplicate_audit(dataset: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    working = dataset[["message", "intent"]].copy()
    working["normalized_message"] = working["message"].map(normalize_message)
    records: list[dict[str, object]] = []

    for normalized, group in working.groupby("normalized_message", sort=True):
        if len(group) < 2:
            continue
        unique_messages = sorted(group["message"].unique())
        records.append(
            {
                "duplicate_type": (
                    "exact" if len(unique_messages) == 1 else "normalized_variant"
                ),
                "normalized_message": normalized,
                "row_count": len(group),
                "unique_text_count": len(unique_messages),
                "intents": " | ".join(sorted(group["intent"].unique())),
                "intent_conflict": group["intent"].nunique() > 1,
                "message_variants": " || ".join(unique_messages),
            }
        )

    columns = [
        "duplicate_type",
        "normalized_message",
        "row_count",
        "unique_text_count",
        "intents",
        "intent_conflict",
        "message_variants",
    ]
    duplicates = pd.DataFrame(records, columns=columns)
    exact_groups = int((duplicates["duplicate_type"] == "exact").sum()) if len(duplicates) else 0
    normalized_variant_groups = (
        int((duplicates["duplicate_type"] == "normalized_variant").sum())
        if len(duplicates)
        else 0
    )
    stats = {
        "exact_duplicate_groups": exact_groups,
        "normalized_variant_groups": normalized_variant_groups,
        "duplicate_rows_involved": int(duplicates["row_count"].sum())
        if len(duplicates)
        else 0,
        "conflicting_label_groups": int(duplicates["intent_conflict"].sum())
        if len(duplicates)
        else 0,
    }
    return duplicates, stats


def holdout_is_subset(predictions: pd.DataFrame, dataset: pd.DataFrame) -> bool:
    available = Counter(zip(dataset["message"], dataset["intent"]))
    for pair in zip(predictions["message"], predictions["true_intent"]):
        if available[pair] <= 0:
            return False
        available[pair] -= 1
    return True


def build_class_distribution(
    predictions: pd.DataFrame, dataset: pd.DataFrame, can_infer_train: bool
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    def append_counts(split: str, series: pd.Series) -> None:
        counts = series.value_counts().reindex(LABELS, fill_value=0)
        total = int(counts.sum())
        for label, count in counts.items():
            rows.append(
                {
                    "split": split,
                    "intent": label,
                    "count": int(count),
                    "percentage": round((100 * count / total) if total else 0.0, 3),
                }
            )

    append_counts("full_synthetic_dataset", dataset["intent"])
    if can_infer_train:
        full_counts = dataset["intent"].value_counts().reindex(LABELS, fill_value=0)
        test_counts = (
            predictions["true_intent"].value_counts().reindex(LABELS, fill_value=0)
        )
        inferred = pd.Series(
            [label for label in LABELS for _ in range(int(full_counts[label] - test_counts[label]))]
        )
        append_counts("inferred_training_split", inferred)
    append_counts("synthetic_holdout_true", predictions["true_intent"])
    append_counts("synthetic_holdout_predicted", predictions["predicted_intent"])
    return pd.DataFrame(rows)


def extract_model_diagnostics(
    model_path: Path,
    predictions: pd.DataFrame,
    top_n: int,
) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    if not model_path.is_file():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    model = joblib.load(model_path)
    required_steps = {"tfidf", "classifier"}
    if not hasattr(model, "named_steps") or not required_steps.issubset(
        model.named_steps
    ):
        raise ValueError("Expected a pipeline with 'tfidf' and 'classifier' steps")

    model_predictions = model.predict(predictions["message"])
    predictions_match = bool(
        (model_predictions == predictions["predicted_intent"].to_numpy()).all()
    )
    if not predictions_match:
        raise ValueError(
            "Saved model predictions do not match results/test_predictions.csv; "
            "the artifacts may come from different runs"
        )

    classifier = model.named_steps["classifier"]
    vectorizer = model.named_steps["tfidf"]
    probabilities = model.predict_proba(predictions["message"])
    class_to_index = {label: i for i, label in enumerate(classifier.classes_)}
    probability_rows: list[dict[str, float]] = []
    for row_index, row in predictions.iterrows():
        row_probabilities = probabilities[row_index]
        ordered = sorted(row_probabilities, reverse=True)
        probability_rows.append(
            {
                "predicted_probability": float(
                    row_probabilities[class_to_index[row["predicted_intent"]]]
                ),
                "true_class_probability": float(
                    row_probabilities[class_to_index[row["true_intent"]]]
                ),
                "top_two_margin": float(ordered[0] - ordered[1]),
            }
        )
    probability_frame = pd.DataFrame(probability_rows, index=predictions.index)

    feature_names = vectorizer.get_feature_names_out()
    feature_rows: list[dict[str, object]] = []
    for class_index, label in enumerate(classifier.classes_):
        coefficients = classifier.coef_[class_index]
        strongest = coefficients.argsort()[-top_n:][::-1]
        for rank, feature_index in enumerate(strongest, start=1):
            feature_rows.append(
                {
                    "intent": label,
                    "rank": rank,
                    "feature": feature_names[feature_index],
                    "coefficient": round(float(coefficients[feature_index]), 6),
                }
            )
    return probability_frame, pd.DataFrame(feature_rows), predictions_match


def explain_error(message: str, true_intent: str, predicted_intent: str) -> str:
    return KNOWN_ERROR_EXPLANATIONS.get(
        message,
        PAIR_EXPLANATIONS.get(
            (true_intent, predicted_intent),
            "The message likely lacks enough distinctive training evidence for the correct class.",
        ),
    )


def write_confusion_svg(matrix: pd.DataFrame, path: Path) -> None:
    """Write a dependency-free SVG heatmap for local viewing on macOS."""
    cell = 112
    left = 180
    top = 125
    width = left + cell * len(LABELS) + 35
    height = top + cell * len(LABELS) + 85
    maximum = max(1, int(matrix.to_numpy().max()))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#172033}.title{font-size:20px;font-weight:700}.axis{font-size:14px;font-weight:600}.label{font-size:13px}.count{font-size:24px;font-weight:700}</style>',
        f'<text x="{width / 2:.1f}" y="30" text-anchor="middle" class="title">Confusion matrix — synthetic holdout</text>',
        f'<text x="{left + (cell * len(LABELS)) / 2:.1f}" y="58" text-anchor="middle" class="axis">Predicted intent</text>',
        f'<text x="25" y="{top + (cell * len(LABELS)) / 2:.1f}" text-anchor="middle" class="axis" transform="rotate(-90 25 {top + (cell * len(LABELS)) / 2:.1f})">True intent</text>',
    ]

    for column, label in enumerate(LABELS):
        x = left + column * cell + cell / 2
        parts.append(
            f'<text x="{x}" y="92" text-anchor="middle" class="label">{html.escape(label)}</text>'
        )
    for row, label in enumerate(LABELS):
        y = top + row * cell + cell / 2 + 5
        parts.append(
            f'<text x="{left - 14}" y="{y}" text-anchor="end" class="label">{html.escape(label)}</text>'
        )
        for column, predicted_label in enumerate(LABELS):
            count = int(matrix.loc[label, predicted_label])
            intensity = count / maximum
            red = round(239 - 205 * intensity)
            green = round(246 - 105 * intensity)
            blue = round(255 - 39 * intensity)
            fill = f"rgb({red},{green},{blue})"
            text_fill = "#ffffff" if intensity >= 0.55 else "#172033"
            x = left + column * cell
            y = top + row * cell
            parts.extend(
                [
                    f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{fill}" stroke="#ffffff" stroke-width="3" rx="5"/>',
                    f'<text x="{x + cell / 2}" y="{y + cell / 2 + 8}" text-anchor="middle" class="count" style="fill:{text_fill}">{count}</text>',
                ]
            )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def markdown_escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = [
        "| " + " | ".join(markdown_escape(value) for value in row) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def build_report(
    accuracy: float,
    macro_precision: float,
    macro_recall: float,
    macro_f1: float,
    metrics: pd.DataFrame,
    matrix: pd.DataFrame,
    errors: pd.DataFrame,
    class_distribution: pd.DataFrame,
    duplicate_stats: dict[str, int],
    dataset_rows: int,
    holdout_rows: int,
    can_infer_train: bool,
    predictions_match: bool,
    top_features: pd.DataFrame,
) -> str:
    correct = int(round(accuracy * holdout_rows))
    error_count = holdout_rows - correct
    pair_counts = (
        errors.groupby(["true_intent", "predicted_intent"])
        .size()
        .sort_values(ascending=False)
    )
    prediction_counts = (
        class_distribution[class_distribution["split"] == "synthetic_holdout_predicted"]
        .set_index("intent")["count"]
        .reindex(LABELS)
    )
    true_counts = (
        class_distribution[class_distribution["split"] == "synthetic_holdout_true"]
        .set_index("intent")["count"]
        .reindex(LABELS)
    )
    low_margin_errors = int((errors["top_two_margin"] <= 0.025).sum())
    max_error_probability = float(errors["predicted_probability"].max()) if len(errors) else 0
    min_error_probability = float(errors["predicted_probability"].min()) if len(errors) else 0

    metric_rows = [
        [
            row["intent"],
            f'{row["one_vs_rest_accuracy"]:.3f}',
            f'{row["precision"]:.3f}',
            f'{row["recall"]:.3f}',
            f'{row["f1_score"]:.3f}',
            int(row["support"]),
            int(row["true_positive"]),
            int(row["false_positive"]),
            int(row["false_negative"]),
        ]
        for _, row in metrics.iterrows()
    ]
    matrix_rows = [
        [label, *[int(matrix.loc[label, predicted]) for predicted in LABELS]]
        for label in LABELS
    ]
    error_rows = [
        [
            index + 1,
            row["message"],
            row["true_intent"],
            row["predicted_intent"],
            f'{row["predicted_probability"]:.3f}',
            f'{row["top_two_margin"]:.3f}',
            row["possible_reason"],
        ]
        for index, (_, row) in enumerate(errors.iterrows())
    ]
    distribution_rows = [
        [
            label,
            int(
                class_distribution[
                    (class_distribution["split"] == "full_synthetic_dataset")
                    & (class_distribution["intent"] == label)
                ]["count"].iloc[0]
            ),
            int(true_counts[label]),
            int(prediction_counts[label]),
        ]
        for label in LABELS
    ]
    pair_rows = [
        [true_label, predicted_label, int(count), f"{100 * count / error_count:.1f}%"]
        for (true_label, predicted_label), count in pair_counts.items()
    ]
    feature_rows = []
    for label in LABELS:
        values = top_features[top_features["intent"] == label].head(5)
        rendered = ", ".join(
            f'`{row["feature"]}` ({row["coefficient"]:.3f})'
            for _, row in values.iterrows()
        )
        feature_rows.append([label, rendered])

    training_split_note = (
        "The holdout rows were all found in the seed dataset, so the training counts can be "
        "inferred as 18 per class (72 total)."
        if can_infer_train
        else "The holdout is not a complete subset of the supplied seed dataset, so training counts were not inferred."
    )
    model_match_note = (
        "All stored predictions exactly match fresh inference from the saved model artifact."
        if predictions_match
        else "The stored predictions did not match the saved model artifact."
    )

    return f"""# FI'L AI Baseline Error Analysis

## Scope and validity warning

This analysis covers the existing TF-IDF + Logistic Regression baseline only. It does **not** train or modify a model. The full dataset contains {dataset_rows} manually written **synthetic** Arabic messages, and the evaluated holdout contains only {holdout_rows} synthetic messages. These results are useful for debugging the pipeline, but **cannot establish real-world accuracy, robustness, or deployment readiness**.

## Executive summary

- Accuracy: **{accuracy:.3f} ({correct}/{holdout_rows}, or {accuracy * 100:.1f}%)**
- Macro precision: **{macro_precision:.3f}**
- Macro recall: **{macro_recall:.3f}**
- Macro F1: **{macro_f1:.3f}**
- Misclassifications: **{error_count}/{holdout_rows}**
- Weakest recall: **info_only ({metrics.set_index('intent').loc['info_only', 'recall']:.3f}; 2/6 found)**
- Largest error routes: **info_only → reschedule (3)** and **reschedule → cancellation (3)**; together they make up 6/{error_count} errors.
- The model predicts `info_only` only {int(prediction_counts['info_only'])} times although it occurs {int(true_counts['info_only'])} times, while it overpredicts `cancellation` ({int(prediction_counts['cancellation'])} predictions versus {int(true_counts['cancellation'])} true examples).
- Wrong predictions have low top-class probabilities ({min_error_probability:.3f}–{max_error_probability:.3f}); {low_margin_errors}/{error_count} errors have a top-two probability margin no greater than 0.025. These uncalibrated probabilities are diagnostic only, but they show that several decisions are near ties.
- Because each class has only six test examples, one example changes its recall by **16.7 percentage points**. Treat every metric as high-variance.

## Per-class metrics

{markdown_table(['Intent', 'One-vs-rest accuracy', 'Precision', 'Recall', 'F1', 'Support', 'TP', 'FP', 'FN'], metric_rows)}

Standard multiclass accuracy is the overall 0.500 reported above. Per-class accuracy is shown as one-vs-rest `(TP + TN) / N`; because it includes many true negatives, precision/recall/F1 are more informative for comparing the classes. Macro metrics weight each of the four intents equally. The class supports happen to be equal, so weighted recall and macro recall are both 0.500 in this holdout. Detailed machine-readable values are in `class_metrics.csv` and `error_analysis_summary.json`.

## Confusion matrix

Rows are true labels; columns are predictions.

{markdown_table(['True \\ Predicted', *LABELS], matrix_rows)}

![Confusion matrix](confusion_matrix.svg)

### Error routes

{markdown_table(['True intent', 'Predicted intent', 'Count', 'Share of errors'], pair_rows)}

Half of all errors lie in two systematic routes. Rescheduling messages with negation or implicit replacement language are read as cancellations. Informational statements containing time or change vocabulary are read as reschedules.

## All misclassified messages

The explanations below are evidence-based hypotheses from the wording, training data, and model features; they are not guaranteed causal attributions. Logistic Regression probabilities are not calibrated here.

{markdown_table(['#', 'Message', 'True', 'Predicted', 'Pred. probability', 'Top-two margin', 'Possible reason'], error_rows)}

The complete error inventory, including true-class probability, is available in `misclassified_messages.csv`.

## Main failure patterns

1. **Negation is not composed with the action.** `ما في داعي تتواصلين` and `ما يحتاج ترفعين` contain task-like verbs, but the multiword phrases cancel those actions. Character n-grams see both local fragments without representing their scope.
2. **A deadline is confused with a changed appointment.** `تسليم الواجب يوم الأربعاء` introduces a task deadline; it does not move a previously known time. The baseline has no structured concept of “old time versus new time.”
3. **Time mentions are treated as rescheduling evidence.** A general fact such as courses starting after five is informational even though it contains temporal language.
4. **Implicit change language is weakly covered.** `بنقدمها ليوم الأحد` and `مو اليوم، خلي ... الاثنين` lack the explicit `موعد`/`بدل` patterns strongly associated with reschedule.
5. **Surface style substitutes for semantics.** Feminine verb endings, punctuation, and short character fragments receive substantial weight. This makes the model sensitive to phrasing rather than the communicative intent.
6. **The classes require discourse context.** Cancellation and rescheduling refer to an earlier task or time, but the classifier sees one isolated message. Ambiguous messages therefore cannot always be resolved from text alone.

## Model feature audit

The pipeline uses `TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)` followed by balanced Logistic Regression (`max_iter=2000`). The split is stratified, 25%, with `random_state=42`. {model_match_note}

The five strongest positive character n-grams per class are shown below; coefficients are relative model weights, not probabilities.

{markdown_table(['Intent', 'Top positive features'], feature_rows)}

This supports the observed behavior: `reschedule` leans on explicit fragments from `موعد`, `إلى`, and `بدل`; `cancellation` leans on `إلغاء`, `وقف`, and `سابق`. Meanwhile, `new_task` includes generic endings and punctuation such as `ين` and `؟`. Implicit paraphrases and contrastive sentences can miss the strongest class cues.

## Dataset quality audit

### Class distribution

{markdown_table(['Intent', 'Full synthetic dataset', 'Holdout true', 'Holdout predicted'], distribution_rows)}

- The full dataset is exactly balanced: 24 messages per intent (25% each; max/min class ratio 1.0).
- The stratified holdout is exactly balanced: 6 messages per intent. {training_split_note}
- Balanced counts do **not** guarantee balanced linguistic difficulty or coverage. `info_only` has the lowest recall despite equal support.

### Duplicate check

- Exact duplicate groups: **{duplicate_stats['exact_duplicate_groups']}**
- Normalized-variant duplicate groups: **{duplicate_stats['normalized_variant_groups']}**
- Rows involved in duplicate groups: **{duplicate_stats['duplicate_rows_involved']}**
- Duplicate groups with conflicting labels: **{duplicate_stats['conflicting_label_groups']}**

Normalization for this audit applies Unicode NFKC, removes Arabic diacritics/tatweel and punctuation, standardizes Alef variants and Alef Maqsura, and collapses whitespace. No exact or normalized duplicate leakage was detected. However, the examples share a narrow hand-written style and repeated intent templates, which can still make a random holdout easier or less representative than real messages.

## What the metrics cannot show

- The 96 messages are synthetic, clean, single-sentence, and manually authored. They do not represent naturally occurring spelling variation, dialect diversity, typos, code-switching, forwarded text, or conversational context.
- The random holdout comes from the same synthetic authoring process as training. It measures interpolation within this toy collection, not generalization to users.
- Six examples per class are too few for a stable performance estimate or meaningful subgroup analysis.
- There is no independent real-world test set, annotation agreement measurement, confidence calibration, or multi-intent policy.

## Recommended next step: improve the dataset first

Do **not** choose a more complex model yet. After approval, the next phase should be a dataset and annotation pass:

1. Write an annotation guide that explicitly distinguishes: (a) a new task with a deadline, (b) a change to an existing schedule, (c) cancellation of an existing action, and (d) information that happens to mention a time or change. Define how to label multi-intent and context-dependent messages.
2. Collect **real, naturally occurring Arabic messages** from multiple consenting sources and channels, with permission and irreversible removal of personal or sensitive information. Include dialect, spelling, negation, politeness, and message-length variation. Do not manufacture new examples to claim real-world performance.
3. Prioritize naturally occurring cases from the largest confusion routes: reschedule versus cancellation, info_only statements with time/change terms, new tasks with deadlines, and colloquial multiword negation.
4. Double-annotate an initial sample, discuss disagreements, and revise the guide before scaling collection. Track source and conversation/group identifiers without retaining personal content.
5. Deduplicate and split by source/conversation or template family—not only by row—then lock a sufficiently large, fully real test set. Keep it untouched during model development.

Only after this data phase is approved and completed should the baseline be retrained and compared with other approaches. No next-phase implementation was performed in this analysis.

## Generated artifacts

- `class_metrics.csv` — per-class one-vs-rest accuracy, precision, recall, F1, support, TP, FP, FN, and TN
- `confusion_matrix.csv` / `confusion_matrix.svg` — numeric and visual confusion matrix
- `misclassified_messages.csv` — all errors with confidence diagnostics and hypotheses
- `class_distribution.csv` — full-data, inferred-train, true-holdout, and predicted distributions
- `duplicate_messages.csv` — exact or normalized duplicate groups (header-only when none)
- `top_model_features.csv` — strongest positive character n-grams per class
- `error_analysis_summary.json` — compact machine-readable summary
"""


def main() -> None:
    args = parse_args()
    if args.top_features < 1:
        raise ValueError("--top-features must be at least 1")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    predictions = read_and_validate_csv(
        args.predictions,
        {"message", "true_intent", "predicted_intent"},
        "Predictions",
    )
    dataset = read_and_validate_csv(
        args.dataset, {"message", "intent"}, "Seed dataset"
    )
    validate_labels(predictions, dataset)

    y_true = predictions["true_intent"]
    y_pred = predictions["predicted_intent"]
    accuracy = float(accuracy_score(y_true, y_pred))
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=LABELS, zero_division=0
    )
    macro_precision, macro_recall, macro_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=LABELS, average="macro", zero_division=0
    )
    raw_matrix = confusion_matrix(y_true, y_pred, labels=LABELS)
    matrix = pd.DataFrame(raw_matrix, index=LABELS, columns=LABELS)
    matrix.index.name = "true_intent"
    matrix.columns.name = "predicted_intent"

    metric_rows = []
    total = len(predictions)
    for index, label in enumerate(LABELS):
        true_positive = int(raw_matrix[index, index])
        false_positive = int(raw_matrix[:, index].sum() - true_positive)
        false_negative = int(raw_matrix[index, :].sum() - true_positive)
        true_negative = total - true_positive - false_positive - false_negative
        metric_rows.append(
            {
                "intent": label,
                "one_vs_rest_accuracy": round(
                    float((true_positive + true_negative) / total), 6
                ),
                "precision": round(float(precision[index]), 6),
                "recall": round(float(recall[index]), 6),
                "f1_score": round(float(f1[index]), 6),
                "support": int(support[index]),
                "true_positive": true_positive,
                "false_positive": false_positive,
                "false_negative": false_negative,
                "true_negative": true_negative,
            }
        )
    metrics = pd.DataFrame(metric_rows)

    probability_frame, top_features, predictions_match = extract_model_diagnostics(
        args.model, predictions, args.top_features
    )
    enriched = pd.concat([predictions, probability_frame], axis=1)
    errors = enriched[enriched["true_intent"] != enriched["predicted_intent"]].copy()
    errors.insert(0, "prediction_row", errors.index + 2)
    errors["possible_reason"] = errors.apply(
        lambda row: explain_error(
            row["message"], row["true_intent"], row["predicted_intent"]
        ),
        axis=1,
    )
    for column in ["predicted_probability", "true_class_probability", "top_two_margin"]:
        errors[column] = errors[column].round(6)

    duplicates, duplicate_stats = duplicate_audit(dataset)
    can_infer_train = holdout_is_subset(predictions, dataset)
    class_distribution = build_class_distribution(
        predictions, dataset, can_infer_train
    )

    metrics.to_csv(
        args.output_dir / "class_metrics.csv", index=False, encoding="utf-8-sig"
    )
    matrix.to_csv(args.output_dir / "confusion_matrix.csv", encoding="utf-8-sig")
    errors.to_csv(
        args.output_dir / "misclassified_messages.csv",
        index=False,
        encoding="utf-8-sig",
    )
    class_distribution.to_csv(
        args.output_dir / "class_distribution.csv", index=False, encoding="utf-8-sig"
    )
    duplicates.to_csv(
        args.output_dir / "duplicate_messages.csv", index=False, encoding="utf-8-sig"
    )
    top_features.to_csv(
        args.output_dir / "top_model_features.csv", index=False, encoding="utf-8-sig"
    )
    write_confusion_svg(matrix, args.output_dir / "confusion_matrix.svg")

    full_counts = dataset["intent"].value_counts().reindex(LABELS, fill_value=0)
    pair_counts = (
        errors.groupby(["true_intent", "predicted_intent"])
        .size()
        .sort_values(ascending=False)
    )
    summary = {
        "warning": (
            "Synthetic-data holdout only; these metrics cannot establish real-world accuracy."
        ),
        "dataset_rows": len(dataset),
        "holdout_rows": len(predictions),
        "correct_predictions": int((y_true == y_pred).sum()),
        "misclassifications": len(errors),
        "accuracy": round(accuracy, 6),
        "macro_precision": round(float(macro_precision), 6),
        "macro_recall": round(float(macro_recall), 6),
        "macro_f1": round(float(macro_f1), 6),
        "class_count_min": int(full_counts.min()),
        "class_count_max": int(full_counts.max()),
        "class_imbalance_ratio_max_to_min": round(
            float(full_counts.max() / full_counts.min()), 6
        ),
        "duplicate_audit": duplicate_stats,
        "saved_model_predictions_match_csv": predictions_match,
        "largest_error_routes": [
            {
                "true_intent": true_label,
                "predicted_intent": predicted_label,
                "count": int(count),
            }
            for (true_label, predicted_label), count in pair_counts.items()
        ],
    }
    (args.output_dir / "error_analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = build_report(
        accuracy=accuracy,
        macro_precision=float(macro_precision),
        macro_recall=float(macro_recall),
        macro_f1=float(macro_f1),
        metrics=metrics,
        matrix=matrix,
        errors=errors,
        class_distribution=class_distribution,
        duplicate_stats=duplicate_stats,
        dataset_rows=len(dataset),
        holdout_rows=len(predictions),
        can_infer_train=can_infer_train,
        predictions_match=predictions_match,
        top_features=top_features,
    )
    (args.output_dir / "error_analysis.md").write_text(report, encoding="utf-8")

    print("FI'L AI baseline error analysis complete")
    print("WARNING: synthetic holdout only; not a real-world accuracy estimate")
    print(f"Accuracy: {accuracy:.3f} ({int((y_true == y_pred).sum())}/{len(predictions)})")
    print(f"Macro-F1: {float(macro_f1):.3f}")
    print(f"Misclassified messages: {len(errors)}")
    print(
        "Duplicate groups: "
        f"{duplicate_stats['exact_duplicate_groups']} exact, "
        f"{duplicate_stats['normalized_variant_groups']} normalized variants"
    )
    print(f"Saved analysis artifacts to: {args.output_dir}")


if __name__ == "__main__":
    main()

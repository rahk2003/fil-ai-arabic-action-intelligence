"""Create a human-review queue from action-related MASSIVE examples."""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/amazon_massive"
RELEVANT_SCENARIOS = {"alarm", "calendar", "datetime", "reminder", "lists", "email"}


def main() -> None:
    frames = []
    for split in ("train", "validation", "test"):
        path = RAW / f"{split}.parquet"
        if not path.is_file():
            raise SystemExit("Run scripts/download_massive.py first")
        frame = pd.read_parquet(path)
        frame["source_split"] = split
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True)
    mask = data["scenario"].isin(RELEVANT_SCENARIOS) | data["intent"].astype(str).str.contains("reminder|calendar|schedule|alarm|list|email", case=False, regex=True)
    candidates = data.loc[mask].copy()
    candidates.insert(0, "message_id", candidates.apply(lambda r: f"massive-ar-SA-{r['source_split']}-{r['id']}", axis=1))
    candidates["suggested_relevance"] = "manual_review_required"
    candidates["target_intent_suggestion"] = ""
    candidates["label_status"] = "unreviewed"
    output = ROOT / "data/processed/massive_relevant_candidates.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    candidates[["message_id", "utt", "annot_utt", "scenario", "intent", "source_split", "suggested_relevance", "target_intent_suggestion", "label_status"]].to_csv(output, index=False, encoding="utf-8-sig")
    template = pd.DataFrame({
        "message_id": candidates["message_id"], "message": candidates["utt"], "intent": "",
        "action_text": "", "datetime_text": "", "normalized_datetime": "",
        "source": "amazon_massive_ar-SA", "label_status": "unreviewed", "reviewer": "",
        "notes": candidates.apply(lambda r: f"Original MASSIVE intent={r['intent']}; split={r['source_split']}", axis=1),
    })
    annotation = ROOT / "data/annotation/annotation_template.csv"
    annotation.parent.mkdir(parents=True, exist_ok=True)
    template.to_csv(annotation, index=False, encoding="utf-8-sig")
    review_queue = template.copy()
    review_queue.insert(
        2,
        "review_reason",
        candidates["annot_utt"].map(
            lambda value: "date_or_time_slot_candidate"
            if "[date :" in str(value) or "[time :" in str(value)
            else "action_related_original_intent"
        ).to_numpy(),
    )
    review_queue.head(500).to_csv(
        ROOT / "data/annotation/review_queue.csv", index=False, encoding="utf-8-sig"
    )
    print(
        f"Wrote {len(candidates):,} unreviewed candidates and a 500-row review queue; "
        "none are training-ready."
    )


if __name__ == "__main__":
    main()

"""Download the official Amazon MASSIVE ar-SA splits and preserve provenance."""

from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path

DATASET_ID = "AmazonScience/massive"
CONFIG = "ar-SA"
EXPECTED_COUNTS = {"train": 11514, "validation": 2033, "test": 2974}
OFFICIAL_ARCHIVE = "https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz"


def load_with_official_archive(load_dataset, output_dir: Path):
    """Fallback for temporary Hub-script incompatibilities, still using Datasets.

    The bytes come from Amazon's URL referenced by the official repository. Only
    ar-SA.jsonl and LICENSE are extracted, and Hugging Face Datasets parses JSONL.
    """
    import requests

    archive = output_dir / "amazon-massive-dataset-1.1.tar.gz"
    if not archive.is_file():
        with requests.get(OFFICIAL_ARCHIVE, stream=True, timeout=120) as response:
            response.raise_for_status()
            with archive.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
    extracted_jsonl = output_dir / "ar-SA.jsonl"
    with tarfile.open(archive, "r:gz") as bundle:
        json_member = next((m for m in bundle.getmembers() if m.name.endswith("/data/ar-SA.jsonl")), None)
        license_member = next((m for m in bundle.getmembers() if m.name.endswith("/LICENSE")), None)
        if json_member is None or not json_member.isfile():
            raise RuntimeError("Official archive does not contain data/ar-SA.jsonl")
        source = bundle.extractfile(json_member)
        if source is None:
            raise RuntimeError("Could not read ar-SA.jsonl from official archive")
        with extracted_jsonl.open("wb") as target:
            target.write(source.read())
        if license_member and license_member.isfile():
            source = bundle.extractfile(license_member)
            if source:
                (output_dir / "LICENSE").write_bytes(source.read())
    all_rows = load_dataset("json", data_files=str(extracted_jsonl), split="train")
    partitions = {"train": "train", "validation": "dev", "test": "test"}
    return {name: all_rows.filter(lambda row, expected=value: row["partition"] == expected) for name, value in partitions.items()}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=root / "data/raw/amazon_massive")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    files = {split: args.output_dir / f"{split}.parquet" for split in EXPECTED_COUNTS}
    if all(path.is_file() for path in files.values()) and not args.force:
        print("MASSIVE ar-SA Parquet files already exist; use --force to redownload.")
        return
    try:
        from datasets import load_dataset
    except ImportError as error:
        raise SystemExit("Install requirements-data.txt under Python 3.11/3.12 first.") from error
    loader_note = "AmazonScience/massive Hugging Face dataset script"
    try:
        dataset = load_dataset(DATASET_ID, CONFIG, trust_remote_code=True)
    except Exception as hub_error:
        print(f"Hub dataset script failed ({type(hub_error).__name__}); using the official Amazon archive fallback.")
        try:
            dataset = load_with_official_archive(load_dataset, args.output_dir)
            loader_note = "Official Amazon 1.1 archive parsed with Hugging Face Datasets JSON loader"
        except Exception as archive_error:
            raise SystemExit(
                "Both official download paths failed. "
                f"Hub error: {type(hub_error).__name__}: {hub_error}; "
                f"archive error: {type(archive_error).__name__}: {archive_error}"
            ) from archive_error
    split_aliases = {"train": "train", "validation": "validation" if "validation" in dataset else "dev", "test": "test"}
    observed, schemas = {}, {}
    for canonical, source_split in split_aliases.items():
        if source_split not in dataset:
            raise SystemExit(f"Unexpected MASSIVE schema: missing {source_split!r}; found {list(dataset)}")
        frame = dataset[source_split].to_pandas()
        if "locale" not in frame or set(frame["locale"].unique()) != {CONFIG}:
            raise SystemExit(f"Locale validation failed for split {source_split}")
        observed[canonical] = len(frame)
        schemas[canonical] = {column: str(dtype) for column, dtype in frame.dtypes.items()}
        frame.to_parquet(files[canonical], index=False)
    if observed != EXPECTED_COUNTS:
        raise SystemExit(f"Split-count verification failed: expected {EXPECTED_COUNTS}, observed {observed}")
    manifest = {
        "dataset_id": DATASET_ID,
        "config": CONFIG,
        "source_url": "https://huggingface.co/datasets/AmazonScience/massive",
        "license": "CC BY 4.0",
        "counts": observed,
        "schemas": schemas,
        "preserves_original_labels": True,
        "download_library": "huggingface-datasets",
        "loader_path": loader_note,
        "official_archive_url": OFFICIAL_ARCHIVE,
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

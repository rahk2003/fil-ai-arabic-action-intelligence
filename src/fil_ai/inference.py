"""Local intent inference for the preserved baseline and fine-tuned CAMeLBERT.

Requested models fail explicitly. In particular, a CAMeLBERT request is never
silently replaced with the baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, Literal

import joblib
import numpy as np

from .config import INTENTS, MODELS_DIR, PROJECT_ROOT

ModelKey = Literal["baseline", "camelbert"]
EXPECTED_LABELS = frozenset(INTENTS)


class ModelUnavailableError(RuntimeError):
    """Raised when an explicitly requested local model cannot be used."""


class LabelMappingError(ValueError):
    """Raised when a checkpoint label mapping is incompatible with FI'L AI."""


@dataclass
class Prediction:
    label: str
    confidence: float | None
    probabilities: dict[str, float]
    model_name: str
    inference_latency_ms: float
    warning: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            # Kept for backward API compatibility. This is the maximum raw
            # predict_proba/softmax value and has not been calibrated.
            "confidence": self.confidence,
            "uncalibrated_score": self.confidence,
            "probabilities": self.probabilities,
            "model_name": self.model_name,
            "model_identifier": self.model_name,
            "inference_latency_ms": round(self.inference_latency_ms, 3),
            "warning": self.warning,
        }


def _validate_transformer_config(path: Path) -> dict[int, str]:
    config_path = path / "config.json"
    if not config_path.is_file():
        raise ModelUnavailableError(f"CAMeLBERT config is missing: {config_path}")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModelUnavailableError(f"CAMeLBERT config cannot be read: {error}") from error

    raw_id2label = config.get("id2label") or {}
    raw_label2id = config.get("label2id") or {}
    try:
        id2label = {int(index): str(label) for index, label in raw_id2label.items()}
        label2id = {str(label): int(index) for label, index in raw_label2id.items()}
    except (TypeError, ValueError) as error:
        raise LabelMappingError("CAMeLBERT label mapping contains invalid ids") from error

    if set(id2label.values()) != EXPECTED_LABELS or set(label2id) != EXPECTED_LABELS:
        raise LabelMappingError(
            "CAMeLBERT must map exactly these four intents: " + ", ".join(INTENTS)
        )
    if any(label2id.get(label) != index for index, label in id2label.items()):
        raise LabelMappingError("CAMeLBERT id2label and label2id mappings disagree")
    if sorted(id2label) != list(range(len(INTENTS))):
        raise LabelMappingError("CAMeLBERT label ids must be contiguous from 0 to 3")
    return id2label


class IntentModel:
    """One exact local checkpoint, with lazy loading for Transformer weights."""

    def __init__(
        self,
        model_path: Path | None = None,
        *,
        identifier: str | None = None,
        device: str = "auto",
        lazy_transformer: bool = False,
    ):
        self.warning: str | None = None
        self._lock = Lock()
        self._loaded = False
        self._load_error: str | None = None
        self._device_preference = device
        self.device = "cpu"
        self.model: Any | None = None
        self.tokenizer: Any | None = None

        if model_path is None:
            model_path = self._default_model_path()
            self.warning = (
                "Using the preserved synthetic TF-IDF baseline; its holdout metrics "
                "do not establish real-world accuracy."
            )
        self.path = Path(model_path)
        if not self.path.exists():
            raise ModelUnavailableError(f"Requested model does not exist: {self.path}")

        if self.path.is_dir():
            self.backend = "transformer"
            self.id2label = _validate_transformer_config(self.path)
            required = ["model.safetensors", "tokenizer.json"]
            missing = [name for name in required if not (self.path / name).is_file()]
            if missing:
                raise ModelUnavailableError(
                    "CAMeLBERT checkpoint is incomplete; missing: " + ", ".join(missing)
                )
            self.name = identifier or f"camelbert-da:{self.path.name}"
            if not lazy_transformer:
                self.ensure_loaded()
        elif self.path.is_file():
            self.backend = "joblib"
            self.name = identifier or self.path.stem
            self.model = joblib.load(self.path)
            self._loaded = True
        else:
            raise ModelUnavailableError(f"Requested model path is unsupported: {self.path}")

    @staticmethod
    def _default_model_path() -> Path:
        config_path = PROJECT_ROOT / "config/active_model.json"
        if config_path.is_file():
            configured = json.loads(config_path.read_text(encoding="utf-8"))["model_path"]
            path = PROJECT_ROOT / configured
            if path.is_file():
                return path
        fallback = MODELS_DIR / "intent_baseline.joblib"
        if fallback.is_file():
            return fallback
        raise ModelUnavailableError("No local baseline checkpoint is available")

    @property
    def loaded(self) -> bool:
        return self._loaded

    def _resolve_device(self, torch: Any) -> Any:
        if self._device_preference == "auto":
            requested = "mps" if torch.backends.mps.is_available() else "cpu"
        else:
            requested = self._device_preference
        if requested not in {"cpu", "mps"}:
            raise ModelUnavailableError("Transformer device must be 'auto', 'cpu', or 'mps'")
        if requested == "mps" and not torch.backends.mps.is_available():
            raise ModelUnavailableError("MPS was explicitly requested but is unavailable")
        return torch.device(requested)

    def ensure_loaded(self) -> None:
        if self._loaded or self.backend != "transformer":
            return
        with self._lock:
            if self._loaded:
                return
            try:
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer

                device = self._resolve_device(torch)
                tokenizer = AutoTokenizer.from_pretrained(self.path, local_files_only=True)
                model = AutoModelForSequenceClassification.from_pretrained(
                    self.path,
                    local_files_only=True,
                )
                runtime_mapping = {
                    int(index): str(label) for index, label in model.config.id2label.items()
                }
                if runtime_mapping != self.id2label:
                    raise LabelMappingError("Loaded CAMeLBERT mapping differs from config.json")
                model.to(device).eval()
            except (ImportError, OSError, RuntimeError, ValueError) as error:
                self._load_error = (
                    f"Requested CAMeLBERT checkpoint could not be loaded: "
                    f"{type(error).__name__}: {error}"
                )
                raise ModelUnavailableError(self._load_error) from error
            self.tokenizer = tokenizer
            self.model = model
            self.device = str(device)
            self._loaded = True
            self._load_error = None

    def status(self) -> dict[str, Any]:
        return {
            "identifier": self.name,
            "backend": self.backend,
            "path": str(self.path),
            "available": self.path.exists(),
            "loaded": self.loaded,
            "device": self.device if self.loaded else None,
            "labels": self.id2label if self.backend == "transformer" else list(INTENTS),
            "warning": self._load_error or self.warning,
        }

    def predict(self, message: str) -> Prediction:
        if not message or not message.strip():
            raise ValueError("Message must contain non-whitespace text")
        values: np.ndarray | None = None
        if self.backend == "transformer":
            self.ensure_loaded()
            assert self.model is not None and self.tokenizer is not None
            import torch

            encoded = self.tokenizer(
                message,
                return_tensors="pt",
                truncation=True,
                max_length=128,
            ).to(self.device)
            started = perf_counter()
            with torch.inference_mode():
                logits = self.model(**encoded).logits
                values = torch.softmax(logits, dim=-1)[0].detach().cpu().numpy()
            elapsed_ms = (perf_counter() - started) * 1000
            classes = [self.id2label[index] for index in range(len(values))]
            label = classes[int(np.argmax(values))]
        else:
            assert self.model is not None
            started = perf_counter()
            label = str(self.model.predict([message])[0])
            if hasattr(self.model, "predict_proba"):
                values = self.model.predict_proba([message])[0]
            elapsed_ms = (perf_counter() - started) * 1000
            classes = [str(value) for value in getattr(self.model, "classes_", [])]

        if label not in INTENTS:
            raise ValueError(f"Model returned unsupported label: {label}")
        probabilities: dict[str, float] = {}
        confidence: float | None = None
        if values is not None:
            probabilities = {
                class_name: round(float(value), 6)
                for class_name, value in zip(classes, values)
            }
            confidence = float(np.max(values))
        return Prediction(
            label,
            confidence,
            probabilities,
            self.name,
            elapsed_ms,
            self.warning,
        )


class ModelRegistry:
    """Process-local model cache. CAMeLBERT weights load on first request only."""

    def __init__(
        self,
        baseline_path: Path | None = None,
        camelbert_path: Path | None = None,
        *,
        transformer_device: str = "auto",
    ):
        baseline = baseline_path or MODELS_DIR / "intent_baseline.joblib"
        self._models: dict[ModelKey, IntentModel] = {
            "baseline": IntentModel(
                baseline,
                identifier="tfidf-logreg:intent_baseline",
            )
        }
        self._camelbert_error: str | None = None
        checkpoint = camelbert_path or MODELS_DIR / "FIL_AI_CAMeLBERT"
        try:
            self._models["camelbert"] = IntentModel(
                checkpoint,
                identifier="camelbert-da:FIL_AI_CAMeLBERT",
                device=transformer_device,
                lazy_transformer=True,
            )
        except (ModelUnavailableError, LabelMappingError) as error:
            self._camelbert_error = str(error)

    def get(self, key: ModelKey) -> IntentModel:
        if key not in self._models:
            detail = self._camelbert_error or f"Requested model is unavailable: {key}"
            raise ModelUnavailableError(detail)
        return self._models[key]

    def statuses(self) -> dict[str, dict[str, Any]]:
        statuses = {key: model.status() for key, model in self._models.items()}
        if "camelbert" not in statuses:
            statuses["camelbert"] = {
                "identifier": "camelbert-da:FIL_AI_CAMeLBERT",
                "backend": "transformer",
                "available": False,
                "loaded": False,
                "device": None,
                "labels": None,
                "warning": self._camelbert_error,
            }
        return statuses

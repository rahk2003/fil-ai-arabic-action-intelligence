"""Cached, optional local sentence-embedding inference.

The embedding model is a representation layer for contextual matching.  It is
not an intent classifier and is never used to claim CAMeLBERT fine-tuning.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any, Sequence

import numpy as np

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class SemanticMatcher:
    """Load one SentenceTransformer per process and fail closed to lexical matching."""

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        *,
        cache_dir: str | Path | None = None,
        local_files_only: bool = False,
        enabled: bool = True,
    ):
        self.model_name = model_name
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.local_files_only = local_files_only
        self.enabled = enabled
        self._model: Any | None = None
        self._attempted = False
        self._error: str | None = None
        self._device: str | None = None
        self._dimension: int | None = None
        self._lock = Lock()

    def ensure_loaded(self) -> bool:
        if not self.enabled:
            self._error = "Semantic embeddings are disabled by configuration."
            return False
        if self._model is not None:
            return True
        if self._attempted:
            return False
        with self._lock:
            if self._model is not None:
                return True
            if self._attempted:
                return False
            self._attempted = True
            try:
                import torch
                from sentence_transformers import SentenceTransformer

                if self.cache_dir:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                device = "mps" if torch.backends.mps.is_available() else "cpu"
                self._model = SentenceTransformer(
                    self.model_name,
                    cache_folder=str(self.cache_dir) if self.cache_dir else None,
                    device=device,
                    local_files_only=self.local_files_only,
                )
                self._device = device
                dimension_getter = getattr(self._model, "get_embedding_dimension", self._model.get_sentence_embedding_dimension)
                self._dimension = int(dimension_getter())
                return True
            except Exception as error:  # optional dependency, cache, network, or runtime failure
                self._model = None
                self._error = f"{type(error).__name__}: {error}"
                return False

    @property
    def available(self) -> bool:
        return self._model is not None

    @property
    def warning(self) -> str | None:
        if self.available:
            return None
        if self._error:
            return f"Embedding model unavailable; lexical fallback is active. {self._error}"
        return None

    @property
    def method(self) -> str:
        return "embeddings" if self.available else "lexical_fallback"

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "loaded": self.available,
            "model_name": self.model_name,
            "method": self.method,
            "device": self._device,
            "dimension": self._dimension,
            "cache_dir": str(self.cache_dir) if self.cache_dir else None,
            "warning": self.warning,
        }

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not self.ensure_loaded() or self._model is None:
            raise RuntimeError(self.warning or "Embedding model is unavailable")
        return np.asarray(
            self._model.encode(
                list(texts),
                batch_size=min(16, max(1, len(texts))),
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            ),
            dtype=np.float32,
        )

    def similarities(self, query: str, candidates: Sequence[str]) -> list[float]:
        if not candidates:
            return []
        embeddings = self.encode([query, *candidates])
        query_vector = embeddings[0]
        return [float(np.clip(np.dot(query_vector, vector), -1.0, 1.0)) for vector in embeddings[1:]]


@lru_cache(maxsize=4)
def get_semantic_matcher(
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    cache_dir: str | None = None,
    local_files_only: bool = False,
    enabled: bool = True,
) -> SemanticMatcher:
    """Return the process-cached model wrapper rather than loading per request."""

    return SemanticMatcher(
        model_name,
        cache_dir=cache_dir,
        local_files_only=local_files_only,
        enabled=enabled,
    )

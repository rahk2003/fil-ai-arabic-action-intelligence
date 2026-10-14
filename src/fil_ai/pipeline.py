"""End-to-end local analysis orchestration."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .context import rank_context_candidates, suggest_context_action
from .extraction import extract_actions
from .inference import ModelKey, ModelRegistry
from .interpretation import interpret_contextual_action
from .semantic import SemanticMatcher


class ActionIntelligencePipeline:
    def __init__(
        self,
        model_path: Path | None = None,
        camelbert_path: Path | None = None,
        *,
        transformer_device: str = "auto",
        semantic_matcher: SemanticMatcher | None = None,
        semantic_threshold: float = 0.55,
    ):
        self.models = ModelRegistry(
            baseline_path=model_path,
            camelbert_path=camelbert_path,
            transformer_device=transformer_device,
        )
        self.semantic_matcher = semantic_matcher
        self.semantic_threshold = semantic_threshold

    @property
    def intent_model(self):
        """Backward-compatible access to the preserved default baseline."""
        return self.models.get("baseline")

    def analyze(
        self,
        message: str,
        *,
        model: ModelKey = "baseline",
        reference_time: str | datetime | None = None,
        previous_tasks: Iterable[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        prediction = self.models.get(model).predict(message)
        actions = extract_actions(message, prediction.label, reference_time)
        previous_tasks = list(previous_tasks)
        candidates = rank_context_candidates(
            message,
            previous_tasks,
            semantic_matcher=self.semantic_matcher,
            semantic_threshold=self.semantic_threshold,
        )
        context = suggest_context_action(prediction.label, candidates)
        semantic_status = self.semantic_matcher.status() if self.semantic_matcher else {
            "enabled": False, "loaded": False, "model_name": None,
            "method": "lexical_fallback", "device": None, "dimension": None,
            "warning": "Semantic embeddings are not configured for this pipeline.",
        }
        context.update({
            "matching_method": semantic_status["method"] if previous_tasks else "no_candidates",
            "embedding_model": semantic_status["model_name"],
            "embedding_status": semantic_status,
        })
        interpretation = interpret_contextual_action(message, prediction.label, actions, context)
        warnings = [value for value in [prediction.warning] if value]
        warnings.extend(
            warning
            for action in actions
            for warning in action.get("warnings", [])
            if warning not in warnings
        )
        return {
            "message": message,
            "prediction": prediction.as_dict(),
            "actions": actions,
            "context": context,
            "interpretation": interpretation,
            "warnings": warnings,
            "automatic_execution": False,
        }

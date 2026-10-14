"""Conservative contextual matching for task updates and duplicates."""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any, Iterable

from .normalization import normalize_arabic, normalized_tokens

FOLLOW_UP_CUES = re.compile(
    r"(?:^خلاص|\bبس\b|\bفقط\b|خله|خليه|خلوه|وخله|ركز|ركّز|"
    r"لا\s+(?:ترسل|تكمل)|باللغة|بصيغة|بدل|بدال|صار|غير)"
)


def similarity(left: str, right: str) -> float:
    left_norm = normalize_arabic(left, remove_punctuation=True)
    right_norm = normalize_arabic(right, remove_punctuation=True)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    left_tokens, right_tokens = normalized_tokens(left), normalized_tokens(right)
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    sequence = SequenceMatcher(None, left_norm, right_norm).ratio()
    return round(0.65 * jaccard + 0.35 * sequence, 6)


def rank_context_candidates(
    message: str,
    previous_tasks: Iterable[dict[str, Any]],
    *,
    minimum_score: float = 0.2,
    semantic_matcher: Any | None = None,
    semantic_threshold: float = 0.55,
) -> list[dict[str, Any]]:
    tasks = list(previous_tasks)
    semantic_scores: list[float | None] = [None] * len(tasks)
    if tasks and semantic_matcher is not None and semantic_matcher.ensure_loaded():
        try:
            semantic_scores = semantic_matcher.similarities(
                message,
                [str(task.get("title") or task.get("original_message") or "") for task in tasks],
            )
        except RuntimeError:
            semantic_scores = [None] * len(tasks)
    candidates = []
    recent_fallback: dict[str, Any] | None = None
    query_tokens = {token for token in normalized_tokens(message) if len(token) > 2}
    for task, semantic_score in zip(tasks, semantic_scores):
        text = str(task.get("title") or task.get("original_message") or "")
        lexical_score = similarity(message, text)
        candidate_tokens = {token for token in normalized_tokens(text) if len(token) > 2}
        shared_entities = sorted(query_tokens & candidate_tokens)
        semantic_supported = semantic_score is not None and semantic_score >= semantic_threshold and (bool(shared_entities) or bool(task.get("is_recent")))
        if lexical_score >= minimum_score or semantic_supported:
            combined_score = lexical_score if semantic_score is None else round(0.6 * semantic_score + 0.3 * lexical_score + 0.1 * bool(shared_entities), 6)
            candidates.append(
                {
                    "task_id": task.get("id"),
                    "task_text": text,
                    "score": combined_score,
                    "lexical_score": lexical_score,
                    "semantic_score": semantic_score,
                    "is_probable_duplicate": lexical_score >= 0.88 and (semantic_score is None or semantic_score >= 0.88),
                    "requires_confirmation": True,
                    "basis": "semantic_plus_lexical_context" if semantic_score is not None else "lexical_similarity",
                    "supporting_evidence": {"shared_terms": shared_entities, "recent_context": bool(task.get("is_recent"))},
                }
            )
        elif task.get("is_recent") and FOLLOW_UP_CUES.search(normalize_arabic(message, remove_punctuation=True)):
            # Arabic follow-ups commonly omit the task noun. Recency is supporting
            # evidence only: the UI must still ask for confirmation.
            recent_fallback = {
                "task_id": task.get("id"),
                "task_text": text,
                "score": 0.19,
                "lexical_score": lexical_score,
                "semantic_score": semantic_score,
                "is_probable_duplicate": False,
                "requires_confirmation": True,
                "basis": "immediate_preceding_task",
                "supporting_evidence": {"shared_terms": shared_entities, "recent_context": True},
            }
    if not candidates and recent_fallback:
        candidates.append(recent_fallback)
    return sorted(candidates, key=lambda item: item["score"], reverse=True)


def suggest_context_action(intent: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if not candidates:
        return {"suggestion": "new_or_unmatched", "candidates": [], "requires_confirmation": True}
    top = candidates[0]
    if len(candidates) > 1 and top["score"] - candidates[1]["score"] < 0.08:
        suggestion = "ambiguous_candidates"
    elif top["is_probable_duplicate"]:
        suggestion = "possible_duplicate"
    elif intent == "reschedule":
        suggestion = "possible_reschedule"
    elif intent == "cancellation":
        suggestion = "possible_cancellation"
    else:
        suggestion = "possibly_related"
    return {"suggestion": suggestion, "candidates": candidates[:3], "requires_confirmation": True}

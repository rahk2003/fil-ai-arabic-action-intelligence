"""Conservative contextual action interpretation above the four-class model."""

from __future__ import annotations

import re
from typing import Any

from .normalization import normalize_arabic

SCOPE_CUES = re.compile(r"(?:\bبس\b|\bفقط\b|\bجزء\b|\bمختصر\b|\bركز\b|\bركّز\b|فرع\s+الرياض)")
REQUIREMENT_CUES = re.compile(r"(?:وخله|وخلي|ويكون|باللغة|بصيغة|مع\s+إضافة|اضف|أضف)")
PRIORITY_CUES = re.compile(r"(?:عاجل|ضروري|اولوية|أولوية|قبل\s+كل\s+شي)")
COMPLETION_CUES = re.compile(r"(?:خلصنا|انتهينا|تم\s+(?:الانتهاء|اعتماد|إرسال|ارسال)|اكتمل|أنجزنا)")
NEGATIVE_ATTENDANCE = re.compile(r"(?:لا\s*حد|لا\s+احد|محد)\s+(?:يجي|يحضر)")
SCHEDULED_COMMITMENT_CUES = re.compile(r"(?:اجتماع(?:نا)?|موعد(?:نا)?)")

ACTION_LABELS = {
    "create_task": "إنشاء مهمة",
    "update_task_scope": "تعديل نطاق المهمة",
    "update_task_requirement": "إضافة متطلب",
    "update_task_priority": "تعديل الأولوية",
    "reschedule_task": "إعادة جدولة",
    "cancel_task": "إلغاء مهمة",
    "mark_complete": "تسجيل الإكمال",
    "add_instruction": "إضافة تعليمات",
    "no_action": "لا إجراء",
    "needs_clarification": "يحتاج توضيحًا",
}


def interpret_contextual_action(
    message: str,
    classifier_label: str,
    actions: list[dict[str, Any]],
    context: dict[str, Any],
) -> dict[str, Any]:
    normalized = normalize_arabic(message, remove_punctuation=True)
    candidates = context.get("candidates") or []
    candidate = candidates[0] if candidates else None
    extracted = next((item for item in actions if item.get("rule_supported")), actions[0] if actions else {})
    extracted_intent = extracted.get("intent")
    missing: list[str] = []
    action_type = "no_action"
    proposed_change: str | None = None
    basis = "No supported action cue was found."

    if SCOPE_CUES.search(normalized):
        if candidate:
            action_type, proposed_change, basis = "update_task_scope", message, "Scope cue plus a related prior task."
            if re.search(r"(?:بس|فقط)\s+(?:جزء|جزءا?)$", normalized):
                missing.append("تحديد الجزء المطلوب")
        else:
            action_type, basis = "needs_clarification", "Scope-change wording has no safely matched task."
            missing.append("تحديد المهمة المرتبطة")
    elif REQUIREMENT_CUES.search(normalized):
        if candidate:
            action_type, proposed_change, basis = "update_task_requirement", message, "Requirement cue plus a related prior task."
        else:
            action_type, basis = "needs_clarification", "A new requirement was detected without a related task."
            missing.append("تحديد المهمة التي يضاف إليها المتطلب")
    elif PRIORITY_CUES.search(normalized) and candidate:
        action_type, proposed_change, basis = "update_task_priority", message, "Priority cue plus a related prior task."
    elif COMPLETION_CUES.search(normalized):
        if candidate:
            action_type, proposed_change, basis = "mark_complete", message, "Completion cue plus a related task."
        else:
            action_type, basis = "no_action", "Completion/approval statement without a matched task is informational."
    elif NEGATIVE_ATTENDANCE.search(normalized):
        action_type = "needs_clarification" if candidate else "no_action"
        basis = "Negative attendance instruction is not converted into a positive task."
        if candidate:
            missing.append("تأكيد ما إذا كان المقصود إلغاء حدث سابق")
    elif (
        SCHEDULED_COMMITMENT_CUES.search(normalized)
        and extracted.get("datetime_text")
        and not candidate
    ):
        action_type, proposed_change, basis = "create_task", message, "A dated meeting/appointment statement can be reviewed as a new calendar task."
    elif extracted_intent == "reschedule" and extracted.get("rule_supported"):
        if candidate:
            action_type, proposed_change, basis = "reschedule_task", extracted.get("normalized_datetime"), "Schedule-change cue plus a related task."
        else:
            action_type, basis = "needs_clarification", "A schedule change requires a related existing task."
            missing.append("اختيار المهمة المرتبطة")
    elif extracted_intent == "cancellation" and extracted.get("rule_supported"):
        if candidate:
            action_type, proposed_change, basis = "cancel_task", message, "Cancellation cue plus a related task."
        else:
            action_type, basis = "needs_clarification", "A cancellation cue alone does not identify the task to cancel."
            missing.append("اختيار المهمة المراد إلغاؤها")
    elif extracted_intent == "new_task" and extracted.get("rule_supported"):
        action_type, proposed_change, basis = "create_task", extracted.get("action_text"), "Explicit request cue in the message."
    elif classifier_label != "info_only" and candidate:
        action_type, basis = "needs_clarification", "Classifier label is unsupported by an explicit cue; context requires review."
        missing.append("تأكيد نوع التغيير المطلوب")

    consistency = "agree" if extracted_intent == classifier_label else "conflict"
    if not extracted.get("rule_supported"):
        consistency = "unsupported_classifier_label" if classifier_label != "info_only" else "agree"
    return {
        "action_type": action_type,
        "action_label_ar": ACTION_LABELS[action_type],
        "classifier_label": classifier_label,
        "extracted_intent": extracted_intent,
        "classifier_extraction_consistency": consistency,
        "related_task_id": candidate.get("task_id") if candidate else None,
        "related_task_text": candidate.get("task_text") if candidate else None,
        "evidence": message,
        "proposed_change": proposed_change,
        "missing_details": missing,
        "requires_confirmation": action_type not in {"no_action", "needs_clarification"},
        "abstained": action_type in {"no_action", "needs_clarification"},
        "basis": basis,
    }

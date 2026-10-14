"""Transparent rule-based Arabic action and temporal extraction.

This is intentionally described as a rule-based prototype, not a trained NER
model. Evidence text and uncertainty are preserved for human confirmation.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .config import TIMEZONE
from .normalization import normalize_arabic

WEEKDAYS = {
    "الاثنين": 0,
    "الإثنين": 0,
    "الثلاثاء": 1,
    "الاربعاء": 2,
    "الأربعاء": 2,
    "الخميس": 3,
    "الجمعة": 4,
    "السبت": 5,
    "الاحد": 6,
    "الأحد": 6,
}

DATE_PATTERN = re.compile(
    r"(?:بعد\s+بكره|بعد\s+بكرة|بكره|بكرة|غد[ًا]?|اليوم|"
    r"(?:يوم\s+)?(?:الاحد|الأحد|الاثنين|الإثنين|الثلاثاء|الاربعاء|الأربعاء|الخميس|الجمعة|السبت)(?:\s+(?:الجاي|القادم|المقبل))?|"
    r"الاسبوع\s+(?:الجاي|القادم|المقبل)|الأسبوع\s+(?:الجاي|القادم|المقبل)|"
    r"قبل\s+نهاية\s+(?:الدوام|اليوم|الأسبوع|الاسبوع))"
)
TIME_PATTERN = re.compile(
    r"(?:الساعة\s*)?(?P<hour>[0-2٠-٢۰-۲]?[0-9٠-٩۰-۹])(?::(?P<minute>[0-5٠-٥۰-۵][0-9٠-٩۰-۹]))?\s*"
    r"(?P<period>صباح(?:ا|اً)?|الصباح|ظهر(?:ا|اً)?|الظهر|عصر(?:ا|اً)?|العصر|مساء(?:ً|ا)?|المساء|ليل(?:ا|اً)?|الليل)"
)
ACTION_CUES = re.compile(
    r"(?:ارس[لل][يوا]*|أرس[لل][يوا]*|اكتب[يوا]*|جهز[يوا]*|حلل[يوا]*|راجع[يوا]*|"
    r"اكملي|أكملي|اكملوا|أكملوا|سلم[يوا]*|تسليم|ارفع[يوا]*|احجز[يوا]*|"
    r"تواصل[يوا]*|لا\s+تنس(?:ين|ون)|مطلوب|نحتاج|ابغى|أبغى|يرجى|الرجاء)"
)
CHANGE_CUES = re.compile(
    r"(?:تأجل|تاجل|أجلنا|اجلنا|بدل|بدال|صار|اصبح|أصبح|غيرنا|تغير|غيّر|"
    r"موعد\s+جديد|خلوه|خلي|نقلنا|قدمنا|انزاح)"
)
CANCEL_CUES = re.compile(
    r"(?:الغ[يى]|إلغ|الغاء|إلغاء|انلغ|ملغ|وقف|توقف|لا\s+(?:تكمل|ترسل|تسوي)|"
    r"ما\s+(?:عاد|يحتاج)|ما\s+في\s+داعي|لن\s+(?:يتم|تعقد|تُعقد))"
)
PROHIBITION_CUES = re.compile(
    r"(?:لا\s*حد\s+(?:يجي|يحضر)|لا\s+احد\s+(?:يجي|يحضر)|محد\s+(?:يجي|يحضر)|"
    r"لا\s+(?:ترسل|تجي|تحضر|تكمل|تسوي|تعمل))"
)


def _action_span(clause: str, temporal_text: str | None) -> str:
    """Keep actionable evidence while trimming wrappers and time phrases."""
    value = re.sub(
        r"^(?:السلام\s+عليكم\s*|لو\s+سمحت[يوا]*\s*|عندي\s+طلب\s+بسيط\s*[:：]?\s*|خلاص\s*|ترى\s*)",
        "",
        clause.strip(),
    )
    if temporal_text:
        value = value.replace(temporal_text, " ")
    return re.sub(r"\s+", " ", value).strip(" ،,.؛") or clause.strip()


def parse_reference_time(value: str | datetime | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    timezone = ZoneInfo(TIMEZONE)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def _next_weekday(reference: datetime, target: int) -> datetime:
    days = (target - reference.weekday()) % 7
    return reference + timedelta(days=7 if days == 0 else days)


def _resolve_date(date_text: str, reference: datetime) -> datetime | None:
    normalized = normalize_arabic(date_text)
    if normalized == "اليوم":
        return reference
    if normalized in {"بكره", "بكرة", "غدا"}:
        return reference + timedelta(days=1)
    if normalized in {"بعد بكره", "بعد بكرة"}:
        return reference + timedelta(days=2)
    if "الاسبوع" in normalized and any(x in normalized for x in ("الجاي", "القادم", "المقبل")):
        return reference + timedelta(days=7)
    for name, weekday in WEEKDAYS.items():
        if normalize_arabic(name) in normalized:
            return _next_weekday(reference, weekday)
    return None


def _resolve_time(match: re.Match[str]) -> tuple[int, int]:
    hour = int(normalize_arabic(match.group("hour")))
    minute = int(normalize_arabic(match.group("minute") or "0"))
    period = normalize_arabic(match.group("period"))
    if any(value in period for value in ("ظهر", "عصر", "مساء", "ليل")) and hour < 12:
        hour += 12
    if "صباح" in period and hour == 12:
        hour = 0
    return hour, minute


def extract_temporal(message: str, reference_time: str | datetime | None = None) -> dict[str, Any]:
    date_match = DATE_PATTERN.search(message)
    time_match = TIME_PATTERN.search(message)
    evidence = " ".join(
        value for value in (date_match.group(0) if date_match else "", time_match.group(0) if time_match else "") if value
    ).strip() or None
    reference = parse_reference_time(reference_time)
    normalized_datetime = None
    uncertainty: list[str] = []
    if not date_match and not time_match:
        return {
            "datetime_text": None,
            "normalized_datetime": None,
            "is_ambiguous": False,
            "warnings": [],
        }
    if reference is None:
        uncertainty.append("A message/reference timestamp is required to normalize relative dates safely.")
    elif date_match:
        resolved_date = _resolve_date(date_match.group(0), reference)
        if resolved_date is None:
            uncertainty.append("The date phrase is qualitative or underspecified.")
        else:
            if time_match:
                hour, minute = _resolve_time(time_match)
                resolved_date = resolved_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                resolved_date = resolved_date.replace(hour=0, minute=0, second=0, microsecond=0)
                uncertainty.append("A date was found without an exact time; midnight is not asserted as a deadline.")
            if not uncertainty or time_match:
                normalized_datetime = resolved_date.isoformat()
    else:
        uncertainty.append("A time was found without a date; no calendar date was inferred.")
    return {
        "datetime_text": evidence,
        "normalized_datetime": normalized_datetime,
        "is_ambiguous": bool(uncertainty),
        "warnings": uncertainty,
    }


def split_action_clauses(message: str) -> list[str]:
    clauses = [part.strip(" ،,.؛") for part in re.split(r"[؛;\n]+|،\s*(?=(?:و?لا\s+تنس|و?مطلوب|و?ارس|و?أرس))", message)]
    return [clause for clause in clauses if clause]


def extract_actions(
    message: str,
    primary_intent: str,
    reference_time: str | datetime | None = None,
) -> list[dict[str, Any]]:
    clauses = split_action_clauses(message)
    actions: list[dict[str, Any]] = []
    for clause in clauses:
        has_action = bool(ACTION_CUES.search(normalize_arabic(clause)))
        has_change = bool(CHANGE_CUES.search(normalize_arabic(clause)))
        has_cancel = bool(CANCEL_CUES.search(normalize_arabic(clause)))
        has_prohibition = bool(PROHIBITION_CUES.search(normalize_arabic(clause)))
        if not (has_action or has_change or has_cancel or has_prohibition) and len(clauses) > 1:
            continue
        temporal = extract_temporal(clause, reference_time)
        clause_intent = (
            "cancellation" if has_cancel or has_prohibition else "reschedule" if has_change else "new_task" if has_action else primary_intent
        )
        rule_supported = has_action or has_change or has_cancel or has_prohibition
        warnings = list(temporal["warnings"])
        if clause_intent != primary_intent:
            warnings.append(f"Classifier/extraction disagreement: classifier={primary_intent}, extracted={clause_intent}.")
        actions.append(
            {
                "intent": clause_intent,
                "action_text": _action_span(clause, temporal["datetime_text"]),
                **{**temporal, "warnings": warnings},
                "requires_action": rule_supported,
                "evidence": clause,
                "requires_confirmation": True,
                "rule_supported": rule_supported,
            }
        )
    if not actions:
        temporal = extract_temporal(message, reference_time)
        warnings = list(temporal["warnings"])
        if primary_intent != "info_only":
            warnings.append("The classifier label has no matching action/change cue; no operation is proposed without context.")
        actions.append(
            {
                "intent": primary_intent,
                "action_text": None,
                **{**temporal, "warnings": warnings},
                "is_ambiguous": primary_intent != "info_only" or temporal["is_ambiguous"],
                "requires_action": False,
                "evidence": message,
                "requires_confirmation": False,
                "rule_supported": False,
            }
        )
    return actions

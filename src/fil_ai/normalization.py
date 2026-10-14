"""Conservative Arabic normalization for matching and classical ML."""

from __future__ import annotations

import re
import unicodedata

DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
WHITESPACE = re.compile(r"\s+")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize_arabic(text: str, *, remove_punctuation: bool = False) -> str:
    """Normalize orthographic variants without stemming or deleting negation.

    This intentionally preserves Ta Marbuta and Hamza-on-Waw/Ya because collapsing
    them can change lexical identity. It is suitable for matching and TF-IDF, not
    a claim of complete Arabic linguistic normalization.
    """
    value = unicodedata.normalize("NFKC", str(text or "")).strip()
    value = value.translate(ARABIC_DIGITS).replace("ـ", "")
    value = DIACRITICS.sub("", value)
    value = re.sub(r"[إأآٱ]", "ا", value).replace("ى", "ي")
    if remove_punctuation:
        value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return WHITESPACE.sub(" ", value).strip()


def normalized_tokens(text: str) -> set[str]:
    return set(normalize_arabic(text, remove_punctuation=True).split())

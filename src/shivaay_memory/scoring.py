"""Transparent, conservative scoring for candidate memories."""
from __future__ import annotations

SENSITIVE_MARKERS = (
    "password", "passcode", "private key", "secret key", "api key",
    "medical diagnosis", "bank account", "credit card", "home address",
    "phone number", "passport number", "social security",
)
TEMPORARY_MARKERS = (
    "today", "right now", "currently", "for a moment", "this afternoon",
    "tomorrow", "next week", "this weekend", "just finished",
)
DURABLE_CATEGORIES = {"preference", "goal", "decision", "project", "identity", "rule"}


def _get(candidate, key, default):
    try:
        return candidate.get(key, default)
    except AttributeError:
        try:
            return candidate[key]
        except (KeyError, TypeError, IndexError):
            return getattr(candidate, key, default)


def score_candidate(candidate):
    text = str(_get(candidate, "text", "")).strip()
    folded = text.casefold()
    category = str(_get(candidate, "category", "general")).casefold()
    confidence = max(0.0, min(1.0, float(_get(candidate, "confidence", 0.5))))
    importance = max(1, min(5, int(_get(candidate, "importance", 3))))
    durable = 0.9 if category in DURABLE_CATEGORIES else 0.65
    if any(marker in folded for marker in TEMPORARY_MARKERS):
        durable = max(0.15, durable - 0.4)
    usefulness = importance / 5
    project_specific = bool(_get(candidate, "project", "general") not in {"", "general"})
    usefulness = min(1.0, usefulness + (0.08 if project_specific else 0.0))
    sensitive = any(marker in folded for marker in SENSITIVE_MARKERS)
    risk = 1.0 if sensitive else 0.0
    recurrence_count = max(1, int(_get(candidate, "recurrence_count", 1)))
    # Repetition is supporting evidence, not proof. Cap the boost so spam/repetition
    # cannot override sensitivity or confidence safeguards.
    recurrence = min(1.0, 0.5 + 0.1 * min(recurrence_count - 1, 5))
    total = 0.36 * durable + 0.32 * usefulness + 0.22 * confidence + 0.10 * recurrence
    if sensitive:
        total = min(total, 0.2)
    return {
        "durability": round(durable, 3),
        "usefulness": round(usefulness, 3),
        "confidence": round(confidence, 3),
        "recurrence": round(recurrence, 3),
        "recurrence_count": recurrence_count,
        "sensitivity_risk": round(risk, 3),
        "score": round(total, 3),
        "auto_save_eligible": not sensitive and confidence >= 0.90 and total >= 0.85 and importance >= 3,
    }

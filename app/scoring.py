"""Set scores for unweighted tags, plus the older weighted overlap.

Jaccard is the baseline. The overlap coefficient is the alternate.
The weighted formula stays for a corpus whose preference rows carry a weight.
Gemma may rephrase a sentence. It does not rerank.
"""

from __future__ import annotations

SOON_HOURS = 60
SOON_BONUS = 0.06
PAST_PENALTY = 0.08
MAIL_BONUS = 0.05
SATURATION = 0.55
MIN_PROPOSE = 0.62
COMPANY_MIN = 0.75

WEIGHTED_FORMULA = (
    "score = min(0.99, w / (w + 0.55) + time + mail); "
    "w is the sum of the student's preference weights whose tag is on the event; "
    "time is +0.06 if the event starts within 60 hours of the demo clock, "
    "-0.08 if it has already started, otherwise 0; "
    "mail is +0.05 when a mock email links that student to that event."
)
JACCARD_FORMULA = (
    "score = |preferences ∩ event tags| / |preferences ∪ event tags|. "
    "No shared tag means no match. The demo clock and mock mail do not change "
    "this number. They stay on the match so the trace can cite them."
)
OVERLAP_FORMULA = (
    "score = |preferences ∩ event tags| / min(|preferences|, |event tags|). "
    "This is the overlap coefficient. No shared tag means no match. "
    "The demo clock and mock mail do not change this number."
)

FORMULAS = {
    "jaccard": JACCARD_FORMULA,
    "overlap": OVERLAP_FORMULA,
    "weighted": WEIGHTED_FORMULA,
}

# One shared tag on a typical 4-preference / 3-tag pair is Jaccard 1/6 ≈ 0.17.
# The floor asks for a stronger overlap before the agent proposes.
PROPOSE_FLOOR = {
    "jaccard": 0.25,
    "overlap": 0.50,
    "weighted": MIN_PROPOSE,
}
COMPANY_FLOOR = {
    "jaccard": 0.34,
    "overlap": 0.67,
    "weighted": COMPANY_MIN,
}

# Kept for callers that still import the weighted sentence under the old name.
FORMULA = WEIGHTED_FORMULA


def jaccard_score(prefs: set[str], tags: set[str]) -> float:
    """|A ∩ B| / |A ∪ B|, rounded to 2 decimals. Empty intersection is 0."""
    return _set_score(prefs, tags, "jaccard")


def overlap_score(prefs: set[str], tags: set[str]) -> float:
    """|A ∩ B| / min(|A|, |B|), rounded to 2 decimals. Empty intersection is 0."""
    return _set_score(prefs, tags, "overlap")


def _set_score(prefs: set[str], tags: set[str], formula: str) -> float:
    if not prefs or not tags:
        return 0.0
    inter = len(prefs & tags)
    if inter == 0:
        return 0.0
    if formula == "jaccard":
        raw = inter / len(prefs | tags)
    elif formula == "overlap":
        raw = inter / min(len(prefs), len(tags))
    else:
        raise ValueError(formula)
    return round(raw, 2)


def score_overlap(matched_weight: float, hours_until: float | None, mailed: bool) -> float:
    """Weighted tag overlap in [0, 0.99]. Zero weight is zero: no tag, no match."""
    if matched_weight <= 0:
        return 0.0
    base = matched_weight / (matched_weight + SATURATION)
    if hours_until is None:
        adjustment = 0.0
    elif hours_until < 0:
        adjustment = -PAST_PENALTY
    elif hours_until <= SOON_HOURS:
        adjustment = SOON_BONUS
    else:
        adjustment = 0.0
    if mailed:
        adjustment += MAIL_BONUS
    return round(min(0.99, max(0.0, base + adjustment)), 2)


def propose_floor(formula: str) -> float:
    try:
        return PROPOSE_FLOOR[formula]
    except KeyError as exc:
        raise ValueError(f"formula must be one of {', '.join(FORMULAS)}") from exc


def company_floor(formula: str) -> float:
    try:
        return COMPANY_FLOOR[formula]
    except KeyError as exc:
        raise ValueError(f"formula must be one of {', '.join(FORMULAS)}") from exc

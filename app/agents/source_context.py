"""Source-type-specific prompt context for pipeline agents."""
from __future__ import annotations

_SUMMARIZER_CONTEXT: dict[str, str] = {
    "cms_bulletin": (
        "Focus on coding edits, modifiers, PTP/MUE rules, and effective dates. "
        "Audience: certified coders and payment-integrity analysts."
    ),
    "payer_policy": (
        "Focus on coverage criteria, prior authorization, frequency limits, and "
        "documentation requirements. Audience: medical policy reviewers."
    ),
    "code_set": (
        "Focus on added, deleted, and revised codes with effective dates. "
        "Audience: coding operations and claims editors."
    ),
    "contract": (
        "Focus on payment terms, quality thresholds, shared savings, benchmarks, "
        "and settlement triggers. Audience: contract administration and VBP analysts."
    ),
    "clinical_guideline": (
        "Focus on recommendation strength, patient population, and coverage-linked "
        "criteria. Do not make clinical decisions — summarize for coding/policy teams."
    ),
}

_DRAFTER_CONTEXT: dict[str, str] = {
    "cms_bulletin": "Draft prepay claim edits (PTP, modifiers, MUE, deleted codes).",
    "payer_policy": "Draft prepay edits for prior auth, frequency, and coverage limits.",
    "code_set": "Draft edits for deleted/terminated codes and effective-date rejections.",
    "contract": (
        "Draft settlement or quality-threshold rules (shared savings, benchmark gates). "
        "Use action informational or pend_for_review when claim-level edits do not apply."
    ),
    "clinical_guideline": (
        "Draft coverage-linked edits where the guideline ties to billable services. "
        "Flag informational rules when clinical judgment is required."
    ),
}


def summarizer_context(source_type: str) -> str:
    return _SUMMARIZER_CONTEXT.get(source_type, _SUMMARIZER_CONTEXT["cms_bulletin"])


def drafter_context(source_type: str) -> str:
    return _DRAFTER_CONTEXT.get(source_type, _DRAFTER_CONTEXT["cms_bulletin"])

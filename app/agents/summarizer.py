"""Stage 1 agent: ingest and summarize a policy document version."""
from __future__ import annotations

import re

from .llm import llm

from .source_context import summarizer_context

SYSTEM = (
    "You are a healthcare payment-integrity analyst. You summarize CMS bulletins, "
    "payer medical policies, code-set revisions, clinical practice guidelines, and "
    "contract terms for an audience of certified coders and clinical reviewers. "
    "Be precise, cite specific codes and modifiers, and never invent policy that "
    "is not in the text."
)


def summarize(title: str, raw_text: str, source_type: str = "cms_bulletin") -> tuple[str, list[str]]:
    """Return (summary, key_points)."""
    if llm.available:
        try:
            return _summarize_llm(title, raw_text, source_type)
        except Exception:
            pass
    return _summarize_offline(title, raw_text, source_type)


def _summarize_llm(title: str, raw_text: str, source_type: str) -> tuple[str, list[str]]:
    ctx = summarizer_context(source_type)
    prompt = (
        f"Document title: {title}\n"
        f"Source type: {source_type}\n"
        f"Context: {ctx}\n\n"
        f"Document text:\n{raw_text}\n\n"
        "Produce JSON with keys: 'summary' (3-4 sentence plain-language summary) and "
        "'key_points' (array of 3-6 short strings, each a specific actionable fact such "
        "as a code, modifier, unit limit, or effective date)."
    )
    data = llm.complete_json(SYSTEM, prompt)
    summary = str(data.get("summary", "")).strip()
    key_points = [str(k).strip() for k in data.get("key_points", []) if str(k).strip()]
    return summary, key_points


# ---------------------------------------------------------------------------
# Deterministic offline engine
# ---------------------------------------------------------------------------
CODE_RE = re.compile(r"\b(?:[A-Z]\d{4}|\d{5}|G\d{4}|J\d{4}|Q\d{4}|A\d{4})\b")
MODIFIER_RE = re.compile(r"\bmodifier\s+(\d{2}|X[EPSU]|LT|RT)\b", re.IGNORECASE)


def _split_sentences(text: str) -> list[str]:
    flat = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in re.split(r"(?<=[.])\s+", flat) if len(s.strip()) > 25]


def _summarize_offline(title: str, raw_text: str, source_type: str = "cms_bulletin") -> tuple[str, list[str]]:
    sentences = _split_sentences(raw_text)
    # Score sentences by signal words and presence of codes/modifiers.
    signal = (
        "denied", "denial", "deny", "covered", "coverage", "modifier", "unit",
        "medically", "prior authorization", "effective", "rejected", "limit",
        "maximum", "review", "pended", "repriced", "150 percent",
    )
    scored = []
    for s in sentences:
        score = sum(1 for w in signal if w in s.lower())
        score += len(CODE_RE.findall(s))
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [s for _, s in scored[:3]]
    # Preserve original order for readability.
    top_ordered = [s for s in sentences if s in top]
    summary = (
        f"{title}. " + " ".join(top_ordered)
        if top_ordered
        else f"{title}. " + " ".join(sentences[:2])
    )

    key_points: list[str] = []
    codes = sorted(set(CODE_RE.findall(raw_text)))
    mods = sorted(set(m.upper() for m in MODIFIER_RE.findall(raw_text)))
    if codes:
        key_points.append("Codes referenced: " + ", ".join(codes[:8]))
    if mods:
        key_points.append("Modifiers referenced: " + ", ".join(mods))
    for s in top_ordered:
        if any(w in s.lower() for w in ("denied", "deny", "rejected", "pended", "prior authorization", "maximum")):
            key_points.append(s if len(s) < 160 else s[:157] + "...")
    eff = re.search(r"(20\d{2}-\d{2}-\d{2})", raw_text)
    if eff:
        key_points.append(f"Effective date referenced: {eff.group(1)}")
    if source_type == "clinical_guideline":
        for m in re.finditer(r"Class\s+([IVX]+[ab]?)", raw_text, re.I):
            key_points.append(f"Recommendation class: {m.group(0)}")
    if source_type == "contract":
        qm = re.search(r"quality score of\s+(\d+(?:\.\d+)?)", raw_text, re.I)
        if qm:
            key_points.append(f"Quality threshold: {qm.group(1)}")
        sm = re.search(r"(\d+(?:\.\d+)?)\s*%\s*below the benchmark", raw_text, re.I)
        if sm:
            key_points.append(f"Savings threshold: {sm.group(1)}% below benchmark")
    # De-duplicate while preserving order.
    seen = set()
    deduped = []
    for k in key_points:
        if k not in seen:
            seen.add(k)
            deduped.append(k)
    return summary.strip(), deduped[:6]

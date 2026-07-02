"""Stage 2 agent: automated change detection across policy versions."""
from __future__ import annotations

import difflib
import re

from .llm import llm

SYSTEM = (
    "You are a payment-integrity change analyst. You compare two versions of a policy "
    "document and identify substantive changes that affect claim adjudication. Ignore "
    "cosmetic edits. For each change, classify significance by its dollar/compliance "
    "impact."
)

HIGH_SIGNAL = (
    "denied", "denial", "deny", "rejected", "prior authorization", "no longer",
    "repriced", "combined", "pended", "prepayment review", "required",
)
MED_SIGNAL = ("maximum", "limit", "units", "modifier", "threshold", "review", "added", "deleted")


def detect_changes(title: str, old_text: str, new_text: str) -> dict:
    old_trim = _trim_for_compare(old_text)
    new_trim = _trim_for_compare(new_text)
    if llm.available:
        try:
            return _detect_llm(title, old_trim, new_trim)
        except Exception:
            pass
    return _detect_offline(title, old_trim, new_trim)


def _trim_for_compare(text: str, max_chars: int = 18000) -> str:
    """Keep large PDFs comparable without blowing token limits or diff performance."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    head = max_chars * 2 // 3
    tail = max_chars - head
    return (
        text[:head]
        + "\n\n[… document truncated for change detection …]\n\n"
        + text[-tail:]
    )


def _detect_llm(title: str, old_text: str, new_text: str) -> dict:
    prompt = (
        f"Document: {title}\n\n"
        f"PRIOR VERSION:\n{old_text}\n\n"
        f"NEW VERSION:\n{new_text}\n\n"
        "Return JSON with keys 'headline' (one sentence describing the most important "
        "change) and 'changes' (array). Each change object has: 'section', 'change_type' "
        "(added|removed|modified), 'old_text', 'new_text', 'significance' (high|medium|low), "
        "and 'impact_summary' (how it changes adjudication)."
    )
    data = llm.complete_json(SYSTEM, prompt, max_tokens=2000)
    return {
        "headline": str(data.get("headline", "Policy changes detected.")),
        "changes": data.get("changes", []),
    }


# ---------------------------------------------------------------------------
# Deterministic offline engine
# ---------------------------------------------------------------------------
def _paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text.strip())
    paras = [re.sub(r"\s+", " ", p).strip() for p in parts if p.strip()]
    # PDF extracts often lack blank lines — fall back to line grouping.
    if len(paras) <= 3 and len(text) > 2000:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        paras = []
        buf: list[str] = []
        size = 0
        for ln in lines:
            buf.append(ln)
            size += len(ln)
            if size >= 400 or ln.endswith("."):
                paras.append(" ".join(buf))
                buf, size = [], 0
        if buf:
            paras.append(" ".join(buf))
    return paras


def _section_label(paragraph: str) -> str:
    head = paragraph.split(".")[0].split(":")[0]
    return head[:80] if head else "General"


def _significance(text: str) -> str:
    low = text.lower()
    if any(w in low for w in HIGH_SIGNAL):
        return "high"
    if any(w in low for w in MED_SIGNAL):
        return "medium"
    return "low"


def _detect_offline(title: str, old_text: str, new_text: str) -> dict:
    old_paras = _paragraphs(old_text)
    new_paras = _paragraphs(new_text)
    matcher = difflib.SequenceMatcher(None, old_paras, new_paras, autojunk=False)
    changes: list[dict] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            for old_p, new_p in zip(old_paras[i1:i2], new_paras[j1:j2]):
                changes.append(_make_change("modified", old_p, new_p))
            # Handle length mismatch.
            extra_old = old_paras[i1 + (j2 - j1) : i2]
            extra_new = new_paras[j1 + (i2 - i1) : j2]
            for p in extra_old:
                changes.append(_make_change("removed", p, None))
            for p in extra_new:
                changes.append(_make_change("added", None, p))
        elif tag == "delete":
            for p in old_paras[i1:i2]:
                changes.append(_make_change("removed", p, None))
        elif tag == "insert":
            for p in new_paras[j1:j2]:
                changes.append(_make_change("added", None, p))

    changes.sort(key=lambda c: {"high": 0, "medium": 1, "low": 2}[c["significance"]])
    # Cap noisy diffs on very large documents — surface the top adjudication-relevant items.
    if len(changes) > 12:
        changes = changes[:12]
    if changes:
        top = changes[0]
        headline = f"{top['significance'].title()}-impact change in '{top['section']}': {top['impact_summary']}"
    else:
        headline = "No substantive changes detected between versions."
    return {"headline": headline, "changes": changes}


def _word_diff(old: str, new: str) -> str:
    sm = difflib.SequenceMatcher(None, old.split(), new.split())
    added, removed = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            removed.extend(old.split()[i1:i2])
        if tag in ("replace", "insert"):
            added.extend(new.split()[j1:j2])
    bits = []
    if removed:
        bits.append("removed: '" + " ".join(removed[:20]) + "'")
    if added:
        bits.append("added: '" + " ".join(added[:20]) + "'")
    return "; ".join(bits)


def _make_change(change_type: str, old_p, new_p) -> dict:
    basis = new_p or old_p or ""
    section = _section_label(basis)
    if change_type == "modified":
        impact = _word_diff(old_p or "", new_p or "")
        sig = _significance((new_p or "") + " " + (old_p or ""))
    elif change_type == "added":
        impact = "New provision added: " + (new_p[:140] + "..." if len(new_p) > 140 else new_p)
        sig = _significance(new_p)
    else:
        impact = "Provision removed: " + (old_p[:140] + "..." if len(old_p) > 140 else old_p)
        sig = _significance(old_p)
    return {
        "section": section,
        "change_type": change_type,
        "old_text": old_p,
        "new_text": new_p,
        "significance": sig,
        "impact_summary": impact or "Text revised.",
    }

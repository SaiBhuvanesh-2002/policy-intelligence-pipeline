"""Stage 3 agent: draft executable payment-integrity edits from policy text.

Output is a structured, machine-executable rule (RuleLogic) plus human-readable
rationale, a citation back to the source, a confidence score, and pseudocode /
SQL previews so a claims engineer could implement the edit directly.
"""
from __future__ import annotations

import re

from .llm import llm
from .source_context import drafter_context

SYSTEM = (
    "You are a payment-integrity rules engineer. You convert policy language into "
    "precise, executable claim edits. Each edit must be conservative, auditable, and "
    "traceable to the source text. You never fabricate codes. Prefer prepay edits "
    "(prevent the incorrect payment) over postpay recovery when the policy supports it."
)

CODE_RE = re.compile(r"\b(?:G\d{4}|J\d{4}|Q\d{4}|A\d{4}|\d{5})\b")
DX_RE = re.compile(r"\b([A-Z]\d{2}(?:\.\d+)?)\b")


def _format_changes(changes: list[dict] | None) -> str:
    if not changes:
        return ""
    lines = []
    for i, c in enumerate(changes[:8], 1):
        lines.append(
            f"{i}. [{c.get('significance', 'medium')}] {c.get('section', 'Section')}: "
            f"{c.get('change_type', 'modified')} — {c.get('impact_summary', '')[:200]}"
        )
    return "\n".join(lines)


def draft_rules(
    title: str,
    summary: str,
    raw_text: str,
    change_headline: str = "",
    changes: list[dict] | None = None,
    source_type: str = "cms_bulletin",
) -> list[dict]:
    if llm.available:
        try:
            rules = _draft_llm(title, summary, raw_text, change_headline, changes, source_type)
            if rules:
                return rules
        except Exception:
            pass
    return _draft_offline(title, raw_text, changes, source_type)


def _draft_llm(
    title: str,
    summary: str,
    raw_text: str,
    change_headline: str,
    changes: list[dict] | None,
    source_type: str,
) -> list[dict]:
    ctx = drafter_context(source_type)
    change_block = _format_changes(changes)
    prompt = (
        f"Policy: {title}\nSource type: {source_type}\nContext: {ctx}\n"
        f"Summary: {summary}\n"
        f"Most significant change: {change_headline}\n"
    )
    if change_block:
        prompt += f"Detected changes:\n{change_block}\n\n"
    prompt += (
        f"Full text:\n{raw_text}\n\n"
        "Draft 1-3 executable payment-integrity edits as JSON: an array of objects with "
        "keys: title, rationale, citation (quote the governing sentence), severity "
        "(high|medium|low), confidence (0-1 float), edit_type (prepay|postpay), and logic "
        "{when_procedure_codes[], when_diagnosis_codes[], when_modifiers[], "
        "unless_modifiers[], same_date_of_service(bool), max_units(int|null), "
        "effective_date(YYYY-MM-DD|null), action "
        "(deny_line|deny_claim|pend_for_review|adjust_units|require_modifier|"
        "require_documentation|informational), pseudocode, sql_preview}."
    )
    data = llm.complete_json(SYSTEM, prompt, max_tokens=2500)
    rules = data if isinstance(data, list) else data.get("rules", [])
    return [_normalize(r) for r in rules]


def _normalize(r: dict) -> dict:
    logic = r.get("logic", {}) or {}
    return {
        "title": str(r.get("title", "Untitled edit"))[:200],
        "rationale": str(r.get("rationale", "")),
        "citation": str(r.get("citation", "")),
        "severity": r.get("severity", "medium"),
        "confidence": float(r.get("confidence", 0.6)),
        "edit_type": r.get("edit_type", "prepay"),
        "logic": {
            "when_procedure_codes": logic.get("when_procedure_codes", []) or [],
            "when_diagnosis_codes": logic.get("when_diagnosis_codes", []) or [],
            "when_modifiers": logic.get("when_modifiers", []) or [],
            "unless_modifiers": logic.get("unless_modifiers", []) or [],
            "same_date_of_service": bool(logic.get("same_date_of_service", False)),
            "max_units": logic.get("max_units"),
            "effective_date": logic.get("effective_date"),
            "action": logic.get("action", "pend_for_review"),
            "pseudocode": logic.get("pseudocode", ""),
            "sql_preview": logic.get("sql_preview", ""),
        },
    }


# ---------------------------------------------------------------------------
# Deterministic offline engine — pattern-based rule synthesis
# ---------------------------------------------------------------------------
def _draft_offline(
    title: str,
    text: str,
    changes: list[dict] | None = None,
    source_type: str = "cms_bulletin",
) -> list[dict]:
    rules: list[dict] = []
    low = text.lower()

    if source_type == "contract":
        rules.extend(_contract_rules(text))
    if source_type == "clinical_guideline":
        rules.extend(_guideline_rules(text))

    # Pattern 1: PTP / column-two code denial requiring a specific modifier.
    ptp = re.search(
        r"(\d{5})\s*(?:\([^)]*\)\s*)?is a column-two code to\s*(\d{5})", text
    )
    if ptp:
        col2, col1 = ptp.group(1), ptp.group(2)
        required_mod = None
        m = re.search(r"unless modifier\s+(X[EPSU]|\d{2})\b", text)
        if m:
            required_mod = m.group(1).upper()
        rules.append(_ptp_rule(col1, col2, required_mod, ptp.group(0)))

    # Pattern 2: deleted code -> reject on/after effective date.
    for dm in re.finditer(
        r"([A-Z]\d{4}|\d{5}).{0,80}?(?:deleted|rejected|replaced).{0,80}?(20\d{2}-\d{2}-\d{2})",
        text,
        re.IGNORECASE | re.DOTALL,
    ):
        rules.append(_deleted_code_rule(dm.group(1), dm.group(2), dm.group(0).strip()))

    # Pattern 3: prior authorization requirement.
    pa = re.search(r"([A-Z]\d{4}|\d{5})[^.]{0,80}?requires prior authorization", text, re.IGNORECASE)
    if pa:
        rules.append(_prior_auth_rule(pa.group(1), pa.group(0).strip()))

    # Pattern 4: frequency limit (max N tests per period).
    if "maximum of one (1)" in low or "one (1) definitive" in low:
        codes = sorted(set(re.findall(r"G048\d", text)))
        rules.append(_frequency_rule(codes or ["G0480", "G0481", "G0482", "G0483"], 1, _grab(text, "maximum of one")))

    # Pattern 5: modifier-50 unit constraint.
    if "modifier 50" in low and ("greater than one" in low or "one (1) unit" in low):
        action = "deny_line" if "denied" in low else "pend_for_review"
        rules.append(_modifier50_rule(action, _grab(text, "modifier 50")))

    # Pattern 6: MUE date-of-service totaling (MAI 3).
    if "mai 3" in low or "date-of-service totaling" in low or "date of service totaling" in low:
        mue_code = None
        cm = re.search(r"(\d{5}).{0,40}mue", text, re.I)
        if cm:
            mue_code = cm.group(1)
        rules.append(_mue_dos_rule(_grab(text, "mue"), mue_code))

    # Use high-significance changes to draft supplemental rules.
    if changes:
        for ch in changes:
            if ch.get("significance") != "high":
                continue
            new_text = ch.get("new_text") or ""
            if "prior authorization" in new_text.lower():
                cm = re.search(r"([A-Z]\d{4}|\d{5})", new_text)
                if cm and not any(cm.group(1) in r.get("title", "") for r in rules):
                    rules.append(_prior_auth_rule(cm.group(1), new_text[:180]))

    # Fallback: at least produce one informational edit so the stage is never empty.
    if not rules:
        codes = sorted(set(CODE_RE.findall(text)))[:5]
        rules.append(
            {
                "title": f"Monitor policy: {title}",
                "rationale": "No deterministic edit pattern matched; flagged for SME triage. "
                "A live LLM provider will draft richer edits.",
                "citation": _grab(text, codes[0] if codes else "policy"),
                "severity": "low",
                "confidence": 0.35,
                "edit_type": "prepay",
                "logic": {
                    "when_procedure_codes": codes,
                    "when_diagnosis_codes": [],
                    "when_modifiers": [],
                    "unless_modifiers": [],
                    "same_date_of_service": False,
                    "max_units": None,
                    "effective_date": None,
                    "action": "informational",
                    "pseudocode": "FLAG claim WHERE procedure_code IN ("
                    + ", ".join(codes) + ") FOR analyst_review",
                    "sql_preview": "SELECT * FROM claim_lines WHERE procedure_code IN ("
                    + ", ".join(f"'{c}'" for c in codes) + ");",
                },
            }
        )
    return rules


def _contract_rules(text: str) -> list[dict]:
    rules: list[dict] = []
    qm = re.search(r"quality score of\s+(\d+(?:\.\d+)?)", text, re.I)
    if qm:
        threshold = qm.group(1)
        rules.append({
            "title": f"VBP quality gate: minimum score {threshold}",
            "rationale": f"ACO must achieve quality score >= {threshold} for shared savings eligibility.",
            "citation": qm.group(0),
            "severity": "high",
            "confidence": 0.85,
            "edit_type": "postpay",
            "logic": {
                "when_procedure_codes": [],
                "when_diagnosis_codes": [],
                "when_modifiers": [],
                "unless_modifiers": [],
                "same_date_of_service": False,
                "max_units": None,
                "effective_date": None,
                "action": "informational",
                "pseudocode": f"IF quality_composite < {threshold} THEN exclude_from_shared_savings()",
                "sql_preview": f"-- Settlement: quality_score < {threshold} blocks savings",
            },
        })
    sm = re.search(r"(\d+(?:\.\d+)?)\s*%\s*below the benchmark", text, re.I)
    if sm:
        pct = sm.group(1)
        rules.append({
            "title": f"Shared savings threshold: {pct}% below benchmark",
            "rationale": f"Savings calculated only when expenditures are >= {pct}% below benchmark.",
            "citation": sm.group(0),
            "severity": "medium",
            "confidence": 0.8,
            "edit_type": "postpay",
            "logic": {
                "when_procedure_codes": [],
                "when_diagnosis_codes": [],
                "when_modifiers": [],
                "unless_modifiers": [],
                "same_date_of_service": False,
                "max_units": None,
                "effective_date": None,
                "action": "informational",
                "pseudocode": f"IF spend_reduction_pct < {pct} THEN shared_savings = 0",
                "sql_preview": f"-- Settlement: benchmark variance < {pct}%",
            },
        })
    return rules


def _guideline_rules(text: str) -> list[dict]:
    rules: list[dict] = []
    pa = re.search(
        r"([A-Z]?\d{4,5}).{0,60}?diagnosis\s+([A-Z]\d{2}(?:\.\d+)?).{0,60}?prior authorization",
        text,
        re.I | re.DOTALL,
    )
    if pa:
        rules.append({
            "title": f"Guideline-linked prior auth: {pa.group(1)} with {pa.group(2)}",
            "rationale": "Clinical guideline update ties coverage to prior authorization.",
            "citation": pa.group(0)[:180],
            "severity": "medium",
            "confidence": 0.78,
            "edit_type": "prepay",
            "logic": {
                "when_procedure_codes": [pa.group(1)],
                "when_diagnosis_codes": [pa.group(2)],
                "when_modifiers": [],
                "unless_modifiers": [],
                "same_date_of_service": False,
                "max_units": None,
                "effective_date": None,
                "action": "pend_for_review",
                "pseudocode": (
                    f"IF procedure_code == '{pa.group(1)}' AND diagnosis == '{pa.group(2)}' "
                    "AND NOT auth_on_file THEN pend_for_review()"
                ),
                "sql_preview": (
                    f"SELECT * FROM claim_lines WHERE procedure_code='{pa.group(1)}' "
                    f"AND diagnosis_code='{pa.group(2)}';"
                ),
            },
        })
    return rules


def _grab(text: str, needle: str, width: int = 180) -> str:
    idx = text.lower().find(needle.lower())
    if idx == -1:
        return text[:width].strip()
    start = max(0, idx - 20)
    return re.sub(r"\s+", " ", text[start : idx + width]).strip()


def _ptp_rule(col1: str, col2: str, required_mod, citation: str) -> dict:
    unless = [required_mod] if required_mod else ["59", "XE", "XP", "XS", "XU"]
    return {
        "title": f"PTP edit: deny {col2} billed with {col1} same DOS without distinct-service modifier",
        "rationale": f"CPT {col2} is a column-two code to {col1}. Per the policy the column-two "
        f"code is denied on the same date of service unless "
        + (f"modifier {required_mod} is appended." if required_mod else "an appropriate distinct-service modifier is appended."),
        "citation": citation,
        "severity": "high",
        "confidence": 0.88,
        "edit_type": "prepay",
        "logic": {
            "when_procedure_codes": [col1, col2],
            "when_diagnosis_codes": [],
            "when_modifiers": [],
            "unless_modifiers": unless,
            "same_date_of_service": True,
            "max_units": None,
            "effective_date": None,
            "action": "deny_line",
            "pseudocode": (
                f"IF line.procedure_code == '{col2}'\n"
                f"   AND EXISTS sibling line WITH procedure_code == '{col1}' on same DOS\n"
                f"   AND line.modifiers NOT INTERSECT {unless}\n"
                f"THEN deny_line('{col2}', reason='NCCI PTP column-two without distinct-service modifier')"
            ),
            "sql_preview": (
                f"SELECT c2.* FROM claim_lines c2 JOIN claim_lines c1 "
                f"ON c1.claim_id=c2.claim_id AND c1.dos=c2.dos\n"
                f"WHERE c2.procedure_code='{col2}' AND c1.procedure_code='{col1}'\n"
                f"  AND NOT (c2.modifiers && ARRAY{unless});"
            ),
        },
    }


def _deleted_code_rule(code: str, eff_date: str, citation: str) -> dict:
    return {
        "title": f"Reject deleted code {code} for DOS on/after {eff_date}",
        "rationale": f"Code {code} is deleted/replaced effective {eff_date}; claims with a date "
        f"of service on or after this date are invalid.",
        "citation": citation,
        "severity": "high",
        "confidence": 0.9,
        "edit_type": "prepay",
        "logic": {
            "when_procedure_codes": [code],
            "when_diagnosis_codes": [],
            "when_modifiers": [],
            "unless_modifiers": [],
            "same_date_of_service": False,
            "max_units": None,
            "effective_date": eff_date,
            "action": "deny_line",
            "pseudocode": (
                f"IF line.procedure_code == '{code}' AND line.dos >= DATE('{eff_date}')\n"
                f"THEN deny_line('{code}', reason='Deleted/terminated code')"
            ),
            "sql_preview": (
                f"SELECT * FROM claim_lines WHERE procedure_code='{code}' "
                f"AND dos >= '{eff_date}';"
            ),
        },
    }


def _prior_auth_rule(code: str, citation: str) -> dict:
    return {
        "title": f"Require prior authorization for {code}",
        "rationale": f"Policy now requires prior authorization for {code}; pend lines lacking an "
        f"approved authorization on file.",
        "citation": citation,
        "severity": "medium",
        "confidence": 0.82,
        "edit_type": "prepay",
        "logic": {
            "when_procedure_codes": [code],
            "when_diagnosis_codes": [],
            "when_modifiers": [],
            "unless_modifiers": [],
            "same_date_of_service": False,
            "max_units": None,
            "effective_date": None,
            "action": "pend_for_review",
            "pseudocode": (
                f"IF line.procedure_code == '{code}' AND NOT auth_on_file(member, '{code}', line.dos)\n"
                f"THEN pend_for_review(reason='Prior authorization required')"
            ),
            "sql_preview": (
                f"SELECT cl.* FROM claim_lines cl LEFT JOIN authorizations a "
                f"ON a.member_id=cl.member_id AND a.code=cl.procedure_code\n"
                f"WHERE cl.procedure_code='{code}' AND a.id IS NULL;"
            ),
        },
    }


def _frequency_rule(codes: list[str], max_units: int, citation: str) -> dict:
    return {
        "title": f"Frequency limit: max {max_units} definitive drug test per DOS ({', '.join(codes)})",
        "rationale": f"Policy allows a maximum of {max_units} definitive drug test per date of "
        f"service; additional same-DOS lines are not separately reimbursable.",
        "citation": citation,
        "severity": "medium",
        "confidence": 0.8,
        "edit_type": "prepay",
        "logic": {
            "when_procedure_codes": codes,
            "when_diagnosis_codes": [],
            "when_modifiers": [],
            "unless_modifiers": [],
            "same_date_of_service": True,
            "max_units": max_units,
            "effective_date": None,
            "action": "deny_line",
            "pseudocode": (
                f"count = COUNT(lines WHERE procedure_code IN {codes} AND same DOS)\n"
                f"IF count > {max_units} THEN deny_line(excess, reason='Frequency limit exceeded')"
            ),
            "sql_preview": (
                f"SELECT claim_id, dos, COUNT(*) FROM claim_lines\n"
                f"WHERE procedure_code IN ({', '.join(repr(c) for c in codes)})\n"
                f"GROUP BY claim_id, dos HAVING COUNT(*) > {max_units};"
            ),
        },
    }


def _modifier50_rule(action: str, citation: str) -> dict:
    return {
        "title": "Bilateral (modifier 50) must be billed as 1 unit on a single line",
        "rationale": "Bilateral-indicator-1 procedures reported with modifier 50 and units > 1 "
        "are invalid; correct reporting is one line, one unit, paid at 150%.",
        "citation": citation,
        "severity": "medium",
        "confidence": 0.84,
        "edit_type": "prepay",
        "logic": {
            "when_procedure_codes": [],
            "when_diagnosis_codes": [],
            "when_modifiers": ["50"],
            "unless_modifiers": [],
            "same_date_of_service": False,
            "max_units": 1,
            "effective_date": None,
            "action": action,
            "pseudocode": (
                "IF '50' IN line.modifiers AND line.units > 1\n"
                f"THEN {action}(reason='Modifier 50 requires a single unit')"
            ),
            "sql_preview": (
                "SELECT * FROM claim_lines WHERE '50' = ANY(modifiers) AND units > 1;"
            ),
        },
    }


def _mue_dos_rule(citation: str, procedure_code: str | None = None) -> dict:
    proc = [procedure_code] if procedure_code else []
    return {
        "title": "Apply MUE date-of-service totaling (MAI 3) across lines",
        "rationale": "For MAI 3 codes, sum units across all lines for the same code and DOS and "
        "deny units exceeding the MUE value.",
        "citation": citation,
        "severity": "medium",
        "confidence": 0.7,
        "edit_type": "prepay",
        "logic": {
            "when_procedure_codes": proc,
            "when_diagnosis_codes": [],
            "when_modifiers": [],
            "unless_modifiers": [],
            "same_date_of_service": True,
            "max_units": 1,
            "effective_date": None,
            "action": "adjust_units",
            "pseudocode": (
                "total = SUM(units WHERE same code AND same DOS)\n"
                "IF total > MUE_value(code) THEN adjust_units(down to MUE_value)"
            ),
            "sql_preview": (
                "SELECT claim_id, procedure_code, dos, SUM(units) AS total_units\n"
                "FROM claim_lines GROUP BY claim_id, procedure_code, dos\n"
                "HAVING SUM(units) > (SELECT mue FROM mue_table m WHERE m.code = procedure_code);"
            ),
        },
    }

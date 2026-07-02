"""Execute an approved rule's structured logic against synthetic claims.

This is a faithful, explainable interpreter for the rule archetypes the
rule_drafter produces (PTP pairs, frequency limits, bilateral units, prior
auth, deleted codes). It returns the flagged lines and an illustrative
'dollars caught' total from the mock fee schedule.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .fee_schedule import allowed_amount


def _line_dollar(line: dict[str, Any]) -> float:
    return float(line.get("billed_amount") or allowed_amount(line["procedure_code"]))


def _intersects(a: list[str], b: list[str]) -> bool:
    return bool(set(x.upper() for x in a) & set(y.upper() for y in b))


def _dos_on_or_after(dos: str, effective_date: str | None) -> bool:
    if not effective_date:
        return True
    return dos >= effective_date


def _matches_diagnosis(line: dict[str, Any], dx_codes: list[str]) -> bool:
    if not dx_codes:
        return True
    line_dx = line.get("diagnosis_code") or line.get("diagnosis_codes") or []
    if isinstance(line_dx, str):
        line_dx = [line_dx]
    return _intersects(line_dx, dx_codes)


def _line_matches_proc(line: dict[str, Any], proc: list[str]) -> bool:
    if not proc:
        return True
    return line["procedure_code"] in proc


def evaluate_rule(rule: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
    logic = rule["logic"]
    proc = [c for c in logic.get("when_procedure_codes", [])]
    dx = logic.get("when_diagnosis_codes", []) or []
    mods = logic.get("when_modifiers", []) or []
    unless = logic.get("unless_modifiers", []) or []
    max_units = logic.get("max_units")
    same_dos = bool(logic.get("same_date_of_service"))
    effective_date = logic.get("effective_date")
    action = logic.get("action", "informational")

    flagged: list[dict[str, Any]] = []
    interpretation = ""

    by_claim: dict[str, list[dict]] = defaultdict(list)
    for ln in claims:
        by_claim[ln["claim_id"]].append(ln)

    def flag(line, reason):
        flagged.append(
            {
                "claim_id": line["claim_id"],
                "line_no": line["line_no"],
                "procedure_code": line["procedure_code"],
                "modifiers": line["modifiers"],
                "units": line["units"],
                "dos": line["dos"],
                "billed_amount": line["billed_amount"],
                "reason": reason,
                "dollars": round(_line_dollar(line), 2),
            }
        )

    # ---- Archetype 1: bilateral modifier-50 units > limit ----
    if max_units is not None and mods and not proc:
        interpretation = (
            f"Flag lines with modifier {mods} and units greater than {max_units}."
        )
        for ln in claims:
            if _intersects(ln["modifiers"], mods) and ln["units"] > max_units:
                flag(ln, f"Modifier {','.join(mods)} requires {max_units} unit; billed {ln['units']}.")

    # ---- Archetype 2: frequency limit (per code per DOS) ----
    elif max_units is not None and proc and not unless and action != "adjust_units":
        interpretation = (
            f"For codes {proc}, allow {max_units} per date of service; flag excess same-DOS lines."
        )
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for ln in claims:
            if _line_matches_proc(ln, proc) and _matches_diagnosis(ln, dx):
                groups[(ln["claim_id"], ln["procedure_code"], ln["dos"])].append(ln)
        for _, lines in groups.items():
            if len(lines) > max_units:
                for ln in sorted(lines, key=lambda x: x["line_no"])[max_units:]:
                    flag(ln, f"Frequency limit exceeded ({len(lines)} > {max_units} per DOS).")

    # ---- Archetype 3: PTP code pair requiring distinct-service modifier ----
    elif same_dos and len(proc) >= 2 and unless:
        col1, col2 = proc[0], proc[1]
        interpretation = (
            f"Deny {col2} when billed with {col1} on the same DOS without a "
            f"distinct-service modifier ({', '.join(unless)})."
        )
        for lines in by_claim.values():
            by_dos: dict[str, list[dict]] = defaultdict(list)
            for ln in lines:
                by_dos[ln["dos"]].append(ln)
            for _, dos_lines in by_dos.items():
                codes = {ln["procedure_code"] for ln in dos_lines}
                if col1 in codes and col2 in codes:
                    for ln in dos_lines:
                        if (
                            ln["procedure_code"] == col2
                            and not _intersects(ln["modifiers"], unless)
                            and _dos_on_or_after(ln["dos"], effective_date)
                        ):
                            flag(ln, f"{col2} with {col1} same DOS, no {'/'.join(unless)} modifier.")

    # ---- Archetype 4: prior authorization required ----
    elif action == "pend_for_review" and proc:
        interpretation = f"Pend lines for codes {proc} lacking an authorization on file."
        for ln in claims:
            if (
                _line_matches_proc(ln, proc)
                and _matches_diagnosis(ln, dx)
                and not _has_auth_modifier(ln)
                and _dos_on_or_after(ln["dos"], effective_date)
            ):
                flag(ln, "Prior authorization required; no auth on file.")

    # ---- Archetype 5: deleted / terminated code with effective date ----
    elif action == "deny_line" and proc and not same_dos:
        interpretation = f"Deny lines billing deleted/terminated code(s) {proc}."
        for ln in claims:
            if _line_matches_proc(ln, proc) and _dos_on_or_after(ln["dos"], effective_date):
                if effective_date and ln["dos"] < effective_date:
                    continue
                flag(ln, f"Deleted/terminated code {ln['procedure_code']}.")

    # ---- Archetype 6: MUE / adjust_units same-DOS totaling ----
    elif action == "adjust_units" and same_dos and max_units is not None:
        interpretation = (
            f"Sum units per code per DOS; flag when total exceeds {max_units}."
        )
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for ln in claims:
            if (not proc or _line_matches_proc(ln, proc)) and _matches_diagnosis(ln, dx):
                groups[(ln["claim_id"], ln["procedure_code"], ln["dos"])].append(ln)
        for _, lines in groups.items():
            total = sum(ln["units"] for ln in lines)
            if total > max_units:
                running = 0
                for ln in sorted(lines, key=lambda x: x["line_no"]):
                    if running >= max_units:
                        flag(ln, f"MUE/MAI excess units (total {total} > {max_units}).")
                    running += ln["units"]

    # ---- Archetype 7: require_modifier ----
    elif action == "require_modifier" and proc and mods:
        interpretation = f"Require modifier(s) {mods} on codes {proc}."
        for ln in claims:
            if _line_matches_proc(ln, proc) and not _intersects(ln["modifiers"], mods):
                flag(ln, f"Missing required modifier {','.join(mods)}.")

    # ---- Archetype 8: require_documentation ----
    elif action == "require_documentation" and proc:
        interpretation = f"Pend lines for codes {proc} lacking documentation on file."
        for ln in claims:
            if _line_matches_proc(ln, proc) and not _has_doc_modifier(ln):
                flag(ln, "Documentation required; not on file.")

    # ---- Archetype 9: deny_claim (any matching line denies whole claim) ----
    elif action == "deny_claim" and proc:
        interpretation = f"Deny entire claim when code(s) {proc} present."
        for claim_id, lines in by_claim.items():
            if any(_line_matches_proc(ln, proc) and _matches_diagnosis(ln, dx) for ln in lines):
                for ln in lines:
                    flag(ln, f"Claim denied due to triggering code {proc}.")

    else:
        interpretation = "Informational edit — flagged for analyst review, no automated denial."

    dollars = round(sum(f["dollars"] for f in flagged), 2)
    return {
        "rule_id": rule.get("id"),
        "rule_title": rule.get("title"),
        "action": action,
        "interpretation": interpretation,
        "claims_lines_evaluated": len(claims),
        "claims_total": len(by_claim),
        "flagged_count": len(flagged),
        "dollars_caught": dollars,
        "flagged": flagged,
    }


def _has_auth_modifier(line: dict[str, Any]) -> bool:
    return "AUTH" in [m.upper() for m in line.get("modifiers", [])]


def _has_doc_modifier(line: dict[str, Any]) -> bool:
    return "DOC" in [m.upper() for m in line.get("modifiers", [])]

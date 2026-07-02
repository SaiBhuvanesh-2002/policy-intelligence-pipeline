"""Parse CMS Physician Fee Schedule (PPRRVU) files into allowed amounts.

CMS publishes fixed-width PPRRVU*.txt files inside each MPFS RVU ZIP. We parse
the national non-facility total RVU × conversion factor to derive Medicare
allowed amounts per HCPCS/CPT code.
"""
from __future__ import annotations

import re
from typing import Any

# HCPCS (5) + description + status + work/pe/mp RVUs + total non-fac RVU + CF block
_LINE_RE = re.compile(
    r"^([0-9A-Z]{5})\s+"
    r".{10,}?"
    r"([A-Z])\s+"
    r"([\d.]+)\s+"
    r"([\d.]+)\s+"
    r"([\d.]+)\s+"
    r"([\d.]+)\s+"
    r"([\d.]+)\s+"
    r"([\d.]+)"
)
_CF_RE = re.compile(r"(\d{2}\.\d{4})\s+090")


def is_mpfs_filename(filename: str) -> bool:
    name = (filename or "").upper()
    return "PPRRVU" in name and name.endswith((".TXT", ".CSV", ".TEXT"))


def is_cms_data_not_policy(filename: str) -> bool:
    """True for CMS machine-readable files that should not enter the policy pipeline."""
    name = (filename or "").upper()
    if is_mpfs_filename(filename):
        return True
    if "GPCI" in name:
        return True
    if name.startswith("HCPC") and name.endswith(".TXT"):
        return True
    if "RECORDLAYOUT" in name or "RECORD_LAYOUT" in name:
        return True
    return False


def cms_data_upload_hint(filename: str) -> str:
    name = (filename or "").upper()
    if "GPCI" in name:
        return (
            "GPCI files set geographic pricing adjustments. This app uses national MPFS "
            "amounts from PPRRVU*.txt for the Impact tab. GPCI upload is not required."
        )
    if name.startswith("HCPC"):
        return (
            "HCPCS alpha-numeric files list codes and descriptors, not policy language. "
            "Upload the NCCI Policy Manual (PDF) for rule drafting, or PPRRVU*.txt for pricing."
        )
    return "Unrecognized CMS data file."


def parse_pprrvu_text(text: str) -> dict[str, Any]:
    """Return {codes: {code: amount}, conversion_factor, rows_parsed, source_label}."""
    codes: dict[str, float] = {}
    conversion_factor: float | None = None
    rows_parsed = 0

    for line in text.splitlines():
        if line.startswith("HDR") or not line.strip():
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        code = m.group(1)
        total_rvu = float(m.group(7))
        if total_rvu <= 0:
            continue
        cf_match = _CF_RE.search(line)
        cf = float(cf_match.group(1)) if cf_match else conversion_factor
        if cf is None:
            continue
        if conversion_factor is None:
            conversion_factor = cf
        amount = round(total_rvu * cf, 2)
        # Keep the highest allowed amount when duplicate base codes appear.
        codes[code] = max(codes.get(code, 0.0), amount)
        rows_parsed += 1

    return {
        "codes": codes,
        "conversion_factor": conversion_factor,
        "rows_parsed": rows_parsed,
    }


def import_pprrvu_text(
    conn,
    text: str,
    *,
    source_label: str,
    actor: str = "mpfs:loader",
) -> dict[str, Any]:
    from .. import db

    parsed = parse_pprrvu_text(text)
    if not parsed["codes"]:
        raise ValueError(
            "No procedure codes found — is this a CMS PPRRVU relative value file?"
        )

    db.replace_fee_schedule(
        conn,
        parsed["codes"],
        source_label=source_label,
        conversion_factor=parsed["conversion_factor"],
    )
    db.log_audit(
        conn,
        actor,
        "fee_schedule_imported",
        f"{len(parsed['codes'])} code(s) from {source_label} "
        f"(CF={parsed['conversion_factor']})",
    )
    conn.commit()
    return {
        "source": source_label,
        "codes_loaded": len(parsed["codes"]),
        "conversion_factor": parsed["conversion_factor"],
        "rows_parsed": parsed["rows_parsed"],
        "sample": dict(list(parsed["codes"].items())[:5]),
    }

"""Classify uploaded files and normalize metadata for version-aware ingestion."""
from __future__ import annotations

import re
from typing import Any

_CMS_DATA_MARKERS = (
    "PPRRVU",
    "GPCI",
    "HCPC",
    "RECORDLAYOUT",
    "RECORD_LAYOUT",
    "PROC_NOTES",
    "RVU",
)

_NCCI_RE = re.compile(r"ncci", re.I)
_MANUAL_RE = re.compile(r"manual|policy", re.I)
_YEAR_RE = re.compile(r"(20\d{2})")


def is_cms_data_document(title: str) -> bool:
    upper = (title or "").upper()
    return any(marker in upper for marker in _CMS_DATA_MARKERS)


def document_kind(title: str, source_name: str) -> str:
    if is_cms_data_document(title):
        return "cms_data"
    if (source_name or "").strip() in {
        "CMS NCCI Policy Manual",
        "CMS HCPCS Quarterly Update",
        "Regional Health Plan",
        "Medicare Administrative Contractor",
        "ACC/AHA Clinical Practice Guideline",
        "Regional ACO — VBP Agreement",
    }:
        return "seed"
    return "policy"


def normalize_policy_upload(filename: str, text: str) -> dict[str, Any] | None:
    """Map common CMS policy uploads onto stable document identity + version labels."""
    name = filename or ""
    low = name.lower()

    if _NCCI_RE.search(name) and _MANUAL_RE.search(name):
        year = _YEAR_RE.search(name)
        y = year.group(1) if year else None
        return {
            "source_type": "cms_bulletin",
            "source_name": "CMS NCCI Policy Manual",
            "title": "Medicare NCCI Policy Manual",
            "version_label": f"v{y}" if y else "uploaded",
            "effective_date": f"{y}-01-01" if y else None,
        }

    if "hcpcs" in low and ("update" in low or "alpha" in low or "anweb" in low):
        year = _YEAR_RE.search(name)
        quarter = re.search(r"(jan|apr|jul|oct)", low)
        q = (quarter.group(1)[:3].title() if quarter else "Q")
        y = year.group(1) if year else "20xx"
        return {
            "source_type": "code_set",
            "source_name": "CMS HCPCS Quarterly Update",
            "title": "HCPCS Level II Code Additions, Deletions, and Revisions",
            "version_label": f"{y} {q}",
            "effective_date": None,
        }

    if low.endswith(".pdf") and len(text) > 500:
        # Generic policy PDF — group by filename stem so re-uploads become versions.
        stem = re.sub(r"[^a-z0-9]+", " ", low.rsplit(".", 1)[0]).strip().title()
        year = _YEAR_RE.search(name)
        if any(w in low for w in ("guideline", "cpg", "clinical-practice")):
            return {
                "source_type": "clinical_guideline",
                "source_name": "Uploaded clinical guideline",
                "title": stem[:120] or "Clinical practice guideline",
                "version_label": year.group(1) if year else "uploaded",
                "effective_date": f"{year.group(1)}-01-01" if year else None,
            }
        if any(w in low for w in ("contract", "msa", "vbp", "shared-savings", "aco")):
            return {
                "source_type": "contract",
                "source_name": "Uploaded payer-provider contract",
                "title": stem[:120] or "Payer-provider contract",
                "version_label": year.group(1) if year else "uploaded",
                "effective_date": f"{year.group(1)}-01-01" if year else None,
            }
        if any(w in low for w in ("medical-policy", "medical_policy", "coverage")):
            return {
                "source_type": "payer_policy",
                "source_name": "Uploaded payer policy",
                "title": stem[:120] or "Payer medical policy",
                "version_label": year.group(1) if year else "uploaded",
                "effective_date": f"{year.group(1)}-01-01" if year else None,
            }
        return {
            "source_type": "cms_bulletin",
            "source_name": "Uploaded policy",
            "title": stem[:120] or "Uploaded policy document",
            "version_label": year.group(1) if year else "uploaded",
            "effective_date": f"{year.group(1)}-01-01" if year else None,
        }

    return None

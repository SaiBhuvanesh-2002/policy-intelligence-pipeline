"""Synthetic policy generator.

Produces a realistic-looking policy document in TWO versions (v1 and a mutated
v2) so the change-detection and rule-drafting stages have a guaranteed delta to
operate on. Output is clearly synthetic and is labeled as MOCK in the UI.
"""
from __future__ import annotations

import random

# Archetypes, each with a v1 and a v2 that introduces a detectable, high-value
# change (modifier tightening, new PTP edit, prior-auth, frequency, deletion).
_ARCHETYPES = [
    {
        "source_type": "cms_bulletin",
        "source_name": "MOCK MAC Bulletin",
        "title": "Correct Coding: Lesion Destruction PTP Edit ({c1}/{c2})",
        "v1": (
            "SECTION A. PTP EDIT {c1}/{c2}\n"
            "CPT {c2} is a column-two code to {c1}. When billed on the same date of "
            "service, the column-two code is denied unless an appropriate modifier is "
            "appended."
        ),
        "v2": (
            "SECTION A. PTP EDIT {c1}/{c2}\n"
            "CPT {c2} is a column-two code to {c1}. When billed on the same date of "
            "service, the column-two code is denied unless modifier {mod} is appended; "
            "modifier 59 alone is no longer sufficient to bypass this edit."
        ),
        "codes": [("17000", "11102"), ("11720", "11055"), ("36415", "36416")],
        "mods": ["XS", "XU", "XE"],
    },
    {
        "source_type": "payer_policy",
        "source_name": "MOCK Regional Health Plan",
        "title": "Medical Policy: {svc} Frequency and Authorization",
        "v1": (
            "POLICY {pol}\nCOVERAGE:\nCode {c1} is covered when medically necessary.\n"
            "FREQUENCY LIMITATIONS:\nA maximum of one (1) {svc} per date of service is "
            "considered medically necessary."
        ),
        "v2": (
            "POLICY {pol}\nCOVERAGE:\nCode {c1} is covered when medically necessary. "
            "Code {c1} now requires prior authorization.\n"
            "FREQUENCY LIMITATIONS:\nA maximum of one (1) {svc} per date of service is "
            "considered medically necessary; additional same-day units are denied."
        ),
        "codes": [("G0480",), ("G0483",), ("80307",)],
        "svcs": ["definitive drug test", "specialized panel", "molecular assay"],
    },
    {
        "source_type": "code_set",
        "source_name": "MOCK HCPCS Update",
        "title": "Code-Set Update: Quarterly Additions and Deletions",
        "v1": (
            "QUARTERLY UPDATE\nACTIVE CODES:\n{c1} — Active service code\n"
            "{c2} — Active service code\nDELETED CODES:\n(none this quarter)"
        ),
        "v2": (
            "QUARTERLY UPDATE\nACTIVE CODES:\n{c2} — Active service code\n"
            "DELETED CODES:\n{c1} — deleted/replaced; claims with date of service on or "
            "after {date} will be rejected"
        ),
        "codes": [("G0463", "G0511"), ("J1304", "J9999"), ("Q5142", "J0178")],
        "dates": ["2026-01-01", "2026-04-01", "2026-07-01"],
    },
    {
        "source_type": "contract",
        "source_name": "MOCK ACO — VBP Agreement",
        "title": "VBP Contract: Quality Gate {score}% / Savings {pct}%",
        "v1": (
            "QUALITY PERFORMANCE:\n"
            "Minimum quality score of {score} required for shared savings eligibility.\n"
            "SHARED SAVINGS:\n"
            "Savings threshold: {pct}% below benchmark."
        ),
        "v2": (
            "QUALITY PERFORMANCE:\n"
            "Minimum quality score of {score2} required for shared savings eligibility "
            "(raised from {score}).\n"
            "SHARED SAVINGS:\n"
            "Savings threshold: {pct2}% below benchmark (previously {pct}%)."
        ),
        "scores": [(80, 85), (75, 82), (88, 90)],
        "pcts": [(2.0, 2.5), (3.0, 3.5)],
    },
    {
        "source_type": "clinical_guideline",
        "source_name": "MOCK Clinical Guideline Panel",
        "title": "Guideline: {condition} — Statin Therapy",
        "v1": (
            "RECOMMENDATION (Class I):\n"
            "Moderate-intensity statin for adults with {condition}.\n"
            "COVERAGE: Code {c1} covered with diagnosis {dx}."
        ),
        "v2": (
            "RECOMMENDATION (Class I):\n"
            "Moderate-intensity statin for adults with {condition}.\n"
            "NEW: Code {c1} with diagnosis {dx} now requires prior authorization "
            "unless LDL-C >= 190 mg/dL documented."
        ),
        "conditions": ["diabetes", "ASCVD", "familial hypercholesterolemia"],
        "codes": [("80061", "E11.9"), ("80061", "E78.5"), ("83721", "E78.0")],
    },
]


def generate_mock_policy(seed: int | None = None) -> dict:
    rng = random.Random(seed)
    arc = rng.choice(_ARCHETYPES)
    fields: dict = {}

    codes = rng.choice(arc["codes"])
    fields["c1"] = codes[0]
    fields["c2"] = codes[1] if len(codes) > 1 else codes[0]
    if "mods" in arc:
        fields["mod"] = rng.choice(arc["mods"])
    if "svcs" in arc:
        fields["svc"] = rng.choice(arc["svcs"])
        fields["pol"] = f"LAB-{rng.randint(10, 99)}"
    if "dates" in arc:
        fields["date"] = rng.choice(arc["dates"])
    if "scores" in arc:
        s1, s2 = rng.choice(arc["scores"])
        fields["score"], fields["score2"] = s1, s2
        p1, p2 = rng.choice(arc["pcts"])
        fields["pct"], fields["pct2"] = p1, p2
    if "conditions" in arc:
        fields["condition"] = rng.choice(arc["conditions"])
        c, dx = rng.choice(arc["codes"])
        fields["c1"], fields["dx"] = c, dx

    title = arc["title"].format(**fields)
    v1 = arc["v1"].format(**fields)
    v2 = arc["v2"].format(**fields)

    return {
        "source_type": arc["source_type"],
        "source_name": arc["source_name"],
        "title": title,
        "versions": [
            {"version_label": "v1 (MOCK)", "effective_date": "2025-01-01", "raw_text": v1},
            {"version_label": "v2 (MOCK)", "effective_date": "2026-01-01", "raw_text": v2},
        ],
    }

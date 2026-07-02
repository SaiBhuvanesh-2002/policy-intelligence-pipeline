"""Representative, real-structure policy corpus shipped with the demo.

These documents mirror the structure and language of genuine public sources
(CMS NCCI Policy Manual, HCPCS quarterly updates, MACs, and commercial payer
medical policies). Each entry ships TWO versions so the change-detection and
rule-drafting stages have real version deltas to operate on offline.

When PIP_ALLOW_NETWORK_FETCH=true, the fetcher can additionally pull live
public documents; this corpus guarantees the demo always works.
"""
from __future__ import annotations

SEED_CORPUS: list[dict] = [
    # ------------------------------------------------------------------ #
    # 1. CMS NCCI Policy Manual — modifier 59 / X{EPSU} distinct service  #
    # ------------------------------------------------------------------ #
    {
        "source_type": "cms_bulletin",
        "source_name": "CMS NCCI Policy Manual",
        "title": "Chapter I — General Correct Coding Policies: Modifier 59 and X{EPSU}",
        "url": "https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits",
        "versions": [
            {
                "version_label": "v2024",
                "effective_date": "2024-01-01",
                "raw_text": (
                    "SECTION D. MODIFIER 59 AND SUBSET MODIFIERS\n"
                    "Modifier 59 is used to identify procedures/services, other than E/M "
                    "services, that are not normally reported together but are appropriate "
                    "under the circumstances. Documentation must support a different session, "
                    "different procedure, different site, or separate injury.\n\n"
                    "When a column-two code of a PTP edit is eligible for a modifier and the "
                    "clinical circumstances justify a distinct procedural service, modifier 59 "
                    "may be appended to bypass the edit.\n\n"
                    "SECTION E. UNITS OF SERVICE\n"
                    "Providers should report the appropriate number of units consistent with "
                    "the Medically Unlikely Edit (MUE) value assigned to each HCPCS/CPT code. "
                    "Claims exceeding the MUE value on a single line are denied.\n\n"
                    "SECTION F. PTP EDIT 11055/11720\n"
                    "CPT 11055 (paring of corn/callus) is a column-two code to 11720 "
                    "(debridement of nails). When billed on the same date of service, the "
                    "column-two code is denied unless an appropriate modifier is appended."
                ),
            },
            {
                "version_label": "v2025",
                "effective_date": "2025-01-01",
                "raw_text": (
                    "SECTION D. MODIFIER 59 AND SUBSET MODIFIERS\n"
                    "Modifier 59 is used to identify procedures/services, other than E/M "
                    "services, that are not normally reported together but are appropriate "
                    "under the circumstances. Documentation must support a different session, "
                    "different procedure, different site, or separate injury.\n\n"
                    "CMS strongly encourages providers to use the more specific X{EPSU} "
                    "modifiers (XE, XP, XS, XU) in lieu of modifier 59 whenever a subset "
                    "modifier accurately describes the distinct service. Effective this "
                    "edition, claims appending modifier 59 where a subset modifier is clearly "
                    "applicable may be subject to prepayment review.\n\n"
                    "SECTION E. UNITS OF SERVICE\n"
                    "Providers should report the appropriate number of units consistent with "
                    "the Medically Unlikely Edit (MUE) value assigned to each HCPCS/CPT code. "
                    "Claims exceeding the MUE value on a single line are denied. Line-level "
                    "MUE adjudication (MAI 3) now applies date-of-service totaling across "
                    "multiple lines for designated codes.\n\n"
                    "SECTION F. PTP EDIT 11055/11720\n"
                    "CPT 11055 (paring of corn/callus) is a column-two code to 11720 "
                    "(debridement of nails). When billed on the same date of service, the "
                    "column-two code is denied unless modifier XS (separate structure) is "
                    "appended; modifier 59 alone is no longer sufficient to bypass this edit."
                ),
            },
        ],
    },
    # ------------------------------------------------------------------ #
    # 2. HCPCS quarterly code-set update                                  #
    # ------------------------------------------------------------------ #
    {
        "source_type": "code_set",
        "source_name": "CMS HCPCS Quarterly Update",
        "title": "HCPCS Level II Code Additions, Deletions, and Revisions",
        "url": "https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system/quarterly-update",
        "versions": [
            {
                "version_label": "2025 Q1",
                "effective_date": "2025-01-01",
                "raw_text": (
                    "HCPCS LEVEL II QUARTERLY UPDATE — EFFECTIVE 2025-01-01\n\n"
                    "ADDED CODES:\n"
                    "J1304 — Injection, sutimlimab-jome, 10 mg\n"
                    "A2025 — Skin substitute graft, per square centimeter\n\n"
                    "ACTIVE CODES (no change):\n"
                    "J0178 — Injection, aflibercept, 1 mg\n"
                    "G0463 — Hospital outpatient clinic visit\n\n"
                    "DELETED CODES:\n"
                    "(none this quarter)\n"
                ),
            },
            {
                "version_label": "2025 Q2",
                "effective_date": "2025-04-01",
                "raw_text": (
                    "HCPCS LEVEL II QUARTERLY UPDATE — EFFECTIVE 2025-04-01\n\n"
                    "ADDED CODES:\n"
                    "J1304 — Injection, sutimlimab-jome, 10 mg\n"
                    "A2025 — Skin substitute graft, per square centimeter\n"
                    "J9999 — Antineoplastic drug, not otherwise classified\n"
                    "Q5142 — Injection, biosimilar, per 10 mg\n\n"
                    "ACTIVE CODES (no change):\n"
                    "J0178 — Injection, aflibercept, 1 mg\n\n"
                    "DELETED CODES:\n"
                    "G0463 — Hospital outpatient clinic visit (replaced by facility-specific "
                    "reporting; claims with date of service on or after 2025-04-01 will be "
                    "rejected)\n"
                ),
            },
        ],
    },
    # ------------------------------------------------------------------ #
    # 3. Commercial payer medical policy — definitive drug testing       #
    # ------------------------------------------------------------------ #
    {
        "source_type": "payer_policy",
        "source_name": "Regional Health Plan",
        "title": "Medical Policy: Definitive Drug Testing (Urine)",
        "url": None,
        "versions": [
            {
                "version_label": "Rev 3.0",
                "effective_date": "2024-06-01",
                "raw_text": (
                    "MEDICAL POLICY: DEFINITIVE DRUG TESTING\n"
                    "POLICY NUMBER: LAB-014  REVISION: 3.0\n\n"
                    "COVERAGE:\n"
                    "Definitive (quantitative) drug testing is covered when ordered by the "
                    "treating provider for medical necessity. Codes G0480-G0483 are "
                    "differentiated by the number of drug classes tested.\n\n"
                    "FREQUENCY LIMITATIONS:\n"
                    "A maximum of one (1) definitive drug test per date of service is "
                    "considered medically necessary. Presumptive testing (80305-80307) on the "
                    "same date is included and not separately reimbursed.\n\n"
                    "DOCUMENTATION:\n"
                    "The medical record must document the clinical indication and the specific "
                    "drugs or drug classes being monitored."
                ),
            },
            {
                "version_label": "Rev 4.0",
                "effective_date": "2025-07-01",
                "raw_text": (
                    "MEDICAL POLICY: DEFINITIVE DRUG TESTING\n"
                    "POLICY NUMBER: LAB-014  REVISION: 4.0\n\n"
                    "COVERAGE:\n"
                    "Definitive (quantitative) drug testing is covered when ordered by the "
                    "treating provider for medical necessity. Codes G0480-G0483 are "
                    "differentiated by the number of drug classes tested. Code G0483 (22 or "
                    "more drug classes) now requires prior authorization.\n\n"
                    "FREQUENCY LIMITATIONS:\n"
                    "A maximum of one (1) definitive drug test per date of service is "
                    "considered medically necessary. For members in active substance use "
                    "disorder treatment, up to twelve (12) definitive tests per rolling "
                    "twelve-month period are allowed without additional review; tests beyond "
                    "this threshold are pended for medical review. Presumptive testing "
                    "(80305-80307) on the same date is included and not separately reimbursed.\n\n"
                    "DOCUMENTATION:\n"
                    "The medical record must document the clinical indication, the specific "
                    "drugs or drug classes being monitored, and the treatment plan justifying "
                    "the testing frequency."
                ),
            },
        ],
    },
    # ------------------------------------------------------------------ #
    # 4. MAC bulletin — bilateral procedures / modifier 50               #
    # ------------------------------------------------------------------ #
    {
        "source_type": "cms_bulletin",
        "source_name": "Medicare Administrative Contractor",
        "title": "Bulletin: Bilateral Procedures and Modifier 50 Reporting",
        "url": "https://www.cms.gov/medicare/payment/fee-schedules/physician",
        "versions": [
            {
                "version_label": "2024-11",
                "effective_date": "2024-11-01",
                "raw_text": (
                    "PROVIDER BULLETIN — BILATERAL PROCEDURES\n\n"
                    "When a procedure with a bilateral surgery indicator of '1' on the "
                    "Medicare Physician Fee Schedule (MPFS) is performed bilaterally, report "
                    "the procedure on a single line with modifier 50 and one (1) unit of "
                    "service. Payment is 150 percent of the fee schedule amount.\n\n"
                    "Procedures reported with modifier 50 and a unit count greater than one "
                    "(1) will be returned to the provider for correction.\n\n"
                    "Modifiers LT and RT should not be used in combination with modifier 50 "
                    "on the same line."
                ),
            },
            {
                "version_label": "2025-05",
                "effective_date": "2025-05-01",
                "raw_text": (
                    "PROVIDER BULLETIN — BILATERAL PROCEDURES\n\n"
                    "When a procedure with a bilateral surgery indicator of '1' on the "
                    "Medicare Physician Fee Schedule (MPFS) is performed bilaterally, report "
                    "the procedure on a single line with modifier 50 and one (1) unit of "
                    "service. Payment is 150 percent of the fee schedule amount.\n\n"
                    "Procedures reported with modifier 50 and a unit count greater than one "
                    "(1) will be denied (previously: returned for correction). Resubmission "
                    "with corrected units is required.\n\n"
                    "Modifiers LT and RT should not be used in combination with modifier 50 "
                    "on the same line. Effective this bulletin, claims billing both LT and RT "
                    "on separate lines for a bilateral-indicator-1 procedure will be combined "
                    "and repriced as a single modifier-50 service."
                ),
            },
        ],
    },
    # ------------------------------------------------------------------ #
    # 5. Clinical practice guideline — lipid management (coverage-linked) #
    # ------------------------------------------------------------------ #
    {
        "source_type": "clinical_guideline",
        "source_name": "ACC/AHA Clinical Practice Guideline",
        "title": "Guideline on the Management of Blood Cholesterol",
        "url": None,
        "versions": [
            {
                "version_label": "2018",
                "effective_date": "2018-11-10",
                "raw_text": (
                    "CLINICAL PRACTICE GUIDELINE — BLOOD CHOLESTEROL\n"
                    "RECOMMENDATION (Class I, Level A):\n"
                    "In patients 40-75 years with diabetes and LDL-C 70-189 mg/dL, "
                    "moderate-intensity statin therapy is recommended.\n\n"
                    "COVERAGE LINKAGE:\n"
                    "Plans may require documented ASCVD risk score before covering "
                    "high-intensity statin therapy (CPT 80061 panel with diagnosis E11.9).\n\n"
                    "DOCUMENTATION:\n"
                    "Medical record must document risk assessment and shared decision-making."
                ),
            },
            {
                "version_label": "2022",
                "effective_date": "2022-08-01",
                "raw_text": (
                    "CLINICAL PRACTICE GUIDELINE — BLOOD CHOLESTEROL (UPDATE)\n"
                    "RECOMMENDATION (Class I, Level A):\n"
                    "In patients 40-75 years with diabetes and LDL-C 70-189 mg/dL, "
                    "moderate-intensity statin therapy is recommended.\n\n"
                    "NEW RECOMMENDATION (Class IIa, Level B-R):\n"
                    "For adults with LDL-C 190 mg/dL or greater, high-intensity statin "
                    "therapy is recommended without requiring prior ASCVD risk calculation.\n\n"
                    "COVERAGE LINKAGE:\n"
                    "Plans may require documented ASCVD risk score before covering "
                    "high-intensity statin therapy unless LDL-C >= 190 mg/dL. "
                    "Code 80061 with diagnosis E78.5 now requires prior authorization "
                    "when billed without documented LDL-C >= 190.\n\n"
                    "DOCUMENTATION:\n"
                    "Medical record must document risk assessment, LDL-C value, and "
                    "shared decision-making."
                ),
            },
        ],
    },
    # ------------------------------------------------------------------ #
    # 6. Payer-provider VBP contract — shared savings / quality gate     #
    # ------------------------------------------------------------------ #
    {
        "source_type": "contract",
        "source_name": "Regional ACO — VBP Agreement",
        "title": "Medicare Shared Savings Program — ACO Participation Agreement",
        "url": None,
        "versions": [
            {
                "version_label": "CY2024",
                "effective_date": "2024-01-01",
                "raw_text": (
                    "ACO PARTICIPATION AGREEMENT — PERFORMANCE YEAR 2024\n\n"
                    "QUALITY PERFORMANCE:\n"
                    "The ACO must achieve a minimum quality score of 80.0 on the "
                    "CMS quality composite to be eligible for shared savings.\n\n"
                    "SHARED SAVINGS:\n"
                    "If actual expenditures are at least 2.0% below the benchmark "
                    "and quality threshold is met, the ACO earns 50% of generated savings.\n\n"
                    "SETTLEMENT:\n"
                    "Quarterly interim settlements are trued up in Q1 of the following "
                    "performance year."
                ),
            },
            {
                "version_label": "CY2025",
                "effective_date": "2025-01-01",
                "raw_text": (
                    "ACO PARTICIPATION AGREEMENT — PERFORMANCE YEAR 2025\n\n"
                    "QUALITY PERFORMANCE:\n"
                    "The ACO must achieve a minimum quality score of 85.0 on the "
                    "CMS quality composite to be eligible for shared savings (raised from 80.0).\n\n"
                    "SHARED SAVINGS:\n"
                    "If actual expenditures are at least 2.5% below the benchmark "
                    "and quality threshold is met, the ACO earns 55% of generated savings.\n\n"
                    "SETTLEMENT:\n"
                    "Quarterly interim settlements are trued up in Q1 of the following "
                    "performance year. Claims with quality measure gaps flagged in the "
                    "final quarter are excluded from savings calculation until remediated."
                ),
            },
        ],
    },
]

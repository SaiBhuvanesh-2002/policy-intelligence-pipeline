# Hackathon Proof of Concept — Policy Intelligence Pipeline

**Companion to:** `docs/WRITTEN_REPORT.md`  
**Project:** Cotiviti Policy Intelligence Pipeline  
**Date:** June 30, 2026

---

## What Was Built

The Policy Intelligence Pipeline is an agentic web application that converts written healthcare policy into structured payment-integrity edits with mandatory human SME sign-off before simulation or export. It implements a **four-stage pipeline** orchestrated in `app/pipeline.py`:

| Stage | Agent | Output |
|-------|-------|--------|
| 1. Ingest & summarize | `summarizer` | Plain-language summary + extracted codes, modifiers, limits, dates |
| 2. Detect changes | `change_detector` | Version-to-version diff, ranked by dollar/compliance impact |
| 3. Draft executable edits | `rule_drafter` | Structured claim edits with pseudocode, SQL previews, citations |
| 4. Human sign-off | Router + review UI | Every draft queued as `pending`; simulation and export require approval |

**Tech stack:** Python 3, FastAPI, SQLite persistence, vanilla JS + Tailwind frontend, optional LLM providers (Anthropic, OpenAI, Groq) with a deterministic offline engine for zero-API-key demos. CMS Physician Fee Schedule pricing via PPRRVU import; synthetic claims for impact simulation; JSON/YAML export adapter (Edifecs bridge stub).

## Mapping to the Report Topic

The proof of concept operationalizes the written report’s central thesis: **industrializing policy-to-rules** for payment integrity. It addresses Section 3 content-management dimensions—billing/coding policies, partial clinical guideline and contract coverage, summarization, change comparison, and conversion to executable rules—while enforcing human-in-the-loop governance and prepay “dollars caught” narrative via MPFS-backed simulation.

## Main Functions Demonstrated

- **Ingest:** Paste, upload PDF/DOCX/TXT, or load shipped seed corpus (NCCI, MAC bulletins, payer medical policy, ACC/AHA-style guideline, VBP contract).
- **Diff:** Automatic change detection when a new document version is ingested (e.g., NCCI v2024 → v2025).
- **Draft:** Rule drafter emits structured `RuleLogic` JSON with payment-integrity actions (deny, require modifier, cap units, etc.).
- **SME review:** Review queue UI and API; approve, reject, or request changes; full audit trail of agent and human actions.
- **Impact simulation:** Synthetic claims evaluated against approved rules; Medicare dollars caught using imported CMS MPFS rates.

## Honest Scope Limits (Demo vs. Production)

| Capability | Demo status |
|------------|-------------|
| Four-stage pipeline + audit trail | Working |
| SME gate before simulate/export | Enforced |
| Edifecs / production rules-engine push | Export stub only |
| Live CMS URL fetch | Gated; not wired to ingest API |
| NCCI PTP table import | Not implemented |
| Real EDI 837 claims | Synthetic claims only |
| Authentication / SME roles | Not implemented |
| VBP settlement engine | Seed + patterns; Phase 2 extension |
| Clinical decision-making | Explicitly out of scope |

Overall Section 3 compliance in demo scope: **~65%** (see `docs/SECTION3_COMPLIANCE.md`).

## How to Run

```bash
# Start the application (creates venv, installs deps, serves on :8000)
./run.sh
```

Open http://127.0.0.1:8000

```bash
# One-command demo prep for assessment/interview
./prepare_demo.sh           # refresh claims + impact simulation (keeps uploads)
./prepare_demo.sh --reset   # clean seed corpus + MPFS + claims + simulation
```

Optional: set `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GROQ_API_KEY` in `.env` for live LLM agents; otherwise the offline deterministic engine runs fully reproducible demos with no API keys.

**Suggested 6-minute demo flow:** Dashboard → Policies & Changes (NCCI diff) → optional live PDF ingest → SME Review (approve one edit) → Impact / Dollars Caught → Audit Trail.

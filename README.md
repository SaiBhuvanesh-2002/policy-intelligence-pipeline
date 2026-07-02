# Policy Intelligence Pipeline

An agentic system that turns written healthcare policy into **structured payment-integrity
edits** — with a human subject-matter expert (SME) in the loop before simulation or export.

Built as a working demo of the recommended solution for Cotiviti: industrializing the
company's founding competency — *converting written policy into executable rules* — and
shifting captured dollars from post-pay recovery toward cheaper, less abrasive **prepay accuracy**.

## What it does (the four-stage pipeline)

| Stage | Agent | Output |
|------|-------|--------|
| 1. Ingest & summarize | `summarizer` | Plain-language summary + extracted codes / modifiers / limits / dates |
| 2. Detect changes | `change_detector` | Version-to-version diff, ranked by dollar / compliance impact |
| 3. Draft executable edits | `rule_drafter` | Structured claim edits with pseudocode + SQL previews + citations |
| 4. Human sign-off | router + review UI | Every draft routed to an SME; simulation and export require approval |

A full **audit trail** records every agent action and every human decision — the compliance
backbone of the human-in-the-loop design.

## Quick start

```bash
./run.sh
```

Then open http://127.0.0.1:8000

### One-command demo prep (assessment / interview)

```bash
./prepare_demo.sh           # refresh claims + impact simulation (keeps uploads)
./prepare_demo.sh --reset   # clean seed corpus + MPFS + claims + simulation
```

Or click **Prepare demo** in the UI header / Dashboard checklist.

## Assessment demo (6 minutes)

**Before the call:** run `./prepare_demo.sh`, confirm Dashboard shows **Demo ready** (green).

| Step | Tab | What to show |
|------|-----|--------------|
| 1 | Dashboard | Four-stage pipeline + demo readiness checklist |
| 2 | Policies & Changes | NCCI version diff (v2024 → v2025) |
| 3 | Ingest | Live-upload a CMS NCCI PDF (optional) |
| 4 | SME Review Queue | Approve one high-severity edit live |
| 5 | Impact / Dollars Caught | Medicare $ caught with CMS MPFS pricing |
| 6 | Audit Trail | Agent + SME decision log |

**Files to have ready** (download from cms.gov):

- NCCI Policy Manual PDF → policy ingest
- `PPRRVU*.txt` from [CMS MPFS](https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files) → Medicare pricing

**Do not upload** `GPCI*.txt` or `HCPC*.txt` as policy — they are data files, not policy text.

## Runs with zero API keys

The agents default to a **deterministic offline engine**, so the demo is fully runnable
and reproducible out of the box. To turn the agents **LIVE**, paste one API key into
`.env` and restart — the engine **auto-detects** whichever key is present (Anthropic,
OpenAI, or Groq):

```bash
ANTHROPIC_API_KEY=sk-ant-...     # or: OPENAI_API_KEY=...  or: GROQ_API_KEY=...
```

On startup the UI header shows **Agents: LIVE · &lt;provider&gt;** (green) or **OFFLINE** (grey).

## Architecture

```
app/
  config.py            settings (.env)
  db.py                SQLite persistence + audit log
  schemas.py           domain model (documents, versions, changes, rules)
  pipeline.py          orchestrates the 4 stages
  demo.py              one-click demo preparation
  agents/
    llm.py             provider abstraction (Anthropic / OpenAI / offline)
    summarizer.py      stage 1
    change_detector.py stage 2
    rule_drafter.py    stage 3 (policy text -> executable edits)
  claims/
    generator.py       synthetic claims seeded per rule
    evaluator.py       runs RuleLogic against claims
    mpfs_loader.py     CMS PPRRVU fee schedule import
    simulation.py      persisted impact simulation
  ingestion/
    fetcher.py         live public-source fetcher (gated by env flag)
    seed_data.py       shipped versioned corpus
  export/
    rule_export.py     JSON/YAML export adapter (Edifecs bridge stub)
  main.py              FastAPI API + serves the UI
frontend/              single-page UI (Tailwind CDN + vanilla JS)
```

## Key API endpoints

- `POST /api/ingest` — run the full pipeline on new policy text
- `POST /api/upload` — upload PDF/DOCX/TXT (policy) or PPRRVU*.txt (CMS pricing)
- `POST /api/mock/policy` — generate a synthetic policy (v1 + mutated v2)
- `GET  /api/documents` / `GET /api/documents/{id}` — policies, versions, changes, edits
- `GET  /api/rules?status=pending` — SME review queue (monitor-only junk rules hidden)
- `POST /api/rules/{id}/review` — SME decision (approve / reject / request changes)
- `GET  /api/rules/{id}/export` — export approved rule as JSON or YAML (Edifecs bridge stub)
- `POST /api/claims/generate` — generate synthetic, scenario-seeded claims
- `GET  /api/impact` — impact dashboard with persisted simulation results
- `POST /api/impact/simulate-all` — simulate all approved edits
- `POST /api/fee-schedule/import` — reload CMS MPFS from ingested PPRRVU file
- `GET  /api/demo/status` — demo readiness checklist
- `POST /api/demo/prepare` — one-click demo preparation
- `GET  /api/audit` — full audit trail
- `GET  /api/stats` — dashboard metrics

## Data inputs

- **Policy text:** paste, upload PDF/DOCX, or use the shipped seed corpus
- **CMS pricing:** upload `PPRRVU*.txt` — loads Medicare Physician Fee Schedule rates
- **Impact:** synthetic claims (no PHI) + CMS MPFS where available; simulates prepay dollars caught

## Phase 2 (per the recommendation)

The same pipeline extends to **value-based-payment contract administration** — turning
contract language directly into settlement logic. Seed corpus now includes a VBP contract
example; export format supports handoff to external rules engines.

> Human-in-the-loop by design: agents augment professional expertise and are never used
> for clinical decision-making.

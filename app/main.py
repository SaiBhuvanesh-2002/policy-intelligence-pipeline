"""FastAPI application: API + static single-page UI."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from . import db
from .agents.llm import llm
from .claims.bootstrap import ensure_fee_schedule_loaded
from .claims.simulation import rule_row_to_dict, simulate_and_store
from .claims.fee_schedule import refresh_cache, schedule_info
from .claims.generator import generate_claims
from .claims.mpfs_loader import (
    cms_data_upload_hint,
    import_pprrvu_text,
    is_cms_data_not_policy,
    is_mpfs_filename,
)
from .config import FRONTEND_DIR
from .ingestion.document_classify import document_kind, is_cms_data_document, normalize_policy_upload
from .ingestion.extract import UnsupportedFileType, extract_text
from .ingestion.mock_generator import generate_mock_policy
from .demo import demo_status, prepare_demo
from .export.rule_export import export_json, export_yaml, rule_to_export_dict
from .pipeline import run_pipeline, seed_demo
from .schemas import IngestRequest, ReviewDecision

app = FastAPI(title="Cotiviti Policy Intelligence Pipeline", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    # Auto-seed an empty database so the demo is populated on first run.
    conn = db.get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
    finally:
        conn.close()
    if count == 0:
        seed_demo(reset=False)

    mpfs = ensure_fee_schedule_loaded()
    if mpfs:
        print(
            f"[Policy Intelligence] Fee schedule: CMS MPFS loaded "
            f"({mpfs.get('codes_loaded') or mpfs.get('codes')} codes, "
            f"source={mpfs.get('source') or mpfs.get('source_label')})"
        )
    else:
        print("[Policy Intelligence] Fee schedule: mock illustrative amounts (upload PPRRVU*.txt for CMS pricing)")

    if llm.available:
        print(f"[Policy Intelligence] Agents: LIVE  (provider={llm.label})")
    else:
        print(
            "[Policy Intelligence] Agents: OFFLINE deterministic engine "
            "(no API key found). Paste a key in .env and restart to go live."
        )


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------
def _rule_row_to_dict(row) -> dict:
    return rule_row_to_dict(row)


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "engine": llm.label}


@app.get("/api/demo/status")
def api_demo_status() -> dict:
    return demo_status()


@app.post("/api/demo/prepare")
def api_demo_prepare(reset: bool = False) -> dict:
    """Generate claims, load MPFS if available, and simulate all approved edits."""
    return prepare_demo(reset=reset)


@app.post("/api/seed")
def seed(reset: bool = True) -> dict:
    return seed_demo(reset=reset)


@app.get("/api/stats")
def stats() -> dict:
    conn = db.get_conn()
    try:
        def scalar(q, *a):
            return conn.execute(q, a).fetchone()[0]

        by_status = {
            r["review_status"]: r["n"]
            for r in conn.execute(
                "SELECT review_status, COUNT(*) AS n FROM draft_rules GROUP BY review_status"
            ).fetchall()
        }
        return {
            "documents": scalar("SELECT COUNT(*) FROM documents"),
            "versions": scalar("SELECT COUNT(*) FROM versions"),
            "change_reports": scalar("SELECT COUNT(*) FROM change_reports"),
            "rules_total": scalar("SELECT COUNT(*) FROM draft_rules"),
            "rules_pending": by_status.get("pending", 0),
            "rules_approved": by_status.get("approved", 0),
            "rules_rejected": by_status.get("rejected", 0),
            "rules_changes_requested": by_status.get("changes_requested", 0),
            "high_severity_pending": scalar(
                "SELECT COUNT(*) FROM draft_rules WHERE review_status='pending' "
                "AND severity='high' AND title NOT LIKE 'Monitor policy:%'"
            ),
            "actionable_pending": scalar(
                "SELECT COUNT(*) FROM draft_rules WHERE review_status='pending' "
                "AND title NOT LIKE 'Monitor policy:%'"
            ),
            "engine": llm.label,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
@app.get("/api/documents")
def list_documents(policies_only: bool = Query(True)) -> list[dict]:
    conn = db.get_conn()
    try:
        docs = conn.execute("SELECT * FROM documents ORDER BY id").fetchall()
        out = []
        for d in docs:
            kind = document_kind(d["title"], d["source_name"])
            if policies_only and kind == "cms_data":
                continue
            vcount = conn.execute(
                "SELECT COUNT(*) AS n FROM versions WHERE document_id=?", (d["id"],)
            ).fetchone()["n"]
            pending = conn.execute(
                "SELECT COUNT(*) AS n FROM draft_rules r JOIN versions v ON v.id=r.version_id "
                "WHERE v.document_id=? AND r.review_status='pending' "
                "AND r.title NOT LIKE 'Monitor policy:%'",
                (d["id"],),
            ).fetchone()["n"]
            latest = conn.execute(
                "SELECT version_label, effective_date FROM versions WHERE document_id=? "
                "ORDER BY id DESC LIMIT 1",
                (d["id"],),
            ).fetchone()
            report = conn.execute(
                "SELECT cr.headline, cr.changes, v1.version_label AS from_label, "
                "v2.version_label AS to_label "
                "FROM change_reports cr "
                "JOIN versions v1 ON v1.id = cr.from_version_id "
                "JOIN versions v2 ON v2.id = cr.to_version_id "
                "WHERE cr.document_id=? ORDER BY cr.id DESC LIMIT 1",
                (d["id"],),
            ).fetchone()
            change_count = 0
            headline = None
            from_label = to_label = None
            if report:
                headline = report["headline"]
                from_label = report["from_label"]
                to_label = report["to_label"]
                change_count = len(json.loads(report["changes"] or "[]"))
            out.append(
                {
                    "id": d["id"],
                    "source_type": d["source_type"],
                    "source_name": d["source_name"],
                    "title": d["title"],
                    "url": d["url"],
                    "kind": kind,
                    "version_count": vcount,
                    "pending_rules": pending,
                    "latest_version": latest["version_label"] if latest else None,
                    "latest_effective": latest["effective_date"] if latest else None,
                    "has_changes": change_count > 0,
                    "change_count": change_count,
                    "change_headline": headline,
                    "change_from": from_label,
                    "change_to": to_label,
                }
            )
        # Seed corpus first, then policies with changes, then the rest.
        out.sort(
            key=lambda x: (
                0 if x["kind"] == "seed" else 1,
                0 if x["has_changes"] else 1,
                -x["change_count"],
                -x["version_count"],
                x["id"],
            )
        )
        return out
    finally:
        conn.close()


@app.get("/api/documents/{document_id}")
def document_detail(document_id: int) -> dict:
    conn = db.get_conn()
    try:
        d = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if d is None:
            raise HTTPException(404, "Document not found")
        versions = [
            {
                "id": v["id"],
                "version_label": v["version_label"],
                "effective_date": v["effective_date"],
                "summary": v["summary"],
                "key_points": json.loads(v["key_points"] or "[]"),
                "text_length": len(v["raw_text"] or ""),
                "created_at": v["created_at"],
            }
            for v in conn.execute(
                "SELECT * FROM versions WHERE document_id=? ORDER BY id", (document_id,)
            ).fetchall()
        ]
        reports = []
        for r in conn.execute(
            "SELECT cr.*, v1.version_label AS from_label, v2.version_label AS to_label "
            "FROM change_reports cr "
            "JOIN versions v1 ON v1.id = cr.from_version_id "
            "JOIN versions v2 ON v2.id = cr.to_version_id "
            "WHERE cr.document_id=? ORDER BY cr.id",
            (document_id,),
        ).fetchall():
            reports.append(
                {
                    "id": r["id"],
                    "from_version_id": r["from_version_id"],
                    "to_version_id": r["to_version_id"],
                    "from_label": r["from_label"],
                    "to_label": r["to_label"],
                    "headline": r["headline"],
                    "changes": json.loads(r["changes"]),
                    "created_at": r["created_at"],
                }
            )
        version_ids = [v["id"] for v in versions]
        rules = []
        if version_ids:
            placeholders = ",".join("?" * len(version_ids))
            rules = [
                _rule_row_to_dict(r)
                for r in conn.execute(
                    f"SELECT * FROM draft_rules WHERE version_id IN ({placeholders}) "
                    f"AND title NOT LIKE 'Monitor policy:%' ORDER BY id",
                    version_ids,
                ).fetchall()
            ]
        return {
            "id": d["id"],
            "source_type": d["source_type"],
            "source_name": d["source_name"],
            "title": d["title"],
            "url": d["url"],
            "kind": document_kind(d["title"], d["source_name"]),
            "versions": versions,
            "change_reports": reports,
            "rules": rules,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Rules / review queue
# ---------------------------------------------------------------------------
@app.get("/api/rules")
def list_rules(
    status: Optional[str] = Query(None),
    exclude_monitor: bool = Query(True),
) -> list[dict]:
    conn = db.get_conn()
    try:
        monitor_clause = " AND title NOT LIKE 'Monitor policy:%'" if exclude_monitor else ""
        order = (
            "CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, id DESC"
        )
        if status:
            rows = conn.execute(
                f"SELECT * FROM draft_rules WHERE review_status=?{monitor_clause} ORDER BY {order}",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT * FROM draft_rules WHERE 1=1{monitor_clause} ORDER BY {order}"
            ).fetchall()
        out = []
        for r in rows:
            d = _rule_row_to_dict(r)
            ctx = conn.execute(
                "SELECT v.version_label, doc.title, doc.source_name FROM versions v "
                "JOIN documents doc ON doc.id=v.document_id WHERE v.id=?",
                (r["version_id"],),
            ).fetchone()
            if ctx:
                d["version_label"] = ctx["version_label"]
                d["document_title"] = ctx["title"]
                d["source_name"] = ctx["source_name"]
            out.append(d)
        return out
    finally:
        conn.close()


@app.get("/api/rules/{rule_id}")
def rule_detail(rule_id: int) -> dict:
    conn = db.get_conn()
    try:
        r = conn.execute("SELECT * FROM draft_rules WHERE id=?", (rule_id,)).fetchone()
        if r is None:
            raise HTTPException(404, "Rule not found")
        return _rule_row_to_dict(r)
    finally:
        conn.close()


@app.get("/api/rules/{rule_id}/export", response_model=None)
def export_rule(rule_id: int, format: str = Query("json")) -> Response:
    """Export an approved rule as JSON or YAML (Edifecs / rules-engine bridge stub)."""
    conn = db.get_conn()
    try:
        r = conn.execute("SELECT * FROM draft_rules WHERE id=?", (rule_id,)).fetchone()
        if r is None:
            raise HTTPException(404, "Rule not found")
        rule = _rule_row_to_dict(r)
        if rule["review_status"] != "approved":
            raise HTTPException(409, "Only approved rules can be exported. Complete SME review first.")
        fmt = format.lower()
        if fmt == "yaml":
            try:
                body = export_yaml(rule)
            except RuntimeError as exc:
                raise HTTPException(501, str(exc)) from exc
            return PlainTextResponse(body, media_type="text/yaml")
        return JSONResponse(rule_to_export_dict(rule))
    finally:
        conn.close()


@app.get("/api/rules/export/approved")
def export_approved_rules(format: str = Query("json")) -> JSONResponse:
    """Export all approved rules as a portable bundle."""
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM draft_rules WHERE review_status='approved' ORDER BY id"
        ).fetchall()
        bundle = {
            "export_format": "cotiviti-policy-intel-bundle",
            "export_version": "1.0",
            "rules": [rule_to_export_dict(_rule_row_to_dict(r)) for r in rows],
        }
        return JSONResponse(bundle)
    finally:
        conn.close()


@app.post("/api/rules/{rule_id}/review")
def review_rule(rule_id: int, decision: ReviewDecision) -> dict:
    conn = db.get_conn()
    try:
        r = conn.execute("SELECT * FROM draft_rules WHERE id=?", (rule_id,)).fetchone()
        if r is None:
            raise HTTPException(404, "Rule not found")
        conn.execute(
            "UPDATE draft_rules SET review_status=?, sme_name=?, sme_notes=?, reviewed_at=? "
            "WHERE id=?",
            (decision.decision.value, decision.sme_name, decision.sme_notes, db.now_iso(), rule_id),
        )
        db.log_audit(
            conn,
            f"sme:{decision.sme_name}",
            f"rule_{decision.decision.value}",
            f"rule={rule_id} '{r['title'][:80]}' :: {decision.sme_notes[:120]}",
        )
        if decision.decision.value == "approved":
            try:
                simulate_and_store(conn, rule_id, require_approved=False)
            except ValueError:
                pass
        conn.commit()
        updated = conn.execute("SELECT * FROM draft_rules WHERE id=?", (rule_id,)).fetchone()
        return _rule_row_to_dict(updated)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Ingest (run the full pipeline on new text)
# ---------------------------------------------------------------------------
@app.post("/api/ingest")
def ingest(req: IngestRequest) -> dict:
    return run_pipeline(
        source_type=req.source_type.value,
        source_name=req.source_name,
        title=req.title,
        version_label=req.version_label,
        raw_text=req.raw_text,
        url=req.url,
        effective_date=req.effective_date,
        actor="api:ingest",
    )


# ---------------------------------------------------------------------------
# Upload a file -> run the pipeline
# ---------------------------------------------------------------------------
@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    source_type: str = Query("cms_bulletin"),
    source_name: str = Query("Uploaded document"),
    version_label: str = Query("uploaded"),
    title: Optional[str] = Query(None),
) -> dict:
    content = await file.read()
    try:
        text = extract_text(file.filename or "upload", content)
    except UnsupportedFileType as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            400,
            f"Could not read '{file.filename or 'upload'}': {exc}",
        ) from exc
    if not text.strip():
        raise HTTPException(400, "Could not extract any text from the uploaded file.")
    filename = file.filename or ""
    doc_title = title or (filename or "Uploaded document")

    if is_mpfs_filename(filename):
        conn = db.get_conn()
        try:
            try:
                result = import_pprrvu_text(
                    conn,
                    text,
                    source_label=doc_title,
                    actor=f"api:upload({filename})",
                )
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            refresh_cache(conn)
            db.clear_simulation_results(conn)
            return {"upload_type": "fee_schedule", **result, "schedule": schedule_info()}
        finally:
            conn.close()

    if is_cms_data_not_policy(filename):
        raise HTTPException(
            400,
            cms_data_upload_hint(filename),
        )

    meta = normalize_policy_upload(filename, text) or {}
    doc_title = meta.get("title") or title or (file.filename or "Uploaded document")
    src_name = meta.get("source_name") or source_name
    ver_label = meta.get("version_label") or version_label
    eff_date = meta.get("effective_date")
    src_type = meta.get("source_type") or source_type

    try:
        result = run_pipeline(
            source_type=src_type,
            source_name=src_name,
            title=doc_title,
            version_label=ver_label,
            raw_text=text,
            url=None,
            effective_date=eff_date,
            actor=f"api:upload({file.filename})",
        )
    except Exception as exc:
        raise HTTPException(
            500,
            f"Pipeline failed after extracting text: {exc}",
        ) from exc
    result["upload_type"] = "policy"
    result["normalized"] = bool(meta)
    return result


# ---------------------------------------------------------------------------
# Generate a synthetic policy (v1 + mutated v2) and run both through pipeline
# ---------------------------------------------------------------------------
@app.post("/api/mock/policy")
def mock_policy(seed: Optional[int] = None) -> dict:
    spec = generate_mock_policy(seed)
    results = []
    for ver in spec["versions"]:
        results.append(
            run_pipeline(
                source_type=spec["source_type"],
                source_name=spec["source_name"],
                title=spec["title"],
                version_label=ver["version_label"],
                raw_text=ver["raw_text"],
                effective_date=ver.get("effective_date"),
                actor="api:mock_policy",
            )
        )
    return {
        "title": spec["title"],
        "source_name": spec["source_name"],
        "versions_loaded": len(results),
        "latest": results[-1],
    }


# ---------------------------------------------------------------------------
# Claims: generate synthetic claims + simulate an edit ("dollars caught")
# ---------------------------------------------------------------------------
@app.post("/api/claims/generate")
def claims_generate(seed: int = 42, noise_claims: int = 12) -> dict:
    conn = db.get_conn()
    try:
        db.clear_simulation_results(conn)
        conn.commit()
    finally:
        conn.close()
    result = generate_claims(seed=seed, noise_claims=noise_claims)
    result["schedule"] = schedule_info()
    return result


@app.get("/api/fee-schedule/stats")
def fee_schedule_stats() -> dict:
    return schedule_info()


@app.post("/api/fee-schedule/import")
def fee_schedule_import() -> dict:
    """Re-import the newest PPRRVU document already stored in the database."""
    conn = db.get_conn()
    try:
        latest = db.latest_pprrvu_text(conn)
        if latest is None:
            raise HTTPException(404, "No PPRRVU file found. Upload a PPRRVU*.txt from CMS MPFS first.")
        title, raw_text = latest
        try:
            result = import_pprrvu_text(
                conn, raw_text, source_label=title, actor="api:fee_schedule_import"
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        refresh_cache(conn)
        db.clear_simulation_results(conn)
        result["schedule"] = schedule_info()
        return result
    finally:
        conn.close()


def _simulate_and_store(conn, rule_id: int) -> dict:
    try:
        return simulate_and_store(conn, rule_id, require_approved=True)
    except ValueError as exc:
        msg = str(exc).lower()
        if "not found" in msg:
            raise HTTPException(404, str(exc)) from exc
        if "approved" in msg:
            raise HTTPException(409, str(exc)) from exc
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/impact")
def impact_dashboard() -> dict:
    conn = db.get_conn()
    try:
        lines = db.count_claims(conn)
        claims = conn.execute(
            "SELECT COUNT(DISTINCT claim_id) AS n FROM claims"
        ).fetchone()["n"]
        sims = db.fetch_simulation_results(conn)
        rules = conn.execute("SELECT id, title, review_status, severity FROM draft_rules").fetchall()
        actionable = [r for r in rules if r["review_status"] == "approved"]
        with_hits = sum(1 for s in sims.values() if s.get("flagged_count", 0) > 0)
        total_dollars = sum(s.get("dollars_caught", 0) for s in sims.values())
        return {
            "claims": claims,
            "claim_lines": lines,
            "schedule": schedule_info(),
            "rules_total": len(rules),
            "rules_approved": len(actionable),
            "simulated": len(sims),
            "rules_with_hits": with_hits,
            "total_dollars_caught": round(total_dollars, 2),
            "simulations": {str(k): v for k, v in sims.items()},
        }
    finally:
        conn.close()


@app.post("/api/impact/simulate-all")
def impact_simulate_all() -> dict:
    conn = db.get_conn()
    try:
        if db.count_claims(conn) == 0:
            raise HTTPException(409, "No claims to simulate against. Generate sample claims first.")
        rows = conn.execute(
            "SELECT id FROM draft_rules WHERE review_status='approved' ORDER BY id"
        ).fetchall()
        if not rows:
            raise HTTPException(409, "No approved edits. Approve rules in the SME Review Queue first.")
        results = []
        for row in rows:
            results.append(_simulate_and_store(conn, int(row["id"])))
        conn.commit()
        total_dollars = sum(r["dollars_caught"] for r in results)
        with_hits = sum(1 for r in results if r["flagged_count"] > 0)
        return {
            "simulated": len(results),
            "rules_with_hits": with_hits,
            "total_dollars_caught": round(total_dollars, 2),
            "schedule": schedule_info(),
        }
    finally:
        conn.close()


@app.get("/api/claims/stats")
def claims_stats() -> dict:
    conn = db.get_conn()
    try:
        lines = db.count_claims(conn)
        claims = conn.execute("SELECT COUNT(DISTINCT claim_id) AS n FROM claims").fetchone()["n"]
        return {"claim_lines": lines, "claims": claims}
    finally:
        conn.close()


@app.post("/api/rules/{rule_id}/simulate")
def simulate_rule(rule_id: int) -> dict:
    conn = db.get_conn()
    try:
        result = _simulate_and_store(conn, rule_id)
        conn.commit()
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
@app.get("/api/audit")
def audit(limit: int = 100) -> list[dict]:
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            {
                "id": r["id"],
                "actor": r["actor"],
                "action": r["action"],
                "detail": r["detail"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Frontend (mounted last so /api/* wins)
# ---------------------------------------------------------------------------
@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")

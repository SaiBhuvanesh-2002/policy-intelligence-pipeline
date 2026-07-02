"""One-click demo preparation for assessment presentations."""
from __future__ import annotations

from . import db
from .agents.llm import llm
from .claims.bootstrap import ensure_fee_schedule_loaded
from .claims.fee_schedule import refresh_cache, schedule_info
from .config import settings
from .claims.generator import generate_claims
from .claims.mpfs_loader import import_pprrvu_text
from .claims.simulation import simulate_and_store
from .pipeline import seed_demo

_ACTIONABLE = "title NOT LIKE 'Monitor policy:%'"


def demo_status() -> dict:
    conn = db.get_conn()
    try:
        rules_total = int(conn.execute("SELECT COUNT(*) FROM draft_rules").fetchone()[0])
        rules_pending = int(
            conn.execute(
                f"SELECT COUNT(*) FROM draft_rules WHERE review_status='pending' AND {_ACTIONABLE}"
            ).fetchone()[0]
        )
        rules_approved = int(
            conn.execute(
                f"SELECT COUNT(*) FROM draft_rules WHERE review_status='approved' AND {_ACTIONABLE}"
            ).fetchone()[0]
        )
        claim_lines = db.count_claims(conn)
        sims = len(db.fetch_simulation_results(conn))
        docs = int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
        mpfs = db.count_fee_schedule(conn)
        pprrvu = db.latest_pprrvu_text(conn)

        schedule = schedule_info()
        checks = {
            "seeded_corpus": docs >= 6,
            "cms_mpfs_loaded": schedule.get("mode") == "cms_mpfs",
            "claims_generated": claim_lines > 0,
            "impact_simulated": sims > 0,
            "actionable_approved_edits": rules_approved > 0,
            "live_llm": llm.available,
        }
        ready = all(
            checks[k]
            for k in (
                "seeded_corpus",
                "claims_generated",
                "impact_simulated",
                "actionable_approved_edits",
            )
        )
        return {
            "ready": ready,
            "checks": checks,
            "engine": llm.label,
            "documents": docs,
            "rules_total": rules_total,
            "rules_pending_actionable": rules_pending,
            "rules_approved_actionable": rules_approved,
            "claim_lines": claim_lines,
            "simulations": sims,
            "schedule": schedule,
            "pprrvu_available": pprrvu is not None,
            "pprrvu_source": pprrvu[0] if pprrvu else None,
            "mpfs_codes": mpfs,
        }
    finally:
        conn.close()


def prepare_demo(*, reset: bool = False, import_mpfs: bool = True) -> dict:
    steps: list[str] = []
    total_dollars = 0.0
    saved_pprrvu: tuple[str, str] | None = None

    if reset:
        conn = db.get_conn()
        try:
            saved_pprrvu = db.latest_pprrvu_text(conn)
        finally:
            conn.close()
        seed_demo(reset=True)
        steps.append("Reset and loaded shipped policy corpus (6 sources, 12 versions)")
        if settings.demo_auto_approve:
            conn = db.get_conn()
            try:
                cur = conn.execute(
                    "UPDATE draft_rules SET review_status='approved', sme_name='Demo SME', "
                    "sme_notes='Pre-approved for assessment demo', reviewed_at=? "
                    "WHERE review_status='pending' AND title NOT LIKE 'Monitor policy:%'",
                    (db.now_iso(),),
                )
                approved_n = cur.rowcount
                db.log_audit(conn, "demo:prepare", "rules_auto_approved", f"{approved_n} seed edit(s)")
                conn.commit()
                steps.append(f"Pre-approved {approved_n} actionable seed edits for demo")
            finally:
                conn.close()
        else:
            steps.append("Auto-approve disabled (PIP_DEMO_AUTO_APPROVE=false); approve edits in SME queue")

    conn = db.get_conn()
    try:
        if import_mpfs:
            latest = saved_pprrvu or db.latest_pprrvu_text(conn)
            if latest:
                title, raw_text = latest
                import_pprrvu_text(conn, raw_text, source_label=title, actor="demo:prepare")
                refresh_cache(conn)
                steps.append(f"Loaded CMS MPFS from {title}")
            else:
                ensure_fee_schedule_loaded()
                refresh_cache(conn)
                if db.count_fee_schedule(conn) > 0:
                    meta = db.fee_schedule_meta(conn)
                    steps.append(f"MPFS already loaded ({meta['codes']} codes)")
                else:
                    steps.append("No PPRRVU file — mock fee estimates (upload PPRRVU*.txt on Ingest)")

        db.clear_simulation_results(conn)
        conn.commit()
    finally:
        conn.close()

    claims_result = generate_claims(actor="demo:prepare")
    steps.append(f"Generated {claims_result['claim_lines']} synthetic claim lines")

    conn = db.get_conn()
    try:
        rows = conn.execute(
            f"SELECT id FROM draft_rules WHERE review_status='approved' AND {_ACTIONABLE} ORDER BY id"
        ).fetchall()
        simulated = 0
        with_hits = 0
        for row in rows:
            result = simulate_and_store(conn, int(row["id"]))
            simulated += 1
            if result["flagged_count"] > 0:
                with_hits += 1
            total_dollars += result["dollars_caught"]
        conn.commit()
        steps.append(f"Simulated {simulated} approved edits ({with_hits} with hits)")
    finally:
        conn.close()

    return {
        "steps": steps,
        "status": demo_status(),
        "total_dollars_caught": round(total_dollars, 2),
    }

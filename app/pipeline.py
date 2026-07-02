"""Orchestrates the four-stage Policy Intelligence Pipeline.

  Stage 1  ingest + summarize       (summarizer agent)
  Stage 2  change detection         (change_detector agent)
  Stage 3  draft executable edits   (rule_drafter agent)
  Stage 4  route to human SME       (every draft persisted as 'pending')
"""
from __future__ import annotations

import json
from typing import Optional

from . import db
from .agents import change_detector, rule_drafter, summarizer
from .agents.llm import llm


def run_pipeline(
    *,
    source_type: str,
    source_name: str,
    title: str,
    version_label: str,
    raw_text: str,
    url: Optional[str] = None,
    effective_date: Optional[str] = None,
    actor: str = "pipeline",
) -> dict:
    conn = db.get_conn()
    try:
        # --- locate or create the document ---
        doc = db.find_document(conn, source_name, title)
        if doc is None:
            document_id = db.insert_document(conn, source_type, source_name, title, url)
            db.log_audit(conn, actor, "document_created", f"{source_name} :: {title}")
        else:
            document_id = doc["id"]

        # --- Stage 1: summarize ---
        summary, key_points = summarizer.summarize(title, raw_text, source_type)
        version_id = db.insert_version(
            conn, document_id, version_label, effective_date, raw_text, summary, key_points
        )
        db.log_audit(
            conn,
            f"agent:summarizer({llm.label})",
            "version_ingested",
            f"doc={document_id} version='{version_label}' ({len(key_points)} key points)",
        )

        # --- Stage 2: change detection (needs a prior version) ---
        change_report = None
        prior = db.latest_prior_version(conn, document_id, version_id)
        if prior is not None:
            result = change_detector.detect_changes(title, prior["raw_text"], raw_text)
            report_id = db.insert_change_report(
                conn,
                document_id,
                prior["id"],
                version_id,
                result["headline"],
                result["changes"],
            )
            change_report = {
                "id": report_id,
                "document_id": document_id,
                "from_version_id": prior["id"],
                "to_version_id": version_id,
                "from_label": prior["version_label"],
                "to_label": version_label,
                "headline": result["headline"],
                "changes": result["changes"],
            }
            db.log_audit(
                conn,
                f"agent:change_detector({llm.label})",
                "changes_detected",
                f"doc={document_id} {len(result['changes'])} change(s): {result['headline'][:120]}",
            )

        # --- Stage 3: draft executable edits ---
        headline = change_report["headline"] if change_report else ""
        change_items = change_report["changes"] if change_report else []
        drafts = rule_drafter.draft_rules(
            title,
            summary,
            raw_text,
            headline,
            changes=change_items,
            source_type=source_type,
        )
        draft_rules = []
        for r in drafts:
            rule_id = db.insert_draft_rule(conn, version_id, r)
            draft_rules.append({"id": rule_id, "version_id": version_id, **r})
        db.log_audit(
            conn,
            f"agent:rule_drafter({llm.label})",
            "rules_drafted",
            f"version={version_id} drafted {len(draft_rules)} edit(s) (status=pending SME)",
        )

        # --- Stage 4: routing to human SME is implicit (status='pending') ---
        db.log_audit(
            conn,
            "router",
            "routed_to_sme",
            f"{len(draft_rules)} draft(s) queued for human sign-off",
        )

        conn.commit()
        return {
            "document_id": document_id,
            "version_id": version_id,
            "summary": summary,
            "key_points": key_points,
            "change_report": change_report,
            "draft_rules": draft_rules,
            "engine": llm.label,
        }
    finally:
        conn.close()


def seed_demo(reset: bool = True) -> dict:
    """Load the shipped corpus through the pipeline, version by version.

    Bootstrapping the fixed demo corpus always uses the fast, free offline
    engine — re-running a live LLM over unchanging fixtures on every boot would
    be slow and waste API tokens. Interactive ingest/upload/mock actions still
    use the configured live engine. We temporarily force the singleton client
    offline for the duration of seeding, then restore it.
    """
    if reset:
        db.reset_db()
    else:
        db.init_db()
    from .ingestion.seed_data import SEED_CORPUS

    saved_available = llm.available
    llm.available = False  # force offline for the bootstrap corpus
    loaded = 0
    try:
        for entry in SEED_CORPUS:
            for ver in entry["versions"]:
                run_pipeline(
                    source_type=entry["source_type"],
                    source_name=entry["source_name"],
                    title=entry["title"],
                    version_label=ver["version_label"],
                    raw_text=ver["raw_text"],
                    url=entry.get("url"),
                    effective_date=ver.get("effective_date"),
                    actor="seed",
                )
                loaded += 1
    finally:
        llm.available = saved_available
    return {
        "documents": len(SEED_CORPUS),
        "versions_loaded": loaded,
        "engine": llm.label,
        "seed_engine": "offline-deterministic-engine",
        "live_engine": llm.label,
    }

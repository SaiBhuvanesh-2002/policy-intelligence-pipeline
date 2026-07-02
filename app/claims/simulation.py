"""Persisted rule simulation against the claims store."""
from __future__ import annotations

import json
from typing import Any

from .. import db
from .evaluator import evaluate_rule


def rule_row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "version_id": row["version_id"],
        "title": row["title"],
        "rationale": row["rationale"],
        "citation": row["citation"],
        "severity": row["severity"],
        "confidence": row["confidence"],
        "edit_type": row["edit_type"],
        "logic": json.loads(row["logic"]),
        "review_status": row["review_status"],
        "sme_name": row["sme_name"],
        "sme_notes": row["sme_notes"],
        "reviewed_at": row["reviewed_at"],
        "created_at": row["created_at"],
    }


def simulate_and_store(conn, rule_id: int, *, require_approved: bool = True) -> dict[str, Any]:
    r = conn.execute("SELECT * FROM draft_rules WHERE id=?", (rule_id,)).fetchone()
    if r is None:
        raise ValueError("Rule not found")
    if require_approved and r["review_status"] != "approved":
        raise ValueError("Rule must be approved before simulation. Complete SME review first.")
    if db.count_claims(conn) == 0:
        raise ValueError("No claims to simulate against. Generate sample claims first.")
    rule = rule_row_to_dict(r)
    claims = db.fetch_all_claims(conn)
    result = evaluate_rule(rule, claims)
    db.upsert_simulation_result(conn, rule_id, result)
    db.log_audit(
        conn,
        "claims:simulator",
        "rule_simulated",
        f"rule={rule_id} flagged {result['flagged_count']} line(s), "
        f"${result['dollars_caught']:.2f}",
    )
    return result

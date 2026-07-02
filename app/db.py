"""SQLite persistence layer (zero-config, single file)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

from .config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    version_label TEXT NOT NULL,
    effective_date TEXT,
    raw_text TEXT NOT NULL,
    summary TEXT,
    key_points TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS change_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    from_version_id INTEGER NOT NULL,
    to_version_id INTEGER NOT NULL,
    headline TEXT,
    changes TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS draft_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    rationale TEXT NOT NULL,
    citation TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence REAL NOT NULL,
    edit_type TEXT NOT NULL,
    logic TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'pending',
    sme_name TEXT,
    sme_notes TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (version_id) REFERENCES versions(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    member_id TEXT NOT NULL,
    procedure_code TEXT NOT NULL,
    modifiers TEXT NOT NULL,
    units INTEGER NOT NULL,
    dos TEXT NOT NULL,
    billed_amount REAL NOT NULL,
    scenario TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fee_schedule (
    procedure_code TEXT PRIMARY KEY,
    allowed_amount REAL NOT NULL,
    source_label TEXT NOT NULL,
    conversion_factor REAL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation_results (
    rule_id INTEGER PRIMARY KEY,
    result TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (rule_id) REFERENCES draft_rules(id)
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def reset_db() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------
def log_audit(conn: sqlite3.Connection, actor: str, action: str, detail: str) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor, action, detail, created_at) VALUES (?,?,?,?)",
        (actor, action, detail, now_iso()),
    )


# ---------------------------------------------------------------------------
# Document / version helpers
# ---------------------------------------------------------------------------
def find_document(conn: sqlite3.Connection, source_name: str, title: str) -> Optional[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM documents WHERE source_name = ? AND title = ?",
        (source_name, title),
    )
    return cur.fetchone()


def insert_document(
    conn: sqlite3.Connection,
    source_type: str,
    source_name: str,
    title: str,
    url: Optional[str],
) -> int:
    cur = conn.execute(
        "INSERT INTO documents (source_type, source_name, title, url, created_at) "
        "VALUES (?,?,?,?,?)",
        (source_type, source_name, title, url, now_iso()),
    )
    return int(cur.lastrowid)


def insert_version(
    conn: sqlite3.Connection,
    document_id: int,
    version_label: str,
    effective_date: Optional[str],
    raw_text: str,
    summary: Optional[str],
    key_points: Optional[list[str]],
) -> int:
    cur = conn.execute(
        "INSERT INTO versions "
        "(document_id, version_label, effective_date, raw_text, summary, key_points, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            document_id,
            version_label,
            effective_date,
            raw_text,
            summary,
            json.dumps(key_points or []),
            now_iso(),
        ),
    )
    return int(cur.lastrowid)


def latest_prior_version(
    conn: sqlite3.Connection, document_id: int, exclude_version_id: int
) -> Optional[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM versions WHERE document_id = ? AND id != ? "
        "ORDER BY id DESC LIMIT 1",
        (document_id, exclude_version_id),
    )
    return cur.fetchone()


def update_version_summary(
    conn: sqlite3.Connection, version_id: int, summary: str, key_points: list[str]
) -> None:
    conn.execute(
        "UPDATE versions SET summary = ?, key_points = ? WHERE id = ?",
        (summary, json.dumps(key_points), version_id),
    )


def insert_change_report(
    conn: sqlite3.Connection,
    document_id: int,
    from_version_id: int,
    to_version_id: int,
    headline: str,
    changes: list[dict[str, Any]],
) -> int:
    cur = conn.execute(
        "INSERT INTO change_reports "
        "(document_id, from_version_id, to_version_id, headline, changes, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (
            document_id,
            from_version_id,
            to_version_id,
            headline,
            json.dumps(changes),
            now_iso(),
        ),
    )
    return int(cur.lastrowid)


def insert_draft_rule(conn: sqlite3.Connection, version_id: int, rule: dict[str, Any]) -> int:
    cur = conn.execute(
        "INSERT INTO draft_rules "
        "(version_id, title, rationale, citation, severity, confidence, edit_type, logic, "
        " review_status, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            version_id,
            rule["title"],
            rule["rationale"],
            rule["citation"],
            rule["severity"],
            rule["confidence"],
            rule["edit_type"],
            json.dumps(rule["logic"]),
            "pending",
            now_iso(),
        ),
    )
    return int(cur.lastrowid)


# ---------------------------------------------------------------------------
# Claims helpers
# ---------------------------------------------------------------------------
def clear_claims(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM claims")


def insert_claim_line(conn: sqlite3.Connection, line: dict[str, Any]) -> int:
    cur = conn.execute(
        "INSERT INTO claims "
        "(claim_id, line_no, member_id, procedure_code, modifiers, units, dos, "
        " billed_amount, scenario, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            line["claim_id"],
            line["line_no"],
            line["member_id"],
            line["procedure_code"],
            json.dumps(line.get("modifiers", [])),
            line["units"],
            line["dos"],
            line["billed_amount"],
            line.get("scenario"),
            now_iso(),
        ),
    )
    return int(cur.lastrowid)


def fetch_all_claims(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM claims ORDER BY claim_id, line_no").fetchall()
    return [
        {
            "id": r["id"],
            "claim_id": r["claim_id"],
            "line_no": r["line_no"],
            "member_id": r["member_id"],
            "procedure_code": r["procedure_code"],
            "modifiers": json.loads(r["modifiers"]),
            "units": r["units"],
            "dos": r["dos"],
            "billed_amount": r["billed_amount"],
            "scenario": r["scenario"],
        }
        for r in rows
    ]


def count_claims(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0])


# ---------------------------------------------------------------------------
# Fee schedule (CMS MPFS)
# ---------------------------------------------------------------------------
def count_fee_schedule(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM fee_schedule").fetchone()[0])


def replace_fee_schedule(
    conn: sqlite3.Connection,
    codes: dict[str, float],
    *,
    source_label: str,
    conversion_factor: float | None,
) -> None:
    conn.execute("DELETE FROM fee_schedule")
    ts = now_iso()
    conn.executemany(
        "INSERT INTO fee_schedule "
        "(procedure_code, allowed_amount, source_label, conversion_factor, updated_at) "
        "VALUES (?,?,?,?,?)",
        [
            (code, amount, source_label, conversion_factor, ts)
            for code, amount in codes.items()
        ],
    )


def lookup_allowed_amount(conn: sqlite3.Connection, code: str) -> float | None:
    row = conn.execute(
        "SELECT allowed_amount FROM fee_schedule WHERE procedure_code = ?",
        (code,),
    ).fetchone()
    return float(row["allowed_amount"]) if row else None


def fee_schedule_meta(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT source_label, conversion_factor, updated_at, COUNT(*) AS codes "
        "FROM fee_schedule"
    ).fetchone()
    if not row or row["codes"] == 0:
        return None
    return {
        "source_label": row["source_label"],
        "conversion_factor": row["conversion_factor"],
        "updated_at": row["updated_at"],
        "codes": row["codes"],
    }


def latest_pprrvu_text(conn: sqlite3.Connection) -> tuple[str, str] | None:
    """Return (title, raw_text) for the newest ingested PPRRVU document version."""
    row = conn.execute(
        "SELECT d.title, v.raw_text "
        "FROM versions v "
        "JOIN documents d ON d.id = v.document_id "
        "WHERE UPPER(d.title) LIKE '%PPRRVU%' "
        "ORDER BY v.id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return row["title"], row["raw_text"]


# ---------------------------------------------------------------------------
# Simulation results (persisted for Impact tab)
# ---------------------------------------------------------------------------
def upsert_simulation_result(
    conn: sqlite3.Connection, rule_id: int, result: dict[str, Any]
) -> None:
    conn.execute(
        "INSERT INTO simulation_results (rule_id, result, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(rule_id) DO UPDATE SET result=excluded.result, updated_at=excluded.updated_at",
        (rule_id, json.dumps(result), now_iso()),
    )


def fetch_simulation_results(conn: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    rows = conn.execute("SELECT rule_id, result FROM simulation_results").fetchall()
    return {int(r["rule_id"]): json.loads(r["result"]) for r in rows}


def clear_simulation_results(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM simulation_results")

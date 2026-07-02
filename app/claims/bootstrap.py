"""Bootstrap CMS MPFS data from ingested PPRRVU files."""
from __future__ import annotations

from .fee_schedule import refresh_cache
from .mpfs_loader import import_pprrvu_text


def ensure_fee_schedule_loaded() -> dict | None:
    """Load the newest PPRRVU version from the DB if fee_schedule is empty."""
    from .. import db

    conn = db.get_conn()
    try:
        if db.count_fee_schedule(conn) > 0:
            refresh_cache(conn)
            return db.fee_schedule_meta(conn)
        latest = db.latest_pprrvu_text(conn)
        if latest is None:
            refresh_cache(conn)
            return None
        title, raw_text = latest
        result = import_pprrvu_text(
            conn, raw_text, source_label=title, actor="mpfs:startup"
        )
        refresh_cache(conn)
        return result
    finally:
        conn.close()

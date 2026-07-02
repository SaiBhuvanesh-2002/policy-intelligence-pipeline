"""Medicare allowed amounts — CMS MPFS when loaded, mock fallback otherwise."""
from __future__ import annotations

from typing import Any

MOCK_FEE_SCHEDULE: dict[str, float] = {
    "17000": 92.50,
    "11102": 78.20,
    "11720": 36.40,
    "11055": 41.10,
    "G0480": 114.00,
    "G0481": 156.00,
    "G0482": 198.00,
    "G0483": 246.00,
    "80305": 28.50,
    "80306": 33.75,
    "80307": 79.90,
    "J1304": 312.00,
    "J9999": 540.00,
    "Q5142": 188.00,
    "J0178": 96.30,
    "G0463": 142.00,
    "G0511": 78.00,
    "36415": 6.10,
    "36416": 8.40,
}

DEFAULT_ALLOWED = 120.00

_mpfs_cache: dict[str, float] = {}
_meta: dict[str, Any] | None = None


def refresh_cache(conn) -> None:
    """Reload in-memory MPFS amounts from SQLite."""
    global _mpfs_cache, _meta
    from .. import db

    rows = conn.execute(
        "SELECT procedure_code, allowed_amount FROM fee_schedule"
    ).fetchall()
    _mpfs_cache = {r["procedure_code"]: float(r["allowed_amount"]) for r in rows}
    _meta = db.fee_schedule_meta(conn)


def schedule_info() -> dict[str, Any]:
    if _mpfs_cache:
        return {
            "mode": "cms_mpfs",
            "codes": len(_mpfs_cache),
            **(_meta or {}),
        }
    return {"mode": "mock", "codes": len(MOCK_FEE_SCHEDULE)}


def using_mpfs() -> bool:
    return bool(_mpfs_cache)


def allowed_amount(code: str) -> float:
    if code in _mpfs_cache:
        return _mpfs_cache[code]
    return MOCK_FEE_SCHEDULE.get(code, DEFAULT_ALLOWED)

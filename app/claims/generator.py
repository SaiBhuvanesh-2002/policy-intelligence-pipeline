"""Generate synthetic claims seeded to exercise the current draft rules.

The mix is deterministic (seeded) but realistic: for every rule we create a few
claims that SHOULD be caught and a few compliant claims that should NOT, plus
unrelated noise claims. This guarantees an approved edit always catches
something in the demo while keeping a believable catch rate.
"""
from __future__ import annotations

import random
from typing import Any

from .. import db
from .fee_schedule import MOCK_FEE_SCHEDULE, allowed_amount

_NOISE_CODES = ["36415", "36416", "80305", "80306", "G0511", "J0178"]


class _ClaimBuilder:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.lines: list[dict[str, Any]] = []
        self._seq = 0

    def _billed(self, code: str, units: int) -> float:
        return round(allowed_amount(code) * units * self.rng.uniform(1.0, 1.4), 2)

    def add_claim(self, scenario: str, lines: list[dict[str, Any]]) -> None:
        self._seq += 1
        claim_id = f"CLM-{self._seq:04d}"
        member_id = f"M{self.rng.randint(10000, 99999)}"
        dos = self.rng.choice(["2026-02-03", "2026-02-11", "2026-03-07", "2026-03-19"])
        for i, ln in enumerate(lines, start=1):
            code = ln["procedure_code"]
            units = ln.get("units", 1)
            self.lines.append(
                {
                    "claim_id": claim_id,
                    "line_no": i,
                    "member_id": member_id,
                    "procedure_code": code,
                    "modifiers": ln.get("modifiers", []),
                    "units": units,
                    "dos": ln.get("dos", dos),
                    "billed_amount": ln.get("billed_amount", self._billed(code, units)),
                    "scenario": scenario,
                }
            )


def _seed_for_rule(b: _ClaimBuilder, rule: dict[str, Any]) -> None:
    logic = rule["logic"]
    proc = logic.get("when_procedure_codes", []) or []
    mods = logic.get("when_modifiers", []) or []
    unless = logic.get("unless_modifiers", []) or []
    max_units = logic.get("max_units")
    same_dos = bool(logic.get("same_date_of_service"))
    action = logic.get("action", "informational")

    # Bilateral modifier-units
    if max_units is not None and mods and not proc:
        code = "64483"
        b.add_claim("violation:bilateral", [{"procedure_code": code, "modifiers": mods, "units": max_units + 1}])
        b.add_claim("clean:bilateral", [{"procedure_code": code, "modifiers": mods, "units": max_units}])

    # Frequency limit
    elif max_units is not None and proc and not unless:
        code = proc[0]
        dos = "2026-03-07"
        b.add_claim(
            "violation:frequency",
            [{"procedure_code": code, "dos": dos} for _ in range(max_units + 2)],
        )
        b.add_claim(
            "clean:frequency",
            [{"procedure_code": code, "dos": dos} for _ in range(max_units)],
        )

    # PTP code pair
    elif same_dos and len(proc) >= 2 and unless:
        col1, col2 = proc[0], proc[1]
        dos = "2026-02-11"
        b.add_claim(
            "violation:ptp",
            [
                {"procedure_code": col1, "dos": dos},
                {"procedure_code": col2, "dos": dos, "modifiers": []},
            ],
        )
        b.add_claim(
            "clean:ptp",
            [
                {"procedure_code": col1, "dos": dos},
                {"procedure_code": col2, "dos": dos, "modifiers": [unless[0]]},
            ],
        )

    # Prior authorization
    elif action == "pend_for_review" and proc:
        code = proc[0]
        b.add_claim("violation:prior_auth", [{"procedure_code": code, "modifiers": []}])
        b.add_claim("clean:prior_auth", [{"procedure_code": code, "modifiers": ["AUTH"]}])

    # Deleted code (respect effective_date when present)
    elif action == "deny_line" and proc and not same_dos:
        code = proc[0]
        eff = logic.get("effective_date") or "2020-01-01"
        b.add_claim("violation:deleted_code", [{"procedure_code": code, "dos": eff}])
        b.add_claim("clean:deleted_code", [{"procedure_code": code, "dos": "2019-12-31"}])

    # MUE / adjust_units same-DOS totaling
    elif action == "adjust_units" and same_dos and max_units is not None:
        code = proc[0] if proc else "11720"
        dos = "2026-03-07"
        b.add_claim(
            "violation:mue",
            [
                {"procedure_code": code, "dos": dos, "units": 1},
                {"procedure_code": code, "dos": dos, "units": 1},
            ],
        )
        b.add_claim("clean:mue", [{"procedure_code": code, "dos": dos, "units": 1}])


def generate_claims(
    *, seed: int = 42, noise_claims: int = 12, actor: str = "claims:generator"
) -> dict[str, Any]:
    rng = random.Random(seed)
    conn = db.get_conn()
    try:
        rule_rows = conn.execute("SELECT id, logic FROM draft_rules").fetchall()
        import json

        rules = [{"id": r["id"], "logic": json.loads(r["logic"])} for r in rule_rows]

        b = _ClaimBuilder(rng)
        for rule in rules:
            _seed_for_rule(b, rule)

        # Unrelated noise so the catch rate is realistic (not 100%).
        rule_codes = {c for r in rules for c in r["logic"].get("when_procedure_codes", [])}
        noise_pool = [c for c in _NOISE_CODES if c not in rule_codes] or list(MOCK_FEE_SCHEDULE)
        for _ in range(noise_claims):
            code = rng.choice(noise_pool)
            b.add_claim("noise:clean", [{"procedure_code": code, "units": rng.choice([1, 1, 2])}])

        db.clear_claims(conn)
        for line in b.lines:
            db.insert_claim_line(conn, line)
        db.log_audit(
            conn,
            actor,
            "claims_generated",
            f"{len(b.lines)} synthetic claim line(s) across {b._seq} claims (seed={seed})",
        )
        conn.commit()
        return {
            "claims": b._seq,
            "claim_lines": len(b.lines),
            "seeded_for_rules": len(rules),
            "note": "Synthetic claims (no PHI). Dollar amounts use CMS MPFS when loaded, else mock estimates.",
        }
    finally:
        conn.close()

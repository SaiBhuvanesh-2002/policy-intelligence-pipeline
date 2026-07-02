"""Export approved rules to JSON/YAML for external rules engines (Edifecs bridge stub)."""
from __future__ import annotations

import json
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None  # type: ignore[assignment]


EXPORT_VERSION = "1.0"
EXPORT_FORMAT = "cotiviti-policy-intel-rule"


def rule_to_export_dict(rule: dict[str, Any]) -> dict[str, Any]:
    """Normalize a draft rule row dict into a portable export payload."""
    logic = rule.get("logic") or {}
    return {
        "export_format": EXPORT_FORMAT,
        "export_version": EXPORT_VERSION,
        "rule_id": rule.get("id"),
        "title": rule.get("title"),
        "rationale": rule.get("rationale"),
        "citation": rule.get("citation"),
        "severity": rule.get("severity"),
        "confidence": rule.get("confidence"),
        "edit_type": rule.get("edit_type"),
        "review_status": rule.get("review_status"),
        "logic": {
            "when_procedure_codes": logic.get("when_procedure_codes", []),
            "when_diagnosis_codes": logic.get("when_diagnosis_codes", []),
            "when_modifiers": logic.get("when_modifiers", []),
            "unless_modifiers": logic.get("unless_modifiers", []),
            "same_date_of_service": logic.get("same_date_of_service", False),
            "max_units": logic.get("max_units"),
            "effective_date": logic.get("effective_date"),
            "action": logic.get("action", "pend_for_review"),
            "pseudocode": logic.get("pseudocode", ""),
            "sql_preview": logic.get("sql_preview", ""),
        },
        "deployment_note": (
            "Export stub for Edifecs / payer edit-engine integration. "
            "Map logic.action to your rules runtime; pseudocode and sql_preview are advisory."
        ),
    }


def export_json(rule: dict[str, Any], *, indent: int = 2) -> str:
    return json.dumps(rule_to_export_dict(rule), indent=indent)


def export_yaml(rule: dict[str, Any]) -> str:
    if yaml is None:
        raise RuntimeError("PyYAML not installed; use format=json or pip install pyyaml")
    return yaml.dump(rule_to_export_dict(rule), default_flow_style=False, sort_keys=False)

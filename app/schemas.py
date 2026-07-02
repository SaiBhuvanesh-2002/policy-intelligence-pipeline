"""Pydantic schemas for the Policy Intelligence Pipeline domain model."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    cms_bulletin = "cms_bulletin"
    payer_policy = "payer_policy"
    code_set = "code_set"
    contract = "contract"
    clinical_guideline = "clinical_guideline"


class ReviewStatus(str, Enum):
    pending = "pending"          # waiting for SME
    approved = "approved"        # signed off, ready to deploy
    rejected = "rejected"        # SME declined
    changes_requested = "changes_requested"


class RuleAction(str, Enum):
    deny_line = "deny_line"
    deny_claim = "deny_claim"
    pend_for_review = "pend_for_review"
    adjust_units = "adjust_units"
    require_modifier = "require_modifier"
    require_documentation = "require_documentation"
    informational = "informational"


class Severity(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


# ---------------------------------------------------------------------------
# Documents & versions
# ---------------------------------------------------------------------------
class PolicyDocument(BaseModel):
    id: int
    source_type: SourceType
    source_name: str
    title: str
    url: Optional[str] = None
    created_at: datetime


class PolicyVersion(BaseModel):
    id: int
    document_id: int
    version_label: str
    effective_date: Optional[str] = None
    raw_text: str
    summary: Optional[str] = None
    key_points: list[str] = Field(default_factory=list)
    created_at: datetime


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------
class PolicyChange(BaseModel):
    section: str
    change_type: str            # added | removed | modified
    old_text: Optional[str] = None
    new_text: Optional[str] = None
    significance: Severity
    impact_summary: str


class ChangeReport(BaseModel):
    document_id: int
    from_version_id: int
    to_version_id: int
    changes: list[PolicyChange]
    headline: str


# ---------------------------------------------------------------------------
# Draft rules / payment-integrity edits
# ---------------------------------------------------------------------------
class RuleLogic(BaseModel):
    """A structured, executable representation of a payment-integrity edit."""
    when_procedure_codes: list[str] = Field(default_factory=list)
    when_diagnosis_codes: list[str] = Field(default_factory=list)
    when_modifiers: list[str] = Field(default_factory=list)
    unless_modifiers: list[str] = Field(default_factory=list)
    same_date_of_service: bool = False
    max_units: Optional[int] = None
    effective_date: Optional[str] = None
    action: RuleAction = RuleAction.pend_for_review
    pseudocode: str = ""
    sql_preview: str = ""


class DraftRule(BaseModel):
    id: int
    version_id: int
    title: str
    rationale: str
    citation: str
    severity: Severity
    confidence: float
    edit_type: str              # prepay | postpay
    logic: RuleLogic
    review_status: ReviewStatus
    sme_name: Optional[str] = None
    sme_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
class AuditEntry(BaseModel):
    id: int
    actor: str
    action: str
    detail: str
    created_at: datetime


# ---------------------------------------------------------------------------
# API request bodies
# ---------------------------------------------------------------------------
class ReviewDecision(BaseModel):
    decision: ReviewStatus
    sme_name: str = "SME"
    sme_notes: str = ""


class IngestRequest(BaseModel):
    source_type: SourceType
    source_name: str
    title: str
    version_label: str
    raw_text: str
    url: Optional[str] = None
    effective_date: Optional[str] = None


class PipelineResult(BaseModel):
    document_id: int
    version_id: int
    summary: str
    key_points: list[str]
    change_report: Optional[ChangeReport] = None
    draft_rules: list[DraftRule] = Field(default_factory=list)

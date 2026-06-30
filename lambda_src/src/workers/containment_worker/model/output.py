"""
output.py — ContainmentOutput, ActionResult, AuditRecord.

All output returned to Step Functions and written to S3/DynamoDB.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any


# ---------------------------------------------------------------------------
# Action results — result of each execution mode
# ---------------------------------------------------------------------------

@dataclass
class DryRunResult:
    """Simulate result — does not actually do anything."""
    would_execute_service: str
    would_execute_method: str
    would_execute_parameters: dict[str, Any] = field(default_factory=dict)
    simulation_note: str = "dry-run: no AWS API call made"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaggingResult:
    """Result of tagging a resource."""
    resource_id: str
    tags_applied: dict[str, str] = field(default_factory=dict)
    boto3_http_status: int = 0
    boto3_request_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SuggestionRecord:
    """Suggestion record sent to Engineering/Finance for review."""
    anomaly_id: str
    resource_id: str
    recommended_action: str
    explanation: str
    route_target: str               # "finance" | "engineering"
    approval_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ApplyResult:
    """Result of executing action on a non-prod resource."""
    resource_id: str
    action_executed: str
    boto3_http_status: int = 0
    boto3_request_id: str = ""
    execution_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeniedActionRecord:
    """Record when action is denied."""
    reason: str                     # "prod_boundary" | "approval_denied" | "low_confidence"
    original_execution_mode: str
    original_environment: str
    denial_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RollbackResult:
    """Result of executing rollback from DynamoDB cache."""
    anomaly_id: str
    rollback_service: str
    rollback_method: str
    boto3_http_status: int = 0
    boto3_request_id: str = ""
    rollback_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Audit record — written to S3 Object Lock
# ---------------------------------------------------------------------------

@dataclass
class AuditChain:
    """Cryptographic chain link for tamper-evidence."""
    audit_id: str
    event_hash: str
    previous_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditRecord:
    """
    Audit record written to S3 Object Lock.
    Schema per 03_security_design.md §5.1.
    Written BEFORE action execution, updated AFTER.
    """
    actor: str
    timestamp: str
    correlation_id: str
    anomaly_id: str
    run_id: str
    resource_owner: str
    resource_id: str
    account_id: str
    environment: str
    execution_mode: str
    original_execution_mode: str
    approval_status: str
    data_confidence: str

    before_state: dict[str, Any] = field(default_factory=dict)
    proposed_after_state: dict[str, Any] = field(default_factory=dict)
    rollback_path: dict[str, Any] = field(default_factory=dict)

    action_result: dict[str, Any] = field(default_factory=dict)
    rollback_status: str = "pending"
    rollback_executed_at: str = ""

    retention_location: str = ""
    retention_period_days: int = 90
    audit_chain: dict[str, Any] = field(default_factory=dict)

    def compute_hash(self, previous_hash: str = "") -> str:
        """Compute SHA256 hash of record + previous_hash for audit chain."""
        payload = json.dumps(self.to_dict(), sort_keys=True, default=str)
        content = payload + previous_hash
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor": self.actor,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "anomaly_id": self.anomaly_id,
            "run_id": self.run_id,
            "resource_owner": self.resource_owner,
            "resource_id": self.resource_id,
            "account_id": self.account_id,
            "environment": self.environment,
            "execution_mode": self.execution_mode,
            "original_execution_mode": self.original_execution_mode,
            "approval_status": self.approval_status,
            "data_confidence": self.data_confidence,
            "before_state": self.before_state,
            "proposed_after_state": self.proposed_after_state,
            "rollback_path": self.rollback_path,
            "action_result": self.action_result,
            "rollback_status": self.rollback_status,
            "rollback_executed_at": self.rollback_executed_at,
            "retention_location": self.retention_location,
            "retention_period_days": self.retention_period_days,
            "audit_chain": self.audit_chain,
        }


# ---------------------------------------------------------------------------
# Main output type — returned to Step Functions
# ---------------------------------------------------------------------------

@dataclass
class ContainmentOutput:
    """
    Output returned to Step Functions after containment completes.
    Step Functions uses this output to call /v1/verify next.
    """
    run_id: str
    anomaly_id: str
    correlation_id: str
    status: str                         # "completed" | "dry-run" | "denied" | "failed"
    execution_mode_applied: str

    audit_record_id: str = ""
    audit_record_s3_uri: str = ""

    dry_run_result: dict[str, Any] = field(default_factory=dict)
    tagging_result: dict[str, Any] = field(default_factory=dict)
    suggestion_record: dict[str, Any] = field(default_factory=dict)
    apply_result: dict[str, Any] = field(default_factory=dict)
    denied_action_record: dict[str, Any] = field(default_factory=dict)
    rollback_result: dict[str, Any] = field(default_factory=dict)

    before_state: dict[str, Any] = field(default_factory=dict)
    proposed_after_state: dict[str, Any] = field(default_factory=dict)
    rollback_path: dict[str, Any] = field(default_factory=dict)

    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "run_id": self.run_id,
            "anomaly_id": self.anomaly_id,
            "correlation_id": self.correlation_id,
            "status": self.status,
            "execution_mode_applied": self.execution_mode_applied,
            "audit_record_id": self.audit_record_id,
            "audit_record_s3_uri": self.audit_record_s3_uri,
            "before_state": self.before_state,
            "proposed_after_state": self.proposed_after_state,
            "rollback_path": self.rollback_path,
        }
        if self.dry_run_result:
            d["dry_run_result"] = self.dry_run_result
        if self.tagging_result:
            d["tagging_result"] = self.tagging_result
        if self.suggestion_record:
            d["suggestion_record"] = self.suggestion_record
        if self.apply_result:
            d["apply_result"] = self.apply_result
        if self.denied_action_record:
            d["denied_action_record"] = self.denied_action_record
        if self.rollback_result:
            d["rollback_result"] = self.rollback_result
        if self.errors:
            d["errors"] = self.errors
        return d

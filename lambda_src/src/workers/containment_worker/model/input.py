"""
input.py — ContainmentInput and related types.

Input received from Step Functions after /v1/decide returns action plan.
This Lambda does NOT call the AI Engine — it only receives the result and executes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Execution modes
# ---------------------------------------------------------------------------

MODE_DRY_RUN = "dry-run"
MODE_TAG = "tag"
MODE_SUGGEST = "suggest"
MODE_APPLY = "apply"

VALID_EXECUTION_MODES = {MODE_DRY_RUN, MODE_TAG, MODE_SUGGEST, MODE_APPLY}

# Environments — determines containment strategy
PROD_ENVS = {"prod", "prod-core", "prod-payments"}
NON_PROD_ENVS = {"staging", "dev", "sandbox", "ml-research", "data-analytics"}

# Approval statuses
APPROVAL_APPROVED = "approved"
APPROVAL_PENDING = "pending"
APPROVAL_DENIED = "denied"

# Data confidence
DATA_CONFIDENCE_HIGH = "HIGH"
DATA_CONFIDENCE_LOW = "LOW"


# ---------------------------------------------------------------------------
# Boto3 equivalent payload — from /v1/decide rollback_payload.boto3_equivalent
# ---------------------------------------------------------------------------

@dataclass
class Boto3Payload:
    """
    Boto3 payload to execute or rollback action.
    From DecideResponse.applied_payload or rollback_payload.boto3_equivalent.
    """
    service: str        # "ec2", "rds", "sagemaker", "servicequotas"
    method: str         # "stop_instances", "create_tags", "stop_db_instance"
    parameters: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Boto3Payload":
        return cls(
            service=d["service"],
            method=d["method"],
            parameters=d.get("parameters", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "method": self.method,
            "parameters": self.parameters,
        }


# ---------------------------------------------------------------------------
# Audit writer config — S3 + DynamoDB targets for audit records
# ---------------------------------------------------------------------------

@dataclass
class AuditWriterConfig:
    """Storage target configuration for audit records."""
    audit_bucket: str           # company-cdo-{account_id}-telemetry
    audit_prefix: str           # "audit/"
    dashboard_table: str        # DynamoDB Dashboard Cache table name
    rollback_cache_table: str   # finops-rollback-cache table name

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AuditWriterConfig":
        return cls(
            audit_bucket=d["audit_bucket"],
            audit_prefix=d.get("audit_prefix", "audit/"),
            dashboard_table=d["dashboard_table"],
            rollback_cache_table=d["rollback_cache_table"],
        )


# ---------------------------------------------------------------------------
# Main input type
# ---------------------------------------------------------------------------

@dataclass
class ContainmentInput:
    """
    Payload from Step Functions — result after /v1/decide.

    Step Functions passes the full AI decision + context here.
    Lambda only needs to read and execute according to policy.
    """
    # --- AI decision fields (from /v1/decide response) ---
    run_id: str
    anomaly_id: str
    correlation_id: str
    model_version: str
    anomaly_type: str
    confidence: float
    severity: str
    explanation: str
    data_confidence: str            # HIGH | LOW — if LOW, force dry-run

    # --- Resource context ---
    resource_id: str
    resource_owner: str
    account_id: str
    environment: str
    containment_role_name: str
    external_id: str

    # --- Policy inputs ---
    execution_mode: str
    approval_status: str
    recommended_containment_mode: str

    # --- Boto3 payloads from /v1/decide ---
    applied_payload: Boto3Payload
    rollback_payload: Boto3Payload

    # --- Audit config ---
    audit_config: AuditWriterConfig

    # --- Optional fields ---
    tenant_id: str = ""
    evidence_uri: str = ""
    cost_window_start: str = ""
    cost_window_end: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ContainmentInput":
        return cls(
            run_id=d["run_id"],
            anomaly_id=d["anomaly_id"],
            correlation_id=d["correlation_id"],
            model_version=d.get("model_version", "unknown"),
            anomaly_type=d.get("anomaly_type", "unknown"),
            confidence=float(d.get("confidence", 0.0)),
            severity=d.get("severity", "medium"),
            explanation=d.get("explanation", ""),
            data_confidence=d.get("data_confidence", DATA_CONFIDENCE_HIGH),
            resource_id=d["resource_id"],
            resource_owner=d.get("resource_owner", ""),
            account_id=d["account_id"],
            environment=d["environment"],
            containment_role_name=d["containment_role_name"],
            external_id=d.get("external_id", ""),
            execution_mode=d["execution_mode"],
            approval_status=d.get("approval_status", APPROVAL_PENDING),
            recommended_containment_mode=d.get("recommended_containment_mode", "tag-for-review"),
            applied_payload=Boto3Payload.from_dict(d["applied_payload"]),
            rollback_payload=Boto3Payload.from_dict(d["rollback_payload"]),
            audit_config=AuditWriterConfig.from_dict(d["audit_config"]),
            tenant_id=d.get("tenant_id", ""),
            evidence_uri=d.get("evidence_uri", ""),
            cost_window_start=d.get("cost_window_start", ""),
            cost_window_end=d.get("cost_window_end", ""),
        )

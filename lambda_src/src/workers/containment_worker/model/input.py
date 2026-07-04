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
        # Support both nested Step Functions context and flat dict formats.
        # SFN passes the full state context: anomaly fields are under d["anomaly"],
        # AI response under d["ai_decide_response"], policy under d["account_policy"],
        # and containment mode under d["ai"]["recommended_containment_mode"].

        # --- Resolve anomaly sub-object ---
        anomaly = d.get("anomaly", {})
        ai_decide = d.get("ai_decide_response", {})
        ai_summary = d.get("ai", {})
        account_policy = d.get("account_policy", {})

        # anomaly_id: flat key preferred, fallback to nested
        anomaly_id = d.get("anomaly_id") or anomaly.get("anomaly_id", "")
        resource_id = d.get("resource_id") or anomaly.get("resource_id", "")
        anomaly_type = d.get("anomaly_type") or anomaly.get("anomaly_type", "unknown")
        severity = d.get("severity") or anomaly.get("severity", "medium")
        environment = d.get("environment") or account_policy.get("environment", "sandbox")
        account_id = d.get("account_id") or account_policy.get("account_id", "")

        # recommended_containment_mode: flat > ai summary > ai_decide action_plan
        recommended_containment_mode = (
            d.get("recommended_containment_mode")
            or ai_summary.get("recommended_containment_mode")
            or (ai_decide.get("action_plan") or [{}])[0].get("action", "tag-for-review")
        )

        # applied_payload: flat > ai_decide.applied_payload
        # The AI Engine returns applied_payload as {"action_type": ..., "aws_cli_command": ...}
        # but Boto3Payload.from_dict expects {"service", "method", "parameters"}.
        # Build a compatible Boto3Payload from whatever is available.
        raw_applied = d.get("applied_payload") or ai_decide.get("applied_payload", {})
        raw_rollback = d.get("rollback_payload") or ai_decide.get("rollback_payload", {})

        def _to_boto3_payload(raw: dict[str, Any]) -> Boto3Payload:
            """Coerce AI Engine applied/rollback payload to Boto3Payload format."""
            if "service" in raw and "method" in raw:
                return Boto3Payload.from_dict(raw)
            # AI Engine returns action_type + aws_cli_command format; wrap it.
            return Boto3Payload(
                service=raw.get("action_type", "unknown"),
                method=raw.get("aws_cli_command", raw.get("aws_cli_rollback_command", "unknown")),
                parameters=raw,
            )

        # audit_config: flat > synthesise from SFN environment variables
        raw_audit = d.get("audit_config") or {}
        if not raw_audit:
            import os
            raw_audit = {
                "audit_bucket": os.environ.get("AUDIT_BUCKET_NAME", ""),
                "audit_prefix": "audit/",
                "dashboard_table": os.environ.get("DASHBOARD_CACHE_TABLE") or os.environ.get("DASHBOARD_VIEWS_TABLE_NAME", ""),
                "rollback_cache_table": os.environ.get("ROLLBACK_CACHE_TABLE") or os.environ.get("ROLLBACK_CACHE_TABLE_NAME", ""),
            }

        return cls(
            run_id=d.get("run_id", ""),
            anomaly_id=anomaly_id,
            correlation_id=d.get("correlation_id", ""),
            model_version=d.get("model_version", "unknown"),
            anomaly_type=anomaly_type,
            confidence=float(d.get("confidence") or anomaly.get("confidence_score", 0.0)),
            severity=severity,
            explanation=d.get("explanation", ""),
            data_confidence=d.get("data_confidence", DATA_CONFIDENCE_HIGH),
            resource_id=resource_id,
            resource_owner=d.get("resource_owner") or anomaly.get("responsible_team", ""),
            account_id=account_id,
            environment=environment,
            containment_role_name=d.get("containment_role_name", ""),
            external_id=d.get("external_id", ""),
            execution_mode=d.get("execution_mode", MODE_TAG),
            approval_status=d.get("approval_status", APPROVAL_PENDING),
            recommended_containment_mode=recommended_containment_mode,
            applied_payload=_to_boto3_payload(raw_applied),
            rollback_payload=_to_boto3_payload(raw_rollback),
            audit_config=AuditWriterConfig.from_dict(raw_audit),
            tenant_id=d.get("tenant_id", ""),
            evidence_uri=d.get("evidence_uri", ""),
            cost_window_start=d.get("cost_window_start", ""),
            cost_window_end=d.get("cost_window_end", ""),
        )

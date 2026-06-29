import dataclasses
from typing import Optional, Any, Dict

@dataclasses.dataclass
class AccountPolicy:
    account_id: str = ""
    environment: str = ""

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> Optional["AccountPolicy"]:
        if not d:
            return None
        return cls(
            account_id=d.get("account_id", ""),
            environment=d.get("environment", "")
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "environment": self.environment
        }

@dataclasses.dataclass
class CURRetryInfo:
    count: int = 0
    max: int = 0

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> Optional["CURRetryInfo"]:
        if not d:
            return None
        return cls(
            count=d.get("count", 0),
            max=d.get("max", 0)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "max": self.max
        }

@dataclasses.dataclass
class ErrorDetails:
    error: str = ""
    cause: str = ""

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> Optional["ErrorDetails"]:
        if not d:
            return None
        # Note: Go uses capitalized Error and Cause keys in JSON
        return cls(
            error=d.get("Error", d.get("error", "")),
            cause=d.get("Cause", d.get("cause", ""))
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Error": self.error,
            "Cause": self.cause
        }

@dataclasses.dataclass
class Response:
    status: str = ""
    run_id: str = ""
    correlation_id: str = ""
    worker: str = ""
    raw_data_uri: Optional[str] = None
    curated_data_uri: Optional[str] = None
    required_fields_valid: Optional[bool] = None
    anomaly_found: Optional[bool] = None
    recommended_containment_mode: Optional[str] = None
    anomaly_id: Optional[str] = None
    severity: Optional[str] = None
    confidence: Optional[float] = None
    execution_mode: Optional[str] = None
    containment_status: Optional[str] = None
    audit_id: Optional[str] = None
    audit_uri: Optional[str] = None
    route_target: Optional[str] = None
    tenant_id: Optional[str] = None
    is_ad_hoc: Optional[bool] = None
    operation: Optional[str] = None
    payload_sha256: Optional[str] = None
    request_timestamp: Optional[str] = None
    telemetry_quality: Optional[float] = None
    force_dry_run: Optional[bool] = None
    details: Dict[str, Any] = dataclasses.field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> Optional["Response"]:
        if not d:
            return None
        return cls(
            status=d.get("status", ""),
            run_id=d.get("run_id", ""),
            correlation_id=d.get("correlation_id", ""),
            worker=d.get("worker", ""),
            raw_data_uri=d.get("raw_data_uri"),
            curated_data_uri=d.get("curated_data_uri"),
            required_fields_valid=d.get("required_fields_valid"),
            anomaly_found=d.get("anomaly_found"),
            recommended_containment_mode=d.get("recommended_containment_mode"),
            anomaly_id=d.get("anomaly_id"),
            severity=d.get("severity"),
            # khanh fix: FormatDecideResult trong statemachine gửi key "confidence_score", không phải "confidence"
            confidence=d.get("confidence") or d.get("confidence_score"),
            execution_mode=d.get("execution_mode") or d.get("execution_mode_applied"),
            containment_status=d.get("containment_status") or d.get("status"),
            audit_id=d.get("audit_id"),
            audit_uri=d.get("audit_uri"),
            route_target=d.get("route_target"),
            tenant_id=d.get("tenant_id"),
            is_ad_hoc=d.get("is_ad_hoc"),
            operation=d.get("operation"),
            payload_sha256=d.get("payload_sha256"),
            request_timestamp=d.get("request_timestamp"),
            telemetry_quality=d.get("telemetry_quality"),
            force_dry_run=d.get("force_dry_run"),
            details=d.get("details", {})
        )

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "status": self.status,
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "worker": self.worker,
            "details": self.details
        }
        if self.raw_data_uri is not None:
            d["raw_data_uri"] = self.raw_data_uri
        if self.curated_data_uri is not None:
            d["curated_data_uri"] = self.curated_data_uri
        if self.required_fields_valid is not None:
            d["required_fields_valid"] = self.required_fields_valid
        if self.anomaly_found is not None:
            d["anomaly_found"] = self.anomaly_found
        if self.recommended_containment_mode is not None:
            d["recommended_containment_mode"] = self.recommended_containment_mode
        if self.anomaly_id is not None:
            d["anomaly_id"] = self.anomaly_id
        if self.severity is not None:
            d["severity"] = self.severity
        if self.confidence is not None:
            d["confidence"] = self.confidence
        if self.execution_mode is not None:
            d["execution_mode"] = self.execution_mode
        if self.containment_status is not None:
            d["containment_status"] = self.containment_status
        if self.audit_id is not None:
            d["audit_id"] = self.audit_id
        if self.audit_uri is not None:
            d["audit_uri"] = self.audit_uri
        if self.route_target is not None:
            d["route_target"] = self.route_target
        if self.tenant_id is not None:
            d["tenant_id"] = self.tenant_id
        if self.is_ad_hoc is not None:
            d["is_ad_hoc"] = self.is_ad_hoc
        if self.operation is not None:
            d["operation"] = self.operation
        if self.payload_sha256 is not None:
            d["payload_sha256"] = self.payload_sha256
        if self.request_timestamp is not None:
            d["request_timestamp"] = self.request_timestamp
        if self.telemetry_quality is not None:
            d["telemetry_quality"] = self.telemetry_quality
        if self.force_dry_run is not None:
            d["force_dry_run"] = self.force_dry_run
        return d

@dataclasses.dataclass
class Event:
    run_id: str = ""
    correlation_id: str = ""
    account_id: str = ""
    cost_period: str = ""
    billing_period: str = ""
    execution_date: str = ""
    environment: str = ""
    source_data_version: str = ""
    ai_contract_version: str = ""
    approval_status: str = ""
    action: str = ""
    tenant_id: str = ""
    is_ad_hoc: bool = False
    operation: str = ""
    payload_sha256: str = ""
    request_timestamp: str = ""
    telemetry_quality: float = 0.0
    audit_id: str = ""
    force_dry_run: bool = False

    cur_retry: Optional[CURRetryInfo] = None
    account_policy: Optional[AccountPolicy] = None
    state: Optional[Response] = None
    ingestion: Optional[Response] = None
    normalized: Optional[Response] = None
    ai: Optional[Response] = None
    alert: Optional[Response] = None
    containment: Optional[Response] = None

    error: Optional[ErrorDetails] = None
    alert_error: Optional[ErrorDetails] = None
    containment_error: Optional[ErrorDetails] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        return cls(
            run_id=d.get("run_id", ""),
            correlation_id=d.get("correlation_id", ""),
            account_id=d.get("account_id", ""),
            cost_period=d.get("cost_period", ""),
            billing_period=d.get("billing_period", ""),
            execution_date=d.get("execution_date", ""),
            environment=d.get("environment", ""),
            source_data_version=d.get("source_data_version", ""),
            ai_contract_version=d.get("ai_contract_version", ""),
            approval_status=d.get("approval_status", ""),
            action=d.get("action", ""),
            tenant_id=d.get("tenant_id", ""),
            is_ad_hoc=d.get("is_ad_hoc", False),
            operation=d.get("operation", ""),
            payload_sha256=d.get("payload_sha256", ""),
            request_timestamp=d.get("request_timestamp", ""),
            telemetry_quality=d.get("telemetry_quality", 0.0),
            audit_id=d.get("audit_id", ""),
            force_dry_run=d.get("force_dry_run", False),
            cur_retry=CURRetryInfo.from_dict(d.get("cur_retry")),
            account_policy=AccountPolicy.from_dict(d.get("account_policy")),
            state=Response.from_dict(d.get("state")),
            ingestion=Response.from_dict(d.get("ingestion")),
            normalized=Response.from_dict(d.get("normalized")),
            ai=Response.from_dict(d.get("ai")),
            alert=Response.from_dict(d.get("alert")),
            containment=Response.from_dict(d.get("containment")),
            error=ErrorDetails.from_dict(d.get("error")),
            alert_error=ErrorDetails.from_dict(d.get("alert_error")),
            containment_error=ErrorDetails.from_dict(d.get("containment_error"))
        )

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "account_id": self.account_id,
            "cost_period": self.cost_period,
            "billing_period": self.billing_period,
            "execution_date": self.execution_date,
            "environment": self.environment,
            "source_data_version": self.source_data_version,
            "ai_contract_version": self.ai_contract_version,
            "approval_status": self.approval_status,
            "action": self.action,
            "tenant_id": self.tenant_id,
            "is_ad_hoc": self.is_ad_hoc,
            "operation": self.operation,
            "payload_sha256": self.payload_sha256,
            "request_timestamp": self.request_timestamp,
            "telemetry_quality": self.telemetry_quality,
            "audit_id": self.audit_id,
            "force_dry_run": self.force_dry_run,
        }
        if self.cur_retry is not None:
            d["cur_retry"] = self.cur_retry.to_dict()
        if self.account_policy is not None:
            d["account_policy"] = self.account_policy.to_dict()
        if self.state is not None:
            d["state"] = self.state.to_dict()
        if self.ingestion is not None:
            d["ingestion"] = self.ingestion.to_dict()
        if self.normalized is not None:
            d["normalized"] = self.normalized.to_dict()
        if self.ai is not None:
            d["ai"] = self.ai.to_dict()
        if self.alert is not None:
            d["alert"] = self.alert.to_dict()
        if self.containment is not None:
            d["containment"] = self.containment.to_dict()
        if self.error is not None:
            d["error"] = self.error.to_dict()
        if self.alert_error is not None:
            d["alert_error"] = self.alert_error.to_dict()
        if self.containment_error is not None:
            d["containment_error"] = self.containment_error.to_dict()
        return d

def normalize_event(event: Event) -> Event:
    if not event.cost_period:
        event.cost_period = event.billing_period
    if not event.billing_period:
        event.billing_period = event.cost_period
    if not event.correlation_id:
        event.correlation_id = event.run_id
    if not event.source_data_version:
        event.source_data_version = event.ai_contract_version
    if not event.ai_contract_version:
        event.ai_contract_version = event.source_data_version
    if not event.action and event.ai:
        event.action = event.ai.recommended_containment_mode or ""
    return event

def validate_event(event: Event) -> None:
    normalize_event(event)
    if not event.run_id:
        raise ValueError("missing required event field: run_id")
    if not event.correlation_id:
        raise ValueError("missing required event field: correlation_id")
    if not event.cost_period:
        raise ValueError("missing required event field: cost_period or billing_period")

def create_response(status: str, run_id: str, correlation_id: str, worker: str, details: Optional[Dict[str, Any]] = None) -> Response:
    if details is None:
        details = {}
    return Response(
        status=status,
        run_id=run_id,
        correlation_id=correlation_id,
        worker=worker,
        details=details
    )

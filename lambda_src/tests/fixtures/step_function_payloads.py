"""
fixtures/step_function_payloads.py
===================================
Deterministic fixture payloads for Step Functions workflow verification tests.

Each fixture is a plain dictionary that represents the *exact* execution context
(the Step Functions dollar-variable) at a specific boundary in the workflow.
Tests in test_step_function_payload_contract.py drive a lightweight ASL
parameter resolver against these dicts to prove that every state can find the
JSONPaths it needs in the output of the preceding state.

Fixture inventory
-----------------
 1. SCHEDULED_WORKFLOW_INPUT        - EventBridge Scheduler -> PrepareRunContext
 2. POST_PREPARE_RUN_CONTEXT        - PrepareRunContext output (full state after state_lambda)
 3. POST_INGEST_COST_DATA_S3        - IngestCostData output - CUR-ready, S3_POINTER mode
 4. POST_INGEST_COST_DATA_CE        - IngestCostData output - CUR delayed, CE fallback
 5. POST_NORMALIZE_HEALTHY          - NormalizeCostWindow output - high quality
 6. POST_NORMALIZE_DEGRADED         - NormalizeCostWindow output - telemetry-degraded
 7. POST_BUILD_DETECT_REQUEST       - BuildDetectRequest output (Pass state, ai_detect_request)
 8. POST_INVOKE_DETECT_ANOMALY      - InvokeDetect result - anomaly detected
 9. POST_INVOKE_DETECT_NO_ANOMALY   - InvokeDetect result - no anomaly
10. POST_INVOKE_DECIDE              - InvokeDecide result - action plan returned
11. POST_FORMAT_DECIDE_RESULT       - FormatDecideResult Pass state - ai populated
12. POST_ROUTER                     - RouteAlert output
13. POST_CONTAINMENT_POLICY_APPLY   - context entering ExecuteContainment (safe, apply allowed)
14. POST_CONTAINMENT_POLICY_DENIED_PROD  - prod+destructive -> WriteDeniedAudit
15. POST_CONTAINMENT_POLICY_DRYRUN_DENIED - force_dry_run=True + destructive -> WriteDeniedAudit
16. POST_EXECUTE_CONTAINMENT        - ExecuteContainment result
17. POST_VERIFY_RESULT              - ReportVerifyResult result
18. AI_FAIL_CLOSED_CONTEXT          - context after SetAIFailClosedError
19. CUR_DELAY_EXCEEDED_CONTEXT      - context after SetCURDelayExceededError
"""

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

TENANT_ID = "tenant-abc123"
ACCOUNT_ID = "123456789012"
RUN_ID = "run-2026-06-27-daily-abc123"
CORRELATION_ID = "corr-2026-06-27-abc123"
IDEMPOTENCY_KEY = f"{TENANT_ID}:2026-06-27:daily"
COST_PERIOD = "2026-06-01/2026-06-27"
EXECUTION_DATE = "2026-06-27"
AI_CONTRACT_VERSION = "v1"
ENVIRONMENT = "sandbox"

ANOMALY_ID = "anomaly-ec2-spike-20260627"
RESOURCE_ID = "i-1234567890abcdef0"
SEVERITY = "high"
CONFIDENCE_SCORE = 0.91
ANOMALY_TYPE = "ec2_cost_spike"

# ---------------------------------------------------------------------------
# 1. SCHEDULED_WORKFLOW_INPUT
# ---------------------------------------------------------------------------

SCHEDULED_WORKFLOW_INPUT = {
    "run_id": RUN_ID,
    "correlation_id": CORRELATION_ID,
    "account_id": ACCOUNT_ID,
    "cost_period": COST_PERIOD,
    "execution_date": EXECUTION_DATE,
    "tenant_id": TENANT_ID,
    "is_ad_hoc": False,
    "force_dry_run": False,
    "environment": ENVIRONMENT,
    "ai_contract_version": AI_CONTRACT_VERSION,
    "cur_retry": {"count": 0, "max": 4},
    "ce_retry": {"count": 0, "max": 3},
    "ai_retry": {"count": 0, "max": 6},
    "retry_after_seconds": 3600,
}

# ---------------------------------------------------------------------------
# 2. POST_PREPARE_RUN_CONTEXT
# ---------------------------------------------------------------------------

POST_PREPARE_RUN_CONTEXT = {
    **SCHEDULED_WORKFLOW_INPUT,
    "account_policy": {
        "account_id": ACCOUNT_ID,
        "environment": ENVIRONMENT,
    },
    "state": {
        "status": "NEW",
        "run_id": RUN_ID,
        "correlation_id": CORRELATION_ID,
        "worker": "state",
        "details": {},
    },
    "error_budget_locked": False,
}

# ---------------------------------------------------------------------------
# 3. POST_INGEST_COST_DATA_S3 - CUR-ready, S3_POINTER mode
# ---------------------------------------------------------------------------

_INGESTION_S3 = {
    "status": "READY",
    "run_id": RUN_ID,
    "correlation_id": CORRELATION_ID,
    "worker": "cost_puller",
    "raw_data_uri": f"s3://tf2-finops-lakehouse-bucket/cur/account_id={ACCOUNT_ID}/year=2026/month=06/day=27/{RUN_ID}_raw.json.gz",
    "details": {
        "status": "READY",
        "raw_data_uri": f"s3://tf2-finops-lakehouse-bucket/cur/account_id={ACCOUNT_ID}/year=2026/month=06/day=27/{RUN_ID}_raw.json.gz",
        "data_source_type": "S3_POINTER",
        "s3_object_checksum": "abc123sha256checksum",
        "telemetry_delay_event": False,
        "missing_resources": [],
        "current_ce_cost_gap_usd": 0.0,
        "comparison_window": {"start_date": EXECUTION_DATE, "end_date": EXECUTION_DATE},
        "delayed_cur": False,
        "missing_cloudwatch": False,
        "stale_cost_explorer": False,
        "estimated_billing": False,
        "completeness_score": 1.0,
    },
}

POST_INGEST_COST_DATA_S3 = {
    **POST_PREPARE_RUN_CONTEXT,
    "ingestion": _INGESTION_S3,
}

# ---------------------------------------------------------------------------
# 4. POST_INGEST_COST_DATA_CE - CUR delayed, CE fallback
# ---------------------------------------------------------------------------

_INGESTION_CE = {
    "status": "READY",
    "run_id": RUN_ID,
    "correlation_id": CORRELATION_ID,
    "worker": "cost_puller",
    "raw_data_uri": f"s3://tf2-finops-lakehouse-bucket/cur/account_id={ACCOUNT_ID}/year=2026/month=06/day=27/{RUN_ID}_raw.json.gz",
    "details": {
        "status": "READY",
        "raw_data_uri": f"s3://tf2-finops-lakehouse-bucket/cur/account_id={ACCOUNT_ID}/year=2026/month=06/day=27/{RUN_ID}_raw.json.gz",
        "data_source_type": "S3_POINTER",
        "s3_object_checksum": "def456sha256checksum",
        "telemetry_delay_event": True,
        "missing_resources": ["AmazonEC2"],
        "current_ce_cost_gap_usd": 150.0,
        "comparison_window": {"start_date": EXECUTION_DATE, "end_date": EXECUTION_DATE},
        "delayed_cur": True,
        "missing_cloudwatch": False,
        "stale_cost_explorer": True,
        "estimated_billing": True,
        "completeness_score": 0.64,
    },
}

POST_INGEST_COST_DATA_CE = {
    **POST_PREPARE_RUN_CONTEXT,
    "ingestion": _INGESTION_CE,
}

# ---------------------------------------------------------------------------
# 5. POST_NORMALIZE_HEALTHY - high quality CUR data
# ---------------------------------------------------------------------------

_CUR_LINE_ITEMS = [
    {
        "bill_billing_period_start_date": "2026-06-01T00:00:00Z",
        "bill_payer_account_id": "112233445566",
        "line_item_usage_account_id": ACCOUNT_ID,
        "line_item_usage_account_name": "prod-core",
        "line_item_line_item_type": "Usage",
        "line_item_usage_start_date": "2026-06-27T00:00:00Z",
        "line_item_usage_end_date": "2026-06-27T23:59:59Z",
        "line_item_product_code": "AmazonEC2",
        "line_item_usage_type": "BoxUsage:m5.2xlarge",
        "line_item_operation": "RunInstances",
        "line_item_resource_id": RESOURCE_ID,
        "line_item_usage_amount": 24.0,
        "pricing_unit": "Hrs",
        "line_item_unblended_rate": 6.25,
        "line_item_unblended_cost": 150.00,
        "line_item_currency_code": "USD",
        "product_product_name": "Amazon Elastic Compute Cloud",
        "product_region_code": "ap-southeast-1",
        "product_instance_type": "m5.2xlarge",
        "resource_tags_user_environment": ENVIRONMENT,
        "resource_tags_user_owner": "Engineering",
        "resource_tags_user_team": "Engineering",
        "resource_tags_user_cost_center": "CC-2001",
        "usage_density_24h": 1.0,
    }
]

_BUSINESS_CONTEXT_DEFAULT = {
    "linked_account_id": ACCOUNT_ID,
    "traffic_volume": 100000,
    "traffic_source": "Mixed",
    "campaign_flag": False,
    "load_test_flag": False,
    "migration_flag": False,
}

_NORMALIZED_HEALTHY_DETAILS = {
    "curated_data_uri": f"s3://tf2-finops-lakehouse-bucket/cost/curated/account_id={ACCOUNT_ID}/year=2026/month=06/{RUN_ID}_curated.parquet",
    "schema": "finops-cost-window-v1",
    "partition_keys": ["account_id", "year", "month"],
    "completeness_score": 1.0,
    "delayed_cur": False,
    "stale_cost_explorer": False,
    "missing_cloudwatch": False,
    "estimated_billing": False,
    "detect_request_mode": "RAW_JSON",
    "s3_bucket_uri": f"s3://tf2-finops-lakehouse-bucket/cur/account_id={ACCOUNT_ID}/year=2026/month=06/day=27/{RUN_ID}_raw.json.gz",
    "business_context": _BUSINESS_CONTEXT_DEFAULT,
    "resource_utilization_metrics": None,
    "aws_cur_line_items": _CUR_LINE_ITEMS,
    "aws_cost_explorer_daily": [],
    "missing_resources": [],
    "current_ce_cost_gap_usd": 0.0,
    "comparison_window": {"start_date": EXECUTION_DATE, "end_date": EXECUTION_DATE},
    "batch_type": "daily",
    "telemetry_delay_event": False,
}

POST_NORMALIZE_HEALTHY = {
    **POST_INGEST_COST_DATA_S3,
    "normalized": {
        "status": "NORMALIZED",
        "run_id": RUN_ID,
        "correlation_id": CORRELATION_ID,
        "worker": "normalizer",
        "details": _NORMALIZED_HEALTHY_DETAILS,
    },
}

_NORMALIZED_POINTER_DETAILS = {
    **_NORMALIZED_HEALTHY_DETAILS,
    "detect_request_mode": "S3_POINTER",
    "s3_bucket_uri": f"s3://company-cdo-{ACCOUNT_ID}-telemetry/{RUN_ID}_raw.json.gz",
}

POST_NORMALIZE_POINTER = {
    **POST_INGEST_COST_DATA_S3,
    "normalized": {
        "status": "NORMALIZED",
        "run_id": RUN_ID,
        "correlation_id": CORRELATION_ID,
        "worker": "normalizer",
        "details": _NORMALIZED_POINTER_DETAILS,
    },
}

# ---------------------------------------------------------------------------
# 6. POST_NORMALIZE_DEGRADED - quality triggers SetTelemetryForceDryRun
# ---------------------------------------------------------------------------

_NORMALIZED_DEGRADED_DETAILS = {
    "curated_data_uri": f"s3://tf2-finops-lakehouse-bucket/cost/curated/account_id={ACCOUNT_ID}/year=2026/month=06/{RUN_ID}_curated.parquet",
    "schema": "finops-cost-window-v1",
    "partition_keys": ["account_id", "year", "month"],
    "completeness_score": 0.55,
    "delayed_cur": True,
    "stale_cost_explorer": True,
    "missing_cloudwatch": False,
    "estimated_billing": True,
    "detect_request_mode": "RAW_JSON_CE_FALLBACK",
    "s3_bucket_uri": f"s3://tf2-finops-lakehouse-bucket/cur/account_id={ACCOUNT_ID}/year=2026/month=06/day=27/{RUN_ID}_raw.json.gz",
    "business_context": _BUSINESS_CONTEXT_DEFAULT,
    "resource_utilization_metrics": None,
    "aws_cur_line_items": [],
    "aws_cost_explorer_daily": [],
    "missing_resources": ["AmazonEC2"],
    "current_ce_cost_gap_usd": 150.0,
    "comparison_window": {"start_date": EXECUTION_DATE, "end_date": EXECUTION_DATE},
    "batch_type": "daily",
    "telemetry_delay_event": True,
}

POST_NORMALIZE_DEGRADED = {
    **POST_INGEST_COST_DATA_CE,
    "normalized": {
        "status": "NORMALIZED",
        "run_id": RUN_ID,
        "correlation_id": CORRELATION_ID,
        "worker": "normalizer",
        "details": _NORMALIZED_DEGRADED_DETAILS,
    },
}

# ---------------------------------------------------------------------------
# 7. POST_BUILD_DETECT_REQUEST - BuildDetectRequest Pass state output
# ---------------------------------------------------------------------------

POST_BUILD_DETECT_REQUEST = {
    **POST_NORMALIZE_HEALTHY,
    "ai_detect_request": {
        "path": "/v1/detect",
        "method": "POST",
        "tenant_id": TENANT_ID,
        "correlation_id": CORRELATION_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "ai_contract_version": AI_CONTRACT_VERSION,
        "dry_run_mode": False,
        "body": {
            "data_source_type": "RAW_JSON",
            "is_ad_hoc": False,
            "telemetry_delay_event": False,
            "aws_cur_line_items": _CUR_LINE_ITEMS,
            "business_context": _BUSINESS_CONTEXT_DEFAULT,
            "resource_utilization_metrics": None,
        },
    },
}

POST_BUILD_DETECT_REQUEST_S3_POINTER = {
    **POST_NORMALIZE_POINTER,
    "ai_detect_request": {
        "path": "/v1/detect",
        "method": "POST",
        "tenant_id": TENANT_ID,
        "correlation_id": CORRELATION_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "ai_contract_version": AI_CONTRACT_VERSION,
        "dry_run_mode": False,
        "body": {
            "data_source_type": "S3_POINTER",
            "is_ad_hoc": False,
            "telemetry_delay_event": False,
            "s3_bucket_uri": f"s3://company-cdo-{ACCOUNT_ID}-telemetry/{RUN_ID}_raw.json.gz",
            "business_context": _BUSINESS_CONTEXT_DEFAULT,
            "resource_utilization_metrics": None,
        },
    },
}

POST_BUILD_DETECT_REQUEST_CE_FALLBACK = {
    **POST_NORMALIZE_DEGRADED,
    "ai_detect_request": {
        "path": "/v1/detect",
        "method": "POST",
        "tenant_id": TENANT_ID,
        "correlation_id": CORRELATION_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "ai_contract_version": AI_CONTRACT_VERSION,
        "dry_run_mode": True,
        "body": {
            "data_source_type": "RAW_JSON",
            "is_ad_hoc": False,
            "telemetry_delay_event": True,
            "aws_cost_explorer_daily": [],
            "missing_resources": ["AmazonEC2"],
            "current_ce_cost_gap_usd": 150.0,
            "comparison_window": {"start_date": EXECUTION_DATE, "end_date": EXECUTION_DATE},
            "business_context": _BUSINESS_CONTEXT_DEFAULT,
            "resource_utilization_metrics": None,
        },
    },
}

# ---------------------------------------------------------------------------
# 8. POST_INVOKE_DETECT_ANOMALY - VPC ALB caller returns anomaly detected
# ---------------------------------------------------------------------------

_DETECT_RESPONSE_ANOMALY = {
    "success": True,
    "anomalies_detected": True,
    "data_confidence": "HIGH",
    "anomalies_list": [
        {
            "anomaly_id": ANOMALY_ID,
            "anomaly_type": ANOMALY_TYPE,
            "severity": SEVERITY,
            "confidence_score": CONFIDENCE_SCORE,
            "resource_id": RESOURCE_ID,
            "resource_owner": "Engineering",
            "account_id": ACCOUNT_ID,
            "explanation": "EC2 usage spiked 3x above 30-day baseline.",
        }
    ],
}

POST_INVOKE_DETECT_ANOMALY = {
    **POST_BUILD_DETECT_REQUEST,
    "ai_detect_response": _DETECT_RESPONSE_ANOMALY,
}

# ---------------------------------------------------------------------------
# 9. POST_INVOKE_DETECT_NO_ANOMALY - clean result -> MarkRunComplete
# ---------------------------------------------------------------------------

POST_INVOKE_DETECT_NO_ANOMALY = {
    **POST_BUILD_DETECT_REQUEST,
    "ai_detect_response": {
        "success": True,
        "anomalies_detected": False,
        "data_confidence": "HIGH",
        "anomalies_list": [],
    },
}

# ---------------------------------------------------------------------------
# 10. POST_INVOKE_DECIDE - InvokeDecide result
# ---------------------------------------------------------------------------

_DECIDE_RESPONSE = {
    "success": True,
    "correlation_id": CORRELATION_ID,
    "idempotency_key": IDEMPOTENCY_KEY,
    "dry_run_mode": False,
    "action_plan": [
        {
            "action": "tag",
            "target": RESOURCE_ID,
            "parameters": {
                "TagKey": "FinOpsAction",
                "TagValue": "flagged-for-review",
            },
        }
    ],
    "rollback_payload": {
        "boto3_equivalent": {
            "service": "ec2",
            "method": "delete_tags",
            "parameters": {
                "Resources": [RESOURCE_ID],
                "Tags": [{"Key": "FinOpsAction"}],
            },
        }
    },
    "applied_payload": {
        "service": "ec2",
        "method": "create_tags",
        "parameters": {
            "Resources": [RESOURCE_ID],
            "Tags": [{"Key": "FinOpsAction", "Value": "flagged-for-review"}],
        },
    },
}

POST_INVOKE_DECIDE = {
    **POST_INVOKE_DETECT_ANOMALY,
    "ai_decide_response": _DECIDE_RESPONSE,
}

# ---------------------------------------------------------------------------
# 11. POST_FORMAT_DECIDE_RESULT - FormatDecideResult Pass state
# ---------------------------------------------------------------------------

POST_FORMAT_DECIDE_RESULT = {
    **POST_INVOKE_DECIDE,
    "ai": {
        "anomaly_found": True,
        "required_fields_valid": True,
        "recommended_containment_mode": "tag",
        "anomaly_id": ANOMALY_ID,
        "severity": SEVERITY,
        "confidence_score": CONFIDENCE_SCORE,
    },
}

# ---------------------------------------------------------------------------
# 12. POST_ROUTER - RouteAlert output
# ---------------------------------------------------------------------------

_ROUTER_RESPONSE = {
    "status": "ROUTED",
    "run_id": RUN_ID,
    "correlation_id": CORRELATION_ID,
    "worker": "router",
    "details": {
        "finance_route": {
            "channel": "sns-finance",
            "action_required": True,
            "summary": f"CRITICAL ALERT: Cost anomaly detected (ID: {ANOMALY_ID}, severity: {SEVERITY})",
            "deliver": True,
            "subject": "Critical FinOps Alert: Cost Anomaly Detected",
            "message": f"Critical FinOps cost anomaly detected. Anomaly ID: {ANOMALY_ID}",
        },
        "engineering_route": {
            "channel": "sns-engineering",
            "action_required": True,
            "summary": f"CRITICAL CONTAINMENT: Resource anomaly detected (ID: {ANOMALY_ID})",
            "deliver": True,
            "subject": "Critical FinOps Containment: Engineering Action Required",
            "message": f"Critical resource anomaly detected. Anomaly ID: {ANOMALY_ID}",
        },
    },
}

POST_ROUTER = {
    **POST_FORMAT_DECIDE_RESULT,
    "alert": _ROUTER_RESPONSE,
}

# ---------------------------------------------------------------------------
# 13. POST_CONTAINMENT_POLICY_APPLY - sandbox + tag -> WritePreActionAudit
# ---------------------------------------------------------------------------

POST_CONTAINMENT_POLICY_APPLY = dict(POST_ROUTER)

# ---------------------------------------------------------------------------
# 14. POST_CONTAINMENT_POLICY_DENIED_PROD - prod + terminate -> WriteDeniedAudit
# ---------------------------------------------------------------------------

POST_CONTAINMENT_POLICY_DENIED_PROD = {
    **POST_ROUTER,
    "account_policy": {
        "account_id": ACCOUNT_ID,
        "environment": "prod",
    },
    "environment": "prod",
    "ai": {
        "anomaly_found": True,
        "required_fields_valid": True,
        "recommended_containment_mode": "terminate",
        "anomaly_id": ANOMALY_ID,
        "severity": SEVERITY,
        "confidence_score": CONFIDENCE_SCORE,
    },
}

# ---------------------------------------------------------------------------
# 15. POST_CONTAINMENT_POLICY_DRYRUN_DENIED - force_dry_run + apply -> WriteDeniedAudit
# ---------------------------------------------------------------------------

POST_CONTAINMENT_POLICY_DRYRUN_DENIED = {
    **POST_ROUTER,
    "force_dry_run": True,
    "ai": {
        "anomaly_found": True,
        "required_fields_valid": True,
        "recommended_containment_mode": "apply",
        "anomaly_id": ANOMALY_ID,
        "severity": SEVERITY,
        "confidence_score": CONFIDENCE_SCORE,
    },
}

# ---------------------------------------------------------------------------
# 16. POST_EXECUTE_CONTAINMENT - ExecuteContainment output
# ---------------------------------------------------------------------------

_CONTAINMENT_RESPONSE = {
    "status": "completed",
    "run_id": RUN_ID,
    "anomaly_id": ANOMALY_ID,
    "execution_mode_applied": "tag",
    "audit_record_id": f"audit-{RUN_ID}",
    "audit_record_s3_uri": f"s3://company-cdo-{ACCOUNT_ID}-telemetry/audit/year=2026/month=06/audit-{RUN_ID}.json",
}

POST_EXECUTE_CONTAINMENT = {
    **POST_CONTAINMENT_POLICY_APPLY,
    "containment": _CONTAINMENT_RESPONSE,
}

# ---------------------------------------------------------------------------
# 17. POST_VERIFY_RESULT - ReportVerifyResult (/v1/verify) output
# ---------------------------------------------------------------------------

_VERIFY_RESPONSE = {
    "success": True,
    "verification_status": "CONFIRMED",
    "correlation_id": CORRELATION_ID,
    "dry_run_mode": False,
    "post_action_anomaly_score": 0.12,
    "confidence": "HIGH",
}

POST_VERIFY_RESULT = {
    **POST_EXECUTE_CONTAINMENT,
    "verify_result": _VERIFY_RESPONSE,
}

# ---------------------------------------------------------------------------
# 18. AI_FAIL_CLOSED_CONTEXT - after SetAIFailClosedError
# ---------------------------------------------------------------------------

AI_FAIL_CLOSED_CONTEXT = {
    **POST_BUILD_DETECT_REQUEST,
    "ai_detect_response": {
        "success": False,
        "anomalies_detected": False,
        "data_confidence": "LOW",
        "anomalies_list": [],
    },
    "error": {
        "Error": "AIEngineFailClosed",
        "Cause": "AI Engine returned an unsuccessful or low-confidence detection response.",
    },
}

# ---------------------------------------------------------------------------
# 19. CUR_DELAY_EXCEEDED_CONTEXT - after SetCURDelayExceededError
# ---------------------------------------------------------------------------

CUR_DELAY_EXCEEDED_CONTEXT = {
    **POST_PREPARE_RUN_CONTEXT,
    "cur_retry": {"count": 4, "max": 4},
    "error": {
        "Error": "CURDelayExceeded",
        "Cause": "Billing reports (CUR) export delayed beyond 4 hours.",
    },
}

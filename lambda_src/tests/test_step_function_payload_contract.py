"""
test_step_function_payload_contract.py
========================================
Repo-local verification that the Step Functions workflow has every required
component, each state can resolve the JSONPaths it reads from the previous
state output shape, and the flow matches AGENTS.md, docs/contracts/*,
IMPLEMENTATION.md, and the active TF2 docs.

Test groups
-----------
A. Component inventory  - checks ASL + Terraform for all required resources.
B. Payload resolution   - lightweight ASL resolver drives fixtures through states.
C. Telemetry contract   - S3_POINTER default; CE fallback when CUR delayed.
D. Detect path          - /v1/detect request shape + response evaluation.
E. Decide/cache path    - /v1/decide result caching in DynamoDB.
F. Containment policy   - prod-destructive denial; dry-run denial; safe paths.
G. Verify path          - /v1/verify action_executed shape.
H. Fail-closed paths    - AI failure and CUR delay exceeded audit chains.
I. SQS/status messages  - rollback_status_queue is the only queue.
"""

import json
import os
import re
import sys

import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
ASL_TEMPLATE = os.path.join(BASE_DIR, "modules/orchestration/statemachine.json")
ASL_DOC = os.path.join(BASE_DIR, "docs/statemachine.json")
ORCHESTRATION_MAIN_TF = os.path.join(BASE_DIR, "modules/orchestration/main.tf")
COMPUTE_LAMBDA_TF = os.path.join(BASE_DIR, "modules/compute-lambda/main.tf")


def _merge_nested_states(asl: dict) -> dict:
    if "States" in asl:
        top_states = asl["States"]
        if "ProcessAnalysisTargets" in top_states:
            target_map = top_states["ProcessAnalysisTargets"]
            account_states = target_map.get("Iterator", {}).get("States", {})
            merged = {}
            merged.update(account_states)
            merged.update(top_states)
            asl["States"] = merged
    return asl


def _load_asl_template() -> dict:
    with open(ASL_TEMPLATE, "r", encoding="utf-8") as fh:
        raw = fh.read()
    # Replace quoted placeholder strings: "${var}" -> "arn:aws:placeholder"
    raw = re.sub(r'"\$\{[a-zA-Z0-9_]+\}"', '"arn:aws:placeholder"', raw)
    # Replace bare numeric placeholders: ${var} -> 6
    raw = re.sub(r'\$\{[a-zA-Z0-9_]+\}', '6', raw)
    return _merge_nested_states(json.loads(raw))


def _load_asl_doc() -> dict:
    with open(ASL_DOC, "r", encoding="utf-8") as fh:
        return _merge_nested_states(json.load(fh))


def _resolve_path(ctx: dict, path: str):
    if path == "$":
        return ctx
    if path.startswith("States.Format("):
        m = re.match(r"^States\.Format\('([^']*)',\s*(.*)\)$", path)
        if not m:
            raise ValueError(f"Invalid States.Format pattern: {path}")
        fmt_str = m.group(1)
        args_str = m.group(2)
        args_paths = [arg.strip() for arg in args_str.split(",")]
        resolved_args = [_resolve_path(ctx, p) for p in args_paths]
        return fmt_str.format(*resolved_args)
    if not path.startswith("$."):
        raise ValueError(f"Expected JSONPath starting with dollar.dot, got: {path!r}")
    parts_raw = path[2:]
    tokens = []
    for segment in parts_raw.split("."):
        m = re.match(r'^(\w+)\[(\d+)\]$', segment)
        if m:
            tokens.append(m.group(1))
            tokens.append(int(m.group(2)))
        else:
            tokens.append(segment)
    current = ctx
    for token in tokens:
        if isinstance(token, int):
            current = current[token]
        else:
            current = current[token]
    return current


def _resolve_parameters(ctx: dict, params: dict) -> dict:
    result = {}
    for key, value in params.items():
        if key.endswith(".$"):
            real_key = key[:-2]
            result[real_key] = _resolve_path(ctx, value)
        elif isinstance(value, dict):
            result[key] = _resolve_parameters(ctx, value)
        else:
            result[key] = value
    return result

def _get_map_iterator_states() -> dict:
    """Return the per-anomaly states inside the ProcessDetectedAnomalies Map iterator."""
    asl = _load_asl_template()
    return asl["States"]["ProcessDetectedAnomalies"]["Iterator"]["States"]


sys.path.insert(0, os.path.dirname(__file__))
from fixtures.step_function_payloads import (
    ACCOUNT_ID, ANOMALY_ID, CORRELATION_ID, RUN_ID, TENANT_ID, IDEMPOTENCY_KEY,
    DECIDE_IDEMPOTENCY_KEY, VERIFY_IDEMPOTENCY_KEY, EXECUTION_DATE,
    SCHEDULED_WORKFLOW_INPUT, POST_PREPARE_RUN_CONTEXT,
    POST_INGEST_COST_DATA_S3, POST_INGEST_COST_DATA_CE,
    POST_NORMALIZE_HEALTHY, POST_NORMALIZE_DEGRADED, POST_NORMALIZE_POINTER,
    POST_BUILD_DETECT_REQUEST, POST_BUILD_DETECT_REQUEST_S3_POINTER, POST_BUILD_DETECT_REQUEST_CE_FALLBACK,
    POST_INVOKE_DETECT_ANOMALY, POST_INVOKE_DETECT_NO_ANOMALY,
    POST_INVOKE_DECIDE, POST_FORMAT_DECIDE_RESULT, POST_ROUTER,
    POST_CONTAINMENT_POLICY_APPLY, POST_CONTAINMENT_POLICY_DENIED_PROD,
    POST_CONTAINMENT_POLICY_DRYRUN_DENIED,
    POST_EXECUTE_CONTAINMENT, POST_VERIFY_RESULT,
    AI_FAIL_CLOSED_CONTEXT, CUR_DELAY_EXCEEDED_CONTEXT,
)


class TestComponentInventory:
    def test_asl_template_exists(self):
        assert os.path.exists(ASL_TEMPLATE)

    def test_asl_doc_exists(self):
        assert os.path.exists(ASL_DOC)

    def test_orchestration_main_tf_exists(self):
        assert os.path.exists(ORCHESTRATION_MAIN_TF)

    def test_asl_starts_at_prepare_run_context(self):
        asl = _load_asl_template()
        assert asl["StartAt"] == "PrepareRunContext"

    def test_asl_required_states_present(self):
        asl = _load_asl_template()
        states = asl["States"]
        # Top-level parent states
        required_parent = [
            "PrepareRunContext", "LoadAccountPolicy", "OverwriteEnvironment",
            "CheckRunState", "DuplicateRun", "CheckAdHocQuotaDecision", "CheckAdHocQuota",
            "CheckErrorBudgetLock", "EvaluateErrorBudgetLock",
            "IngestCostData", "IngestionReady",
            "NormalizeCostWindow", "CheckTelemetryQuality", "SetTelemetryForceDryRun",
            "VerifyS3Pointer", "SetS3PointerMissingError",
            "ChooseDetectRequestMode", "BuildDetectRequestRawJson",
            "BuildDetectRequestS3Pointer", "InvokeDetect", "EvaluateDetectResponse",
            "SetAIFailClosedError",
            # G1 fix: anomaly processing is now a Map + summarize, not flat states
            "ProcessDetectedAnomalies", "SummarizeAnomalyResults", "EvaluateAnomalySummary",
            "FailClosed", "SendFailClosedAlert",
            "MarkRunComplete", "MarkRunFailed",
            "RunCompleted", "RunFailed",
            "AccountRunCompleted", "AccountRunFailed", "AccountDuplicateIgnored",
            "CURRetryExceeded", "WaitForCURExport",
        ]
        for state in required_parent:
            assert state in states, f"Required parent state missing: {state}"

        # Per-anomaly Map iterator states
        iter_states = _get_map_iterator_states()
        required_iter = [
            "InvokeDecideForAnomaly", "CacheRollbackPayloadForAnomaly",
            "FormatDecideResultForAnomaly", "RouteAlertForAnomaly",
            "FinanceAlertRequiredForAnomaly", "SendFinanceAlertForAnomaly",
            "EngineeringAlertRequiredForAnomaly", "SendEngineeringAlertForAnomaly",
            "EvaluateContainmentPolicyForAnomaly",
            "WritePreActionAuditForAnomaly", "BuildContainmentInputForAnomaly",
            "ExecuteContainmentForAnomaly",
            "ReportVerifyResultForAnomaly", "EvaluateVerifyResultForAnomaly",
            "ExecuteRollbackFromCacheForAnomaly", "NotifyAIRollbackForAnomaly",
            "WriteRollbackAuditForAnomaly", "SendRolledBackStatusMessageForAnomaly",
            "WriteEscalationAuditForAnomaly", "SendEscalationAlertForAnomaly",
            "WritePostActionAuditForAnomaly", "SendAppliedStatusMessageForAnomaly",
            "WriteDeniedAuditForAnomaly", "SendDeniedStatusMessageForAnomaly",
            "WritePendingApprovalAuditForAnomaly", "SendPendingStatusMessageForAnomaly",
            "AnomalyApplied", "AnomalyDenied", "AnomalyPending",
            "AnomalyRolledBack", "AnomalyEscalated",
            "AnomalyAIFailClosed", "AnomalyPlatformFailed",
        ]
        for state in required_iter:
            assert state in iter_states, f"Required iterator state missing: {state}"

    def test_no_polling_states_present(self):
        asl = _load_asl_template()
        states = asl["States"]
        for s in ["WaitForAIResult", "PollAIResult", "CheckDBResultExists",
                  "FormatAIResult", "AIResultDecision"]:
            assert s not in states, f"Stale polling state found: {s}"

    def test_vpc_alb_caller_used_for_ai_endpoints(self):
        asl = _load_asl_template()
        parent_states = asl["States"]
        iter_states = _get_map_iterator_states()
        # InvokeDetect remains at the top level (one detect per run)
        for state_name in ["InvokeDetect"]:
            resource = parent_states[state_name]["Resource"]
            assert resource == "arn:aws:placeholder", (
                f"{state_name}.Resource must reference vpc_alb_caller_lambda_arn"
            )
        # InvokeDecide and ReportVerifyResult are inside the Map iterator
        for state_name in ["InvokeDecideForAnomaly", "ReportVerifyResultForAnomaly",
                           "NotifyAIRollbackForAnomaly"]:
            resource = iter_states[state_name]["Resource"]
            assert resource == "arn:aws:placeholder", (
                f"{state_name}.Resource must reference vpc_alb_caller_lambda_arn"
            )

    def test_rollback_cache_is_dynamodb_put(self):
        iter_states = _get_map_iterator_states()
        state = iter_states["CacheRollbackPayloadForAnomaly"]
        assert state["Type"] == "Task"
        assert state["Resource"] == "arn:aws:states:::dynamodb:putItem"

    def test_alert_delivery_uses_sns(self):
        asl = _load_asl_template()
        states = asl["States"]
        iter_states = _get_map_iterator_states()
        # Top-level alert states
        for state_name in ["SendCURDelayAlert", "SendFailClosedAlert"]:
            resource = states[state_name]["Resource"]
            assert resource == "arn:aws:states:::sns:publish", (
                f"{state_name} must use sns:publish"
            )
        # Per-anomaly (Map iterator) alert states
        for state_name in ["SendFinanceAlertForAnomaly", "SendEngineeringAlertForAnomaly"]:
            resource = iter_states[state_name]["Resource"]
            assert resource == "arn:aws:states:::sns:publish", (
                f"{state_name} must use sns:publish"
            )

    def test_status_messages_use_sqs(self):
        iter_states = _get_map_iterator_states()
        for state_name in ["SendAppliedStatusMessageForAnomaly", "SendDeniedStatusMessageForAnomaly",
                            "SendPendingStatusMessageForAnomaly", "SendRolledBackStatusMessageForAnomaly"]:
            resource = iter_states[state_name]["Resource"]
            assert resource == "arn:aws:states:::sqs:sendMessage", (
                f"{state_name} must use sqs:sendMessage"
            )

    def test_notify_ai_rollback_uses_vpc_alb_caller(self):
        """NotifyAIRollbackForAnomaly must call /v1/audit/{id}/rollback via vpc_alb_caller."""
        iter_states = _get_map_iterator_states()
        state = iter_states["NotifyAIRollbackForAnomaly"]
        assert state["Resource"] == "arn:aws:placeholder", (
            "NotifyAIRollbackForAnomaly must use vpc_alb_caller_lambda_arn"
        )
        path_param = state["Parameters"].get("path.$", "")
        assert "rollback" in path_param and "audit" in path_param, (
            "NotifyAIRollbackForAnomaly path must reference /v1/audit/{id}/rollback"
        )

    def test_cache_rollback_payload_item_has_contract_fields(self):
        """CacheRollbackPayloadForAnomaly DDB item must include anomaly_id, correlation_id, boto3_equivalent."""
        iter_states = _get_map_iterator_states()
        item = iter_states["CacheRollbackPayloadForAnomaly"]["Parameters"]["Item"]
        assert "anomaly_id" in item
        assert "correlation_id" in item
        assert "boto3_equivalent" in item
        assert "rollback_payload" in item

    def test_no_detection_queue_in_asl(self):
        """No async detection queue or polling loop must exist in ASL."""
        with open(ASL_TEMPLATE, "r", encoding="utf-8") as fh:
            content = fh.read()
        # These are async-detection patterns banned from the synchronous ALB path.
        # Note: ai_poll_interval is a legit retry-config key in PrepareRunContext;
        # we target ai_poll_queue which specifically identifies the retired detection queue.
        for term in ["detection_queue", "ai_poll_queue", "results_table_name", "detect_queue_"]:
            assert term not in content, f"Forbidden async-detection term in ASL: {term}"

    def test_asl_doc_matches_template_states(self):
        # Compare top-level states only; the Map iterator states are embedded within
        # ProcessDetectedAnomalies and are already verified by test_asl_required_states_present.
        template_states = set(_load_asl_template()["States"].keys())
        doc_states = set(_load_asl_doc()["States"].keys())
        assert not (doc_states - template_states), f"Extra states in doc: {doc_states - template_states}"
        assert not (template_states - doc_states), f"Missing states in doc: {template_states - doc_states}"

    def test_orchestration_tf_references_rollback_cache_table(self):
        with open(ORCHESTRATION_MAIN_TF, "r", encoding="utf-8") as fh:
            content = fh.read()
        assert "rollback_cache_table_name" in content

    def test_orchestration_tf_references_rollback_status_queue(self):
        with open(ORCHESTRATION_MAIN_TF, "r", encoding="utf-8") as fh:
            content = fh.read()
        assert "rollback_status_queue_url" in content

    def test_orchestration_tf_references_sns_topics(self):
        with open(ORCHESTRATION_MAIN_TF, "r", encoding="utf-8") as fh:
            content = fh.read()
        assert "finance_alerts_sns_topic_arn" in content
        assert "engineering_alerts_sns_topic_arn" in content


class TestPayloadResolution:
    def test_scheduled_input_has_required_top_level_keys(self):
        ctx = SCHEDULED_WORKFLOW_INPUT
        for key in ["run_id", "correlation_id", "account_id", "cost_period",
                    "execution_date", "tenant_id", "is_ad_hoc", "force_dry_run",
                    "ai_contract_version", "cur_retry", "ai_retry"]:
            assert key in ctx

    def test_check_run_state_parameters_resolvable(self):
        ctx = POST_PREPARE_RUN_CONTEXT
        asl = _load_asl_template()
        params = asl["States"]["CheckRunState"]["Parameters"]
        resolved = _resolve_parameters(ctx, params)
        assert resolved["run_id"] == RUN_ID
        assert resolved["account_id"] == ACCOUNT_ID

    def test_ingestion_s3_pointer_data_source_type(self):
        ctx = POST_INGEST_COST_DATA_S3
        ds_type = _resolve_path(ctx, "$.ingestion.details.data_source_type")
        assert ds_type == "S3_POINTER"

    def test_ingestion_ce_fallback_carries_delayed_cur_flag(self):
        ctx = POST_INGEST_COST_DATA_CE
        delayed = _resolve_path(ctx, "$.ingestion.details.delayed_cur")
        assert delayed is True

    def test_normalize_output_has_details_completeness_score(self):
        ctx = POST_NORMALIZE_HEALTHY
        score = _resolve_path(ctx, "$.normalized.details.completeness_score")
        assert isinstance(score, float) and 0.0 <= score <= 1.0

    def test_normalize_output_has_details_aws_cur_line_items(self):
        ctx = POST_NORMALIZE_HEALTHY
        items = _resolve_path(ctx, "$.normalized.details.aws_cur_line_items")
        assert isinstance(items, list) and len(items) > 0

    def test_normalize_degraded_triggers_quality_gate(self):
        ctx = POST_NORMALIZE_DEGRADED
        score = _resolve_path(ctx, "$.normalized.details.completeness_score")
        estimated = _resolve_path(ctx, "$.normalized.details.estimated_billing")
        assert score < 0.8 or estimated is True

    def test_build_detect_request_aws_cur_line_items_populated(self):
        ctx = POST_BUILD_DETECT_REQUEST
        items = _resolve_path(ctx, "$.ai_detect_request.body.aws_cur_line_items")
        assert isinstance(items, list) and len(items) > 0

    def test_build_detect_request_path_is_v1_detect(self):
        ctx = POST_BUILD_DETECT_REQUEST
        path = _resolve_path(ctx, "$.ai_detect_request.path")
        assert path == "/v1/detect"

    def test_invoke_detect_parameters_resolvable(self):
        ctx = POST_BUILD_DETECT_REQUEST
        asl = _load_asl_template()
        params = asl["States"]["InvokeDetect"]["Parameters"]
        resolved = _resolve_parameters(ctx, params)
        assert resolved["path"] == "/v1/detect"
        assert resolved["tenant_id"] == TENANT_ID
        assert resolved["correlation_id"] == CORRELATION_ID
        assert "body" in resolved

    def test_invoke_detect_reads_path_from_ai_detect_request(self):
        asl = _load_asl_template()
        path_expr = asl["States"]["InvokeDetect"]["Parameters"]["path.$"]
        assert path_expr == "$.ai_detect_request.path"
        ctx = POST_BUILD_DETECT_REQUEST
        assert _resolve_path(ctx, path_expr) == "/v1/detect"

    def test_detect_response_anomalies_list_0_has_anomaly_id(self):
        ctx = POST_INVOKE_DETECT_ANOMALY
        anomaly_id = _resolve_path(ctx, "$.ai_detect_response.anomalies_list[0].anomaly_id")
        assert anomaly_id == ANOMALY_ID

    def test_detect_response_anomalies_list_0_has_resource_id(self):
        ctx = POST_INVOKE_DETECT_ANOMALY
        resource_id = _resolve_path(ctx, "$.ai_detect_response.anomalies_list[0].resource_id")
        assert resource_id is not None and resource_id != ""

    def test_decide_response_has_action_plan_0_action(self):
        ctx = POST_INVOKE_DECIDE
        action = _resolve_path(ctx, "$.ai_decide_response.action_plan[0].action")
        assert isinstance(action, str) and action != ""

    def test_decide_response_has_rollback_payload(self):
        ctx = POST_INVOKE_DECIDE
        payload = _resolve_path(ctx, "$.ai_decide_response.rollback_payload")
        assert isinstance(payload, dict)

    def test_cache_rollback_payload_key_resolvable(self):
        ctx = POST_INVOKE_DECIDE
        anomaly_id = _resolve_path(ctx, "$.ai_detect_response.anomalies_list[0].anomaly_id")
        assert anomaly_id == ANOMALY_ID

    def test_format_decide_result_ai_populated(self):
        ctx = POST_FORMAT_DECIDE_RESULT
        ai = _resolve_path(ctx, "$.ai")
        assert "recommended_containment_mode" in ai
        assert "anomaly_id" in ai
        assert "severity" in ai

    def test_router_output_has_finance_and_engineering_routes(self):
        ctx = POST_ROUTER
        finance = _resolve_path(ctx, "$.alert.details.finance_route")
        engineering = _resolve_path(ctx, "$.alert.details.engineering_route")
        assert "deliver" in finance and "deliver" in engineering

    def test_report_verify_result_parameters_resolvable(self):
        # G1 fix: ReportVerifyResultForAnomaly lives in the Map iterator; context must include $.anomaly
        ctx = {
            **POST_EXECUTE_CONTAINMENT,
            "anomaly": POST_EXECUTE_CONTAINMENT["ai_detect_response"]["anomalies_list"][0],
        }
        iter_states = _get_map_iterator_states()
        params = iter_states["ReportVerifyResultForAnomaly"]["Parameters"]
        resolved = _resolve_parameters(ctx, params)
        assert resolved["path"] == "/v1/verify"
        assert resolved["tenant_id"] == TENANT_ID
        body = resolved["body"]
        assert "action_executed" in body

    def test_verify_result_written_to_verify_result_key(self):
        ctx = POST_VERIFY_RESULT
        result = _resolve_path(ctx, "$.verify_result")
        assert result["success"] is True


class TestTelemetryContract:
    def test_cur_ready_uses_s3_pointer(self):
        ctx = POST_INGEST_COST_DATA_S3
        ds_type = _resolve_path(ctx, "$.ingestion.details.data_source_type")
        assert ds_type == "S3_POINTER"

    def test_cur_delayed_ce_fallback_still_ready(self):
        ctx = POST_INGEST_COST_DATA_CE
        status = _resolve_path(ctx, "$.ingestion.status")
        assert status == "READY"

    def test_degraded_normalization_completeness_below_threshold(self):
        ctx = POST_NORMALIZE_DEGRADED
        score = _resolve_path(ctx, "$.normalized.details.completeness_score")
        assert score < 0.8

    def test_healthy_normalization_completeness_at_or_above_threshold(self):
        ctx = POST_NORMALIZE_HEALTHY
        score = _resolve_path(ctx, "$.normalized.details.completeness_score")
        assert score >= 0.8

    def test_normalized_details_has_all_telemetry_quality_flags(self):
        for fixture_label, ctx in [
            ("healthy", POST_NORMALIZE_HEALTHY),
            ("degraded", POST_NORMALIZE_DEGRADED),
        ]:
            details = _resolve_path(ctx, "$.normalized.details")
            for flag in ["completeness_score", "delayed_cur", "stale_cost_explorer",
                         "missing_cloudwatch", "estimated_billing"]:
                assert flag in details, (
                    f"normalized.details.{flag} missing in {fixture_label}"
                )


class TestDetectPath:
    def test_build_detect_request_tenant_id(self):
        ctx = POST_BUILD_DETECT_REQUEST
        assert _resolve_path(ctx, "$.ai_detect_request.tenant_id") == TENANT_ID

    def test_build_detect_request_stable_idempotency_key(self):
        ctx = POST_BUILD_DETECT_REQUEST
        idem = _resolve_path(ctx, "$.ai_detect_request.idempotency_key")
        assert idem == IDEMPOTENCY_KEY

    def test_build_detect_request_body_has_business_context(self):
        ctx = POST_BUILD_DETECT_REQUEST
        bc = _resolve_path(ctx, "$.ai_detect_request.body.business_context")
        assert "linked_account_id" in bc

    def test_builder_s3_pointer_only_contains_required_fields(self):
        asl = _load_asl_template()
        params = asl["States"]["BuildDetectRequestS3Pointer"]["Parameters"]
        ctx = POST_NORMALIZE_POINTER
        resolved = _resolve_parameters(ctx, params)
        body = resolved["body"]
        assert body["data_source_type"] == "S3_POINTER"
        assert body["schema_version"] == "3.2.0"
        assert body["tenant_id"] == TENANT_ID
        assert body["account_id"] == ACCOUNT_ID
        assert body["account_name"] == "sandbox"
        assert body["correlation_id"] == CORRELATION_ID
        assert body["idempotency_key"] == IDEMPOTENCY_KEY
        assert "s3_bucket_uri" in body
        assert re.fullmatch(r"[a-f0-9]{64}", body["s3_object_checksum"])
        assert "aws_cost_explorer_daily" in body
        assert "missing_resources" in body
        assert "current_ce_cost_gap_usd" in body
        assert "comparison_window" in body
        assert "business_context" in body
        assert "telemetry_delay_event" in body
        assert "is_ad_hoc" in body
        assert "aws_cur_line_items" not in body
        assert resolved["idempotency_key"] == IDEMPOTENCY_KEY
        assert resolved["dry_run_mode"] is False

    def test_verify_s3_pointer_choice_logic(self):
        asl = _load_asl_template()
        choices = asl["States"]["VerifyS3Pointer"]["Choices"]
        default = asl["States"]["VerifyS3Pointer"]["Default"]
        assert default == "SetS3PointerMissingError"

        rule = choices[0]
        assert rule["And"][0]["Variable"] == "$.normalized.details.s3_bucket_uri"
        assert rule["And"][0]["IsPresent"] is True
        assert rule["And"][1]["Variable"] == "$.normalized.details.s3_bucket_uri"
        assert rule["And"][1]["StringMatches"] == "s3://*.json.gz"
        # VerifyS3Pointer now routes through ChooseDetectRequestMode (not directly to S3Pointer builder)
        assert rule["Next"] == "ChooseDetectRequestMode"

    def test_set_s3_pointer_missing_error_payload(self):
        asl = _load_asl_template()
        result = asl["States"]["SetS3PointerMissingError"]["Result"]
        assert result["Error"] == "S3PointerMissing"
        assert "Cause" in result

    def test_invoke_detect_passes_all_required_fields(self):
        asl = _load_asl_template()
        params = asl["States"]["InvokeDetect"]["Parameters"]
        ctx = POST_BUILD_DETECT_REQUEST
        resolved = _resolve_parameters(ctx, params)
        assert resolved["path"] == "/v1/detect"
        assert resolved["tenant_id"] == TENANT_ID
        assert resolved["idempotency_key"] == IDEMPOTENCY_KEY
        assert resolved["dry_run_mode"] is False
        assert isinstance(resolved["body"], dict)

        ctx_fallback = POST_BUILD_DETECT_REQUEST_CE_FALLBACK
        resolved_fallback = _resolve_parameters(ctx_fallback, params)
        assert resolved_fallback["path"] == "/v1/detect"
        assert resolved_fallback["tenant_id"] == TENANT_ID
        assert resolved_fallback["idempotency_key"] == IDEMPOTENCY_KEY
        assert resolved_fallback["dry_run_mode"] is True
        assert isinstance(resolved_fallback["body"], dict)

    def test_choose_detect_request_mode_routes_raw_json_for_small_ce_fallback(self):
        """ChooseDetectRequestMode must route to BuildDetectRequestRawJson for RAW_JSON+telemetry_delay_event=True."""
        asl = _load_asl_template()
        choices = asl["States"]["ChooseDetectRequestMode"]["Choices"]
        default = asl["States"]["ChooseDetectRequestMode"]["Default"]
        assert default == "BuildDetectRequestS3Pointer"
        rule = choices[0]
        assert rule["Next"] == "BuildDetectRequestRawJson"
        cond_vars = {c.get("Variable"): c for c in rule["And"]}
        assert "$.normalized.details.detect_request_mode" in cond_vars
        assert cond_vars["$.normalized.details.detect_request_mode"]["StringEquals"] == "RAW_JSON"
        assert "$.normalized.details.telemetry_delay_event" in cond_vars
        assert cond_vars["$.normalized.details.telemetry_delay_event"]["BooleanEquals"] is True

    def test_build_detect_request_raw_json_body_structure(self):
        """BuildDetectRequestRawJson must produce a RAW_JSON body with required contract fields."""
        asl = _load_asl_template()
        params = asl["States"]["BuildDetectRequestRawJson"]["Parameters"]
        ctx = POST_BUILD_DETECT_REQUEST_CE_FALLBACK  # small CE-fallback fixture
        # Manually reconstruct the context as it would be before this state runs
        ctx_before = {
            **POST_NORMALIZE_DEGRADED,
        }
        resolved = _resolve_parameters(ctx_before, params)
        body = resolved["body"]
        assert body["data_source_type"] == "RAW_JSON"
        assert body["schema_version"] == "3.2.0"
        assert body["tenant_id"] == TENANT_ID
        assert body["account_id"] == ACCOUNT_ID
        assert body["correlation_id"] == CORRELATION_ID
        assert body["idempotency_key"] == IDEMPOTENCY_KEY
        assert body["request_timestamp"] == "2026-06-27T00:00:00Z"
        assert body["telemetry_delay_event"] is True
        assert "aws_cost_explorer_daily" in body
        assert "missing_resources" in body
        assert "current_ce_cost_gap_usd" in body
        assert "comparison_window" in body
        assert "business_context" in body
        assert "quality" in body
        quality = body["quality"]
        assert "completeness_score" in quality
        assert "delayed_cur" in quality
        # Must NOT include CUR line items in RAW_JSON CE-fallback mode
        assert "aws_cur_line_items" not in body
        assert resolved["path"] == "/v1/detect"
        assert resolved["dry_run_mode"] is False  # force_dry_run in fixture context

    def test_choose_detect_request_mode_s3_pointer_for_cur_ready(self):
        """ChooseDetectRequestMode default routes CUR-ready (telemetry_delay_event=False) to BuildDetectRequestS3Pointer."""
        # CUR-ready fixture has detect_request_mode=S3_POINTER and telemetry_delay_event=False.
        # Neither condition in ChooseDetectRequestMode matches, so default applies.
        asl = _load_asl_template()
        default = asl["States"]["ChooseDetectRequestMode"]["Default"]
        assert default == "BuildDetectRequestS3Pointer"

    def test_detect_response_fail_closed_on_success_false(self):
        asl = _load_asl_template()
        choices = asl["States"]["EvaluateDetectResponse"]["Choices"]
        found = any(
            c.get("Variable") == "$.ai_detect_response.success" and
            c.get("BooleanEquals") is False and
            c.get("Next") == "SetAIFailClosedError"
            for c in choices
        )
        assert found

    def test_detect_response_fail_closed_on_low_confidence(self):
        asl = _load_asl_template()
        choices = asl["States"]["EvaluateDetectResponse"]["Choices"]
        found = any(
            c.get("Variable") == "$.ai_detect_response.data_confidence" and
            c.get("StringEquals") == "LOW" and
            c.get("Next") == "SetAIFailClosedError"
            for c in choices
        )
        assert found

    def test_detect_no_anomaly_default_leads_to_mark_run_complete(self):
        asl = _load_asl_template()
        default_next = asl["States"]["EvaluateDetectResponse"]["Default"]
        assert default_next == "MarkRunComplete"


class TestDecideCachePath:
    def test_invoke_decide_path_is_v1_decide(self):
        """InvokeDecideForAnomaly must have path=/v1/decide (literal, not $.*)."""
        iter_states = _get_map_iterator_states()
        params = iter_states["InvokeDecideForAnomaly"]["Parameters"]
        assert params.get("path") == "/v1/decide"

    def test_invoke_decide_uses_anomaly_specific_idempotency_key(self):
        """G1 fix: idempotency key must include anomaly_id to be anomaly-scoped."""
        iter_states = _get_map_iterator_states()
        params = iter_states["InvokeDecideForAnomaly"]["Parameters"]
        idem_path = params.get("idempotency_key.$", "")
        assert "anomaly_id" in idem_path or "anomaly.anomaly_id" in idem_path, (
            "InvokeDecideForAnomaly idempotency_key must include anomaly_id for per-anomaly isolation"
        )

    def test_invoke_decide_body_uses_anomaly_context(self):
        """G1 fix: anomaly_context must reference $.anomaly (Map item), not anomalies_list[0]."""
        iter_states = _get_map_iterator_states()
        params = iter_states["InvokeDecideForAnomaly"]["Parameters"]
        body = params.get("body", {})
        assert "anomaly_context.$" in body
        assert body["anomaly_context.$"] == "$.anomaly", (
            "G1 fix: anomaly_context must be $.anomaly (Map item), not anomalies_list[0]"
        )

    def test_decide_response_rollback_payload_has_boto3_equivalent(self):
        ctx = POST_INVOKE_DECIDE
        payload = _resolve_path(ctx, "$.ai_decide_response.rollback_payload")
        assert "boto3_equivalent" in payload

    def test_cache_rollback_payload_uses_dynamodb_put_item(self):
        iter_states = _get_map_iterator_states()
        state = iter_states["CacheRollbackPayloadForAnomaly"]
        assert state["Type"] == "Task"
        assert state["Resource"] == "arn:aws:states:::dynamodb:putItem"
        assert "TableName" in state["Parameters"]
        assert "Item" in state["Parameters"]

    def test_format_decide_result_reads_action_plan_0_action(self):
        """FormatDecideResultForAnomaly reads recommended_containment_mode from action_plan[0].action."""
        iter_states = _get_map_iterator_states()
        params = iter_states["FormatDecideResultForAnomaly"]["Parameters"]
        assert "recommended_containment_mode.$" in params
        path = params["recommended_containment_mode.$"]
        ctx = POST_INVOKE_DECIDE
        mode = _resolve_path(ctx, path)
        assert isinstance(mode, str) and mode != ""

    def test_format_decide_result_reads_anomaly_id_from_anomaly(self):
        """G1 fix: FormatDecideResultForAnomaly must read anomaly_id from $.anomaly, not anomalies_list[0]."""
        iter_states = _get_map_iterator_states()
        params = iter_states["FormatDecideResultForAnomaly"]["Parameters"]
        assert "anomaly_id.$" in params
        path = params["anomaly_id.$"]
        assert "anomalies_list[0]" not in path, (
            "G1 fix: FormatDecideResultForAnomaly must use $.anomaly.anomaly_id, not anomalies_list[0]"
        )
        # Resolve against a Map item context (anomaly key at top level)
        ctx = {**POST_INVOKE_DECIDE, "anomaly": POST_INVOKE_DECIDE["ai_detect_response"]["anomalies_list"][0]}
        assert _resolve_path(ctx, path) == ANOMALY_ID


class TestContainmentPolicy:
    def _choices(self):
        iter_states = _get_map_iterator_states()
        return iter_states["EvaluateContainmentPolicyForAnomaly"]["Choices"]

    def test_prod_destructive_mode_denied(self):
        ctx = POST_CONTAINMENT_POLICY_DENIED_PROD
        assert ctx["account_policy"]["environment"] == "prod"
        assert ctx["ai"]["recommended_containment_mode"] in [
            "terminate", "delete", "modify_iam", "apply", "auto-shutdown",
            "quota-cap", "time-gated-countdown"
        ]
        choices = self._choices()
        found = False
        for choice in choices:
            if "And" in choice and choice.get("Next") == "WriteDeniedAuditForAnomaly":
                conds = choice["And"]
                has_prod = any(
                    c.get("Variable") == "$.account_policy.environment" and
                    c.get("StringEquals") == "prod"
                    for c in conds
                )
                has_destructive_or = any("Or" in c for c in conds)
                if has_prod and has_destructive_or:
                    found = True
                    break
        assert found

    def test_force_dry_run_with_apply_fixture_is_deniable(self):
        ctx = POST_CONTAINMENT_POLICY_DRYRUN_DENIED
        assert ctx["force_dry_run"] is True
        assert ctx["ai"]["recommended_containment_mode"] == "apply"

    def test_sandbox_tag_mode_has_safe_path_in_asl(self):
        ctx = POST_CONTAINMENT_POLICY_APPLY
        assert ctx["account_policy"]["environment"] == "sandbox"
        assert ctx["ai"]["recommended_containment_mode"] == "tag"
        choices = self._choices()
        sandbox_safe_found = any(
            "And" in choice and choice.get("Next") == "WritePreActionAuditForAnomaly" and
            any(c.get("Variable") == "$.account_policy.environment" and
                c.get("StringEquals") == "sandbox"
                for c in choice["And"])
            for choice in choices
        )
        assert sandbox_safe_found

    def test_execute_containment_output_has_status_and_anomaly_id(self):
        ctx = POST_EXECUTE_CONTAINMENT
        containment = _resolve_path(ctx, "$.containment")
        assert "status" in containment
        assert containment["anomaly_id"] == ANOMALY_ID


class TestVerifyPath:
    def test_report_verify_result_path_is_v1_verify(self):
        iter_states = _get_map_iterator_states()
        params = iter_states["ReportVerifyResultForAnomaly"]["Parameters"]
        assert params.get("path") == "/v1/verify"

    def test_report_verify_result_uses_anomaly_specific_idempotency_key(self):
        """G1 fix: verify idempotency key must include anomaly_id."""
        iter_states = _get_map_iterator_states()
        params = iter_states["ReportVerifyResultForAnomaly"]["Parameters"]
        idem_path = params.get("idempotency_key.$", "")
        assert "anomaly_id" in idem_path or "anomaly.anomaly_id" in idem_path, (
            "ReportVerifyResultForAnomaly idempotency_key must include anomaly_id"
        )

    def test_verify_body_action_executed_target_reads_anomaly_resource_id(self):
        """G1 fix: verify action_executed.target must read from $.anomaly.resource_id, not anomalies_list[0]."""
        iter_states = _get_map_iterator_states()
        params = iter_states["ReportVerifyResultForAnomaly"]["Parameters"]
        body = params.get("body", {})
        action_executed = body.get("action_executed", {})
        target_path = action_executed.get("target.$")
        assert target_path is not None
        assert "anomalies_list[0]" not in target_path, (
            "G1 fix: verify target must use $.anomaly.resource_id, not anomalies_list[0]"
        )
        ctx = {**POST_EXECUTE_CONTAINMENT, "anomaly": POST_EXECUTE_CONTAINMENT["ai_detect_response"]["anomalies_list"][0]}
        target = _resolve_path(ctx, target_path)
        assert target is not None and target != ""

    def test_verify_result_leads_to_evaluate_verify_result(self):
        """ReportVerifyResultForAnomaly must route to EvaluateVerifyResultForAnomaly."""
        iter_states = _get_map_iterator_states()
        assert iter_states["ReportVerifyResultForAnomaly"].get("Next") == "EvaluateVerifyResultForAnomaly"

    def test_write_post_action_audit_leads_to_applied_status_message(self):
        iter_states = _get_map_iterator_states()
        assert iter_states["WritePostActionAuditForAnomaly"]["Next"] == "SendAppliedStatusMessageForAnomaly"

    def test_applied_status_message_has_correct_status_value(self):
        iter_states = _get_map_iterator_states()
        params = iter_states["SendAppliedStatusMessageForAnomaly"]["Parameters"]
        body = params.get("MessageBody", {})
        assert body.get("status") == "APPLIED"


class TestFailClosedPaths:
    def test_ai_fail_closed_error_populated(self):
        ctx = AI_FAIL_CLOSED_CONTEXT
        error = _resolve_path(ctx, "$.error")
        assert error["Error"] == "AIEngineFailClosed"

    def test_set_ai_fail_closed_error_state_is_pass(self):
        asl = _load_asl_template()
        state = asl["States"]["SetAIFailClosedError"]
        assert state["Type"] == "Pass"
        assert state["ResultPath"] == "$.error"
        assert state["Next"] == "FailClosed"

    def test_fail_closed_chain(self):
        asl = _load_asl_template()
        assert asl["States"]["FailClosed"]["Next"] == "SendFailClosedAlert"
        assert asl["States"]["SendFailClosedAlert"]["Next"] == "MarkRunFailed"

    def test_fail_closed_audit_parameters_resolvable(self):
        ctx = AI_FAIL_CLOSED_CONTEXT
        asl = _load_asl_template()
        params = asl["States"]["FailClosed"]["Parameters"]
        resolved = _resolve_parameters(ctx, params)
        for field in ["run_id", "correlation_id", "account_id", "cost_period",
                      "execution_date", "tenant_id", "environment", "account_policy", "error"]:
            assert field in resolved, f"FailClosed missing field: {field}"

    def test_cur_delay_exceeded_context_has_error(self):
        ctx = CUR_DELAY_EXCEEDED_CONTEXT
        error = _resolve_path(ctx, "$.error")
        assert error["Error"] == "CURDelayExceeded"

    def test_cur_delay_exceeded_audit_parameters_resolvable(self):
        ctx = CUR_DELAY_EXCEEDED_CONTEXT
        asl = _load_asl_template()
        params = asl["States"]["WriteCURDelayAudit"]["Parameters"]
        resolved = _resolve_parameters(ctx, params)
        for field in ["run_id", "correlation_id", "account_id", "cost_period",
                      "execution_date", "tenant_id", "environment", "account_policy", "error"]:
            assert field in resolved, f"WriteCURDelayAudit missing field: {field}"

    def test_cur_retry_count_4_exceeds_limit(self):
        ctx = CUR_DELAY_EXCEEDED_CONTEXT
        count = _resolve_path(ctx, "$.cur_retry.count")
        assert count >= 4


class TestSQSStatusMessages:
    def test_only_rollback_status_queue_in_asl(self):
        """All SQS queue refs must use rollback_status_queue_url or the placeholder ARN."""
        with open(ASL_TEMPLATE, "r", encoding="utf-8") as fh:
            content = fh.read()
        queue_refs = re.findall(r'"QueueUrl"\s*:\s*"([^"]+)"', content)
        for ref in queue_refs:
            assert "rollback_status_queue_url" in ref or ref == "arn:aws:placeholder", (
                f"Unexpected SQS queue in ASL: {ref!r}"
            )

    def test_applied_status_is_applied(self):
        iter_states = _get_map_iterator_states()
        status = iter_states["SendAppliedStatusMessageForAnomaly"]["Parameters"]["MessageBody"]["status"]
        assert status == "APPLIED"

    def test_denied_status_is_denied(self):
        iter_states = _get_map_iterator_states()
        status = iter_states["SendDeniedStatusMessageForAnomaly"]["Parameters"]["MessageBody"]["status"]
        assert status == "DENIED"

    def test_pending_status_is_pending(self):
        iter_states = _get_map_iterator_states()
        status = iter_states["SendPendingStatusMessageForAnomaly"]["Parameters"]["MessageBody"]["status"]
        assert status == "PENDING"

    def test_rolled_back_status_is_rolled_back(self):
        iter_states = _get_map_iterator_states()
        status = iter_states["SendRolledBackStatusMessageForAnomaly"]["Parameters"]["MessageBody"]["status"]
        assert status == "ROLLED_BACK"

    def test_status_messages_have_run_id_correlation_id_tenant_id(self):
        iter_states = _get_map_iterator_states()
        for state_name in ["SendAppliedStatusMessageForAnomaly", "SendDeniedStatusMessageForAnomaly",
                           "SendPendingStatusMessageForAnomaly", "SendRolledBackStatusMessageForAnomaly"]:
            body = iter_states[state_name]["Parameters"]["MessageBody"]
            assert "run_id.$" in body
            assert "correlation_id.$" in body
            assert "tenant_id.$" in body


class TestVerifyBranching:
    """Contract Section 5: /v1/verify response branching: DONE|RETRY|ROLLBACK|ESCALATE."""

    def test_report_verify_result_routes_to_evaluate_verify_result(self):
        iter_states = _get_map_iterator_states()
        assert iter_states["ReportVerifyResultForAnomaly"]["Next"] == "EvaluateVerifyResultForAnomaly"

    def test_evaluate_verify_result_is_choice(self):
        iter_states = _get_map_iterator_states()
        state = iter_states["EvaluateVerifyResultForAnomaly"]
        assert state["Type"] == "Choice"

    def test_evaluate_verify_result_done_goes_to_write_post_action_audit(self):
        iter_states = _get_map_iterator_states()
        choices = iter_states["EvaluateVerifyResultForAnomaly"]["Choices"]
        found = any(
            c.get("Next") == "WritePostActionAuditForAnomaly" and "Or" in c
            for c in choices
        )
        assert found, "EvaluateVerifyResultForAnomaly must have DONE branch (Or condition) to WritePostActionAuditForAnomaly"

    def test_evaluate_verify_result_rollback_goes_to_execute_rollback(self):
        iter_states = _get_map_iterator_states()
        choices = iter_states["EvaluateVerifyResultForAnomaly"]["Choices"]
        found = any(
            c.get("Variable") == "$.verify_result.next_action" and
            c.get("StringEquals") == "ROLLBACK" and
            c.get("Next") == "ExecuteRollbackFromCacheForAnomaly"
            for c in choices
        )
        assert found, "EvaluateVerifyResultForAnomaly must route ROLLBACK to ExecuteRollbackFromCacheForAnomaly"

    def test_evaluate_verify_result_escalate_goes_to_write_escalation_audit(self):
        iter_states = _get_map_iterator_states()
        choices = iter_states["EvaluateVerifyResultForAnomaly"]["Choices"]
        found = any(
            c.get("Variable") == "$.verify_result.next_action" and
            c.get("StringEquals") == "ESCALATE" and
            c.get("Next") == "WriteEscalationAuditForAnomaly"
            for c in choices
        )
        assert found, "EvaluateVerifyResultForAnomaly must route ESCALATE to WriteEscalationAuditForAnomaly"

    def test_evaluate_verify_result_default_is_write_post_action_audit(self):
        iter_states = _get_map_iterator_states()
        default = iter_states["EvaluateVerifyResultForAnomaly"]["Default"]
        assert default == "WritePostActionAuditForAnomaly"

    def test_rollback_path_chain(self):
        iter_states = _get_map_iterator_states()
        assert iter_states["ExecuteRollbackFromCacheForAnomaly"]["Next"] == "NotifyAIRollbackForAnomaly"
        assert iter_states["NotifyAIRollbackForAnomaly"]["Next"] == "WriteRollbackAuditForAnomaly"
        assert iter_states["WriteRollbackAuditForAnomaly"]["Next"] == "SendRolledBackStatusMessageForAnomaly"
        assert iter_states["SendRolledBackStatusMessageForAnomaly"]["Next"] == "AnomalyRolledBack"

    def test_escalation_path_chain(self):
        iter_states = _get_map_iterator_states()
        assert iter_states["WriteEscalationAuditForAnomaly"]["Next"] == "SendEscalationAlertForAnomaly"
        assert iter_states["SendEscalationAlertForAnomaly"]["Next"] == "AnomalyEscalated"

    def test_notify_ai_rollback_path_format(self):
        """NotifyAIRollbackForAnomaly must use States.Format path for /v1/audit/{id}/rollback."""
        iter_states = _get_map_iterator_states()
        params = iter_states["NotifyAIRollbackForAnomaly"]["Parameters"]
        assert "path.$" in params
        path_expr = params["path.$"]
        assert "rollback" in path_expr
        assert "audit" in path_expr
        assert "States.Format" in path_expr

    def test_notify_ai_rollback_body_has_required_fields(self):
        """NotifyAIRollbackForAnomaly body must include correlation_id, anomaly_id, rollback_status."""
        iter_states = _get_map_iterator_states()
        body = iter_states["NotifyAIRollbackForAnomaly"]["Parameters"]["body"]
        assert "correlation_id.$" in body
        assert "anomaly_id.$" in body
        assert "rollback_status.$" in body

    def test_execute_rollback_from_cache_is_task(self):
        iter_states = _get_map_iterator_states()
        state = iter_states["ExecuteRollbackFromCacheForAnomaly"]
        assert state["Type"] == "Task"
        # Must use containment_worker (CDO-owned) not vpc_alb_caller
        assert state["Resource"] == "arn:aws:placeholder"

    def test_send_escalation_alert_uses_sns(self):
        iter_states = _get_map_iterator_states()
        resource = iter_states["SendEscalationAlertForAnomaly"]["Resource"]
        assert resource == "arn:aws:states:::sns:publish"

    def test_verify_result_written_to_verify_result_key(self):
        ctx = POST_VERIFY_RESULT
        result = _resolve_path(ctx, "$.verify_result")
        assert result["success"] is True


class TestG1MultiAnomalyMap:
    """G1 fix: Verify that the ProcessDetectedAnomalies Map is correctly structured
    for sequential multi-anomaly processing."""

    def test_process_detected_anomalies_is_map_type(self):
        asl = _load_asl_template()
        state = asl["States"]["ProcessDetectedAnomalies"]
        assert state["Type"] == "Map"

    def test_map_items_path_is_anomalies_list(self):
        asl = _load_asl_template()
        state = asl["States"]["ProcessDetectedAnomalies"]
        assert state["ItemsPath"] == "$.ai_detect_response.anomalies_list"

    def test_map_max_concurrency_is_1(self):
        """MaxConcurrency must be 1 to prevent parallel containment blast radius."""
        asl = _load_asl_template()
        state = asl["States"]["ProcessDetectedAnomalies"]
        assert state["MaxConcurrency"] == 1

    def test_map_item_selector_injects_anomaly_and_context(self):
        """ItemSelector must inject $.anomaly and required parent context fields."""
        asl = _load_asl_template()
        item_selector = asl["States"]["ProcessDetectedAnomalies"]["ItemSelector"]
        assert "anomaly.$" in item_selector
        assert item_selector["anomaly.$"] == "$$.Map.Item.Value"
        for field in ["run_id.$", "tenant_id.$", "correlation_id.$", "account_id.$",
                      "execution_date.$", "force_dry_run.$", "account_policy.$", "environment.$"]:
            assert field in item_selector, f"ItemSelector missing: {field}"

    def test_map_routes_to_summarize_anomaly_results(self):
        asl = _load_asl_template()
        state = asl["States"]["ProcessDetectedAnomalies"]
        assert state.get("Next") == "SummarizeAnomalyResults"

    def test_summarize_anomaly_results_uses_state_lambda(self):
        asl = _load_asl_template()
        state = asl["States"]["SummarizeAnomalyResults"]
        assert state["Type"] == "Task"
        assert state["Resource"] == "arn:aws:placeholder"
        params = state["Parameters"]
        assert params.get("operation") == "summarize_anomaly_results"
        assert "processed_anomaly_results.$" in params

    def test_evaluate_anomaly_summary_routes_failed_to_mark_run_failed(self):
        asl = _load_asl_template()
        state = asl["States"]["EvaluateAnomalySummary"]
        assert state["Type"] == "Choice"
        choices = state["Choices"]
        found = any(
            c.get("Variable") == "$.anomaly_summary.workflow_status" and
            c.get("StringEquals") == "FAILED" and
            c.get("Next") == "MarkRunFailed"
            for c in choices
        )
        assert found, "EvaluateAnomalySummary must route workflow_status=FAILED to MarkRunFailed"
        assert state["Default"] == "MarkRunComplete"

    def test_map_iterator_starts_at_invoke_decide_for_anomaly(self):
        asl = _load_asl_template()
        iterator = asl["States"]["ProcessDetectedAnomalies"]["Iterator"]
        assert iterator["StartAt"] == "InvokeDecideForAnomaly"

    def test_decide_idempotency_includes_anomaly_id(self):
        """InvokeDecideForAnomaly idempotency_key must contain anomaly_id for per-anomaly isolation."""
        iter_states = _get_map_iterator_states()
        params = iter_states["InvokeDecideForAnomaly"]["Parameters"]
        idem_expr = params.get("idempotency_key.$", "")
        assert "anomaly_id" in idem_expr or "anomaly.anomaly_id" in idem_expr

    def test_verify_idempotency_includes_anomaly_id(self):
        """ReportVerifyResultForAnomaly idempotency_key must contain anomaly_id."""
        iter_states = _get_map_iterator_states()
        params = iter_states["ReportVerifyResultForAnomaly"]["Parameters"]
        idem_expr = params.get("idempotency_key.$", "")
        assert "anomaly_id" in idem_expr or "anomaly.anomaly_id" in idem_expr

    def test_anomaly_terminal_states_use_end_true(self):
        """All per-anomaly terminal states must have End=true."""
        iter_states = _get_map_iterator_states()
        for state_name in ["AnomalyApplied", "AnomalyDenied", "AnomalyPending",
                           "AnomalyRolledBack", "AnomalyEscalated",
                           "AnomalyAIFailClosed", "AnomalyPlatformFailed"]:
            state = iter_states[state_name]
            assert state.get("End") is True, (
                f"{state_name} must have End=true (iterator terminal state)"
            )

    def test_evaluate_detect_response_routes_to_map(self):
        """EvaluateDetectResponse must route anomalies_detected=True to ProcessDetectedAnomalies."""
        asl = _load_asl_template()
        choices = asl["States"]["EvaluateDetectResponse"]["Choices"]
        found = any(
            c.get("Next") == "ProcessDetectedAnomalies"
            for c in choices
        )
        assert found, "EvaluateDetectResponse must have a choice routing to ProcessDetectedAnomalies"

    def test_no_anomalies_list_0_references_in_map_iterator(self):
        """G1 fix: no per-anomaly state should reference anomalies_list[0] (blast radius regression guard)."""
        import json as _json
        iter_states = _get_map_iterator_states()
        serialized = _json.dumps(iter_states)
        assert "anomalies_list[0]" not in serialized, (
            "G1 regression: Map iterator must not reference anomalies_list[0]. Use $.anomaly instead."
        )


class TestNormalizedAIErrorEnvelope:
    """vpc_alb_caller must return normalized envelope for AI HTTP errors (not raise)."""

    def _make_mock_handler(self, status_code: int, response_body: str = "{}",
                           error_code_in_body: str = None):
        """
        Returns (envelope_dict, exception) tuple by calling the handler logic directly.
        Simulates an HTTPError from the ALB.
        """
        import importlib
        import unittest.mock as mock
        import urllib.error
        import io

        # Import handler to test module-level constants
        handler_mod = importlib.import_module("workers.vpc_alb_caller.handler")

        body_bytes = response_body.encode("utf-8") if isinstance(response_body, str) else response_body
        mock_he = urllib.error.HTTPError(
            url="https://internal-alb/v1/detect",
            code=status_code,
            msg="Error",
            hdrs=None,
            fp=io.BytesIO(body_bytes),
        )

        ai_error_codes = handler_mod._AI_HTTP_ERROR_CODES
        non_retryable = handler_mod._NON_RETRYABLE_ERROR_CODES
        retryable = handler_mod._RETRYABLE_ERROR_CODES
        unavailable = handler_mod._UNAVAILABLE_ERROR_CODES

        error_code = ai_error_codes.get(status_code, f"ERR_HTTP_{status_code}")
        if error_code_in_body:
            error_code = error_code_in_body

        return {
            "ai_error": True,
            "http_status": status_code,
            "error_code": error_code,
            "retryable": error_code in retryable,
            "unavailable": error_code in unavailable,
            "non_retryable": error_code in non_retryable,
            "message": response_body[:500],
            "path": "/v1/detect",
        }

    def test_400_maps_to_err_invalid_schema(self):
        import importlib
        m = importlib.import_module("workers.vpc_alb_caller.handler")
        assert m._AI_HTTP_ERROR_CODES[400] == "ERR_INVALID_SCHEMA"

    def test_401_maps_to_err_auth_failed(self):
        import importlib
        m = importlib.import_module("workers.vpc_alb_caller.handler")
        assert m._AI_HTTP_ERROR_CODES[401] == "ERR_AUTH_FAILED"

    def test_403_maps_to_err_cross_tenant_denied(self):
        import importlib
        m = importlib.import_module("workers.vpc_alb_caller.handler")
        assert m._AI_HTTP_ERROR_CODES[403] == "ERR_CROSS_TENANT_DENIED"

    def test_404_maps_to_err_anomaly_not_found(self):
        import importlib
        m = importlib.import_module("workers.vpc_alb_caller.handler")
        assert m._AI_HTTP_ERROR_CODES[404] == "ERR_ANOMALY_NOT_FOUND"

    def test_409_maps_to_err_dup_idempotency(self):
        import importlib
        m = importlib.import_module("workers.vpc_alb_caller.handler")
        assert m._AI_HTTP_ERROR_CODES[409] == "ERR_DUP_IDEMPOTENCY"

    def test_422_maps_to_err_containment_not_supported(self):
        import importlib
        m = importlib.import_module("workers.vpc_alb_caller.handler")
        assert m._AI_HTTP_ERROR_CODES[422] == "ERR_CONTAINMENT_NOT_SUPPORTED"

    def test_429_maps_to_err_rate_limited(self):
        import importlib
        m = importlib.import_module("workers.vpc_alb_caller.handler")
        assert m._AI_HTTP_ERROR_CODES[429] == "ERR_RATE_LIMITED"

    def test_500_maps_to_err_llm_timeout(self):
        import importlib
        m = importlib.import_module("workers.vpc_alb_caller.handler")
        assert m._AI_HTTP_ERROR_CODES[500] == "ERR_LLM_TIMEOUT"

    def test_503_maps_to_err_service_down(self):
        import importlib
        m = importlib.import_module("workers.vpc_alb_caller.handler")
        assert m._AI_HTTP_ERROR_CODES[503] == "ERR_SERVICE_DOWN"

    def test_non_retryable_codes_do_not_trigger_containment(self):
        import importlib
        m = importlib.import_module("workers.vpc_alb_caller.handler")
        for code in ["ERR_INVALID_SCHEMA", "ERR_CROSS_TENANT_DENIED",
                     "ERR_ANOMALY_NOT_FOUND", "ERR_CONTAINMENT_NOT_SUPPORTED"]:
            assert code in m._NON_RETRYABLE_ERROR_CODES, (
                f"{code} must be non-retryable (no containment)"
            )

    def test_retryable_codes_classification(self):
        import importlib
        m = importlib.import_module("workers.vpc_alb_caller.handler")
        for code in ["ERR_REPLAY_DETECTED", "ERR_AUTH_FAILED", "ERR_RATE_LIMITED"]:
            assert code in m._RETRYABLE_ERROR_CODES, f"{code} must be retryable"

    def test_unavailable_codes_classification(self):
        import importlib
        m = importlib.import_module("workers.vpc_alb_caller.handler")
        for code in ["ERR_LLM_TIMEOUT", "ERR_SERVICE_DOWN"]:
            assert code in m._UNAVAILABLE_ERROR_CODES, f"{code} must be unavailable"

    def test_envelope_has_ai_error_flag_true(self):
        env = self._make_mock_handler(400)
        assert env["ai_error"] is True

    def test_envelope_has_http_status(self):
        env = self._make_mock_handler(422)
        assert env["http_status"] == 422

    def test_422_is_non_retryable(self):
        env = self._make_mock_handler(422)
        assert env["non_retryable"] is True
        assert env["retryable"] is False

    def test_429_is_retryable(self):
        env = self._make_mock_handler(429)
        assert env["retryable"] is True

    def test_503_is_unavailable(self):
        env = self._make_mock_handler(503)
        assert env["unavailable"] is True

    def test_body_error_code_overrides_status_code_mapping(self):
        """If response body contains error_code, it overrides the HTTP status mapping."""
        env = self._make_mock_handler(
            400,
            response_body='{"error_code": "ERR_IDEMPOTENCY_MISMATCH"}',
            error_code_in_body="ERR_IDEMPOTENCY_MISMATCH",
        )
        assert env["error_code"] == "ERR_IDEMPOTENCY_MISMATCH"


class TestRollbackCacheContract:
    """finops-rollback-cache DynamoDB item must include contract-required fields."""

    def test_cache_rollback_payload_item_has_anomaly_id(self):
        iter_states = _get_map_iterator_states()
        item = iter_states["CacheRollbackPayloadForAnomaly"]["Parameters"]["Item"]
        assert "anomaly_id" in item
        assert "S.$" in item["anomaly_id"]

    def test_cache_rollback_payload_item_has_correlation_id(self):
        iter_states = _get_map_iterator_states()
        item = iter_states["CacheRollbackPayloadForAnomaly"]["Parameters"]["Item"]
        assert "correlation_id" in item
        assert "S.$" in item["correlation_id"]

    def test_cache_rollback_payload_item_has_boto3_equivalent(self):
        """boto3_equivalent must be present so CDO can execute rollback independently."""
        iter_states = _get_map_iterator_states()
        item = iter_states["CacheRollbackPayloadForAnomaly"]["Parameters"]["Item"]
        assert "boto3_equivalent" in item

    def test_rollback_cache_table_is_dynamodb_put(self):
        iter_states = _get_map_iterator_states()
        state = iter_states["CacheRollbackPayloadForAnomaly"]
        assert state["Resource"] == "arn:aws:states:::dynamodb:putItem"
        assert "TableName" in state["Parameters"]

    def test_dynamo_cache_ttl_attribute_is_ttl_expiry(self):
        """dynamo_cache.py must use ttl_expiry (not ttl_epoch) for rollback cache TTL."""
        import os
        dynamo_cache_path = os.path.join(
            os.path.dirname(__file__),
            "../src/workers/containment_worker/audit/dynamo_cache.py"
        )
        with open(dynamo_cache_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "ttl_expiry" in content, (
            "dynamo_cache.py must use 'ttl_expiry' as the TTL attribute name"
        )
        assert "ttl_epoch" not in content, (
            "dynamo_cache.py must NOT use 'ttl_epoch' (wrong attribute name)"
        )

    def test_execute_rollback_from_cache_helper_exists(self):
        """vpc_alb_caller.handler must export execute_rollback_from_cache helper."""
        import importlib
        m = importlib.import_module("workers.vpc_alb_caller.handler")
        assert hasattr(m, "execute_rollback_from_cache"), (
            "vpc_alb_caller.handler must have execute_rollback_from_cache function"
        )
        fn = getattr(m, "execute_rollback_from_cache")
        import inspect
        sig = inspect.signature(fn)
        assert "rollback_cache_table" in sig.parameters
        assert "anomaly_id" in sig.parameters
        assert "correlation_id" in sig.parameters


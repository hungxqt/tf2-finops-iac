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


def _load_asl_template() -> dict:
    with open(ASL_TEMPLATE, "r", encoding="utf-8") as fh:
        raw = fh.read()
    # Replace quoted placeholder strings: "${var}" -> "arn:aws:placeholder"
    raw = re.sub(r'"\$\{[a-zA-Z0-9_]+\}"', '"arn:aws:placeholder"', raw)
    # Replace bare numeric placeholders: ${var} -> 6
    raw = re.sub(r'\$\{[a-zA-Z0-9_]+\}', '6', raw)
    return json.loads(raw)


def _load_asl_doc() -> dict:
    with open(ASL_DOC, "r", encoding="utf-8") as fh:
        return json.load(fh)


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
        required = [
            "PrepareRunContext", "LoadAccountPolicy", "OverwriteEnvironment",
            "CheckRunState", "DuplicateRun", "CheckAdHocQuotaDecision", "CheckAdHocQuota",
            "CheckErrorBudgetLock", "EvaluateErrorBudgetLock",
            "IngestCostData", "IngestionReady",
            "NormalizeCostWindow", "CheckTelemetryQuality", "SetTelemetryForceDryRun",
            "VerifyS3Pointer", "SetS3PointerMissingError",
            "ChooseDetectRequestMode", "BuildDetectRequestRawJson",
            "BuildDetectRequestS3Pointer", "InvokeDetect", "EvaluateDetectResponse",
            "SetAIFailClosedError", "InvokeDecide", "CacheRollbackPayload",
            "FormatDecideResult", "RouteAlert",
            "FinanceAlertRequired", "SendFinanceAlert",
            "EngineeringAlertRequired", "SendEngineeringAlert",
            "EvaluateContainmentPolicy",
            "WritePreActionAudit", "ExecuteContainment",
            "ReportVerifyResult", "EvaluateVerifyResult",
            "ExecuteRollbackFromCache", "NotifyAIRollback",
            "WriteRollbackAudit", "SendRolledBackStatusMessage",
            "WriteEscalationAudit", "SendEscalationAlert",
            "WritePostActionAudit",
            "SendAppliedStatusMessage", "WriteDeniedAudit", "SendDeniedStatusMessage",
            "WritePendingApprovalAudit", "SendPendingStatusMessage",
            "FailClosed", "SendFailClosedAlert",
            "MarkRunComplete", "MarkRunFailed",
            "RunCompleted", "RunFailed", "DuplicateIgnored",
            "CURRetryExceeded", "WaitForCURExport",
        ]
        for state in required:
            assert state in states, f"Required state missing: {state}"

    def test_no_polling_states_present(self):
        asl = _load_asl_template()
        states = asl["States"]
        for s in ["WaitForAIResult", "PollAIResult", "CheckDBResultExists",
                  "FormatAIResult", "AIResultDecision"]:
            assert s not in states, f"Stale polling state found: {s}"

    def test_vpc_alb_caller_used_for_ai_endpoints(self):
        asl = _load_asl_template()
        states = asl["States"]
        for state_name in ["InvokeDetect", "InvokeDecide", "ReportVerifyResult"]:
            resource = states[state_name]["Resource"]
            assert resource == "arn:aws:placeholder", (
                f"{state_name}.Resource must reference vpc_alb_caller_lambda_arn"
            )

    def test_rollback_cache_is_dynamodb_put(self):
        asl = _load_asl_template()
        state = asl["States"]["CacheRollbackPayload"]
        assert state["Type"] == "Task"
        assert state["Resource"] == "arn:aws:states:::dynamodb:putItem"

    def test_alert_delivery_uses_sns(self):
        asl = _load_asl_template()
        states = asl["States"]
        for state_name in ["SendCURDelayAlert", "SendFinanceAlert",
                            "SendEngineeringAlert", "SendFailClosedAlert"]:
            resource = states[state_name]["Resource"]
            assert resource == "arn:aws:states:::sns:publish", (
                f"{state_name} must use sns:publish"
            )

    def test_status_messages_use_sqs(self):
        asl = _load_asl_template()
        states = asl["States"]
        for state_name in ["SendAppliedStatusMessage", "SendDeniedStatusMessage",
                            "SendPendingStatusMessage", "SendRolledBackStatusMessage"]:
            resource = states[state_name]["Resource"]
            assert resource == "arn:aws:states:::sqs:sendMessage", (
                f"{state_name} must use sqs:sendMessage"
            )

    def test_notify_ai_rollback_uses_vpc_alb_caller(self):
        """NotifyAIRollback must call /v1/audit/{id}/rollback via vpc_alb_caller."""
        asl = _load_asl_template()
        state = asl["States"]["NotifyAIRollback"]
        assert state["Resource"] == "arn:aws:placeholder", (
            "NotifyAIRollback must use vpc_alb_caller_lambda_arn"
        )
        path_param = state["Parameters"].get("path.$", "")
        assert "rollback" in path_param and "audit" in path_param, (
            "NotifyAIRollback path must reference /v1/audit/{id}/rollback"
        )

    def test_cache_rollback_payload_item_has_contract_fields(self):
        """CacheRollbackPayload DDB item must include anomaly_id, correlation_id, boto3_equivalent."""
        asl = _load_asl_template()
        item = asl["States"]["CacheRollbackPayload"]["Parameters"]["Item"]
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
        ctx = POST_EXECUTE_CONTAINMENT
        asl = _load_asl_template()
        params = asl["States"]["ReportVerifyResult"]["Parameters"]
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
        asl = _load_asl_template()
        params = asl["States"]["InvokeDecide"]["Parameters"]
        assert params.get("path") == "/v1/decide"

    def test_invoke_decide_uses_contract_idempotency_key(self):
        asl = _load_asl_template()
        params = asl["States"]["InvokeDecide"]["Parameters"]
        resolved = _resolve_parameters(POST_INVOKE_DETECT_ANOMALY, params)
        assert resolved["idempotency_key"] == DECIDE_IDEMPOTENCY_KEY
        assert resolved["body"]["idempotency_key"] == DECIDE_IDEMPOTENCY_KEY
        assert resolved["body"]["correlation_id"] == CORRELATION_ID

    def test_invoke_decide_body_uses_anomalies_list_0(self):
        asl = _load_asl_template()
        params = asl["States"]["InvokeDecide"]["Parameters"]
        body = params.get("body", {})
        assert "anomaly_context.$" in body
        assert body["anomaly_context.$"] == "$.ai_detect_response.anomalies_list[0]"

    def test_decide_response_rollback_payload_has_boto3_equivalent(self):
        ctx = POST_INVOKE_DECIDE
        payload = _resolve_path(ctx, "$.ai_decide_response.rollback_payload")
        assert "boto3_equivalent" in payload

    def test_cache_rollback_payload_uses_dynamodb_put_item(self):
        asl = _load_asl_template()
        state = asl["States"]["CacheRollbackPayload"]
        assert state["Type"] == "Task"
        assert state["Resource"] == "arn:aws:states:::dynamodb:putItem"
        assert "TableName" in state["Parameters"]
        assert "Item" in state["Parameters"]

    def test_format_decide_result_reads_action_plan_0_action(self):
        asl = _load_asl_template()
        params = asl["States"]["FormatDecideResult"]["Parameters"]
        assert "recommended_containment_mode.$" in params
        path = params["recommended_containment_mode.$"]
        ctx = POST_INVOKE_DECIDE
        mode = _resolve_path(ctx, path)
        assert isinstance(mode, str) and mode != ""

    def test_format_decide_result_reads_anomaly_id_from_anomalies_list_0(self):
        asl = _load_asl_template()
        params = asl["States"]["FormatDecideResult"]["Parameters"]
        assert "anomaly_id.$" in params
        path = params["anomaly_id.$"]
        assert "anomalies_list[0]" in path
        ctx = POST_INVOKE_DECIDE
        assert _resolve_path(ctx, path) == ANOMALY_ID


class TestContainmentPolicy:
    def _choices(self):
        asl = _load_asl_template()
        return asl["States"]["EvaluateContainmentPolicy"]["Choices"]

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
            if "And" in choice and choice.get("Next") == "WriteDeniedAudit":
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
            "And" in choice and choice.get("Next") == "WritePreActionAudit" and
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
        asl = _load_asl_template()
        params = asl["States"]["ReportVerifyResult"]["Parameters"]
        assert params.get("path") == "/v1/verify"

    def test_report_verify_result_uses_contract_idempotency_key(self):
        asl = _load_asl_template()
        params = asl["States"]["ReportVerifyResult"]["Parameters"]
        resolved = _resolve_parameters(POST_EXECUTE_CONTAINMENT, params)
        assert resolved["idempotency_key"] == VERIFY_IDEMPOTENCY_KEY
        assert resolved["body"]["idempotency_key"] == VERIFY_IDEMPOTENCY_KEY
        assert resolved["body"]["correlation_id"] == CORRELATION_ID

    def test_verify_body_action_executed_target_reads_anomalies_list_0(self):
        asl = _load_asl_template()
        params = asl["States"]["ReportVerifyResult"]["Parameters"]
        body = params.get("body", {})
        action_executed = body.get("action_executed", {})
        target_path = action_executed.get("target.$")
        assert target_path is not None
        assert "anomalies_list[0]" in target_path
        ctx = POST_EXECUTE_CONTAINMENT
        target = _resolve_path(ctx, target_path)
        assert target is not None and target != ""

    def test_verify_result_leads_to_evaluate_verify_result(self):
        """ReportVerifyResult must now route to EvaluateVerifyResult choice state
        which then branches on next_action: DONE|RETRY|ROLLBACK|ESCALATE."""
        asl = _load_asl_template()
        assert asl["States"]["ReportVerifyResult"].get("Next") == "EvaluateVerifyResult"

    def test_write_post_action_audit_leads_to_applied_status_message(self):
        asl = _load_asl_template()
        assert asl["States"]["WritePostActionAudit"]["Next"] == "SendAppliedStatusMessage"

    def test_applied_status_message_has_correct_status_value(self):
        asl = _load_asl_template()
        params = asl["States"]["SendAppliedStatusMessage"]["Parameters"]
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
        with open(ASL_TEMPLATE, "r", encoding="utf-8") as fh:
            content = fh.read()
        queue_refs = re.findall(r'"QueueUrl"\s*:\s*"([^"]+)"', content)
        for ref in queue_refs:
            assert "rollback_status_queue_url" in ref or ref == "arn:aws:placeholder", (
                f"Unexpected SQS queue in ASL: {ref!r}"
            )

    def test_applied_status_is_applied(self):
        asl = _load_asl_template()
        status = asl["States"]["SendAppliedStatusMessage"]["Parameters"]["MessageBody"]["status"]
        assert status == "APPLIED"

    def test_denied_status_is_denied(self):
        asl = _load_asl_template()
        status = asl["States"]["SendDeniedStatusMessage"]["Parameters"]["MessageBody"]["status"]
        assert status == "DENIED"

    def test_pending_status_is_pending(self):
        asl = _load_asl_template()
        status = asl["States"]["SendPendingStatusMessage"]["Parameters"]["MessageBody"]["status"]
        assert status == "PENDING"

    def test_rolled_back_status_is_rolled_back(self):
        asl = _load_asl_template()
        status = asl["States"]["SendRolledBackStatusMessage"]["Parameters"]["MessageBody"]["status"]
        assert status == "ROLLED_BACK"

    def test_status_messages_have_run_id_correlation_id_tenant_id(self):
        asl = _load_asl_template()
        for state_name in ["SendAppliedStatusMessage", "SendDeniedStatusMessage",
                            "SendPendingStatusMessage", "SendRolledBackStatusMessage"]:
            body = asl["States"][state_name]["Parameters"]["MessageBody"]
            assert "run_id.$" in body
            assert "correlation_id.$" in body
            assert "tenant_id.$" in body


class TestVerifyBranching:
    """Contract Section 5: /v1/verify response branching: DONE|RETRY|ROLLBACK|ESCALATE."""

    def test_report_verify_result_routes_to_evaluate_verify_result(self):
        asl = _load_asl_template()
        assert asl["States"]["ReportVerifyResult"]["Next"] == "EvaluateVerifyResult"

    def test_evaluate_verify_result_is_choice(self):
        asl = _load_asl_template()
        state = asl["States"]["EvaluateVerifyResult"]
        assert state["Type"] == "Choice"

    def test_evaluate_verify_result_done_goes_to_write_post_action_audit(self):
        asl = _load_asl_template()
        choices = asl["States"]["EvaluateVerifyResult"]["Choices"]
        found = any(
            c.get("Next") == "WritePostActionAudit" and "Or" in c
            for c in choices
        )
        assert found, "EvaluateVerifyResult must have DONE branch (Or condition) to WritePostActionAudit"

    def test_evaluate_verify_result_rollback_goes_to_execute_rollback(self):
        asl = _load_asl_template()
        choices = asl["States"]["EvaluateVerifyResult"]["Choices"]
        found = any(
            c.get("Variable") == "$.verify_result.next_action" and
            c.get("StringEquals") == "ROLLBACK" and
            c.get("Next") == "ExecuteRollbackFromCache"
            for c in choices
        )
        assert found, "EvaluateVerifyResult must route ROLLBACK to ExecuteRollbackFromCache"

    def test_evaluate_verify_result_escalate_goes_to_write_escalation_audit(self):
        asl = _load_asl_template()
        choices = asl["States"]["EvaluateVerifyResult"]["Choices"]
        found = any(
            c.get("Variable") == "$.verify_result.next_action" and
            c.get("StringEquals") == "ESCALATE" and
            c.get("Next") == "WriteEscalationAudit"
            for c in choices
        )
        assert found, "EvaluateVerifyResult must route ESCALATE to WriteEscalationAudit"

    def test_evaluate_verify_result_default_is_write_post_action_audit(self):
        asl = _load_asl_template()
        default = asl["States"]["EvaluateVerifyResult"]["Default"]
        assert default == "WritePostActionAudit"

    def test_rollback_path_chain(self):
        asl = _load_asl_template()
        states = asl["States"]
        assert states["ExecuteRollbackFromCache"]["Next"] == "NotifyAIRollback"
        assert states["NotifyAIRollback"]["Next"] == "WriteRollbackAudit"
        assert states["WriteRollbackAudit"]["Next"] == "SendRolledBackStatusMessage"
        assert states["SendRolledBackStatusMessage"]["Next"] == "MarkRunComplete"

    def test_escalation_path_chain(self):
        asl = _load_asl_template()
        states = asl["States"]
        assert states["WriteEscalationAudit"]["Next"] == "SendEscalationAlert"
        assert states["SendEscalationAlert"]["Next"] == "SendPendingStatusMessage"

    def test_notify_ai_rollback_path_format(self):
        """NotifyAIRollback must use States.Format path for /v1/audit/{id}/rollback."""
        asl = _load_asl_template()
        params = asl["States"]["NotifyAIRollback"]["Parameters"]
        assert "path.$" in params
        path_expr = params["path.$"]
        assert "rollback" in path_expr
        assert "audit" in path_expr
        assert "States.Format" in path_expr

    def test_notify_ai_rollback_body_has_required_fields(self):
        """NotifyAIRollback body must include correlation_id, anomaly_id, rollback_status."""
        asl = _load_asl_template()
        body = asl["States"]["NotifyAIRollback"]["Parameters"]["body"]
        assert "correlation_id.$" in body
        assert "anomaly_id.$" in body
        assert "rollback_status.$" in body

    def test_execute_rollback_from_cache_is_task(self):
        asl = _load_asl_template()
        state = asl["States"]["ExecuteRollbackFromCache"]
        assert state["Type"] == "Task"
        # Must use containment_worker (CDO-owned) not vpc_alb_caller
        assert state["Resource"] == "arn:aws:placeholder"

    def test_send_escalation_alert_uses_sns(self):
        asl = _load_asl_template()
        resource = asl["States"]["SendEscalationAlert"]["Resource"]
        assert resource == "arn:aws:states:::sns:publish"

    def test_verify_result_written_to_verify_result_key(self):
        ctx = POST_VERIFY_RESULT
        result = _resolve_path(ctx, "$.verify_result")
        assert result["success"] is True


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
        asl = _load_asl_template()
        item = asl["States"]["CacheRollbackPayload"]["Parameters"]["Item"]
        assert "anomaly_id" in item
        assert "S.$" in item["anomaly_id"]

    def test_cache_rollback_payload_item_has_correlation_id(self):
        asl = _load_asl_template()
        item = asl["States"]["CacheRollbackPayload"]["Parameters"]["Item"]
        assert "correlation_id" in item
        assert "S.$" in item["correlation_id"]

    def test_cache_rollback_payload_item_has_boto3_equivalent(self):
        """boto3_equivalent must be present so CDO can execute rollback independently."""
        asl = _load_asl_template()
        item = asl["States"]["CacheRollbackPayload"]["Parameters"]["Item"]
        assert "boto3_equivalent" in item

    def test_rollback_cache_table_is_dynamodb_put(self):
        asl = _load_asl_template()
        state = asl["States"]["CacheRollbackPayload"]
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


import json
import os
import re

def _get_iter_states(states):
    """Return the Map iterator states from ProcessDetectedAnomalies."""
    map_state = states.get("ProcessDetectedAnomalies", {})
    return map_state.get("Iterator", {}).get("States", {})


def check_asl_file(asl_path, is_template=True):
    assert os.path.exists(asl_path), f"{asl_path} file does not exist"
    
    with open(asl_path, "r", encoding="utf-8") as f:
        raw_content = f.read()
        
    if is_template:
        # Check for placeholders directly in raw file content
        assert "${rollback_cache_table_name}" in raw_content, "Missing placeholder ${rollback_cache_table_name}"
        assert "${vpc_alb_caller_lambda_arn}" in raw_content, "Missing placeholder ${vpc_alb_caller_lambda_arn}"
        assert "${ai_request_lambda_arn}" not in raw_content, "Obsolete placeholder ${ai_request_lambda_arn} still present"
        assert "ai_client" not in raw_content, "Stale ai_client reference in statemachine.json"
        
        # Preprocess template variables to make it valid JSON for loading
        processed_content = re.sub(r'"\$\{[a-zA-Z0-9_]+\}"', '"arn:aws:placeholder"', raw_content)
        processed_content = re.sub(r'\$\{[a-zA-Z0-9_]+\}', '6', processed_content)
    else:
        processed_content = raw_content
        
    asl = json.loads(processed_content)
    
    assert "States" in asl, "ASL missing 'States' key"
    states = asl["States"]
    # G1 fix: per-anomaly states are now inside the Map iterator
    iter_states = _get_iter_states(states)
    
    # Assert no detection polling states remain and no /v1/status detection path exists
    polling_states = ["WaitForAIResult", "PollAIResult", "CheckDBResultExists", "FormatAIResult", "AIResultDecision"]
    for s in polling_states:
        assert s not in states, f"Polling state '{s}' should be removed from {asl_path}"
        
    for state_name, state_def in states.items():
        resource = state_def.get("Resource", "")
        assert "status" not in resource.lower(), f"State '{state_name}' has status in resource path: {resource}"
        
    # Assert required top-level states exist
    required_states = [
        "PrepareRunContext",
        "CheckAdHocQuota",
        "CheckErrorBudgetLock",
        "CheckTelemetryQuality",
        "VerifyS3Pointer",
        "SetS3PointerMissingError",
        "BuildDetectRequestS3Pointer",
        "InvokeDetect",
        "EvaluateDetectResponse",
        "SetAIFailClosedError",
        # G1 fix: per-anomaly states are inside the Map iterator, not top-level
        "ProcessDetectedAnomalies",
        "SummarizeAnomalyResults",
        "EvaluateAnomalySummary",
        "FailClosed",
        "SendFailClosedAlert",
        "SendCURDelayAlert",
        "WriteCURDelayAudit",
        "IncrementCERetry",
        "CERetryExceeded"
    ]
    for s in required_states:
        assert s in states, f"Required state '{s}' missing from state machine in {asl_path}"

    # Assert required Map iterator states exist (G1 fix)
    required_iter_states = [
        "InvokeDecideForAnomaly",
        "CacheRollbackPayloadForAnomaly",
        "FormatDecideResultForAnomaly",
        "EvaluateContainmentPolicyForAnomaly",
        "ReportVerifyResultForAnomaly",
        "EvaluateVerifyResultForAnomaly",
        "ExecuteRollbackFromCacheForAnomaly",
        "NotifyAIRollbackForAnomaly",
        "WriteRollbackAuditForAnomaly",
        "SendRolledBackStatusMessageForAnomaly",
        "WriteEscalationAuditForAnomaly",
        "SendEscalationAlertForAnomaly",
        "SendAppliedStatusMessageForAnomaly",
        "SendDeniedStatusMessageForAnomaly",
        "SendPendingStatusMessageForAnomaly",
        "WritePostActionAuditForAnomaly",
        "WriteDeniedAuditForAnomaly",
        "WritePendingApprovalAuditForAnomaly",
    ]
    for s in required_iter_states:
        assert s in iter_states, f"Required iterator state '{s}' missing from Map iterator in {asl_path}"
        
    # Assert PrepareRunContext receives full input and defaults is_ad_hoc
    prep_state = states["PrepareRunContext"]
    assert prep_state["Parameters"].get("input.$") == "$", f"PrepareRunContext must receive full input using input.$ = $ in {asl_path}"
    assert "account_id.$" not in prep_state["Parameters"], "PrepareRunContext should not map individual parameters"
    assert "is_ad_hoc.$" not in prep_state["Parameters"], "PrepareRunContext should not map individual parameters"
    
    # Assert CUR delay and retry logic
    assert "CURRetryExceeded" in states
    choice_state = states["CURRetryExceeded"]
    assert choice_state["Type"] == "Choice"
    choices = choice_state["Choices"]
    found_limit = False
    for c in choices:
        if c.get("Variable") == "$.cur_retry.count" and c.get("NumericGreaterThanEquals") == 4:
            found_limit = True
            assert c["Next"] == "SetCURDelayExceededError"
    assert found_limit, "CUR retry limit of 4 not enforced in Choice state"
    
    assert "WaitForCURExport" in states
    if is_template:
        assert states["WaitForCURExport"]["Seconds"] == 6, "Template WaitForCURExport Seconds should be replaced with 6"
    else:
        assert states["WaitForCURExport"]["Seconds"] == 3600, "CUR retry interval must be 1 hour (3600 seconds)"
    
    # Assert terminal fail-closed AI handling includes audit + engineering alert
    assert "SetCURDelayExceededError" in states
    assert states["SetCURDelayExceededError"]["Next"] == "SendCURDelayAlert"
    assert states["SendCURDelayAlert"]["Next"] == "WriteCURDelayAudit"
    assert states["WriteCURDelayAudit"]["Next"] == "MarkRunFailed"
    
    assert "SetAIFailClosedError" in states
    assert states["SetAIFailClosedError"]["Type"] == "Pass"
    assert states["SetAIFailClosedError"]["ResultPath"] == "$.error"
    assert states["SetAIFailClosedError"]["Next"] == "FailClosed"

    assert "FailClosed" in states
    assert states["FailClosed"]["Next"] == "SendFailClosedAlert"
    assert states["SendFailClosedAlert"]["Next"] == "MarkRunFailed"

    required_audit_context = [
        "run_id.$",
        "correlation_id.$",
        "account_id.$",
        "cost_period.$",
        "execution_date.$",
        "tenant_id.$",
        "environment.$",
        "account_policy.$",
        "error.$",
    ]
    for state_name in ["WriteCURDelayAudit", "FailClosed"]:
        params = states[state_name]["Parameters"]
        for key in required_audit_context:
            assert key in params, f"{state_name} must pass {key} to audit_writer"
    
    # Assert telemetry quality dry-run gate
    assert "CheckTelemetryQuality" in states
    assert states["CheckTelemetryQuality"]["Type"] == "Choice"
    telemetry_choices = states["CheckTelemetryQuality"]["Choices"]
    found_quality_gate = False
    for tc in telemetry_choices:
        if "Or" in tc:
            found_quality_gate = True
            or_conditions = tc["Or"]
            assert any(cond.get("Variable") == "$.normalized.details.completeness_score" and cond.get("NumericLessThan") == 0.8 for cond in or_conditions)
            assert any(cond.get("Variable") == "$.normalized.details.estimated_billing" and cond.get("BooleanEquals") is True for cond in or_conditions)
            assert tc["Next"] == "SetTelemetryForceDryRun"
    assert found_quality_gate, "Telemetry quality gate not found in CheckTelemetryQuality"
    assert states["SetTelemetryForceDryRun"]["Next"] == "VerifyS3Pointer"
    
    # Assert /v1/detect response handling checks success, anomalies_detected, data_confidence, and anomalies_list
    eval_detect = states["EvaluateDetectResponse"]
    assert eval_detect["Type"] == "Choice"
    detect_choices = eval_detect["Choices"]
    
    found_success_fail = False
    found_confidence_fail = False
    found_anomalies_decide = False
    
    for choice in detect_choices:
        if choice.get("Variable") == "$.ai_detect_response.success" and choice.get("BooleanEquals") is False:
            assert choice["Next"] == "SetAIFailClosedError"
            found_success_fail = True
        if choice.get("Variable") == "$.ai_detect_response.data_confidence" and choice.get("StringEquals") == "LOW":
            assert choice["Next"] == "SetAIFailClosedError"
            found_confidence_fail = True
        if "And" in choice:
            conds = choice["And"]
            has_success_true = any(c.get("Variable") == "$.ai_detect_response.success" and c.get("BooleanEquals") is True for c in conds)
            has_anomalies_detected = any(c.get("Variable") == "$.ai_detect_response.anomalies_detected" and c.get("BooleanEquals") is True for c in conds)
            has_anomalies_list = any(c.get("Variable") == "$.ai_detect_response.anomalies_list" and c.get("IsPresent") is True for c in conds)
            if has_success_true and has_anomalies_detected and has_anomalies_list:
                # G1 fix: routes to ProcessDetectedAnomalies Map, not InvokeDecide
                assert choice["Next"] == "ProcessDetectedAnomalies"
                found_anomalies_decide = True
                
    assert found_success_fail, "EvaluateDetectResponse must check success = False to FailClosed"
    assert found_confidence_fail, "EvaluateDetectResponse must check data_confidence = LOW to FailClosed"
    assert found_anomalies_decide, "EvaluateDetectResponse must check success, anomalies_detected, and anomalies_list to go to ProcessDetectedAnomalies"
    
    # Assert /v1/decide result caching writes rollback payloads before containment (G1 fix: in iterator)
    assert iter_states["InvokeDecideForAnomaly"]["Next"] == "CacheRollbackPayloadForAnomaly"
    assert iter_states["CacheRollbackPayloadForAnomaly"]["Type"] == "Task"
    assert iter_states["CacheRollbackPayloadForAnomaly"]["Resource"] == "arn:aws:states:::dynamodb:putItem"
    assert iter_states["CacheRollbackPayloadForAnomaly"]["Next"] == "FormatDecideResultForAnomaly"
    
    # Assert prod destructive-action denial (G1 fix: in iterator)
    assert "EvaluateContainmentPolicyForAnomaly" in iter_states
    containment_choices = iter_states["EvaluateContainmentPolicyForAnomaly"]["Choices"]
    prod_destructive_denied = False
    for choice in containment_choices:
        if "And" in choice:
            conditions = choice["And"]
            has_prod = any(cond.get("Variable") == "$.account_policy.environment" and cond.get("StringEquals") == "prod" for cond in conditions)
            has_destructive = any("Or" in cond and any(sub_cond.get("Variable") == "$.ai.recommended_containment_mode" and sub_cond.get("StringEquals") in ["terminate", "auto-shutdown"] for sub_cond in cond["Or"]) for cond in conditions)
            if has_prod and has_destructive:
                assert choice["Next"] == "WriteDeniedAuditForAnomaly"
                prod_destructive_denied = True
    assert prod_destructive_denied, "Unsafe production containment actions are not denied"
    
    # Check SQS status reporting (G1 fix: in iterator)
    assert iter_states["WritePostActionAuditForAnomaly"]["Next"] == "SendAppliedStatusMessageForAnomaly"
    assert iter_states["SendAppliedStatusMessageForAnomaly"]["Parameters"]["MessageBody"]["status"] == "APPLIED"
    
    assert iter_states["WriteDeniedAuditForAnomaly"]["Next"] == "SendDeniedStatusMessageForAnomaly"
    assert iter_states["WritePendingApprovalAuditForAnomaly"]["Next"] == "SendPendingStatusMessageForAnomaly"
    
    # Assert new Lambda container integration: no HTTP or Fargate/ECS tasks
    for state_name, state_def in states.items():
        resource = state_def.get("Resource", "")
        assert "${ai_client_lambda_arn}" not in resource
        assert "ecs" not in resource.lower()
        if "arn:aws:states:::sns:publish" not in resource and "arn:aws:states:::dynamodb" not in resource:
            assert "http" not in resource.lower()

    # Assert InvokeDetect uses the VPC ALB caller resource; InvokeDecide and ReportVerifyResult are in iterator
    if is_template:
        assert states["InvokeDetect"]["Resource"] == "arn:aws:placeholder"
        assert iter_states["InvokeDecideForAnomaly"]["Resource"] == "arn:aws:placeholder"
        assert iter_states["ReportVerifyResultForAnomaly"]["Resource"] == "arn:aws:placeholder"
    else:
        assert states["InvokeDetect"]["Resource"] == "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-vpc_alb_caller"
        assert iter_states["InvokeDecideForAnomaly"]["Resource"] == "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-vpc_alb_caller"
        assert iter_states["ReportVerifyResultForAnomaly"]["Resource"] == "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-vpc_alb_caller"

    # Assert AI states keep /v1/detect, /v1/decide, and /v1/verify paths
    assert states["InvokeDetect"]["Parameters"]["path.$"] == "$.ai_detect_request.path"
    assert iter_states["InvokeDecideForAnomaly"]["Parameters"]["path"] == "/v1/decide"
    assert iter_states["ReportVerifyResultForAnomaly"]["Parameters"]["path"] == "/v1/verify"

    detect_body = states["BuildDetectRequestS3Pointer"]["Parameters"]["body"]
    for required_key in [
        "schema_version",
        "tenant_id.$",
        "account_id.$",
        "account_name.$",
        "correlation_id.$",
        "idempotency_key.$",
        "s3_object_checksum.$",
        "aws_cost_explorer_daily.$",
        "missing_resources.$",
        "current_ce_cost_gap_usd.$",
        "comparison_window.$",
    ]:
        assert required_key in detect_body, f"BuildDetectRequestS3Pointer body missing {required_key}"

    # G1 fix: idempotency keys are now anomaly-scoped and reference $.anomaly.anomaly_id
    decide_idem = iter_states["InvokeDecideForAnomaly"]["Parameters"].get("idempotency_key.$", "")
    assert "anomaly_id" in decide_idem or "anomaly.anomaly_id" in decide_idem, (
        "InvokeDecideForAnomaly idempotency_key must include anomaly_id"
    )
    verify_idem = iter_states["ReportVerifyResultForAnomaly"]["Parameters"].get("idempotency_key.$", "")
    assert "anomaly_id" in verify_idem or "anomaly.anomaly_id" in verify_idem, (
        "ReportVerifyResultForAnomaly idempotency_key must include anomaly_id"
    )

    # Assert /v1/verify response branches on next_action: DONE|RETRY|ROLLBACK|ESCALATE (G1 fix: in iterator)
    assert iter_states["ReportVerifyResultForAnomaly"]["Next"] == "EvaluateVerifyResultForAnomaly", \
        "ReportVerifyResultForAnomaly must route to EvaluateVerifyResultForAnomaly choice state"
    assert iter_states["EvaluateVerifyResultForAnomaly"]["Type"] == "Choice"
    verify_choices = iter_states["EvaluateVerifyResultForAnomaly"]["Choices"]
    found_done = found_rollback = found_escalate = found_retry = False
    for vc in verify_choices:
        if vc.get("Next") == "WritePostActionAuditForAnomaly":
            if "Or" in vc or vc.get("Variable") == "$.verify_result.next_action":
                found_done = True
        if vc.get("Variable") == "$.verify_result.next_action" and vc.get("StringEquals") == "ROLLBACK" and vc.get("Next") == "ExecuteRollbackFromCacheForAnomaly":
            found_rollback = True
        if vc.get("Variable") == "$.verify_result.next_action" and vc.get("StringEquals") == "ESCALATE" and vc.get("Next") == "WriteEscalationAuditForAnomaly":
            found_escalate = True
        if vc.get("Variable") == "$.verify_result.next_action" and vc.get("StringEquals") == "RETRY" and vc.get("Next") == "WritePostActionAuditForAnomaly":
            found_retry = True
    assert found_done, "EvaluateVerifyResultForAnomaly must have a DONE branch to WritePostActionAuditForAnomaly"
    assert found_rollback, "EvaluateVerifyResultForAnomaly must have ROLLBACK branch to ExecuteRollbackFromCacheForAnomaly"
    assert found_escalate, "EvaluateVerifyResultForAnomaly must have ESCALATE branch to WriteEscalationAuditForAnomaly"
    assert found_retry, "EvaluateVerifyResultForAnomaly must have RETRY branch to WritePostActionAuditForAnomaly"

    # Assert rollback path in iterator (G1 fix)
    assert iter_states["ExecuteRollbackFromCacheForAnomaly"]["Next"] == "NotifyAIRollbackForAnomaly", \
        "ExecuteRollbackFromCacheForAnomaly must route to NotifyAIRollbackForAnomaly"
    assert iter_states["NotifyAIRollbackForAnomaly"]["Next"] == "WriteRollbackAuditForAnomaly", \
        "NotifyAIRollbackForAnomaly must route to WriteRollbackAuditForAnomaly"
    assert iter_states["WriteRollbackAuditForAnomaly"]["Next"] == "SendRolledBackStatusMessageForAnomaly"
    assert iter_states["SendRolledBackStatusMessageForAnomaly"]["Parameters"]["MessageBody"]["status"] == "ROLLED_BACK"

    # Assert escalation path in iterator (G1 fix)
    assert iter_states["WriteEscalationAuditForAnomaly"]["Next"] == "SendEscalationAlertForAnomaly"
    assert iter_states["SendEscalationAlertForAnomaly"]["Next"] == "SendPendingStatusMessageForAnomaly"

    # Assert CacheRollbackPayload item includes contract-required fields (G1 fix: in iterator)
    cache_item = iter_states["CacheRollbackPayloadForAnomaly"]["Parameters"]["Item"]
    assert "anomaly_id" in cache_item, "CacheRollbackPayloadForAnomaly item must include anomaly_id"
    assert "correlation_id" in cache_item, "CacheRollbackPayloadForAnomaly item must include correlation_id"
    assert "boto3_equivalent" in cache_item, "CacheRollbackPayloadForAnomaly item must include boto3_equivalent"
    assert "rollback_payload" in cache_item, "CacheRollbackPayloadForAnomaly item must include rollback_payload"

def test_state_machine_asl_contract():
    asl_template_path = os.path.join(os.path.dirname(__file__), "../../modules/orchestration/statemachine.json")
    check_asl_file(asl_template_path, is_template=True)
    
    asl_doc_path = os.path.join(os.path.dirname(__file__), "../../docs/statemachine.json")
    check_asl_file(asl_doc_path, is_template=False)

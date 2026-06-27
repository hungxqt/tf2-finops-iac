import json
import os
import re

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
    
    # Assert no detection polling states remain and no /v1/status detection path exists
    polling_states = ["WaitForAIResult", "PollAIResult", "CheckDBResultExists", "FormatAIResult", "AIResultDecision"]
    for s in polling_states:
        assert s not in states, f"Polling state '{s}' should be removed from {asl_path}"
        
    for state_name, state_def in states.items():
        resource = state_def.get("Resource", "")
        assert "status" not in resource.lower(), f"State '{state_name}' has status in resource path: {resource}"
        
    # Assert required states exist
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
        "InvokeDecide",
        "CacheRollbackPayload",
        "FormatDecideResult",
        "EvaluateContainmentPolicy",
        "ReportVerifyResult",
        "EvaluateVerifyResult",
        "ExecuteRollbackFromCache",
        "NotifyAIRollback",
        "WriteRollbackAudit",
        "SendRolledBackStatusMessage",
        "WriteEscalationAudit",
        "SendEscalationAlert",
        "SendAppliedStatusMessage",
        "SendDeniedStatusMessage",
        "SendPendingStatusMessage",
        "FailClosed",
        "SendFailClosedAlert",
        "SendCURDelayAlert",
        "WriteCURDelayAudit",
        "IncrementCERetry",
        "CERetryExceeded"
    ]
    for s in required_states:
        assert s in states, f"Required state '{s}' missing from state machine in {asl_path}"
        
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
                assert choice["Next"] == "InvokeDecide"
                found_anomalies_decide = True
                
    assert found_success_fail, "EvaluateDetectResponse must check success = False to FailClosed"
    assert found_confidence_fail, "EvaluateDetectResponse must check data_confidence = LOW to FailClosed"
    assert found_anomalies_decide, "EvaluateDetectResponse must check success, anomalies_detected, and anomalies_list to go to InvokeDecide"
    
    # Assert /v1/decide result caching writes rollback payloads before containment
    assert states["InvokeDecide"]["Next"] == "CacheRollbackPayload"
    assert states["CacheRollbackPayload"]["Type"] == "Task"
    assert states["CacheRollbackPayload"]["Resource"] == "arn:aws:states:::dynamodb:putItem"
    assert states["CacheRollbackPayload"]["Next"] == "FormatDecideResult"
    
    # Assert prod destructive-action denial
    assert "EvaluateContainmentPolicy" in states
    containment_choices = states["EvaluateContainmentPolicy"]["Choices"]
    prod_destructive_denied = False
    for choice in containment_choices:
        if "And" in choice:
            conditions = choice["And"]
            has_prod = any(cond.get("Variable") == "$.account_policy.environment" and cond.get("StringEquals") == "prod" for cond in conditions)
            has_destructive = any("Or" in cond and any(sub_cond.get("Variable") == "$.ai.recommended_containment_mode" and sub_cond.get("StringEquals") in ["terminate", "auto-shutdown"] for sub_cond in cond["Or"]) for cond in conditions)
            if has_prod and has_destructive:
                assert choice["Next"] == "WriteDeniedAudit"
                prod_destructive_denied = True
    assert prod_destructive_denied, "Unsafe production containment actions are not denied"
    
    # Check SQS status reporting
    assert states["WritePostActionAudit"]["Next"] == "SendAppliedStatusMessage"
    assert states["SendAppliedStatusMessage"]["Parameters"]["MessageBody"]["status"] == "APPLIED"
    
    assert states["WriteDeniedAudit"]["Next"] == "SendDeniedStatusMessage"
    assert states["WritePendingApprovalAudit"]["Next"] == "SendPendingStatusMessage"
    
    # Assert new Lambda container integration: no HTTP or Fargate/ECS tasks
    for state_name, state_def in states.items():
        resource = state_def.get("Resource", "")
        assert "${ai_client_lambda_arn}" not in resource
        assert "ecs" not in resource.lower()
        if "arn:aws:states:::sns:publish" not in resource and "arn:aws:states:::dynamodb" not in resource:
            assert "http" not in resource.lower()

    # Assert InvokeDetect, InvokeDecide, ReportVerifyResult use the VPC ALB caller resource
    if is_template:
        assert states["InvokeDetect"]["Resource"] == "arn:aws:placeholder"
        assert states["InvokeDecide"]["Resource"] == "arn:aws:placeholder"
        assert states["ReportVerifyResult"]["Resource"] == "arn:aws:placeholder"
    else:
        assert states["InvokeDetect"]["Resource"] == "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-vpc_alb_caller"
        assert states["InvokeDecide"]["Resource"] == "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-vpc_alb_caller"
        assert states["ReportVerifyResult"]["Resource"] == "arn:aws:lambda:ap-southeast-1:123456789012:function:tf2-finops-sandbox-vpc_alb_caller"

    # Assert AI states keep /v1/detect, /v1/decide, and /v1/verify paths
    assert states["InvokeDetect"]["Parameters"]["path.$"] == "$.ai_detect_request.path"
    assert states["InvokeDecide"]["Parameters"]["path"] == "/v1/decide"
    assert states["ReportVerifyResult"]["Parameters"]["path"] == "/v1/verify"

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

    assert states["InvokeDecide"]["Parameters"]["idempotency_key.$"] == "States.Format('{}:{}:decide', $.tenant_id, $.execution_date)"
    assert states["InvokeDecide"]["Parameters"]["body"]["idempotency_key.$"] == "States.Format('{}:{}:decide', $.tenant_id, $.execution_date)"
    assert states["ReportVerifyResult"]["Parameters"]["idempotency_key.$"] == "States.Format('{}:{}:verify', $.tenant_id, $.execution_date)"
    assert states["ReportVerifyResult"]["Parameters"]["body"]["idempotency_key.$"] == "States.Format('{}:{}:verify', $.tenant_id, $.execution_date)"

    # Assert /v1/verify response branches on next_action: DONE|RETRY|ROLLBACK|ESCALATE (contract Section 5)
    assert states["ReportVerifyResult"]["Next"] == "EvaluateVerifyResult", \
        "ReportVerifyResult must route to EvaluateVerifyResult choice state"
    assert states["EvaluateVerifyResult"]["Type"] == "Choice"
    verify_choices = states["EvaluateVerifyResult"]["Choices"]
    found_done = found_rollback = found_escalate = found_retry = False
    for vc in verify_choices:
        if vc.get("Next") == "WritePostActionAudit":
            # DONE branch (either via Or with next_action=DONE or success=true)
            if "Or" in vc or vc.get("Variable") == "$.verify_result.next_action":
                found_done = True
        if vc.get("Variable") == "$.verify_result.next_action" and vc.get("StringEquals") == "ROLLBACK" and vc.get("Next") == "ExecuteRollbackFromCache":
            found_rollback = True
        if vc.get("Variable") == "$.verify_result.next_action" and vc.get("StringEquals") == "ESCALATE" and vc.get("Next") == "WriteEscalationAudit":
            found_escalate = True
        if vc.get("Variable") == "$.verify_result.next_action" and vc.get("StringEquals") == "RETRY" and vc.get("Next") == "WritePostActionAudit":
            found_retry = True
    assert found_done, "EvaluateVerifyResult must have a DONE branch to WritePostActionAudit"
    assert found_rollback, "EvaluateVerifyResult must have ROLLBACK branch to ExecuteRollbackFromCache"
    assert found_escalate, "EvaluateVerifyResult must have ESCALATE branch to WriteEscalationAudit"
    assert found_retry, "EvaluateVerifyResult must have RETRY branch to WritePostActionAudit"

    # Assert rollback path: ExecuteRollbackFromCache → NotifyAIRollback → WriteRollbackAudit → SendRolledBackStatusMessage
    assert states["ExecuteRollbackFromCache"]["Next"] == "NotifyAIRollback", \
        "ExecuteRollbackFromCache must route to NotifyAIRollback"
    assert states["NotifyAIRollback"]["Next"] == "WriteRollbackAudit", \
        "NotifyAIRollback must route to WriteRollbackAudit"
    assert states["WriteRollbackAudit"]["Next"] == "SendRolledBackStatusMessage"
    assert states["SendRolledBackStatusMessage"]["Parameters"]["MessageBody"]["status"] == "ROLLED_BACK"

    # Assert escalation path: WriteEscalationAudit → SendEscalationAlert → SendPendingStatusMessage
    assert states["WriteEscalationAudit"]["Next"] == "SendEscalationAlert"
    assert states["SendEscalationAlert"]["Next"] == "SendPendingStatusMessage"

    # Assert CacheRollbackPayload item includes correlation_id and boto3_equivalent
    cache_item = states["CacheRollbackPayload"]["Parameters"]["Item"]
    assert "anomaly_id" in cache_item, "CacheRollbackPayload item must include anomaly_id"
    assert "correlation_id" in cache_item, "CacheRollbackPayload item must include correlation_id"
    assert "boto3_equivalent" in cache_item, "CacheRollbackPayload item must include boto3_equivalent"
    assert "rollback_payload" in cache_item, "CacheRollbackPayload item must include rollback_payload"

def test_state_machine_asl_contract():
    asl_template_path = os.path.join(os.path.dirname(__file__), "../../modules/orchestration/statemachine.json")
    check_asl_file(asl_template_path, is_template=True)
    
    asl_doc_path = os.path.join(os.path.dirname(__file__), "../../docs/statemachine.json")
    check_asl_file(asl_doc_path, is_template=False)

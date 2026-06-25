import json
import os

def test_state_machine_asl_contract():
    asl_path = os.path.join(os.path.dirname(__file__), "../../modules/orchestration/statemachine.json")
    assert os.path.exists(asl_path), "statemachine.json file does not exist"
    
    with open(asl_path, "r", encoding="utf-8") as f:
        asl = json.load(f)
        
    assert "States" in asl, "ASL missing 'States' key"
    states = asl["States"]
    
    # 1. Assert required states exist
    required_states = [
        "PrepareRunContext",
        "CheckAdHocQuota",
        "CheckErrorBudgetLock",
        "CheckTelemetryQuality",
        "SubmitAIRequest",
        "AIRequestDecision",
        "WaitForAIResult",
        "PollAIResult",
        "AIResultDecision",
        "ValidateAIResult",
        "EvaluateContainmentPolicy",
        "SendAppliedStatusMessage",
        "SendDeniedStatusMessage",
        "SendPendingStatusMessage",
        "FailClosed",
        "SendFailClosedAlert",
        "SendCURDelayAlert",
        "WriteCURDelayAudit"
      ]
    for s in required_states:
        assert s in states, f"Required state '{s}' missing from state machine"
        
    # 2. Assert 4x CUR retry and 1h (3600s) delay
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
    assert states["WaitForCURExport"]["Seconds"] == 3600, "CUR retry interval must be 1 hour (3600 seconds)"
    
    # 3. Assert terminal fail-closed AI handling includes audit + engineering alert
    assert "SetCURDelayExceededError" in states
    assert states["SetCURDelayExceededError"]["Next"] == "SendCURDelayAlert"
    assert states["SendCURDelayAlert"]["Parameters"]["TopicArn"] == "${engineering_alerts_sns_topic_arn}"
    assert states["SendCURDelayAlert"]["Next"] == "WriteCURDelayAudit"
    assert states["WriteCURDelayAudit"]["Next"] == "MarkRunFailed"
    
    assert "FailClosed" in states
    assert states["FailClosed"]["Next"] == "SendFailClosedAlert"
    assert states["SendFailClosedAlert"]["Parameters"]["TopicArn"] == "${engineering_alerts_sns_topic_arn}"
    assert states["SendFailClosedAlert"]["Next"] == "MarkRunFailed"
    
    # 4. Assert telemetry quality dry-run gate
    assert "CheckTelemetryQuality" in states
    assert states["CheckTelemetryQuality"]["Type"] == "Choice"
    telemetry_choices = states["CheckTelemetryQuality"]["Choices"]
    # Verify it has completeness_score < 0.8 or estimated_billing etc.
    found_quality_gate = False
    for tc in telemetry_choices:
        if "Or" in tc:
            found_quality_gate = True
            or_conditions = tc["Or"]
            assert any(cond.get("Variable") == "$.normalized.details.completeness_score" and cond.get("NumericLessThan") == 0.8 for cond in or_conditions)
            assert any(cond.get("Variable") == "$.normalized.details.estimated_billing" and cond.get("BooleanEquals") is True for cond in or_conditions)
            assert tc["Next"] == "SetTelemetryForceDryRun"
    assert found_quality_gate, "Telemetry quality gate not found in CheckTelemetryQuality"
    assert states["SetTelemetryForceDryRun"]["Next"] == "SubmitAIRequest"
    
    # 5. Assert no prod destructive containment path
    assert "EvaluateContainmentPolicy" in states
    containment_choices = states["EvaluateContainmentPolicy"]["Choices"]
    # Check that destructive actions in prod go to WriteDeniedAudit
    prod_destructive_denied = False
    for choice in containment_choices:
        if "And" in choice:
            conditions = choice["And"]
            has_prod = any(cond.get("Variable") == "$.account_policy.environment" and cond.get("StringEquals") == "prod" for cond in conditions)
            has_destructive = any("Or" in cond and any(sub_cond.get("Variable") == "$.ai.recommended_containment_mode" and sub_cond.get("StringEquals") == "terminate" for sub_cond in cond["Or"]) for cond in conditions)
            if has_prod and has_destructive:
                assert choice["Next"] == "WriteDeniedAudit"
                prod_destructive_denied = True
    assert prod_destructive_denied, "Unsafe production containment actions are not denied"
    
    # Check SQS status reporting
    assert states["WritePostActionAudit"]["Next"] == "SendAppliedStatusMessage"
    assert states["SendAppliedStatusMessage"]["Parameters"]["QueueUrl"] == "${rollback_status_queue_url}"
    assert states["SendAppliedStatusMessage"]["Parameters"]["MessageBody"]["status"] == "APPLIED"
    
    assert states["WriteDeniedAudit"]["Next"] == "SendDeniedStatusMessage"
    assert states["SendDeniedStatusMessage"]["Parameters"]["QueueUrl"] == "${rollback_status_queue_url}"
    
    assert states["WritePendingApprovalAudit"]["Next"] == "SendPendingStatusMessage"
    assert states["SendPendingStatusMessage"]["Parameters"]["QueueUrl"] == "${rollback_status_queue_url}"

    # 6. Assert new Lambda container integration
    assert states["SubmitAIRequest"]["Resource"] == "${ai_request_lambda_arn}"
    assert states["PollAIResult"]["Resource"] == "arn:aws:states:::dynamodb:getItem"
    assert states["PollAIResult"]["Parameters"]["TableName"] == "${results_table_name}"
    
    # Assert there are no old ECS/HTTP states
    for state_name, state_def in states.items():
        resource = state_def.get("Resource", "")
        # No references to old ai_client or ECS
        assert "${ai_client_lambda_arn}" not in resource
        assert "ecs" not in resource.lower()
        assert "http" not in resource.lower()

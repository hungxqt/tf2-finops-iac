import json
import os
import re


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
ASL_TEMPLATE = os.path.join(BASE_DIR, "modules/orchestration/feedback_statemachine.json")
ASL_DOC = os.path.join(BASE_DIR, "docs/feedback-statemachine.json")
ORCHESTRATION_MAIN_TF = os.path.join(BASE_DIR, "modules/orchestration/main.tf")
ORCHESTRATION_OUTPUTS_TF = os.path.join(BASE_DIR, "modules/orchestration/outputs.tf")


def _load_template() -> dict:
    with open(ASL_TEMPLATE, "r", encoding="utf-8") as fh:
        raw = fh.read()
    raw = re.sub(r'"\$\{[a-zA-Z0-9_]+\}"', '"arn:aws:placeholder"', raw)
    return json.loads(raw)


def _load_doc() -> dict:
    with open(ASL_DOC, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_path(ctx: dict, path: str):
    if path.startswith("States.Format("):
        m = re.match(r"^States\.Format\('([^']*)',\s*(.*)\)$", path)
        assert m, f"Invalid States.Format pattern: {path}"
        fmt_str = m.group(1)
        args = [arg.strip() for arg in m.group(2).split(",")]
        return fmt_str.format(*[_resolve_path(ctx, arg) for arg in args])
    assert path.startswith("$.")
    current = ctx
    for part in path[2:].split("."):
        current = current[part]
    return current


def _resolve_parameters(ctx: dict, params: dict) -> dict:
    result = {}
    for key, value in params.items():
        if key.endswith(".$"):
            result[key[:-2]] = _resolve_path(ctx, value)
        elif isinstance(value, dict):
            result[key] = _resolve_parameters(ctx, value)
        else:
            result[key] = value
    return result


def _feedback_context() -> dict:
    return {
        "run_id": "feedback-2026-06-28-001",
        "correlation_id": "22222222-2222-4222-8222-222222222222",
        "account_id": "123456789012",
        "cost_period": "2026-06-01/2026-06-28",
        "execution_date": "2026-06-28",
        "tenant_id": "11111111-1111-4111-8111-111111111111",
        "ai_contract_version": "v1",
        "human_feedback": {
            "anomaly_id": "ANM-2026-0628A",
            "reviewer_id": "U12345678",
            "verdict": "FALSE_POSITIVE",
            "reason": "Known load test confirmed by service owner.",
            "reviewed_at": "2026-06-28T09:30:00.000Z",
        },
    }


def test_feedback_asl_exists_and_starts_with_validation():
    asl = _load_template()
    assert asl["StartAt"] == "ValidateHumanFeedback"
    assert "ValidateHumanFeedback" in asl["States"]
    assert "SubmitHumanFeedback" in asl["States"]


def test_feedback_validation_contract_fields_and_verdicts():
    state = _load_template()["States"]["ValidateHumanFeedback"]
    assert state["Type"] == "Choice"
    serialized = json.dumps(state)
    for field in ["anomaly_id", "reviewer_id", "verdict", "reason", "reviewed_at"]:
        assert field in serialized
    for verdict in ["TRUE_POSITIVE", "FALSE_POSITIVE", "BENIGN_EVENT"]:
        assert verdict in serialized
    assert state["Default"] == "SetInvalidHumanFeedbackError"


def test_submit_feedback_calls_v1_feedback_through_vpc_alb_caller():
    state = _load_template()["States"]["SubmitHumanFeedback"]
    assert state["Resource"] == "arn:aws:placeholder"
    assert state["Parameters"]["path"] == "/v1/feedback"
    assert state["Parameters"]["method"] == "POST"
    assert state["Parameters"]["dry_run_mode"] is True
    assert state["Next"] == "WriteHumanFeedbackAudit"


def test_submit_feedback_payload_resolves_to_section_15_shape():
    params = _load_template()["States"]["SubmitHumanFeedback"]["Parameters"]
    resolved = _resolve_parameters(_feedback_context(), params)
    assert resolved["idempotency_key"] == (
        "11111111-1111-4111-8111-111111111111:ANM-2026-0628A:U12345678:feedback"
    )
    assert resolved["body"] == _feedback_context()["human_feedback"]


def test_feedback_success_and_failure_audit_paths():
    states = _load_template()["States"]
    assert states["SubmitHumanFeedback"]["Catch"][0]["Next"] == "WriteHumanFeedbackFailureAudit"
    assert states["WriteHumanFeedbackAudit"]["Parameters"]["action"] == "human-feedback-submitted"
    assert states["WriteHumanFeedbackAudit"]["Next"] == "FeedbackCompleted"
    assert states["WriteHumanFeedbackFailureAudit"]["Parameters"]["action"] == "human-feedback-delivery-failed"
    assert states["WriteHumanFeedbackFailureAudit"]["Next"] == "SetHumanFeedbackDeliveryError"
    assert states["SetInvalidHumanFeedbackError"]["Next"] == "WriteInvalidHumanFeedbackAudit"
    assert states["WriteInvalidHumanFeedbackAudit"]["Parameters"]["action"] == "human-feedback-invalid"
    assert states["WriteInvalidHumanFeedbackAudit"]["Next"] == "FeedbackFailed"


def test_daily_state_machine_stays_separate_from_feedback_workflow():
    daily_path = os.path.join(BASE_DIR, "modules/orchestration/statemachine.json")
    with open(daily_path, "r", encoding="utf-8") as fh:
        daily = fh.read()
    assert "/v1/feedback" not in daily
    assert "HumanFeedback" not in daily


def test_feedback_doc_matches_template_states():
    template_states = set(_load_template()["States"].keys())
    doc_states = set(_load_doc()["States"].keys())
    assert doc_states == template_states


def test_terraform_provisions_feedback_state_machine_and_output():
    with open(ORCHESTRATION_MAIN_TF, "r", encoding="utf-8") as fh:
        main_tf = fh.read()
    assert 'resource "aws_sfn_state_machine" "feedback"' in main_tf
    assert "feedback_statemachine.json" in main_tf
    assert 'resource "aws_cloudwatch_log_group" "feedback_sfn"' in main_tf

    with open(ORCHESTRATION_OUTPUTS_TF, "r", encoding="utf-8") as fh:
        outputs_tf = fh.read()
    assert 'output "feedback_state_machine_arn"' in outputs_tf

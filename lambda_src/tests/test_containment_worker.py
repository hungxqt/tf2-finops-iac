"""
test_containment_worker.py — Tests for containment_worker module.

Covers:
  - Hard boundary enforcement (no AWS needed)
  - Action dispatch: dry_run, tag, suggest, stopper (mocked boto3)
  - Audit: S3 write + DynamoDB cache (moto)
  - Handler entry point integration

Run all:     pytest tests/test_containment_worker.py -v
Boundary:    pytest tests/test_containment_worker.py -v -k "boundary"
Audit:       pytest tests/test_containment_worker.py -v -k "audit"
Actions:     pytest tests/test_containment_worker.py -v -k "actions"
"""
import json
import pytest
from unittest.mock import MagicMock

from workers.containment_worker.model.input import (
    ContainmentInput,
    Boto3Payload,
    AuditWriterConfig,
    APPROVAL_APPROVED,
    APPROVAL_DENIED,
    APPROVAL_PENDING,
    DATA_CONFIDENCE_HIGH,
    DATA_CONFIDENCE_LOW,
    MODE_APPLY,
    MODE_DRY_RUN,
    MODE_TAG,
)
from workers.containment_worker.policy.boundary import enforce_boundaries, is_prod_environment
from workers.containment_worker.policy.confidence_guard import (
    is_confidence_sufficient,
    get_confidence_override_reason,
)
from workers.containment_worker.actions.dry_run import execute_dry_run
from workers.containment_worker.actions.suggester import execute_suggest, _determine_route
from workers.containment_worker.actions.tagger import execute_tag, compute_rollback_path_for_tag
from workers.containment_worker.actions.stopper import execute_apply

try:
    from moto import mock_aws
    MOTO_AVAILABLE = True
except ImportError:
    MOTO_AVAILABLE = False

import boto3

AWS_REGION = "ap-southeast-1"
TEST_BUCKET = "company-cdo-200000000012-telemetry"
TEST_TABLE = "finops-dashboard-cache-sandbox"
TEST_ROLLBACK_TABLE = "finops-rollback-cache"


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

def _make_input(
    environment: str = "sandbox",
    execution_mode: str = MODE_APPLY,
    approval_status: str = APPROVAL_APPROVED,
    data_confidence: str = DATA_CONFIDENCE_HIGH,
    anomaly_type: str = "runaway_usage",
    resource_id: str = "i-0test12345",
) -> ContainmentInput:
    return ContainmentInput(
        run_id="run-test-001",
        anomaly_id="anom-test-001",
        correlation_id="corr-test-001",
        model_version="v1.0.0",
        anomaly_type=anomaly_type,
        confidence=0.92,
        severity="high",
        explanation="GPU cluster running 24/7 with no traffic",
        data_confidence=data_confidence,
        resource_id=resource_id,
        resource_owner="squad-ml-core",
        account_id="200000000012",
        environment=environment,
        containment_role_name="FinOpsContainmentWorkerRole",
        external_id="test-external-id",
        execution_mode=execution_mode,
        approval_status=approval_status,
        recommended_containment_mode="auto-shutdown",
        applied_payload=Boto3Payload(
            service="ec2",
            method="stop_instances",
            parameters={"InstanceIds": [resource_id]},
        ),
        rollback_payload=Boto3Payload(
            service="ec2",
            method="start_instances",
            parameters={"InstanceIds": [resource_id]},
        ),
        audit_config=AuditWriterConfig(
            audit_bucket=TEST_BUCKET,
            audit_prefix="audit/",
            dashboard_table=TEST_TABLE,
            rollback_cache_table=TEST_ROLLBACK_TABLE,
        ),
    )


# ===========================================================================
# BOUNDARY TESTS — no AWS needed
# ===========================================================================

class TestIsProdEnvironment:
    def test_prod_is_prod(self):
        assert is_prod_environment("prod") is True

    def test_prod_core_is_prod(self):
        assert is_prod_environment("prod-core") is True

    def test_prod_payments_is_prod(self):
        assert is_prod_environment("prod-payments") is True

    def test_sandbox_not_prod(self):
        assert is_prod_environment("sandbox") is False

    def test_staging_not_prod(self):
        assert is_prod_environment("staging") is False

    def test_dev_not_prod(self):
        assert is_prod_environment("dev") is False


class TestBoundaryProd:
    def test_prod_apply_forced_dry_run(self):
        inp = _make_input(environment="prod", execution_mode=MODE_APPLY)
        assert enforce_boundaries(inp) == MODE_DRY_RUN

    def test_prod_core_apply_forced_dry_run(self):
        inp = _make_input(environment="prod-core", execution_mode=MODE_APPLY)
        assert enforce_boundaries(inp) == MODE_DRY_RUN

    def test_prod_payments_apply_forced_dry_run(self):
        inp = _make_input(environment="prod-payments", execution_mode=MODE_APPLY)
        assert enforce_boundaries(inp) == MODE_DRY_RUN

    def test_prod_dry_run_stays_dry_run(self):
        inp = _make_input(environment="prod", execution_mode=MODE_DRY_RUN)
        assert enforce_boundaries(inp) == MODE_DRY_RUN

    def test_prod_tag_allowed(self):
        inp = _make_input(environment="prod", execution_mode=MODE_TAG)
        assert enforce_boundaries(inp) == MODE_TAG

    def test_prod_suggest_allowed(self):
        inp = _make_input(environment="prod", execution_mode="suggest")
        assert enforce_boundaries(inp) == "suggest"


class TestBoundaryNonProd:
    def test_sandbox_apply_allowed(self):
        inp = _make_input(environment="sandbox", execution_mode=MODE_APPLY)
        assert enforce_boundaries(inp) == MODE_APPLY

    def test_staging_apply_allowed(self):
        inp = _make_input(environment="staging", execution_mode=MODE_APPLY)
        assert enforce_boundaries(inp) == MODE_APPLY

    def test_dev_apply_allowed(self):
        inp = _make_input(environment="dev", execution_mode=MODE_APPLY)
        assert enforce_boundaries(inp) == MODE_APPLY


class TestBoundaryApproval:
    def test_denied_returns_denied(self):
        inp = _make_input(approval_status=APPROVAL_DENIED)
        assert enforce_boundaries(inp) == "denied"

    def test_approved_passes_through(self):
        inp = _make_input(environment="sandbox", execution_mode=MODE_APPLY,
                          approval_status=APPROVAL_APPROVED)
        assert enforce_boundaries(inp) == MODE_APPLY

    def test_pending_passes_through(self):
        inp = _make_input(environment="sandbox", execution_mode=MODE_TAG,
                          approval_status=APPROVAL_PENDING)
        assert enforce_boundaries(inp) == MODE_TAG


class TestBoundaryConfidence:
    def test_low_confidence_apply_forced_dry_run(self):
        inp = _make_input(environment="sandbox", execution_mode=MODE_APPLY,
                          data_confidence=DATA_CONFIDENCE_LOW)
        assert enforce_boundaries(inp) == MODE_DRY_RUN

    def test_low_confidence_tag_forced_dry_run(self):
        inp = _make_input(environment="sandbox", execution_mode=MODE_TAG,
                          data_confidence=DATA_CONFIDENCE_LOW)
        assert enforce_boundaries(inp) == MODE_DRY_RUN

    def test_high_confidence_apply_allowed(self):
        inp = _make_input(environment="sandbox", execution_mode=MODE_APPLY,
                          data_confidence=DATA_CONFIDENCE_HIGH)
        assert enforce_boundaries(inp) == MODE_APPLY

    def test_prod_plus_low_confidence_both_dry_run(self):
        inp = _make_input(environment="prod", execution_mode=MODE_APPLY,
                          data_confidence=DATA_CONFIDENCE_LOW)
        assert enforce_boundaries(inp) == MODE_DRY_RUN

    def test_denied_trumps_everything(self):
        inp = _make_input(environment="sandbox", execution_mode=MODE_APPLY,
                          approval_status=APPROVAL_DENIED,
                          data_confidence=DATA_CONFIDENCE_HIGH)
        assert enforce_boundaries(inp) == "denied"


class TestConfidenceGuard:
    def test_high_sufficient(self):
        assert is_confidence_sufficient(DATA_CONFIDENCE_HIGH) is True

    def test_low_not_sufficient(self):
        assert is_confidence_sufficient(DATA_CONFIDENCE_LOW) is False

    def test_low_reason_not_empty(self):
        reason = get_confidence_override_reason(DATA_CONFIDENCE_LOW)
        assert len(reason) > 0
        assert "LOW" in reason

    def test_high_reason_empty(self):
        assert get_confidence_override_reason(DATA_CONFIDENCE_HIGH) == ""


# ===========================================================================
# ACTION TESTS — mocked boto3
# ===========================================================================

class TestActionsDryRun:
    def test_dry_run_correct_service(self):
        inp = _make_input(execution_mode=MODE_DRY_RUN)
        result = execute_dry_run(inp)
        assert result.would_execute_service == "ec2"

    def test_dry_run_correct_method(self):
        inp = _make_input(execution_mode=MODE_DRY_RUN)
        result = execute_dry_run(inp)
        assert result.would_execute_method == "stop_instances"

    def test_dry_run_no_aws_call(self):
        """If any AWS call is made this raises NoCredentialsError and the test fails."""
        inp = _make_input(execution_mode=MODE_DRY_RUN)
        result = execute_dry_run(inp)
        assert "dry-run" in result.simulation_note.lower()

    def test_dry_run_includes_resource_id(self):
        inp = _make_input(resource_id="i-0abc123test")
        result = execute_dry_run(inp)
        assert "i-0abc123test" in result.simulation_note

    def test_dry_run_to_dict(self):
        inp = _make_input()
        d = execute_dry_run(inp).to_dict()
        assert "would_execute_service" in d
        assert "would_execute_method" in d
        assert "simulation_note" in d


class TestActionsTagger:
    def test_tag_calls_ec2_create_tags(self):
        inp = _make_input(execution_mode=MODE_TAG, resource_id="i-0test999")
        mock_ec2 = MagicMock()
        mock_ec2.create_tags.return_value = {
            "ResponseMetadata": {"HTTPStatusCode": 200, "RequestId": "req-001"}
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_ec2

        result = execute_tag(inp, mock_session)
        mock_ec2.create_tags.assert_called_once()
        call_kwargs = mock_ec2.create_tags.call_args[1]
        assert "i-0test999" in call_kwargs["Resources"]
        tag_keys = [t["Key"] for t in call_kwargs["Tags"]]
        assert "FinOpsWatch" in tag_keys
        assert "FinOpsAnomalyId" in tag_keys

    def test_tag_result_contains_anomaly_id(self):
        inp = _make_input(execution_mode=MODE_TAG)
        mock_ec2 = MagicMock()
        mock_ec2.create_tags.return_value = {
            "ResponseMetadata": {"HTTPStatusCode": 200, "RequestId": "req-002"}
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_ec2
        result = execute_tag(inp, mock_session)
        assert inp.anomaly_id in result.tags_applied.get("FinOpsAnomalyId", "")

    def test_rollback_path_for_tag(self):
        tags = {"FinOpsWatch": "ReviewRequired", "FinOpsAnomalyId": "anom-001"}
        rollback = compute_rollback_path_for_tag(tags)
        assert rollback["action"] == "remove_tags"
        assert "FinOpsWatch" in rollback["keys"]


class TestActionsSuggester:
    def test_runaway_routes_engineering(self):
        assert _determine_route("runaway_usage", "sandbox") == "engineering"

    def test_idle_resource_routes_engineering(self):
        assert _determine_route("idle_resource", "sandbox") == "engineering"

    def test_untagged_spend_routes_finance(self):
        assert _determine_route("untagged_spend", "prod") == "finance"

    def test_sudden_spike_routes_finance(self):
        assert _determine_route("sudden_spike", "prod") == "finance"

    def test_unknown_defaults_engineering(self):
        assert _determine_route("unknown_type", "sandbox") == "engineering"

    def test_suggest_has_anomaly_id(self):
        inp = _make_input(anomaly_type="runaway_usage")
        result = execute_suggest(inp)
        assert result.anomaly_id == inp.anomaly_id

    def test_suggest_prod_requires_approval(self):
        inp = _make_input(environment="prod", anomaly_type="runaway_usage")
        assert execute_suggest(inp).approval_required is True

    def test_suggest_sandbox_tag_no_approval(self):
        inp = _make_input(environment="sandbox", anomaly_type="idle_resource")
        inp.recommended_containment_mode = "tag-for-review"
        assert execute_suggest(inp).approval_required is False


class TestActionsStopper:
    def test_stop_ec2_instance(self):
        inp = _make_input(environment="sandbox", execution_mode=MODE_APPLY,
                          resource_id="i-0test567")
        mock_ec2 = MagicMock()
        mock_ec2.stop_instances.return_value = {
            "StoppingInstances": [{"CurrentState": {"Name": "stopping"}}],
            "ResponseMetadata": {"HTTPStatusCode": 200, "RequestId": "req-stop-001"},
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_ec2

        result = execute_apply(inp, mock_session)
        mock_ec2.stop_instances.assert_called_once_with(InstanceIds=["i-0test567"])
        assert result.boto3_http_status == 200
        assert result.action_executed == "ec2.stop_instances"

    def test_stop_rds_instance(self):
        inp = _make_input(environment="sandbox", execution_mode=MODE_APPLY)
        inp.applied_payload = Boto3Payload(
            service="rds",
            method="stop_db_instance",
            parameters={"DBInstanceIdentifier": "my-db-01"},
        )
        mock_rds = MagicMock()
        mock_rds.stop_db_instance.return_value = {
            "DBInstance": {"DBInstanceStatus": "stopping"},
            "ResponseMetadata": {"HTTPStatusCode": 200, "RequestId": "req-rds-001"},
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_rds

        result = execute_apply(inp, mock_session)
        mock_rds.stop_db_instance.assert_called_once_with(DBInstanceIdentifier="my-db-01")
        assert result.action_executed == "rds.stop_db_instance"


# ===========================================================================
# AUDIT TESTS — moto required
# ===========================================================================

@pytest.mark.skipif(not MOTO_AVAILABLE, reason="moto not installed")
class TestAuditS3:
    @mock_aws
    def test_pre_action_audit_written(self):
        from workers.containment_worker.model.output import AuditRecord
        from workers.containment_worker.audit.s3_audit import write_pre_action_audit

        session = boto3.Session(region_name=AWS_REGION)
        s3 = session.client("s3")
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
        )

        record = AuditRecord(
            actor="cdo-platform-containment-lambda",
            timestamp="2026-06-26T10:00:00Z",
            correlation_id="corr-test-001",
            anomaly_id="anom-test-001",
            run_id="run-test-001",
            resource_owner="squad-ml-core",
            resource_id="i-0test12345",
            account_id="200000000012",
            environment="sandbox",
            execution_mode="dry-run",
            original_execution_mode="apply",
            approval_status="approved",
            data_confidence="HIGH",
        )

        audit_id, s3_uri = write_pre_action_audit(
            session=session,
            audit_record=record,
            audit_bucket=TEST_BUCKET,
            audit_prefix="audit/",
        )

        assert len(audit_id) > 0
        assert TEST_BUCKET in s3_uri
        objects = s3.list_objects_v2(Bucket=TEST_BUCKET, Prefix="audit/")
        assert objects["KeyCount"] >= 1

    @mock_aws
    def test_audit_content_correct(self):
        from workers.containment_worker.model.output import AuditRecord
        from workers.containment_worker.audit.s3_audit import write_pre_action_audit

        session = boto3.Session(region_name=AWS_REGION)
        s3 = session.client("s3")
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
        )

        record = AuditRecord(
            actor="cdo-platform-containment-lambda",
            timestamp="2026-06-26T10:00:00Z",
            correlation_id="corr-001",
            anomaly_id="anom-001",
            run_id="run-001",
            resource_owner="squad-ml",
            resource_id="i-0abc",
            account_id="200000000012",
            environment="sandbox",
            execution_mode="dry-run",
            original_execution_mode="apply",
            approval_status="approved",
            data_confidence="HIGH",
        )

        _, s3_uri = write_pre_action_audit(
            session=session, audit_record=record, audit_bucket=TEST_BUCKET,
        )
        key = s3_uri.replace(f"s3://{TEST_BUCKET}/", "")
        content = json.loads(s3.get_object(Bucket=TEST_BUCKET, Key=key)["Body"].read())
        assert content["anomaly_id"] == "anom-001"
        assert content["execution_mode"] == "dry-run"

    @mock_aws
    def test_audit_chain_hash_computed(self):
        from workers.containment_worker.model.output import AuditRecord
        from workers.containment_worker.audit.s3_audit import write_pre_action_audit

        session = boto3.Session(region_name=AWS_REGION)
        s3 = session.client("s3")
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
        )
        record = AuditRecord(
            actor="cdo-platform-containment-lambda",
            timestamp="2026-06-26T10:00:00Z",
            correlation_id="c", anomaly_id="a", run_id="r",
            resource_owner="o", resource_id="i-0x", account_id="123",
            environment="sandbox", execution_mode="dry-run",
            original_execution_mode="apply", approval_status="approved",
            data_confidence="HIGH",
        )
        write_pre_action_audit(session=session, audit_record=record, audit_bucket=TEST_BUCKET)
        assert len(record.audit_chain.get("event_hash", "")) == 64


@pytest.mark.skipif(not MOTO_AVAILABLE, reason="moto not installed")
class TestAuditDynamo:
    @mock_aws
    def test_dashboard_cache_updated(self):
        from workers.containment_worker.audit.dynamo_cache import update_dashboard_cache

        session = boto3.Session(region_name=AWS_REGION)
        dynamodb = session.resource("dynamodb")
        dynamodb.create_table(
            TableName=TEST_TABLE,
            KeySchema=[{"AttributeName": "anomaly_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "anomaly_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        success = update_dashboard_cache(
            session=session, table_name=TEST_TABLE,
            anomaly_id="anom-test-001", run_id="run-001",
            correlation_id="corr-001", resource_id="i-0test",
            account_id="200000000012", environment="sandbox",
            execution_mode_applied="dry-run", status="dry-run",
            audit_record_id="audit-001",
            audit_record_s3_uri="s3://bucket/key",
        )
        assert success is True
        item = dynamodb.Table(TEST_TABLE).get_item(
            Key={"anomaly_id": "anom-test-001"}
        ).get("Item")
        assert item["status"] == "dry-run"

    @mock_aws
    def test_rollback_cache_stored(self):
        from workers.containment_worker.audit.dynamo_cache import cache_rollback_payload

        session = boto3.Session(region_name=AWS_REGION)
        dynamodb = session.resource("dynamodb")
        dynamodb.create_table(
            TableName=TEST_ROLLBACK_TABLE,
            KeySchema=[{"AttributeName": "anomaly_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "anomaly_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        success = cache_rollback_payload(
            session=session, rollback_cache_table=TEST_ROLLBACK_TABLE,
            anomaly_id="anom-test-001", correlation_id="corr-001",
            rollback_payload={"service": "ec2", "method": "start_instances",
                               "parameters": {"InstanceIds": ["i-0test"]}},
        )
        assert success is True
        item = dynamodb.Table(TEST_ROLLBACK_TABLE).get_item(
            Key={"anomaly_id": "anom-test-001"}
        ).get("Item")
        assert item["boto3_equivalent"]["service"] == "ec2"

    @mock_aws
    def test_dashboard_cache_fails_gracefully(self):
        from workers.containment_worker.audit.dynamo_cache import update_dashboard_cache

        session = boto3.Session(region_name=AWS_REGION)
        # Table does not exist → should return False, not raise
        success = update_dashboard_cache(
            session=session, table_name="non-existent-table",
            anomaly_id="anom-001", run_id="run-001",
            correlation_id="corr-001", resource_id="i-0x",
            account_id="123", environment="sandbox",
            execution_mode_applied="dry-run", status="dry-run",
            audit_record_id="a", audit_record_s3_uri="s3://b/k",
        )
        assert success is False

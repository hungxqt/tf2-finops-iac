import os
import logging
import json
import gzip
import hashlib
import re
from datetime import datetime, timedelta
from typing import Any, Tuple, Optional, Dict
import boto3
import finops_common

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global clients for test injection
s3_client = None
ce_client = None
cw_client = None
sts_client = None

CE_SERVICE_TO_CUR_CODE = {
    "Amazon Elastic Compute Cloud - Compute": "AmazonEC2",
    "Amazon Simple Storage Service": "AmazonS3",
    "Amazon Relational Database Service": "AmazonRDS",
    "Amazon DynamoDB": "AmazonDynamoDB",
    "Amazon SageMaker": "AmazonSageMaker",
    "AWS Key Management Service": "awskms",
    "Amazon CloudFront": "AmazonCloudFront",
    "Amazon Route 53": "AmazonRoute53",
    "Amazon API Gateway": "AmazonApiGateway",
}

def get_clients() -> Tuple[Any, Any, Any, Any]:
    global s3_client, ce_client, cw_client, sts_client
    bucket_configured = os.environ.get("LAKEHOUSE_BUCKET_NAME") is not None

    local_s3 = s3_client or (finops_common.RealS3() if bucket_configured else None)
    local_ce = ce_client or (finops_common.RealCostExplorer() if bucket_configured else None)
    local_cw = cw_client or (finops_common.RealCloudWatch() if bucket_configured else None)
    local_sts = sts_client or (finops_common.RealSTS() if bucket_configured else None)

    return local_s3, local_ce, local_cw, local_sts

def validate_bucket_and_account(account_id: str, bucket_name: str) -> None:
    if not bucket_name:
        return
    # Reject path traversal / invalid chars
    if ".." in bucket_name or "/" in bucket_name or "\\" in bucket_name:
        raise finops_common.UnsafeActionError(f"Unsafe bucket name: {bucket_name}")
    # Verify account matches if a 12-digit number exists in bucket name
    digits = re.findall(r'\d{12}', bucket_name)
    if digits and account_id not in digits:
        raise finops_common.UnsafeActionError(f"Cross-tenant/account bucket access mismatch: bucket {bucket_name} does not match account {account_id}")

def check_cur_freshness(s3_client_inst, cur_bucket: str, cur_prefix: str, exec_time: datetime, threshold_hours: int) -> Tuple[bool, datetime]:
    try:
        response = s3_client_inst.list_objects_v2(cur_bucket, cur_prefix)
        contents = response.get("Contents", [])
        if not contents:
            logger.info("No CUR files found in source bucket. Considering delayed.")
            return True, datetime.min

        latest_modified = max(obj["LastModified"] for obj in contents)
        if isinstance(latest_modified, str):
            # Parse ISO string if return format is string
            latest_modified = datetime.fromisoformat(latest_modified.replace("Z", "+00:00")).replace(tzinfo=None)
        elif latest_modified.tzinfo is not None:
            latest_modified = latest_modified.replace(tzinfo=None)

        now = datetime.utcnow()
        # Gap is between now and the latest modified CUR file
        gap = now - latest_modified
        is_delayed = gap.total_seconds() > (threshold_hours * 3600)
        return is_delayed, latest_modified
    except Exception as e:
        logger.warning("Error checking CUR freshness: %s. Assuming delayed.", e)
        return True, datetime.min

def find_cached_fallback(s3_client_inst, telemetry_bucket: str, account_id: str) -> Optional[Tuple[str, bytes]]:
    if not s3_client_inst:
        return None
    prefix = f"cur/account_id={account_id}/"
    try:
        res = s3_client_inst.list_objects_v2(telemetry_bucket, prefix)
        contents = res.get("Contents", [])
        valid_objs = [obj for obj in contents if obj["Key"].endswith(".json.gz")]
        if not valid_objs:
            return None

        # Get latest modified cached telemetry object
        latest_obj = max(valid_objs, key=lambda x: x["LastModified"])
        key = latest_obj["Key"]
        logger.info("Reading cached fallback object: %s", key)
        data = s3_client_inst.get_object(telemetry_bucket, key)
        return f"s3://{telemetry_bucket}/{key}", data
    except Exception as e:
        logger.warning("Failed to find cached fallback object: %s", e)
        return None

def compute_usage_density(amount: float, unit: str) -> float:
    if unit == "Hrs":
        return min(amount / 24.0, 1.0)
    return 0.0

def query_cw_utilization(cw_client_inst, resource_ids: list, exec_time: datetime) -> Tuple[list, bool]:
    if not cw_client_inst or not resource_ids:
        return [], True

    metrics = []
    missing = False
    for idx, rid in enumerate(resource_ids):
        if not rid:
            continue
        try:
            response = cw_client_inst.get_metric_data(
                MetricDataQueries=[
                    {
                        "Id": f"cpu{idx}",
                        "MetricStat": {
                            "Metric": {
                                "Namespace": "AWS/EC2",
                                "MetricName": "CPUUtilization",
                                "Dimensions": [
                                    {"Name": "InstanceId", "Value": rid}
                                ],
                            },
                            "Period": 3600,
                            "Stat": "Average",
                        },
                    }
                ],
                StartTime=exec_time - timedelta(days=1),
                EndTime=exec_time,
            )
            values = []
            for result in response.get("MetricDataResults", []):
                values.extend(result.get("Values", []))
            if not values:
                missing = True
                continue
            metrics.append({
                "resource_id": rid,
                "cpu_percent": sum(values) / len(values),
                "cpu_utilization_hourly": values,
            })
        except Exception as e:
            logger.warning("CloudWatch metric retrieval failed/unsupported for resource %s: %s", rid, e)
            missing = True
    return metrics, missing or len(metrics) == 0

def query_traffic_context(cw_client_inst, exec_time: datetime) -> Tuple[float, str, bool]:
    if not cw_client_inst:
        return 0.0, "ALB", True
    try:
        response = cw_client_inst.get_metric_data(
            MetricDataQueries=[
                {
                    "Id": "alb",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/ApplicationELB",
                            "MetricName": "RequestCount"
                        },
                        "Period": 86400,
                        "Stat": "Sum"
                    }
                }
            ],
            StartTime=exec_time - timedelta(days=1),
            EndTime=exec_time
        )
        values = []
        for result in response.get("MetricDataResults", []):
            values.extend(result.get("Values", []))
        if not values:
            return 0.0, "ALB", True
        return float(sum(values)), "ALB", False
    except Exception as e:
        logger.warning("CloudWatch traffic metric retrieval failed: %s", e)
        return 0.0, "ALB", True

def get_cross_account_session(sts_client_inst, account_id: str, current_account_id: str, tenant_id: str = "") -> Optional[Any]:
    if not sts_client_inst or account_id == current_account_id:
        return None
    role_name = os.environ.get("TELEMETRY_MEMBER_ROLE_NAME", "cdo-telemetry-ingestion-role")
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
    try:
        logger.info("Assuming role for account %s: %s", account_id, role_arn)
        assume_kwargs = {
            "RoleArn": role_arn,
            "RoleSessionName": "FinOpsWatchTelemetryPull",
        }
        if tenant_id:
            assume_kwargs["ExternalId"] = tenant_id
            assume_kwargs["Tags"] = [{"Key": "tenant_id", "Value": tenant_id}]
            assume_kwargs["TransitiveTagKeys"] = ["tenant_id"]
        res = sts_client_inst.assume_role(**assume_kwargs)
        creds = res["Credentials"]
        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=os.environ.get("AWS_REGION", "ap-southeast-1"),
        )
    except Exception as e:
        if isinstance(e, (NameError, TypeError, ValueError, KeyError, AttributeError, ImportError, IndexError, SyntaxError)):
            raise e
        logger.warning("Failed to assume role %s: %s. Using default session.", role_arn, e)
        return None

def handle_request(event_data: dict, context: Any) -> dict:
    logger.info("Received event: %s", finops_common.redact_sensitive_info(str(event_data)))

    try:
        event = finops_common.Event.from_dict(event_data)
        finops_common.validate_event(event)
    except Exception as e:
        logger.error("Validation failed: %s", e)
        raise e

    try:
        exec_time = finops_common.parse_date(event.execution_date)
    except Exception as e:
        logger.error("Invalid execution date: %s", e)
        raise e

    exec_date_str = exec_time.strftime("%Y-%m-%d")

    # Environment configs
    telemetry_bucket = os.environ.get("LAKEHOUSE_BUCKET_NAME")
    cur_source_bucket = os.environ.get("CUR_SOURCE_BUCKET") or ""
    cur_source_prefix = os.environ.get("CUR_SOURCE_PREFIX") or ""
    cur_delay_threshold = int(os.environ.get("CUR_DELAY_THRESHOLD_HOURS") or 36)
    ce_lookback_window = int(os.environ.get("CE_LOOKBACK_WINDOW_DAYS") or 30)
    if not telemetry_bucket:
        raise finops_common.ConfigMissingError("LAKEHOUSE_BUCKET_NAME is required for cost telemetry writes")

    # Bucket & Account Security validations
    try:
        validate_bucket_and_account(event.account_id, telemetry_bucket)
        if cur_source_bucket:
            validate_bucket_and_account(event.account_id, cur_source_bucket)
    except finops_common.UnsafeActionError as e:
        logger.error("Security validation failed: %s", e)
        raise e

    action = event.action.lower() if event.action else ""
    if not cur_source_bucket and action not in {"simulate-cur-delay", "simulate-cur-delay-no-fallback"}:
        raise finops_common.ConfigMissingError("CUR_SOURCE_BUCKET is required for CUR manifest discovery")

    # Get Clients
    local_s3, local_ce, local_cw, local_sts = get_clients()

    # Check current account identity if real STS client is available
    current_account_id = event.account_id
    if local_sts:
        try:
            current_account_id = local_sts.get_caller_identity()["AccountId"]
        except Exception:
            pass

    # Handle cross account role assumption if target account_id differs
    tenant_id_for_sts = getattr(event, "tenant_id", "") or event_data.get("tenant_id", "")
    remote_session = get_cross_account_session(local_sts, event.account_id, current_account_id, tenant_id=tenant_id_for_sts)
    if remote_session:
        # Override clients with assumed session
        local_s3 = remote_session.client("s3")
        local_ce = remote_session.client("ce")
        local_cw = remote_session.client("cloudwatch")

    # Check if CUR is delayed
    cur_delayed = False
    cur_last_modified = None

    if action == "simulate-cur-delay" or action == "simulate-cur-delay-no-fallback":
        cur_delayed = True
        cur_last_modified = exec_time - timedelta(hours=cur_delay_threshold + 1)
    elif cur_source_bucket and local_s3:
        cur_delayed, cur_last_modified = check_cur_freshness(local_s3, cur_source_bucket, cur_source_prefix, exec_time, cur_delay_threshold)
    else:
        # Default behavior: not delayed if no external config, unless simulated
        cur_delayed = False

    # Initialization of signals
    cur_records = []
    ce_records = []
    utilization_metrics = []
    missing_resources = []
    current_ce_cost_gap_usd = 0.0
    comparison_window = {}

    telemetry_delay_event = False
    stale_cost_explorer = False
    missing_cloudwatch = False
    estimated_billing = False

    status = "READY"

    if cur_delayed:
        telemetry_delay_event = True
        # Try fall back to Cost Explorer daily Cost telemetry
        logger.info("CUR is delayed. Falling back to Cost Explorer.")

        ce_throttled = False
        ce_response = None

        if action == "simulate-ce-throttled":
            ce_throttled = True
        elif local_ce:
            try:
                start_str = (exec_time - timedelta(days=ce_lookback_window)).strftime("%Y-%m-%d")
                end_str = exec_time.strftime("%Y-%m-%d")
                ce_response = local_ce.get_cost_and_usage(
                    TimePeriod={"Start": start_str, "End": end_str},
                    Granularity="DAILY",
                    Metrics=["UnblendedCost"],
                    GroupBy=[
                        {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
                        {"Type": "DIMENSION", "Key": "SERVICE"},
                        {"Type": "DIMENSION", "Key": "REGION"}
                    ]
                )
            except Exception as e:
                error_msg = str(e).lower()
                if "throttling" in error_msg or "rate limit" in error_msg or "limitexceeded" in error_msg:
                    ce_throttled = True
                else:
                    logger.error("Cost Explorer retrieval error: %s", e)
                    # Non-throttling CE failure: if no fallback exists, return CUR_DELAY

        # Process CE data or fallbacks
        if ce_throttled:
            logger.warning("Cost Explorer is throttled.")
            cached = find_cached_fallback(local_s3, telemetry_bucket, event.account_id)
            if cached:
                raw_uri, cached_data = cached
                try:
                    decompressed = cached_data
                    if decompressed.startswith(b'\x1f\x8b'):
                        decompressed = gzip.decompress(decompressed)
                    cached_envelope = json.loads(decompressed.decode("utf-8"))

                    # Extract cached data
                    cur_records = cached_envelope.get("aws_cur_line_items", [])
                    ce_records = cached_envelope.get("aws_cost_explorer_daily", [])
                    utilization_metrics = cached_envelope.get("resource_utilization_metrics", [])

                    stale_cost_explorer = True
                    estimated_billing = cached_envelope.get("quality", {}).get("estimated_billing", False)
                    missing_cloudwatch = cached_envelope.get("quality", {}).get("missing_cloudwatch", False)
                    logger.info("Successfully recovered telemetry from cached object.")
                except Exception as ex:
                    logger.error("Failed to parse cached telemetry: %s", ex)
                    # If parsing cache fails, treat as throttled without cache
                    response = finops_common.create_response("CE_THROTTLED", event.run_id, event.correlation_id, "cost_puller", {
                        "error": "Cost Explorer API request rate limit exceeded and cached fallback is corrupt.",
                        "delayed_cur": True,
                        "stale_cost_explorer": True
                    })
                    return response.to_dict()
            else:
                response = finops_common.create_response("CE_THROTTLED", event.run_id, event.correlation_id, "cost_puller", {
                    "error": "Cost Explorer API request rate limit exceeded.",
                    "delayed_cur": True,
                    "stale_cost_explorer": True
                })
                return response.to_dict()
        elif ce_response:
            # Parse real CE response
            # results format: ResultsByTime: [{ TimePeriod: {Start, End}, Groups: [{ Keys: [account, service, region], Metrics: { UnblendedCost: { Amount } } }], Estimated: bool }]
            for result in ce_response.get("ResultsByTime", []):
                date_str = result.get("TimePeriod", {}).get("Start", "")
                is_est = result.get("Estimated", False)
                if is_est:
                    estimated_billing = True
                for group in result.get("Groups", []):
                    keys = group.get("Keys", ["", "", ""])
                    linked_account = keys[0] if len(keys) > 0 else ""
                    service = keys[1] if len(keys) > 1 else ""
                    region = keys[2] if len(keys) > 2 else ""
                    cost = float(group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", 0.0))

                    # Try to map service name back to service code if possible
                    service_code = CE_SERVICE_TO_CUR_CODE.get(service, service.replace("Amazon ", "").replace(" ", ""))

                    ce_records.append({
                        "date": date_str,
                        "linked_account_id": linked_account,
                        "linked_account_name": event_data.get("account_name") or linked_account or event.account_id,
                        "service": service,
                        "service_code": service_code,
                        "region": region if region else "global",
                        "unblended_cost": cost,
                        "is_estimated": is_est
                    })
        else:
            # CUR is delayed, CE has no data / no fallback
            logger.warning("CUR is delayed and CE fallback has no data.")
            status = "CUR_DELAY"
            response = finops_common.create_response(status, event.run_id, event.correlation_id, "cost_puller", {
                "error": "Billing reports (CUR) not yet exported to S3 and no CE fallback available.",
                "delayed_cur": True
            })
            return response.to_dict()

        if not ce_records:
            logger.warning("CUR is delayed and real CE fallback returned no cost records.")
            response = finops_common.create_response("CUR_DELAY", event.run_id, event.correlation_id, "cost_puller", {
                "error": "Billing reports (CUR) are delayed and Cost Explorer returned no records.",
                "delayed_cur": True
            })
            return response.to_dict()

        # Compute mismatch signals for the current execution date
        comparison_window = {
            "start_date": exec_date_str,
            "end_date": exec_date_str
        }
        exec_ce_records = [r for r in ce_records if r["date"] == exec_date_str]
        for r in exec_ce_records:
            service_code = r.get("service_code") or r.get("service")
            if service_code:
                missing_resources.append(service_code)
                current_ce_cost_gap_usd += float(r.get("unblended_cost") or 0.0)

    manifest_uri = ""
    assembly_id = ""
    report_keys = []

    if not cur_delayed:
        # CUR is ready, collect manifest metadata
        logger.info("CUR is available. Discovering CUR manifest.")

        discovered_key = None
        if local_s3 and cur_source_bucket:
            try:
                res = local_s3.list_objects_v2(cur_source_bucket, cur_source_prefix)
                for obj in res.get("Contents", []):
                    k = obj["Key"]
                    if k.endswith("manifest.json") or k.endswith("-Manifest.json"):
                        discovered_key = k
                        break
            except Exception as e:
                logger.warning("Error listing objects for manifest discovery: %s", e)

        if discovered_key:
            manifest_uri = f"s3://{cur_source_bucket}/{discovered_key}"
            try:
                manifest_data = local_s3.get_object(cur_source_bucket, discovered_key)
                if isinstance(manifest_data, dict) and "Body" in manifest_data:
                    manifest_bytes = manifest_data["Body"].read()
                else:
                    manifest_bytes = manifest_data
                manifest_json = json.loads(manifest_bytes.decode("utf-8"))
                # Validation
                if not isinstance(manifest_json, dict) or "assemblyId" not in manifest_json:
                    raise ValueError("Invalid manifest schema: missing assemblyId")
                assembly_id = manifest_json.get("assemblyId", "")
                report_keys = manifest_json.get("reportKeys", [])
            except Exception as e:
                logger.error("Manifest validation failed for %s: %s", manifest_uri, e)
                raise finops_common.InvalidInputError(f"CUR manifest validation failed: {e}")
        else:
            logger.warning("CUR manifest was not found in the configured source bucket.")
            response = finops_common.create_response("CUR_DELAY", event.run_id, event.correlation_id, "cost_puller", {
                "error": "Billing reports (CUR) manifest was not found in the configured source bucket.",
                "delayed_cur": True
            })
            return response.to_dict()

    # Fetch CloudWatch Utilization Metrics (resource_ids is empty for CUR ready since normalizer will query Athena later)
    resource_ids = []
    if cur_delayed and ce_records:
        resource_ids = list(set([r.get("resource_id") for r in ce_records if r.get("resource_id")]))
    utilization_metrics, missing_cloudwatch = query_cw_utilization(local_cw, resource_ids, exec_time)

    # Query Traffic context (Business context)
    traffic_volume, traffic_source, missing_traffic = query_traffic_context(local_cw, exec_time)
    missing_cloudwatch = missing_cloudwatch or missing_traffic

    # Calculate quality / completeness score
    completeness_score = 1.0
    if cur_delayed:
        completeness_score = 0.8
    if missing_cloudwatch:
        completeness_score *= 0.5
    if stale_cost_explorer:
        completeness_score *= 0.8

    raw_data_uri = ""
    s3_object_checksum = ""

    if cur_delayed:
        # Build raw envelope for CE fallback
        raw_envelope = {
            "schema_version": "3.2.0",
            "tenant_id": event.tenant_id or "tenant-default",
            "account_id": event.account_id,
            "correlation_id": event.correlation_id,
            "idempotency_key": event_data.get("idempotency_key") or finops_common.idempotency_key(event.account_id, event.cost_period, event.execution_date),
            "request_timestamp": datetime.utcnow().isoformat() + "Z",
            "aws_cur_line_items": [],
            "aws_cost_explorer_daily": ce_records,
            "resource_utilization_metrics": utilization_metrics,
            "business_context": [
                {
                    "linked_account_id": event.account_id,
                    "traffic_volume": traffic_volume,
                    "traffic_source": traffic_source,
                    "campaign_flag": False,
                    "load_test_flag": False,
                    "migration_flag": False
                }
            ],
            "quality": {
                "completeness_score": completeness_score,
                "delayed_cur": cur_delayed,
                "stale_cost_explorer": stale_cost_explorer,
                "missing_cloudwatch": missing_cloudwatch,
                "estimated_billing": estimated_billing
            }
        }

        # Serialize and compress envelope
        envelope_json = json.dumps(raw_envelope).encode("utf-8")
        gzipped_bytes = gzip.compress(envelope_json)
        s3_object_checksum = hashlib.sha256(gzipped_bytes).hexdigest()

        # Partition path and key
        cur_key = f"cur/account_id={event.account_id}/year={exec_time.year:04d}/month={exec_time.month:02d}/day={exec_time.day:02d}/{event.run_id}_raw.json.gz"
        raw_data_uri = f"s3://{telemetry_bucket}/{cur_key}"

        # Check for path traversal/unsafe chars in raw_key
        if ".." in cur_key:
            raise finops_common.UnsafeActionError("Unsafe raw data key path traversal detected")

        if local_s3:
            try:
                logger.info("Writing gzipped raw cost data to S3: %s", raw_data_uri)
                local_s3.put_object(telemetry_bucket, cur_key, gzipped_bytes)

                # Split features from the cost envelope and write under features/ prefix
                features_envelope = {
                    "resource_utilization_metrics": utilization_metrics,
                    "business_context": raw_envelope["business_context"]
                }
                features_json = json.dumps(features_envelope).encode("utf-8")
                gzipped_features = gzip.compress(features_json)
                features_key = f"features/account_id={event.account_id}/year={exec_time.year:04d}/month={exec_time.month:02d}/day={exec_time.day:02d}/{event.run_id}_features.json.gz"

                logger.info("Writing gzipped features data to S3: s3://%s/%s", telemetry_bucket, features_key)
                local_s3.put_object(telemetry_bucket, features_key, gzipped_features)
            except Exception as e:
                logger.error("Failed to write raw data to S3: %s", e)
                raise e
    else:
        # CUR ready - write features only to S3
        if local_s3:
            try:
                features_envelope = {
                    "resource_utilization_metrics": utilization_metrics,
                    "business_context": [
                        {
                            "linked_account_id": event.account_id,
                            "traffic_volume": traffic_volume,
                            "traffic_source": traffic_source,
                            "campaign_flag": False,
                            "load_test_flag": False,
                            "migration_flag": False
                        }
                    ]
                }
                features_json = json.dumps(features_envelope).encode("utf-8")
                gzipped_features = gzip.compress(features_json)
                features_key = f"features/account_id={event.account_id}/year={exec_time.year:04d}/month={exec_time.month:02d}/day={exec_time.day:02d}/{event.run_id}_features.json.gz"

                logger.info("Writing gzipped features data to S3: s3://%s/%s", telemetry_bucket, features_key)
                local_s3.put_object(telemetry_bucket, features_key, gzipped_features)
            except Exception as e:
                logger.error("Failed to write features data to S3: %s", e)
                raise e

    if cur_delayed:
        details = {
            "status": status,
            "raw_data_uri": raw_data_uri,
            "data_source_type": "S3_POINTER",
            "s3_object_checksum": s3_object_checksum,
            "telemetry_delay_event": True,
            "missing_resources": missing_resources,
            "current_ce_cost_gap_usd": current_ce_cost_gap_usd,
            "comparison_window": comparison_window,
            "delayed_cur": True,
            "missing_cloudwatch": missing_cloudwatch,
            "stale_cost_explorer": stale_cost_explorer,
            "estimated_billing": estimated_billing,
            "completeness_score": completeness_score,
            "resource_utilization_metrics": utilization_metrics,
            "business_context": [
                {
                    "linked_account_id": event.account_id,
                    "traffic_volume": traffic_volume,
                    "traffic_source": traffic_source,
                    "campaign_flag": False,
                    "load_test_flag": False,
                    "migration_flag": False
                }
            ]
        }
    else:
        details = {
            "status": status,
            "data_source_type": "S3_POINTER",
            "cur_manifest_uri": manifest_uri,
            "source_bucket": cur_source_bucket,
            "source_prefix": cur_source_prefix,
            "account_id": event.account_id,
            "run_window": event.cost_period,
            "freshness_flags": {
                "delayed_cur": False,
                "last_modified": cur_last_modified.isoformat() + "Z" if cur_last_modified else (exec_time.isoformat() + "Z")
            },
            "quality_flags": {
                "completeness_score": completeness_score,
                "stale_cost_explorer": stale_cost_explorer,
                "missing_cloudwatch": missing_cloudwatch,
                "estimated_billing": estimated_billing
            },
            "resource_utilization_metrics": utilization_metrics,
            "business_context": [
                {
                    "linked_account_id": event.account_id,
                    "traffic_volume": traffic_volume,
                    "traffic_source": traffic_source,
                    "campaign_flag": False,
                    "load_test_flag": False,
                    "migration_flag": False
                }
            ],
            "delayed_cur": False,
            "missing_cloudwatch": missing_cloudwatch,
            "stale_cost_explorer": stale_cost_explorer,
            "estimated_billing": estimated_billing,
            "completeness_score": completeness_score
        }

    response = finops_common.create_response(status, event.run_id, event.correlation_id, "cost_puller", details)
    if raw_data_uri:
        response.raw_data_uri = raw_data_uri
    response.telemetry_quality = completeness_score
    response.tenant_id = event.tenant_id

    logger.info("Response: %s", response.to_dict())
    return response.to_dict()

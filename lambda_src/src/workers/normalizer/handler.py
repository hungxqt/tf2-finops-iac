import os
import io
import json
import gzip
import logging
import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any
import boto3
import math
import finops_common

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = None
ddb_client = None
athena_client = None


def sanitize_dict_for_logging(d: dict) -> dict:
    if not isinstance(d, dict):
        return d
    sanitized = {}
    for k, v in d.items():
        if k in ("aws_cur_line_items", "aws_cost_explorer_daily", "resource_utilization_metrics", "missing_resources"):
            if isinstance(v, list):
                sanitized[k] = f"<list of {len(v)} items>"
            else:
                sanitized[k] = str(v)
        elif isinstance(v, dict):
            sanitized[k] = sanitize_dict_for_logging(v)
        elif isinstance(v, list):
            if len(v) > 5:
                sanitized[k] = f"<list of {len(v)} items>"
            else:
                sanitized[k] = [sanitize_dict_for_logging(item) if isinstance(item, dict) else item for item in v]
        else:
            sanitized[k] = v
    return sanitized


def sanitize_ce_records(records):
    sanitized = []
    if not records:
        return sanitized
    for r in records:
        if not isinstance(r, dict):
            continue
        val = r.get("unblended_cost")
        if val is None:
            val = r.get("line_item_unblended_cost")
        if val is None:
            val = r.get("cost")
        if val is None:
            continue
        try:
            cost = float(val)
            if not math.isfinite(cost):
                continue
        except (ValueError, TypeError):
            continue
        if cost < 0:
            continue
        sanitized.append(r)
    return sanitized

def sanitize_cur_records(records):
    sanitized = []
    if not records:
        return sanitized
    for r in records:
        if not isinstance(r, dict):
            continue
        val = r.get("line_item_unblended_cost")
        if val is None:
            val = r.get("unblended_cost")
        if val is None:
            val = r.get("cost")
        if val is None:
            continue
        try:
            cost = float(val)
            if not math.isfinite(cost):
                continue
        except (ValueError, TypeError):
            continue
        if cost < 0:
            continue
        sanitized.append(r)
    return sanitized


def get_s3_client():
    global s3_client
    if s3_client is not None:
        return s3_client
    if os.environ.get("LAKEHOUSE_BUCKET_NAME"):
        return finops_common.RealS3()
    return None


def get_ddb_client():
    global ddb_client
    if ddb_client is not None:
        return ddb_client
    if os.environ.get("RUN_STATE_TABLE_NAME"):
        return finops_common.RealDynamoDB()
    return None


def get_athena_client():
    global athena_client
    if athena_client is not None:
        return athena_client
    if os.environ.get("ATHENA_WORKGROUP_NAME"):
        return boto3.client("athena", region_name=os.environ.get("AWS_DEFAULT_REGION", "ap-southeast-1"))
    return None


def quote_identifier(identifier: str) -> str:
    if not identifier or not re.match(r'^[a-zA-Z0-9_-]+\Z', identifier):
        raise ValueError(f"Invalid identifier for quoting: {identifier}")
    return f'"{identifier}"'


def validate_sql_inputs(account_id: str, start_date: str, end_date: str, database: str, table: str, workgroup: str, results_bucket: str, billing_period: str = None) -> None:
    if not re.match(r'^\d{12}$', account_id):
        raise ValueError(f"Invalid account ID: {account_id}")
    if not re.match(r'^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?$', start_date):
        raise ValueError(f"Invalid start date format: {start_date}")
    if not re.match(r'^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?$', end_date):
        raise ValueError(f"Invalid end date format: {end_date}")
    if database and not re.match(r'^[a-zA-Z0-9_-]+$', database):
        raise ValueError(f"Invalid database name: {database}")
    if table and not re.match(r'^[a-zA-Z0-9_-]+$', table):
        raise ValueError(f"Invalid table name: {table}")
    if workgroup and not re.match(r'^[a-zA-Z0-9_-]+$', workgroup):
        raise ValueError(f"Invalid workgroup name: {workgroup}")
    if results_bucket and (".." in results_bucket or "/" in results_bucket or "\\" in results_bucket):
        raise ValueError(f"Invalid results bucket: {results_bucket}")
    if billing_period and not re.match(r'^\d{4}-\d{2}$', billing_period):
        raise ValueError(f"Invalid billing period: {billing_period}")



def resolve_tenant_id(event: finops_common.Event, event_data: dict) -> str:
    tenant_id = event.tenant_id or event_data.get("tenant_id")
    if tenant_id:
        return str(tenant_id)
    if event.account_id:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tf2-finops:{event.account_id}"))
    return str(uuid.uuid4())


def resolve_account_name(event: finops_common.Event, event_data: dict) -> str:
    account_policy = event_data.get("account_policy") if isinstance(event_data.get("account_policy"), dict) else {}
    return (
        event_data.get("account_name")
        or event.environment
        or account_policy.get("environment")
        or event.account_id
    )


def normalize_business_context(raw_context: Any, account_id: str) -> dict:
    default_context = {
        "linked_account_id": account_id,
        "traffic_volume": 0,
        "traffic_source": "ALB",
        "campaign_flag": False,
        "load_test_flag": False,
        "migration_flag": False,
    }

    selected = {}
    if isinstance(raw_context, dict):
        selected = raw_context
    elif isinstance(raw_context, list):
        candidates = [item for item in raw_context if isinstance(item, dict)]
        selected = next(
            (item for item in candidates if item.get("linked_account_id") == account_id),
            candidates[0] if candidates else {},
        )

    return {**default_context, **selected}


def _select_detect_request_mode(payload_bytes: bytes, max_inline_bytes: int) -> str:
    """Return 'RAW_JSON' if payload_bytes fits within max_inline_bytes, else 'S3_POINTER'.

    This is a pure helper extracted from the CE-fallback normalizer path so that
    the boundary decision can be tested in isolation without mocking the full pipeline.

    Args:
        payload_bytes: Canonical UTF-8 JSON-serialised detect payload bytes.
        max_inline_bytes: Maximum byte count that may be carried inline in
            Step Functions execution state (RAW_JSON mode). Callers should read
            the RAW_JSON_INLINE_MAX_BYTES env var (default 200000).

    Returns:
        'RAW_JSON' or 'S3_POINTER'.
    """
    if len(payload_bytes) <= max_inline_bytes:
        return "RAW_JSON"
    return "S3_POINTER"
def build_dynamic_select_fields(manifest_columns: list) -> str:
    # manifest_columns can be a list of strings or list of dicts. Normalize it to lowercase strings.
    normalized_manifest_cols = set()
    for col in manifest_columns:
        if isinstance(col, dict):
            name = col.get("name") or col.get("ColumnName") or col.get("columnName")
            if name:
                normalized_manifest_cols.add(name.lower())
        elif isinstance(col, str):
            normalized_manifest_cols.add(col.lower())
            
    # Check mandatory columns using the shared validator
    finops_common.validate_manifest_columns(manifest_columns)
            
    # All columns we want to query
    all_target_columns = [
        "bill_billing_period_start_date",
        "bill_payer_account_id",
        "line_item_usage_account_id",
        "line_item_line_item_type",
        "line_item_usage_start_date",
        "line_item_usage_end_date",
        "line_item_product_code",
        "line_item_usage_type",
        "line_item_operation",
        "line_item_resource_id",
        "line_item_usage_amount",
        "pricing_unit",
        "line_item_unblended_rate",
        "line_item_unblended_cost",
        "line_item_currency_code",
        "product_product_name",
        "product_region_code",
        "product_instance_type",
        "resource_tags_user_environment",
        "resource_tags_user_owner",
        "resource_tags_user_team",
        "resource_tags_user_cost_center"
    ]
    
    select_fields = []
    for col in all_target_columns:
        if col.lower() in normalized_manifest_cols:
            select_fields.append(col)
        else:
            select_fields.append(f"NULL AS {col}")
            
    return ", ".join(select_fields)


def get_athena_timestamp_window(start_date_str: str, end_date_str: str) -> tuple[str, str]:
    """Converts validated YYYY-MM-DD dates into an Athena-safe half-open timestamp window.

    Args:
        start_date_str: Validated start date string (YYYY-MM-DD format).
        end_date_str: Validated end date string (YYYY-MM-DD format).

    Returns:
        A tuple of (start_timestamp_literal, end_exclusive_timestamp_literal).
    """
    from datetime import datetime, timedelta
    start_dt = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
    end_dt = datetime.strptime(end_date_str[:10], "%Y-%m-%d")
    end_exclusive_dt = end_dt + timedelta(days=1)

    start_ts = f"TIMESTAMP '{start_dt.strftime('%Y-%m-%d')} 00:00:00'"
    end_ts = f"TIMESTAMP '{end_exclusive_dt.strftime('%Y-%m-%d')} 00:00:00'"
    return start_ts, end_ts



def handle_request(event_data: dict, context: Any) -> dict:
    sanitized_event = sanitize_dict_for_logging(event_data)
    logger.info("Received event: %s", finops_common.redact_sensitive_info(str(sanitized_event)))

    operation = (event_data.get("operation") or "").lower()

    # ── fail_contract_check: record contract version mismatch ──────────
    if operation == "fail_contract_check":
        table_name = os.environ.get("RUN_STATE_TABLE_NAME")
        client = get_ddb_client()
        if client and table_name:
            idempotency_key = finops_common.idempotency_key(
                event_data.get("account_id", ""),
                event_data.get("cost_period", ""),
                event_data.get("execution_date", ""),
            )
            try:
                client.put_item(table_name, {
                    "idempotency_key": idempotency_key,
                    "status": "FAILED_CONTRACT_CHECK",
                    "run_id": event_data.get("run_id", ""),
                    "correlation_id": event_data.get("correlation_id", ""),
                    "failure_code": "CONTRACT_MISMATCH",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                status = "FAILED_CONTRACT_CHECK"
            except Exception as e:
                logger.error("DynamoDB fail_contract_check write failed: %s", e)
                raise e
        else:
            status = "FAILED_CONTRACT_CHECK"

        details = {
            "account_id": event_data.get("account_id", ""),
            "cost_period": event_data.get("cost_period", ""),
            "execution_date": event_data.get("execution_date", ""),
            "failure_code": "CONTRACT_MISMATCH",
        }
        response = finops_common.create_response(
            status,
            event_data.get("run_id", ""),
            event_data.get("correlation_id", ""),
            "normalizer",
            details,
        )
        summary = {
            "status": status,
            "run_id": event_data.get("run_id", ""),
            "correlation_id": event_data.get("correlation_id", ""),
            "failure_code": "CONTRACT_MISMATCH",
        }
        logger.info("Response Summary: %s", json.dumps(summary))
        return response.to_dict()

    # ── Normal path: validate event ────────────────────────────────────
    try:
        event = finops_common.Event.from_dict(event_data)
        finops_common.validate_event(event)
    except Exception as e:
        logger.error("Validation failed: %s", e)
        raise e

    bucket_name = os.environ.get("LAKEHOUSE_BUCKET_NAME")
    if not bucket_name:
        raise finops_common.ConfigMissingError("LAKEHOUSE_BUCKET_NAME is required for normalized telemetry writes")

    try:
        exec_time = finops_common.parse_date(event.execution_date)
    except Exception as e:
        logger.error("Invalid execution date: %s", e)
        raise e

    partition_path = (
        f"account_id={event.account_id}/year={exec_time.year:04d}/month={exec_time.month:02d}"
    )
    curated_key = f"cost/curated/{partition_path}/{event.run_id}_curated.parquet"
    curated_data_uri = f"s3://{bucket_name}/{curated_key}"

    # Extract ingestion details
    ingestion_details = event_data.get("ingestion", {}).get("details", {}) if isinstance(event_data.get("ingestion"), dict) else {}
    raw_uri = ingestion_details.get("raw_data_uri") or event_data.get("ingestion", {}).get("raw_data_uri") or ""
    cur_manifest_uri = (
        ingestion_details.get("cur_manifest_uri")
        or event_data.get("cur_manifest_uri")
        or ""
    )
    telemetry_delay_event = bool(
        ingestion_details.get("telemetry_delay_event")
        or raw_uri
        or False
    )

    client = get_s3_client()
    raw_records = None

    # Resolve telemetry quality flags
    explicit_completeness_score = (
        event_data.get("completeness_score") is not None
        or event_data.get("telemetry_quality") is not None
        or ingestion_details.get("completeness_score") is not None
    )
    completeness_score = float(
        event_data.get("completeness_score")
        or event_data.get("telemetry_quality")
        or ingestion_details.get("completeness_score")
        or 1.0
    )
    delayed_cur = telemetry_delay_event
    stale_cost_explorer = bool(
        event_data.get("stale_cost_explorer")
        or ingestion_details.get("stale_cost_explorer")
        or False
    )
    missing_cloudwatch = bool(
        event_data.get("missing_cloudwatch")
        or ingestion_details.get("missing_cloudwatch")
        or False
    )
    estimated_billing = bool(
        event_data.get("estimated_billing")
        or ingestion_details.get("estimated_billing")
        or False
    )

    cur_records = []
    ce_records = []
    s3_bucket_uri = ""
    s3_object_checksum = ""
    if event.is_ad_hoc:
        safe_run_id = "".join(c for c in event.run_id if c.isalnum() or c in "-_")
        batch_type = f"adhoc-{safe_run_id}"
    else:
        batch_type = "daily"
    tenant_id = resolve_tenant_id(event, event_data)
    account_name = resolve_account_name(event, event_data)
    ai_idempotency_key = event_data.get("idempotency_key") or f"{tenant_id}:{event.execution_date}:{batch_type}"
    request_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Resolve business context
    raw_bc = ingestion_details.get("business_context")
    business_context = normalize_business_context(raw_bc, event.account_id)
    if not raw_bc:
        missing_cloudwatch = True
        if not explicit_completeness_score:
            completeness_score = min(completeness_score, 0.5)

    # Resolve resource utilization metrics
    resource_utilization_metrics = ingestion_details.get("resource_utilization_metrics") or []

    if telemetry_delay_event:
        # CE Fallback path: read gzipped CE data from S3, normalize to curated Parquet
        logger.info("Normalizing Cost Explorer fallback telemetry from: %s", raw_uri)
        if not raw_uri:
            raise finops_common.InvalidInputError("telemetry_delay_event requires raw_data_uri")
        if not client:
            raise finops_common.ConfigMissingError("LAKEHOUSE_BUCKET_NAME did not resolve an S3 client")

        try:
            s3_bucket, s3_key = finops_common.parse_s3_uri(raw_uri)
            raw_gzipped = client.get_object(s3_bucket, s3_key)
            if isinstance(raw_gzipped, dict) and "Body" in raw_gzipped:
                raw_data = raw_gzipped["Body"].read()
            else:
                raw_data = raw_gzipped
            s3_object_checksum = hashlib.sha256(raw_data).hexdigest()
        except Exception as e:
            logger.error("Failed to read raw cost data from S3: %s", e)
            raise e

        try:
            if raw_data.startswith(b'\x1f\x8b'):
                decompressed_data = gzip.decompress(raw_data)
            else:
                decompressed_data = raw_data
            raw_records = json.loads(decompressed_data.decode("utf-8"))
        except Exception as e:
            logger.error("Failed to parse raw cost records JSON: %s", e)
            raise e

        if isinstance(raw_records, dict):
            ce_records = raw_records.get("aws_cost_explorer_daily", [])
            if not ce_records and "aws_cur_line_items" in raw_records:
                ce_records = raw_records.get("aws_cur_line_items", [])
            ce_records = sanitize_ce_records(ce_records)
            records_to_normalize = ce_records

            # Extract quality flags from envelope if present and not overridden by event_data
            envelope_quality = raw_records.get("quality", {})
            if envelope_quality:
                if "completeness_score" in envelope_quality and event_data.get("completeness_score") is None:
                    completeness_score = float(envelope_quality["completeness_score"])
                if "delayed_cur" in envelope_quality and event_data.get("delayed_cur") is None:
                    delayed_cur = bool(envelope_quality["delayed_cur"])
                if "stale_cost_explorer" in envelope_quality and event_data.get("stale_cost_explorer") is None:
                    stale_cost_explorer = bool(envelope_quality["stale_cost_explorer"])
                if "missing_cloudwatch" in envelope_quality and event_data.get("missing_cloudwatch") is None:
                    missing_cloudwatch = bool(envelope_quality["missing_cloudwatch"])
                if "estimated_billing" in envelope_quality and event_data.get("estimated_billing") is None:
                    estimated_billing = bool(envelope_quality["estimated_billing"])
        elif isinstance(raw_records, list):
            ce_records = sanitize_ce_records(raw_records)
            records_to_normalize = ce_records
        else:
            records_to_normalize = []

        s3_bucket_uri = raw_uri

    if not telemetry_delay_event:
        # CUR ready path — cur_manifest_uri is required
        if not cur_manifest_uri:
            raise finops_common.InvalidInputError(
                "CUR-ready normalizer path requires ingestion.details.cur_manifest_uri; "
                "pass the manifest URI returned by cost_puller."
            )

        workgroup = os.environ.get("ATHENA_WORKGROUP_NAME")
        database = os.environ.get("GLUE_DATABASE_NAME")
        table = os.environ.get("GLUE_TABLE_NAME")
        results_bucket = os.environ.get("ATHENA_RESULTS_BUCKET_NAME")
        cur_raw_export_prefix = os.environ.get("CUR_RAW_EXPORT_PREFIX") or ""
        missing_athena_config = [
            name for name, value in {
                "ATHENA_WORKGROUP_NAME": workgroup,
                "GLUE_DATABASE_NAME": database,
                "GLUE_TABLE_NAME": table,
                "ATHENA_RESULTS_BUCKET_NAME": results_bucket,
            }.items()
            if not value
        ]
        if missing_athena_config:
            raise finops_common.ConfigMissingError(
                "Missing Athena configuration for CUR normalization: "
                + ", ".join(missing_athena_config)
            )

        # Resolve billing period
        bp = event.cost_period or ""
        billing_period_out = exec_time.strftime("%Y-%m")
        if bp:
            m = re.match(r'^(\d{4}-\d{2})', bp.strip())
            if m:
                billing_period_out = m.group(1)

        # Re-read and re-validate the manifest dataFiles so normalizer can
        # independently confirm they stay within the allowed raw export prefix.
        manifest_columns = []
        if client and cur_manifest_uri:
            try:
                m_bucket, m_key = finops_common.parse_s3_uri(cur_manifest_uri)
                manifest_raw = client.get_object(m_bucket, m_key)
                if isinstance(manifest_raw, dict) and "Body" in manifest_raw:
                    manifest_bytes = manifest_raw["Body"].read()
                else:
                    manifest_bytes = manifest_raw
                manifest_json = json.loads(manifest_bytes.decode("utf-8"))
                
                parsed_manifest = finops_common.parse_and_validate_manifest(manifest_json)
                manifest_columns = parsed_manifest["columns"]
                data_files = parsed_manifest["data_files"]
                
                # Validate columns
                finops_common.validate_manifest_columns(manifest_columns)
                
                # Validate data files
                allowed_prefix = ingestion_details.get("allowed_raw_prefix") or cur_raw_export_prefix
                finops_common.validate_data_files(
                    data_files=data_files,
                    allowed_bucket=m_bucket,
                    allowed_prefix=allowed_prefix,
                    billing_period=billing_period_out
                )
            except (finops_common.UnsafeActionError, finops_common.InvalidInputError, finops_common.ContractMismatchError):
                raise
            except Exception as manifest_err:
                logger.error("CUR manifest re-validation failed: %s", manifest_err)
                raise finops_common.InvalidInputError(f"CUR manifest validation failed: {manifest_err}")
        else:
            raise finops_common.InvalidInputError("CUR-ready normalizer path requires ingestion.details.cur_manifest_uri")

        start_date = event.execution_date
        end_date = event.execution_date

        # SQL validation
        validate_sql_inputs(event.account_id, start_date, end_date, database, table, workgroup, results_bucket, billing_period_out)

        # Build select fields dynamically based on manifest columns
        select_fields = build_dynamic_select_fields(manifest_columns)

        start_ts, end_ts = get_athena_timestamp_window(start_date, end_date)

        # Validate generated timestamp literals to prevent injection
        if not re.match(r"^TIMESTAMP '\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'$", start_ts):
            raise ValueError(f"Invalid start timestamp literal: {start_ts}")
        if not re.match(r"^TIMESTAMP '\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'$", end_ts):
            raise ValueError(f"Invalid end timestamp literal: {end_ts}")

        cur_raw_account_partition_key = os.environ.get("CUR_RAW_ACCOUNT_PARTITION_KEY") or ""
        
        where_clauses = [
            f"billing_period = '{billing_period_out}'",
            f"line_item_usage_account_id = '{event.account_id}'",
            f"line_item_usage_start_date >= {start_ts}",
            f"line_item_usage_start_date < {end_ts}"
        ]
        
        if cur_raw_account_partition_key:
            if not re.match(r'^[a-zA-Z0-9_-]+$', cur_raw_account_partition_key):
                raise ValueError(f"Invalid partition key configured: {cur_raw_account_partition_key}")
            where_clauses.append(f"{cur_raw_account_partition_key} = '{event.account_id}'")

        query = f"""
        SELECT {select_fields}
        FROM {quote_identifier(table)}
        WHERE {" AND ".join(where_clauses)}
        """

        ath = get_athena_client()
        if not ath:
            raise finops_common.ConfigMissingError("ATHENA_WORKGROUP_NAME did not resolve an Athena client")

        try:
            output_loc = f"s3://{results_bucket}/results/"
            response = ath.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": database},
                ResultConfiguration={"OutputLocation": output_loc},
                WorkGroup=workgroup
            )
            query_exec_id = response["QueryExecutionId"]

            # Poll query execution status
            import time
            max_attempts = 30
            attempt = 0
            while attempt < max_attempts:
                status_res = ath.get_query_execution(QueryExecutionId=query_exec_id)
                state = status_res["QueryExecution"]["Status"]["State"]
                if state in ["SUCCEEDED"]:
                    break
                elif state in ["FAILED", "CANCELLED"]:
                    reason = status_res["QueryExecution"]["Status"].get("StateChangeReason", "Unknown")
                    raise RuntimeError(f"Athena query execution {query_exec_id} failed with state {state}: {reason}")
                time.sleep(0.5)
                attempt += 1
            else:
                raise TimeoutError("Athena query execution timed out")

            # Paginate results
            next_token = None
            headers = []
            while True:
                kwargs = {"QueryExecutionId": query_exec_id}
                if next_token:
                    kwargs["NextToken"] = next_token
                res_page = ath.get_query_results(**kwargs)

                rows = res_page["ResultSet"]["Rows"]
                start_idx = 0
                if not next_token and rows:
                    headers = [col.get("VarCharValue", "") for col in rows[0]["Data"]]
                    start_idx = 1

                for row in rows[start_idx:]:
                    row_data = {}
                    for idx, col in enumerate(row["Data"]):
                        val = col.get("VarCharValue", "")
                        if idx < len(headers):
                            row_data[headers[idx]] = val
                    cur_records.append(row_data)

                next_token = res_page.get("NextToken")
                if not next_token:
                    break
        except Exception as e:
            logger.error("Athena query execution failed: %s", e)
            raise e

        cur_records = sanitize_cur_records(cur_records)
        if not cur_records:
            raise finops_common.InvalidInputError("Athena returned no CUR records")

        # Calculate usage density for Hrs pricing unit
        for rec in cur_records:
            if rec.get("pricing_unit") == "Hrs":
                rec["usage_density_24h"] = min(float(rec.get("line_item_usage_amount") or 0.0) / 24.0, 1.0)
            else:
                rec["usage_density_24h"] = 0.0

        records_to_normalize = cur_records

        # Build full AI detect payload JSON, gzip it, and write to S3
        detect_payload = {
            "schema_version": "3.2.0",
            "tenant_id": tenant_id,
            "account_id": event.account_id,
            "account_name": account_name,
            "correlation_id": event.correlation_id,
            "idempotency_key": ai_idempotency_key,
            "request_timestamp": request_timestamp,
            "aws_cur_line_items": cur_records,
            "aws_cost_explorer_daily": [],
            "resource_utilization_metrics": resource_utilization_metrics,
            "business_context": business_context,
            "quality": {
                "completeness_score": completeness_score,
                "delayed_cur": False,
                "stale_cost_explorer": False,
                "missing_cloudwatch": missing_cloudwatch,
                "estimated_billing": estimated_billing
            }
        }

        detect_json = json.dumps(detect_payload).encode("utf-8")
        detect_gzipped = gzip.compress(detect_json)
        s3_object_checksum = hashlib.sha256(detect_gzipped).hexdigest()

        ai_key = f"ai-input/account_id={event.account_id}/year={exec_time.year:04d}/month={exec_time.month:02d}/day={exec_time.day:02d}/{event.run_id}_input.json.gz"
        s3_bucket_uri = f"s3://{bucket_name}/{ai_key}"

        if ".." in ai_key:
            raise finops_common.UnsafeActionError("Unsafe raw data key path traversal detected")

        if client:
            try:
                logger.info("Writing gzipped AI detect input to S3: %s", s3_bucket_uri)
                client.put_object(bucket_name, ai_key, detect_gzipped)
            except Exception as e:
                logger.error("Failed to write AI detect input to S3: %s", e)
                raise e

    # 5. Normalise records
    curated_records = []
    for rec in records_to_normalize:
        account_id = (
            rec.get("account_id")
            or rec.get("line_item_usage_account_id")
            or rec.get("linked_account_id")
            or ""
        )
        cost = float(
            rec.get("cost")
            or rec.get("line_item_unblended_cost")
            or rec.get("unblended_cost")
            or 0.0
        )

        service = (
            rec.get("service")
            or rec.get("line_item_product_code")
            or rec.get("service_code")
            or ""
        )
        if not account_id or not service or cost < 0:
            logger.info("Filtering out invalid cost record (account: %s, service: %s)", account_id, service)
            continue

        owner = rec.get("owner") or rec.get("resource_tags_user_owner") or ""
        if not owner or owner.strip() == "":
            owner = "untagged"

        squad = (
            rec.get("squad")
            or rec.get("team")
            or rec.get("resource_tags_user_team")
            or "untagged"
        )
        cost_center = (
            rec.get("cost_center")
            or rec.get("resource_tags_user_cost_center")
            or "untagged"
        )
        region = rec.get("region") or rec.get("product_region_code") or ""
        resource_id = rec.get("resource_id") or rec.get("line_item_resource_id") or ""
        currency = rec.get("currency") or rec.get("line_item_currency_code") or "USD"
        timestamp = (
            rec.get("timestamp")
            or rec.get("line_item_usage_start_date")
            or rec.get("date")
            or ""
        )

        curated_records.append({
            "account_id": account_id,
            "service": service,
            "region": region,
            "owner": owner,
            "cost": cost,
            "currency": currency,
            "timestamp": timestamp,
            "curated_at": datetime.now(timezone.utc).isoformat(),
            "unblended_cost": cost,
            "service_code": service,
            "resource_id": resource_id,
            "squad": squad,
            "cost_center": cost_center,
            "schema_version": "3.2.0",
            "correlation_id": event.correlation_id,
            "idempotency_key": event_data.get("idempotency_key") or event.correlation_id,
            "quality_score": completeness_score,
        })

    # 6. Serialise to Parquet
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.Table.from_pylist(curated_records)
        buf = io.BytesIO()
        pq.write_table(table, buf)
        curated_data = buf.getvalue()
        logger.info("Successfully generated Parquet bytes: %d bytes", len(curated_data))
    except Exception as e:
        logger.error("Failed to write Parquet using pyarrow: %s", e)
        raise RuntimeError(f"Failed to generate Parquet bytes: {e}") from e

    # 7. Write to S3 curated folder
    if client:
        try:
            logger.info("Writing curated cost data to S3: %s", curated_data_uri)
            client.put_object(bucket_name, curated_key, curated_data)
        except Exception as e:
            logger.error("Failed to write curated cost to S3: %s", e)
            raise e
    else:
        logger.info("S3 Client not configured, skipping curated S3 write")

    # Resolve missing_resources
    missing_resources = []
    if not telemetry_delay_event:
        missing_resources = []
    else:
        if isinstance(raw_records, dict):
            missing_resources = raw_records.get("missing_resources", [])
        if not missing_resources:
            missing_resources = (
                event_data.get("missing_resources")
                or ingestion_details.get("missing_resources")
                or []
            )

    # Resolve current_ce_cost_gap_usd
    current_ce_cost_gap_usd = 0.0
    if telemetry_delay_event:
        if isinstance(raw_records, dict):
            current_ce_cost_gap_usd = float(raw_records.get("current_ce_cost_gap_usd", 0.0))
        if not current_ce_cost_gap_usd:
            current_ce_cost_gap_usd = float(
                event_data.get("current_ce_cost_gap_usd")
                or ingestion_details.get("current_ce_cost_gap_usd")
                or 0.0
            )
        current_ce_cost_gap_usd = max(0.0, current_ce_cost_gap_usd)

    # Resolve comparison_window
    comparison_window = {"start_date": event.execution_date, "end_date": event.execution_date}
    if telemetry_delay_event:
        if isinstance(raw_records, dict) and "comparison_window" in raw_records:
            raw_cw = raw_records["comparison_window"]
            if isinstance(raw_cw, dict):
                comparison_window = raw_cw
        else:
            cw_val = (
                event_data.get("comparison_window")
                or ingestion_details.get("comparison_window")
            )
            if isinstance(cw_val, dict):
                comparison_window = cw_val

    if telemetry_delay_event:
        detect_payload = {
            "schema_version": "3.2.0",
            "tenant_id": tenant_id,
            "account_id": event.account_id,
            "account_name": account_name,
            "correlation_id": event.correlation_id,
            "idempotency_key": ai_idempotency_key,
            "request_timestamp": request_timestamp,
            "aws_cur_line_items": cur_records,
            "aws_cost_explorer_daily": ce_records,
            "missing_resources": missing_resources,
            "current_ce_cost_gap_usd": current_ce_cost_gap_usd,
            "comparison_window": comparison_window,
            "resource_utilization_metrics": resource_utilization_metrics,
            "business_context": business_context,
            "quality": {
                "completeness_score": completeness_score,
                "delayed_cur": delayed_cur,
                "stale_cost_explorer": stale_cost_explorer,
                "missing_cloudwatch": missing_cloudwatch,
                "estimated_billing": estimated_billing,
            },
        }

        detect_json = json.dumps(detect_payload).encode("utf-8")
        detect_gzipped = gzip.compress(detect_json)
        s3_object_checksum = hashlib.sha256(detect_gzipped).hexdigest()
        ai_key = f"ai-input/account_id={event.account_id}/year={exec_time.year:04d}/month={exec_time.month:02d}/day={exec_time.day:02d}/{event.run_id}_input.json.gz"
        s3_bucket_uri = f"s3://{bucket_name}/{ai_key}"

        if ".." in ai_key:
            raise finops_common.UnsafeActionError("Unsafe raw data key path traversal detected")

        if client:
            try:
                logger.info("Writing gzipped AI detect input to S3: %s", s3_bucket_uri)
                client.put_object(bucket_name, ai_key, detect_gzipped)
            except Exception as e:
                logger.error("Failed to write AI detect input to S3: %s", e)
                raise e

    # Determine detect_request_mode for CE fallback.
    # RAW_JSON is used only when the canonical JSON payload fits within the
    # configured inline byte cap (RAW_JSON_INLINE_MAX_BYTES, default 200 KB).
    # This keeps Step Functions execution state safely below Step Functions limits
    # even though the AI API contract allows payloads up to 10 MB.
    raw_json_inline_max_bytes = int(
        os.environ.get("RAW_JSON_INLINE_MAX_BYTES", "200000")
    )
    ce_payload_bytes = json.dumps(detect_payload).encode("utf-8")
    detect_request_mode = _select_detect_request_mode(ce_payload_bytes, raw_json_inline_max_bytes)
    if detect_request_mode == "RAW_JSON":
        logger.info(
            "CE-fallback payload size %d B <= %d B cap; using RAW_JSON mode.",
            len(ce_payload_bytes), raw_json_inline_max_bytes,
        )
    else:
        logger.info(
            "CE-fallback payload size %d B > %d B cap; using S3_POINTER mode.",
            len(ce_payload_bytes), raw_json_inline_max_bytes,
        )

    details = {
        "curated_data_uri": curated_data_uri,
        "schema_version": "3.2.0",
        "schema": "finops-cost-window-v1",
        "tenant_id": tenant_id,
        "account_id": event.account_id,
        "account_name": account_name,
        "correlation_id": event.correlation_id,
        "idempotency_key": ai_idempotency_key,
        "request_timestamp": request_timestamp,
        "partition_keys": ["account_id", "year", "month"],
        "completeness_score": completeness_score,
        "delayed_cur": delayed_cur,
        "stale_cost_explorer": stale_cost_explorer,
        "missing_cloudwatch": missing_cloudwatch,
        "estimated_billing": estimated_billing,
        "detect_request_mode": detect_request_mode,
        "s3_bucket_uri": s3_bucket_uri,
        "s3_object_checksum": s3_object_checksum,
        "business_context": business_context,
        # resource_utilization_metrics and CUR/CE arrays are always included in the
        # normalizer output so downstream states can read them if needed.
        # For RAW_JSON mode the Step Functions ChooseDetectRequestMode state will
        # build the inline body directly from these fields.
        # For S3_POINTER mode the large arrays are present but BuildDetectRequestS3Pointer
        # explicitly omits aws_cur_line_items from the Step Functions body.
        "resource_utilization_metrics": resource_utilization_metrics,
        "aws_cur_line_items": cur_records,
        "aws_cost_explorer_daily": ce_records,
        "missing_resources": missing_resources,
        "current_ce_cost_gap_usd": current_ce_cost_gap_usd,
        "comparison_window": comparison_window,
        "batch_type": batch_type,
        "telemetry_delay_event": telemetry_delay_event,
    }

    response = finops_common.create_response(
        "NORMALIZED", event.run_id, event.correlation_id, "normalizer", details
    )
    response.curated_data_uri = curated_data_uri
    response.telemetry_quality = completeness_score
    summary = {
        "status": "NORMALIZED",
        "run_id": event.run_id,
        "correlation_id": event.correlation_id,
        "curated_data_uri": curated_data_uri,
        "s3_bucket_uri": s3_bucket_uri,
        "detect_request_mode": detect_request_mode,
        "telemetry_quality": completeness_score,
        "item_counts": {
            "cur_records": len(cur_records),
            "ce_records": len(ce_records),
            "curated_records": len(curated_records)
        }
    }
    logger.info("Response Summary: %s", json.dumps(summary))
    return response.to_dict()

import os
import logging
import json
import urllib.request
import urllib.error
import urllib.parse
import hashlib
from datetime import datetime, timezone
from typing import Any, Tuple, Optional
import uuid
import boto3
import botocore.auth
import botocore.awsrequest
import finops_common

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class HTTPClient:
    def post(self, url: str, headers: dict, body: bytes, timeout: float = 10.0) -> Any:
        raise NotImplementedError()

    def get(self, url: str, headers: dict, timeout: float = 10.0) -> Any:
        raise NotImplementedError()

def sign_request(url: str, method: str, headers: dict, body: Optional[bytes], region: str) -> dict:
    session = boto3.Session()
    credentials = session.get_credentials()
    if not credentials:
        return headers
    frozen_creds = credentials.get_frozen_credentials()
    
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc
    
    req_headers = headers.copy()
    req_headers['Host'] = host
    
    service = os.environ.get("AI_ENGINE_SIGNING_SERVICE", "execute-api")
    
    req = botocore.awsrequest.AWSRequest(method=method, url=url, headers=req_headers, data=body)
    botocore.auth.SigV4Auth(frozen_creds, service, region).add_auth(req)
    
    return dict(req.headers)

class RealHTTPClient(HTTPClient):
    def request(self, method: str, url: str, headers: dict, body: Optional[bytes] = None, timeout: float = 10.0) -> Tuple[int, bytes, dict]:
        aws_region = os.environ.get("AWS_REGION", "ap-southeast-1")
        signed_headers = headers.copy()
        try:
            signed_headers = sign_request(url, method, headers, body, aws_region)
        except Exception as e:
            logger.warning("Failed to sign request with SigV4 (using original headers): %s", e)
            
        req = urllib.request.Request(url, data=body, headers=signed_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                resp_headers = {k.lower(): v for k, v in response.getheaders()}
                return response.status, response.read(), resp_headers
        except urllib.error.HTTPError as e:
            resp_headers = {k.lower(): v for k, v in e.headers.items()}
            return e.code, e.read(), resp_headers
        except Exception as e:
            raise e

    def post(self, url: str, headers: dict, body: bytes, timeout: float = 10.0) -> Any:
        return self.request("POST", url, headers, body, timeout)

    def get(self, url: str, headers: dict, timeout: float = 10.0) -> Any:
        return self.request("GET", url, headers, None, timeout)

class FakeHTTPClient(HTTPClient):
    def __init__(self, post_func=None, get_func=None):
        self.post_func = post_func
        self.get_func = get_func

    def post(self, url: str, headers: dict, body: bytes, timeout: float = 10.0) -> Any:
        if self.post_func:
            return self.post_func(url, headers, body, timeout)
        default_resp = b'{"anomaly_found": true, "severity": "medium", "confidence": 0.85, "recommended_containment_mode": "dry-run", "anomaly_id": "ANOM-TEST-001"}'
        return 200, default_resp

    def get(self, url: str, headers: dict, timeout: float = 10.0) -> Any:
        if self.get_func:
            return self.get_func(url, headers, timeout)
        default_resp = b'{"audit_id": "ANOM-TEST-001", "status": "completed", "total_anomalies_found": 0, "anomalies_list": []}'
        return 200, default_resp

secrets_client = None
http_client = RealHTTPClient()

def get_secrets_client():
    global secrets_client
    if secrets_client is not None:
        return secrets_client
    if os.environ.get("AI_ENGINE_SECRET_NAME"):
        return finops_common.RealSecretsManager()
    return None

def execute_http_call_with_retries(method: str, url: str, headers: dict, body: Optional[bytes], timeout_val: float, retry_attempts: int) -> Tuple[int, bytes, dict]:
    import time
    last_error = None
    backoff_delay = 1.0
    
    for attempt in range(retry_attempts + 1):
        try:
            if method == "POST":
                res = http_client.post(url, headers, body or b"", timeout=timeout_val)
            else:
                res = http_client.get(url, headers, timeout=timeout_val)
                
            if len(res) == 2:
                status_code, resp_body = res
                resp_headers = {}
            else:
                status_code, resp_body, resp_headers = res
                
            if status_code == 429:
                retry_after_str = resp_headers.get("retry-after")
                wait_sec = float(retry_after_str) if retry_after_str and retry_after_str.isdigit() else backoff_delay
                logger.warning("HTTP status 429 received. Retrying in %f seconds (attempt %d/%d)", wait_sec, attempt, retry_attempts)
                time.sleep(wait_sec)
                backoff_delay *= 2.0
                continue
                
            if status_code >= 500 and attempt < retry_attempts:
                logger.warning("HTTP status %d received. Retrying in %f seconds (attempt %d/%d)", status_code, backoff_delay, attempt, retry_attempts)
                time.sleep(backoff_delay)
                backoff_delay *= 2.0
                continue
                
            return status_code, resp_body, resp_headers
            
        except Exception as e:
            last_error = e
            if attempt < retry_attempts:
                logger.warning("HTTP request failed: %s. Retrying in %f seconds (attempt %d/%d)", e, backoff_delay, attempt, retry_attempts)
                time.sleep(backoff_delay)
                backoff_delay *= 2.0
            else:
                raise e
                
    if last_error:
        raise last_error
    return status_code, resp_body, resp_headers

def process_detection_response(det_resp: dict, event: finops_common.Event, operation: str) -> dict:
    anomalies_list = det_resp.get("anomalies_list", [])
    
    if "anomalies_list" in det_resp:
        anomaly_found = len(anomalies_list) > 0
        if anomaly_found:
            first_anom = anomalies_list[0]
            meta = first_anom.get("anomaly_metadata", {})
            eng = first_anom.get("engineering_dashboard_data", {})
            fin = first_anom.get("finance_dashboard_data", {})
            mit = eng.get("mitigation_action", {})
            
            anomaly_id = meta.get("anomaly_id", "")
            confidence = meta.get("confidence_score", 0.0)
            recommended_mode = mit.get("immediate_action") or mit.get("strategy") or first_anom.get("recommended_containment_mode", "")
            severity = fin.get("metrics", {}).get("severity") or meta.get("severity") or ""
            explanation = fin.get("executive_summary") or fin.get("explanation") or ""
        else:
            anomaly_id = ""
            confidence = 0.0
            recommended_mode = ""
            severity = ""
            explanation = ""
    else:
        anomaly_found = det_resp.get("anomaly_found")
        confidence = det_resp.get("confidence")
        recommended_mode = det_resp.get("recommended_containment_mode", "")
        anomaly_id = det_resp.get("anomaly_id", "")
        severity = det_resp.get("severity", "")
        explanation = det_resp.get("explanation", "")
        
    if anomaly_found is None or (anomaly_found and (confidence is None or not recommended_mode)):
        logger.error("AI Response schema validation failed. Failing closed.")
        details = {"error": "Required fields schema validation failed."}
        response = finops_common.create_response("CONTRACT_MISMATCH", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()

    # 9. Unsafe containment check in prod
    env = (event.environment or "").lower()
    if event.account_policy and event.account_policy.environment:
        env = event.account_policy.environment.lower()
        
    mode = recommended_mode.lower()
    is_destructive = mode in ["terminate", "delete", "modify_iam", "apply"]
    if env == "prod" and is_destructive:
        logger.error("AI Engine recommended unsafe containment mode '%s' in production. Failing closed.", recommended_mode)
        details = {"error": "Unsafe recommendation in production environment."}
        response = finops_common.create_response("CONTRACT_MISMATCH", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()

    # 10. Return Response
    details = {
        "model_version": "live-detect",
        "anomaly_id": anomaly_id,
        "confidence": confidence,
        "severity": severity,
        "explanation": explanation,
        "recommended_containment_mode": recommended_mode
    }
    
    status = "COMPLETED" if operation else "OK"
    response = finops_common.create_response(status, event.run_id, event.correlation_id, "ai_client", details)
    response.required_fields_valid = True
    response.anomaly_found = bool(anomaly_found)
    response.recommended_containment_mode = recommended_mode
    response.anomaly_id = anomaly_id
    response.severity = severity
    response.confidence = float(confidence)
    
    return response.to_dict()

def handle_request(event_data: dict, context: Any) -> dict:
    logger.info("Received event: %s", finops_common.redact_sensitive_info(str(event_data)))
    
    try:
        event = finops_common.Event.from_dict(event_data)
        finops_common.validate_event(event)
    except Exception as e:
        logger.error("Validation failed: %s", e)
        raise e

    operation = event_data.get("operation") or ""
    action = event.action.lower() if event.action else ""
    if action.startswith("simulate-"):
        return handle_simulation(event, action, operation)

    # 2. Load configuration
    ai_endpoint = os.environ.get("AI_ENGINE_ENDPOINT_URL", "")
    ai_secret_name = os.environ.get("AI_ENGINE_SECRET_NAME", "")
    ai_contract_version = os.environ.get("AI_ENGINE_CONTRACT_VERSION", "")
    allowed_hosts = os.environ.get("AI_ENGINE_ALLOWED_HOSTS", "")
    aws_region = os.environ.get("AWS_REGION", "ap-southeast-1")

    try:
        timeout_val = float(os.environ.get("AI_ENGINE_TIMEOUT_SECONDS", "10.0"))
    except ValueError:
        timeout_val = 10.0
        
    try:
        retry_attempts = int(os.environ.get("AI_ENGINE_RETRY_ATTEMPTS", "3"))
    except ValueError:
        retry_attempts = 3

    if not ai_endpoint or not ai_contract_version:
        logger.error("AI Engine configuration missing. Failing closed.")
        details = {"error": "AI Engine endpoint or contract version missing."}
        response = finops_common.create_response("UNAVAILABLE", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()

    # 3. HTTPS requirement check
    if not ai_endpoint.lower().startswith("https://"):
        logger.error("AI Endpoint URL is not secure (HTTPS required). Failing closed.")
        details = {"error": "Non-HTTPS endpoint is rejected."}
        response = finops_common.create_response("CONTRACT_MISMATCH", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()

    # 4. Host allowlist check
    try:
        u = urllib.parse.urlparse(ai_endpoint)
        hostname = u.hostname
    except Exception as e:
        logger.error("Failed to parse AI Endpoint URL: %s", e)
        hostname = None

    if not hostname:
        logger.error("Invalid endpoint URL hostname. Failing closed.")
        details = {"error": "Invalid endpoint URL hostname."}
        response = finops_common.create_response("UNAVAILABLE", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()

    host_allowed = False
    if allowed_hosts:
        hosts = [h.strip() for h in allowed_hosts.split(",")]
        if hostname in hosts:
            host_allowed = True

    if not host_allowed:
        logger.error("AI Endpoint hostname '%s' is not in allowed hosts list. Failing closed.", hostname)
        details = {"error": "Endpoint hostname is not authorized."}
        response = finops_common.create_response("UNAVAILABLE", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()

    # 5. Version checks
    if event.source_data_version and event.source_data_version != ai_contract_version:
        logger.error("Contract version mismatch: event version '%s' vs engine version '%s'. Failing closed.", event.source_data_version, ai_contract_version)
        details = {"error": "Contract version mismatch."}
        response = finops_common.create_response("CONTRACT_MISMATCH", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()

    # 6. Fetch Bearer Token from Secrets Manager (backward compatibility for tests)
    if ai_secret_name:
        sec_client = get_secrets_client()
        if not sec_client:
            logger.error("Secrets Manager client is not initialized. Failing closed.")
            details = {"error": "Secrets Manager integration is unavailable."}
            response = finops_common.create_response("UNAVAILABLE", event.run_id, event.correlation_id, "ai_client", details)
            response.required_fields_valid = False
            response.anomaly_found = False
            return response.to_dict()
        try:
            sec_client.get_secret_value(ai_secret_name)
        except Exception as e:
            logger.error("Failed to retrieve auth token from Secrets Manager: %s. Failing closed.", e)
            details = {"error": "Auth token retrieval failed."}
            response = finops_common.create_response("UNAVAILABLE", event.run_id, event.correlation_id, "ai_client", details)
            response.required_fields_valid = False
            response.anomaly_found = False
            return response.to_dict()

    tenant_id = event_data.get("tenant_id") or event_data.get("X-Tenant-Id")
    if not tenant_id and event.account_id:
        import uuid
        tenant_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, event.account_id))
    if not tenant_id:
        tenant_id = "11111111-2222-3333-4444-555555555555"

    # ROUTE OPERATIONS
    if operation == "poll_detect_result":
        audit_id = event_data.get("audit_id") or (event.ai and event.ai.audit_id) or event_data.get("ai", {}).get("details", {}).get("audit_id") or event_data.get("ai", {}).get("audit_id")
        if not audit_id:
            logger.error("Missing audit_id for polling. Failing closed.")
            response = finops_common.create_response("CONTRACT_MISMATCH", event.run_id, event.correlation_id, "ai_client", {"error": "Missing audit_id for polling"})
            response.required_fields_valid = False
            response.anomaly_found = False
            return response.to_dict()

        url_result = f"{ai_endpoint.rstrip('/')}/detect/result/{audit_id}"
        logger.info("Polling AI Engine result: %s", url_result)
        
        try:
            get_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            get_headers = {
                "Accept": "application/json",
                "X-Tenant-Id": tenant_id,
                "X-Correlation-Id": event.correlation_id or event.run_id,
                "X-Request-Timestamp": get_timestamp
            }
            
            p_status, p_body, p_headers = execute_http_call_with_retries(
                "GET", url_result, get_headers, None, timeout_val, retry_attempts
            )
        except Exception as e:
            logger.error("Polling request failed: %s", e)
            status = "UNAVAILABLE"
            if "timeout" in str(e).lower() or isinstance(e, TimeoutError):
                status = "TIMEOUT"
            response = finops_common.create_response(status, event.run_id, event.correlation_id, "ai_client", {"error": str(e)})
            response.required_fields_valid = False
            response.anomaly_found = False
            return response.to_dict()
            
        if p_status != 200:
            logger.error("Polling returned unexpected status code: %d", p_status)
            status_mapped = "UNAVAILABLE"
            if p_status in [401, 403]:
                status_mapped = "AUTH_FAILED"
            elif p_status in [400, 422]:
                status_mapped = "CONTRACT_MISMATCH"
            elif p_status == 429:
                status_mapped = "RATE_LIMITED"
            response = finops_common.create_response(status_mapped, event.run_id, event.correlation_id, "ai_client", {"error": f"Polling HTTP {p_status}"})
            response.required_fields_valid = False
            response.anomaly_found = False
            return response.to_dict()
            
        try:
            det_resp = json.loads(p_body.decode("utf-8"))
        except Exception as e:
            logger.error("Failed to parse polling response JSON: %s", e)
            response = finops_common.create_response("CONTRACT_MISMATCH", event.run_id, event.correlation_id, "ai_client", {"error": "Invalid JSON response during polling"})
            response.required_fields_valid = False
            response.anomaly_found = False
            return response.to_dict()
            
        job_status = det_resp.get("status", "")
        if job_status == "completed":
            logger.info("Async processing completed successfully.")
            return process_detection_response(det_resp, event, operation)
        elif job_status == "failed":
            err_msg = det_resp.get("error_message", "Unknown AI Engine error")
            logger.error("Async processing failed on AI Engine: %s", err_msg)
            status_mapped = "UNAVAILABLE"
            if "TIMEOUT" in err_msg:
                status_mapped = "TIMEOUT"
            elif "SCHEMA" in err_msg or "CONTRACT" in err_msg:
                status_mapped = "CONTRACT_MISMATCH"
            response = finops_common.create_response(status_mapped, event.run_id, event.correlation_id, "ai_client", {"error": err_msg})
            response.required_fields_valid = False
            response.anomaly_found = False
            return response.to_dict()
        else: # "processing" or "accepted"
            retry_after = p_headers.get("retry-after") or "10"
            details = {"audit_id": audit_id, "job_status": job_status}
            response = finops_common.create_response("PROCESSING", event.run_id, event.correlation_id, "ai_client", details)
            response.retry_after_seconds = int(retry_after) if retry_after.isdigit() else 10
            response.required_fields_valid = False
            response.anomaly_found = False
            return response.to_dict()

    # 7. Post request to AI Engine API (submit_detect or legacy one-shot)
    curated_uri = ""
    if event.normalized and event.normalized.curated_data_uri:
        curated_uri = event.normalized.curated_data_uri

    data_source_type = "S3_POINTER" if curated_uri else "RAW_JSON"
    
    aws_cost_explorer_daily = []
    if event.normalized and event.normalized.details:
        aws_cost_explorer_daily = event.normalized.details.get("aws_cost_explorer_daily") or event.normalized.details.get("cost_explorer_daily") or []
    
    if not aws_cost_explorer_daily:
        aws_cost_explorer_daily = [{
            "unblended_cost": 0.0,
            "service_code": "AmazonEC2",
            "region": aws_region,
            "cost_ratio_to_7d_avg": 1.0,
            "day_of_week": 0,
            "is_weekend": False
        }]

    req_payload = {
        "data_source_type": data_source_type,
        "is_ad_hoc": event.is_ad_hoc or event.action == "ad-hoc" or event_data.get("is_ad_hoc", False),
        "aws_cost_explorer_daily": aws_cost_explorer_daily
    }

    if data_source_type == "S3_POINTER":
        req_payload["s3_bucket_uri"] = curated_uri
    else:
        aws_cur_line_items = []
        if event.normalized and event.normalized.details:
            aws_cur_line_items = event.normalized.details.get("aws_cur_line_items") or event.normalized.details.get("line_items") or []
        req_payload["aws_cur_line_items"] = aws_cur_line_items

    req_body = json.dumps(req_payload).encode("utf-8")

    date_str = event.execution_date
    if not date_str or len(date_str) < 10:
        if event.cost_period and len(event.cost_period) >= 10:
            date_str = event.cost_period[:10]
        else:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    idem_key = f"{tenant_id}:{date_str}"

    payload_hash = hashlib.sha256(req_body).hexdigest()
    req_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Tenant-Id": tenant_id,
        "X-Idempotency-Key": idem_key,
        "X-Correlation-Id": event.correlation_id or event.run_id,
        "X-Payload-SHA256": payload_hash,
        "X-Request-Timestamp": req_timestamp,
    }

    url_detect = f"{ai_endpoint.rstrip('/')}/detect"
    logger.info("Calling AI Engine API: %s", url_detect)

    try:
        status_code, resp_body, resp_headers = execute_http_call_with_retries(
            "POST", url_detect, headers, req_body, timeout_val, retry_attempts
        )
    except Exception as e:
        logger.error("AI Engine HTTP request failed: %s", e)
        status = "UNAVAILABLE"
        if "timeout" in str(e).lower() or isinstance(e, TimeoutError):
            status = "TIMEOUT"
        details = {"error": str(e)}
        response = finops_common.create_response(status, event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()

    audit_id = None
    det_resp = {}
    
    if status_code in [200, 202, 409]:
        try:
            det_resp = json.loads(resp_body.decode("utf-8"))
            audit_id = det_resp.get("audit_id")
        except Exception as e:
            logger.error("Failed to parse AI response JSON: %s", e)

    if operation == "submit_detect":
        if status_code == 202 or (status_code == 200 and audit_id and "anomalies_list" not in det_resp and "anomaly_found" not in det_resp):
            response = finops_common.create_response("ACCEPTED", event.run_id, event.correlation_id, "ai_client", {"audit_id": audit_id})
            response.required_fields_valid = False
            response.anomaly_found = False
            return response.to_dict()
        elif status_code == 200:
            return process_detection_response(det_resp, event, operation)
        else:
            status_mapped = "UNAVAILABLE"
            if status_code == 429:
                status_mapped = "RATE_LIMITED"
            elif status_code in [401, 403]:
                status_mapped = "AUTH_FAILED"
            elif status_code == 409:
                status_mapped = "IDEMPOTENCY_MISMATCH"
            elif status_code in [400, 422]:
                status_mapped = "CONTRACT_MISMATCH"
            response = finops_common.create_response(status_mapped, event.run_id, event.correlation_id, "ai_client", {"error": f"Failed to submit: HTTP {status_code}"})
            response.required_fields_valid = False
            response.anomaly_found = False
            return response.to_dict()

    # Legacy one-shot mode (no operation specified)
    should_poll = (status_code == 202) or (status_code == 409) or (status_code == 200 and audit_id and "anomalies_list" not in det_resp and "anomaly_found" not in det_resp)
    
    if should_poll and audit_id:
        import time
        url_result = f"{ai_endpoint.rstrip('/')}/detect/result/{audit_id}"
        poll_start = time.time()
        max_poll_duration = 50.0
        poll_interval = 2.0
        
        logger.info("Starting async polling for audit_id: %s", audit_id)
        
        while True:
            if time.time() - poll_start > max_poll_duration:
                logger.error("Async polling timed out after %f seconds", max_poll_duration)
                response = finops_common.create_response("TIMEOUT", event.run_id, event.correlation_id, "ai_client", {"error": "Polling timeout"})
                response.required_fields_valid = False
                response.anomaly_found = False
                return response.to_dict()
                
            logger.info("Polling AI Engine result: %s", url_result)
            try:
                get_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                get_headers = {
                    "Accept": "application/json",
                    "X-Tenant-Id": tenant_id,
                    "X-Correlation-Id": event.correlation_id or event.run_id,
                    "X-Request-Timestamp": get_timestamp
                }
                
                p_status, p_body, p_headers = execute_http_call_with_retries(
                    "GET", url_result, get_headers, None, timeout_val, retry_attempts
                )
            except Exception as e:
                logger.error("Polling request failed: %s", e)
                response = finops_common.create_response("UNAVAILABLE", event.run_id, event.correlation_id, "ai_client", {"error": str(e)})
                response.required_fields_valid = False
                response.anomaly_found = False
                return response.to_dict()
                
            if p_status != 200:
                logger.error("Polling returned unexpected status code: %d", p_status)
                status_mapped = "UNAVAILABLE"
                if p_status == 403:
                    status_mapped = "CONTRACT_MISMATCH"
                response = finops_common.create_response(status_mapped, event.run_id, event.correlation_id, "ai_client", {"error": f"Polling HTTP {p_status}"})
                response.required_fields_valid = False
                response.anomaly_found = False
                return response.to_dict()
                
            try:
                det_resp = json.loads(p_body.decode("utf-8"))
            except Exception as e:
                logger.error("Failed to parse polling response JSON: %s", e)
                response = finops_common.create_response("CONTRACT_MISMATCH", event.run_id, event.correlation_id, "ai_client", {"error": "Invalid JSON response during polling"})
                response.required_fields_valid = False
                response.anomaly_found = False
                return response.to_dict()
                
            job_status = det_resp.get("status", "")
            if job_status == "completed":
                logger.info("Async processing completed successfully.")
                break
            elif job_status == "failed":
                err_msg = det_resp.get("error_message", "Unknown AI Engine error")
                logger.error("Async processing failed on AI Engine: %s", err_msg)
                status_mapped = "UNAVAILABLE"
                if "TIMEOUT" in err_msg:
                    status_mapped = "TIMEOUT"
                elif "SCHEMA" in err_msg or "CONTRACT" in err_msg:
                    status_mapped = "CONTRACT_MISMATCH"
                response = finops_common.create_response(status_mapped, event.run_id, event.correlation_id, "ai_client", {"error": err_msg})
                response.required_fields_valid = False
                response.anomaly_found = False
                return response.to_dict()
            elif job_status == "processing":
                retry_after_str = p_headers.get("retry-after")
                sleep_time = float(retry_after_str) if retry_after_str and retry_after_str.isdigit() else poll_interval
                logger.info("AI Engine still processing. Sleeping for %f seconds...", sleep_time)
                time.sleep(sleep_time)
            else:
                logger.error("Unknown job status: %s", job_status)
                response = finops_common.create_response("CONTRACT_MISMATCH", event.run_id, event.correlation_id, "ai_client", {"error": f"Unknown job status {job_status}"})
                response.required_fields_valid = False
                response.anomaly_found = False
                return response.to_dict()
    elif status_code == 200:
        pass
    else:
        logger.error("Failed to submit job. HTTP status: %d", status_code)
        status_mapped = "UNAVAILABLE"
        if status_code in [400, 422, 403]:
            status_mapped = "CONTRACT_MISMATCH"
        response = finops_common.create_response(status_mapped, event.run_id, event.correlation_id, "ai_client", {"error": f"Failed to submit: HTTP {status_code}"})
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()

    return process_detection_response(det_resp, event, operation)

def handle_simulation(event: finops_common.Event, action: str, operation: str = "") -> dict:
    if action == "simulate-timeout":
        logger.info("Simulating timeout error.")
        details = {"error": "AI Engine request timed out."}
        response = finops_common.create_response("TIMEOUT", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()
    elif action == "simulate-unavailable":
        logger.info("Simulating unavailable service.")
        details = {"error": "AI Engine service is unavailable."}
        response = finops_common.create_response("UNAVAILABLE", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()
    elif action == "simulate-mismatch":
        logger.info("Simulating contract mismatch error.")
        details = {"error": "AI Engine contract mismatch."}
        response = finops_common.create_response("CONTRACT_MISMATCH", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()

    if operation == "submit_detect":
        response = finops_common.create_response("ACCEPTED", event.run_id, event.correlation_id, "ai_client", {"audit_id": "ANOM-SIM-123"})
        return response.to_dict()

    if action == "simulate-invalid":
        logger.info("Simulating invalid required fields response.")
        details = {"error": "Required fields validation failed."}
        response = finops_common.create_response("CONTRACT_MISMATCH", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()
    elif action == "simulate-no-anomaly":
        logger.info("Simulating response with no anomaly found.")
        details = {
            "model_version": "skeleton",
            "explanation": "No cost anomalies detected in the current billing window."
        }
        status = "COMPLETED" if operation else "OK"
        response = finops_common.create_response(status, event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = True
        response.anomaly_found = False
        return response.to_dict()
    elif action == "simulate-unsafe":
        logger.info("Simulating unsafe recommendation (e.g. terminate/delete in prod).")
        anomalies = [
            {
                "anomaly_id": "ANOM-UNSAFE-001",
                "service": "EC2",
                "reason": "Cost limit exceeded, recommendation is destructive",
                "confidence": 0.95,
                "severity": "critical",
                "recommended_containment_mode": "terminate"
            }
        ]
        details = {
            "model_version": "skeleton",
            "anomaly_id": "ANOM-UNSAFE-001",
            "confidence": 0.95,
            "severity": "critical",
            "expected_spend": 100.00,
            "actual_spend": 500.00,
            "delta": 400.00,
            "explanation": "Unsafe recommendation for prod containment override check.",
            "recommended_route": "engineering",
            "recommended_containment_mode": "terminate",
            "evidence_uri": "s3://tf2-finops-audit-bucket/evidence/unsafe.json",
            "anomalies": anomalies
        }
        
        env = (event.environment or "").lower()
        if event.account_policy and event.account_policy.environment:
            env = event.account_policy.environment.lower()
        if env == "prod":
            logger.error("AI Engine recommended unsafe containment mode 'terminate' in production. Failing closed.")
            details_err = {"error": "Unsafe recommendation in production environment."}
            response = finops_common.create_response("CONTRACT_MISMATCH", event.run_id, event.correlation_id, "ai_client", details_err)
            response.required_fields_valid = False
            response.anomaly_found = False
            return response.to_dict()

        status = "COMPLETED" if operation else "OK"
        response = finops_common.create_response(status, event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = True
        response.anomaly_found = True
        response.recommended_containment_mode = "terminate"
        response.anomaly_id = "ANOM-UNSAFE-001"
        response.severity = "critical"
        response.confidence = 0.95
        return response.to_dict()
    else:
        raise ValueError(f"unknown simulation mode: {action}")


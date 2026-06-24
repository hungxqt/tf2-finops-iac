import os
import logging
import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Tuple, Optional
import finops_common

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class HTTPClient:
    def post(self, url: str, headers: dict, body: bytes, timeout: float = 10.0) -> Tuple[int, bytes]:
        raise NotImplementedError()

class RealHTTPClient(HTTPClient):
    def post(self, url: str, headers: dict, body: bytes, timeout: float = 10.0) -> Tuple[int, bytes]:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception as e:
            raise e

class FakeHTTPClient(HTTPClient):
    def __init__(self, post_func=None):
        self.post_func = post_func

    def post(self, url: str, headers: dict, body: bytes, timeout: float = 10.0) -> Tuple[int, bytes]:
        if self.post_func:
            return self.post_func(url, headers, body, timeout)
        default_resp = b'{"anomaly_found": true, "severity": "medium", "confidence": 0.85, "recommended_containment_mode": "dry-run", "anomaly_id": "ANOM-TEST-001"}'
        return 200, default_resp

secrets_client = None
http_client = RealHTTPClient()

def get_secrets_client():
    global secrets_client
    if secrets_client is not None:
        return secrets_client
    # In AWS, real secrets client will be initialized if the env var is present
    if os.environ.get("AI_ENGINE_SECRET_NAME"):
        return finops_common.RealSecretsManager()
    return None

def handle_request(event_data: dict, context: Any) -> dict:
    logger.info("Received event: %s", finops_common.redact_sensitive_info(str(event_data)))
    
    try:
        event = finops_common.Event.from_dict(event_data)
        finops_common.validate_event(event)
    except Exception as e:
        logger.error("Validation failed: %s", e)
        raise e

    action = event.action.lower() if event.action else ""
    if action.startswith("simulate-"):
        return handle_simulation(event, action)

    # 2. Load configuration
    ai_endpoint = os.environ.get("AI_ENGINE_ENDPOINT_URL", "")
    ai_secret_name = os.environ.get("AI_ENGINE_SECRET_NAME", "")
    ai_contract_version = os.environ.get("AI_ENGINE_CONTRACT_VERSION", "")
    allowed_hosts = os.environ.get("AI_ENGINE_ALLOWED_HOSTS", "")

    if not ai_endpoint or not ai_secret_name or not ai_contract_version:
        logger.error("AI Engine configuration missing. Failing closed.")
        details = {"error": "AI Engine endpoint, secret name, or contract version missing."}
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

    # 6. Fetch Bearer Token from Secrets Manager
    sec_client = get_secrets_client()
    if not sec_client:
        logger.error("Secrets Manager client is not initialized. Failing closed.")
        details = {"error": "Secrets Manager integration is unavailable."}
        response = finops_common.create_response("UNAVAILABLE", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()

    try:
        secret_token = sec_client.get_secret_value(ai_secret_name)
    except Exception as e:
        logger.error("Failed to retrieve auth token from Secrets Manager: %s. Failing closed.", e)
        details = {"error": "Auth token retrieval failed."}
        response = finops_common.create_response("UNAVAILABLE", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()

    # 7. Post request to AI Engine API
    curated_uri = ""
    if event.normalized and event.normalized.curated_data_uri:
        curated_uri = event.normalized.curated_data_uri

    req_payload = {
        "contract_version": ai_contract_version,
        "correlation_id": event.correlation_id,
        "curated_data_uri": curated_uri,
        "run_id": event.run_id
    }
    req_body = json.dumps(req_payload).encode("utf-8")
    
    headers = {
        "Authorization": f"Bearer {secret_token}",
        "Content-Type": "application/json"
    }
    
    url_detect = f"{ai_endpoint.rstrip('/')}/detect"
    logger.info("Calling AI Engine API: %s", url_detect)

    try:
        status_code, resp_body = http_client.post(url_detect, headers, req_body, timeout=10.0)
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

    if status_code != 200:
        logger.error("AI Engine returned unexpected status code: %d", status_code)
        details = {"error": f"Unexpected status: {status_code}"}
        response = finops_common.create_response("UNAVAILABLE", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()

    # 8. Schema validation
    try:
        det_resp = json.loads(resp_body.decode("utf-8"))
    except Exception as e:
        logger.error("Failed to parse AI Response body JSON: %s. Failing closed.", e)
        details = {"error": "Invalid response JSON."}
        response = finops_common.create_response("CONTRACT_MISMATCH", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()

    anomaly_found = det_resp.get("anomaly_found")
    confidence = det_resp.get("confidence")
    recommended_mode = det_resp.get("recommended_containment_mode", "")
    
    if anomaly_found is None or confidence is None or not recommended_mode:
        logger.error("AI Response schema validation failed (missing required fields). Failing closed.")
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
        "anomaly_id": det_resp.get("anomaly_id", ""),
        "confidence": confidence,
        "severity": det_resp.get("severity", ""),
        "explanation": det_resp.get("explanation", ""),
        "recommended_containment_mode": recommended_mode
    }
    
    response = finops_common.create_response("OK", event.run_id, event.correlation_id, "ai_client", details)
    response.required_fields_valid = True
    response.anomaly_found = bool(anomaly_found)
    response.recommended_containment_mode = recommended_mode
    response.anomaly_id = det_resp.get("anomaly_id", "")
    response.severity = det_resp.get("severity", "")
    response.confidence = float(confidence)
    
    return response.to_dict()

def handle_simulation(event: finops_common.Event, action: str) -> dict:
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
    elif action == "simulate-invalid":
        logger.info("Simulating invalid required fields response.")
        details = {"error": "Required fields validation failed."}
        response = finops_common.create_response("OK", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = False
        response.anomaly_found = False
        return response.to_dict()
    elif action == "simulate-no-anomaly":
        logger.info("Simulating response with no anomaly found.")
        details = {
            "model_version": "skeleton",
            "explanation": "No cost anomalies detected in the current billing window."
        }
        response = finops_common.create_response("OK", event.run_id, event.correlation_id, "ai_client", details)
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
        response = finops_common.create_response("OK", event.run_id, event.correlation_id, "ai_client", details)
        response.required_fields_valid = True
        response.anomaly_found = True
        response.recommended_containment_mode = "terminate"
        response.anomaly_id = "ANOM-UNSAFE-001"
        response.severity = "critical"
        response.confidence = 0.95
        return response.to_dict()
    else:
        raise ValueError(f"unknown simulation mode: {action}")

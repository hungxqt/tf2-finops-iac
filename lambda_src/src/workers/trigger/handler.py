import os
import json
import logging
import uuid
from typing import Any
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sfn_client = boto3.client("stepfunctions")


def _get_cors_headers(origin: str) -> dict:
    """
    Returns standard CORS response headers.
    If an origin is present, we reflect it to allow browser fetch from both the
    CloudFront domain and local dev environment (http://127.0.0.1:5173).
    """
    allowed_origin = origin if origin else "*"
    return {
        "Access-Control-Allow-Origin": allowed_origin,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "86400",
        "Content-Type": "application/json",
    }


def handle_request(event: dict, context: Any) -> dict:
    """
    Lambda handler invoked by Lambda Function URL.
    Routes OPTIONS preflight and POST requests to trigger the state machine.
    """
    logger.info("Received event: %s", json.dumps(event))

    headers = event.get("headers", {})
    origin = headers.get("origin") or headers.get("Origin") or ""

    # 1. Handle CORS Preflight
    request_context = event.get("requestContext", {})
    http_info = request_context.get("http", {})
    method = http_info.get("method", "").upper()

    if method == "OPTIONS":
        return {
            "statusCode": 204,
            "headers": _get_cors_headers(origin),
            "body": "",
        }

    # 2. Handle trigger POST request
    if method != "POST":
        return {
            "statusCode": 405,
            "headers": _get_cors_headers(origin),
            "body": json.dumps({"message": f"Method {method} not allowed"}),
        }

    # Parse request body
    body_str = event.get("body", "{}")
    # Handle base64 encoded bodies if any
    if event.get("isBase64Encoded", False):
        import base64
        try:
            body_str = base64.b64decode(body_str).decode("utf-8")
        except Exception as e:
            logger.error("Failed to decode base64 body: %s", str(e))
            return {
                "statusCode": 400,
                "headers": _get_cors_headers(origin),
                "body": json.dumps({"message": "Invalid base64 encoding"}),
            }

    try:
        body = json.loads(body_str) if body_str else {}
    except Exception as e:
        logger.error("Failed to parse JSON body: %s", str(e))
        return {
            "statusCode": 400,
            "headers": _get_cors_headers(origin),
            "body": json.dumps({"message": "Invalid JSON body"}),
        }

    # Validate inputs
    is_ad_hoc = body.get("is_ad_hoc")
    if is_ad_hoc is not True:
        return {
            "statusCode": 400,
            "headers": _get_cors_headers(origin),
            "body": json.dumps({"message": "Only ad-hoc runs are supported (is_ad_hoc must be true)"}),
        }

    tenant_id = body.get("tenant_id")
    account_id = body.get("account_id")

    # Resolve state machine ARN from environment
    state_machine_arn = os.environ.get("STATE_MACHINE_ARN")
    if not state_machine_arn:
        logger.error("STATE_MACHINE_ARN environment variable is not set")
        return {
            "statusCode": 500,
            "headers": _get_cors_headers(origin),
            "body": json.dumps({"message": "Server configuration error: state machine ARN missing"}),
        }

    # Prepare execution payload
    run_id = f"adhoc-{uuid.uuid4()}"
    execution_input = {
        "is_ad_hoc": True,
        "run_id": run_id,
        "correlation_id": str(uuid.uuid4()),
        "execution_date": datetime_utc_now_iso(),
    }
    if tenant_id:
        execution_input["tenant_id"] = tenant_id
    if account_id:
        execution_input["account_id"] = account_id

    try:
        logger.info("Starting execution of %s with input: %s", state_machine_arn, json.dumps(execution_input))
        response = sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=run_id,
            input=json.dumps(execution_input),
        )
        execution_arn = response.get("executionArn", "")
        return {
            "statusCode": 200,
            "headers": _get_cors_headers(origin),
            "body": json.dumps({"execution_arn": execution_arn}),
        }
    except Exception as e:
        err_msg = str(e)
        logger.error("Failed to start Step Functions execution: %s", err_msg)
        return {
            "statusCode": 500,
            "headers": _get_cors_headers(origin),
            "body": json.dumps({"message": f"Failed to start execution: {err_msg}"}),
        }


def datetime_utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

"""
handler.py — AWS Lambda entrypoint for Containment Worker.

AWS gọi hàm này khi Step Functions invoke Containment Lambda.
Nhiệm vụ: parse event → chạy executor → return output dict.

Entry point phải match compute-lambda module handler convention:
  workers.containment_worker.handler.handle_request
"""
from __future__ import annotations

import json
import logging
from typing import Any

from workers.containment_worker.aws.session import load
from workers.containment_worker.executor import ContainmentExecutor
from workers.containment_worker.model.input import ContainmentInput
from workers.containment_worker.model.output import ContainmentOutput


def _make_logger() -> logging.Logger:
    logger = logging.getLogger("containment-worker")
    logger.setLevel(logging.INFO)
    return logger


def handle_request(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda entrypoint — called by Step Functions.

    Args:
        event: JSON payload from Step Functions (AI decision + context)
        context: Lambda runtime context (timeout, request ID, etc.)

    Returns:
        ContainmentOutput as dict for Step Functions
    """
    logger = _make_logger()

    # Parse input
    try:
        if isinstance(event, str):
            event = json.loads(event)
        inp = ContainmentInput.from_dict(event)
    except (KeyError, ValueError, TypeError) as exc:
        logger.error("invalid input payload", extra={"error": str(exc)})
        raise

    logger.info(
        "containment worker started",
        extra={
            "run_id": inp.run_id,
            "anomaly_id": inp.anomaly_id,
            "environment": inp.environment,
            "execution_mode": inp.execution_mode,
            "approval_status": inp.approval_status,
        },
    )

    # Load AWS session (CDO management account)
    session = load()

    # Run executor
    executor = ContainmentExecutor(session)
    output: ContainmentOutput = executor.run(inp)

    logger.info(
        "containment worker completed",
        extra={
            "run_id": inp.run_id,
            "anomaly_id": inp.anomaly_id,
            "status": output.status,
            "execution_mode_applied": output.execution_mode_applied,
            "audit_record_id": output.audit_record_id,
        },
    )

    return output.to_dict()

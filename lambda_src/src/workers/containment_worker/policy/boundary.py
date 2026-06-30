"""
boundary.py — Hard boundary enforcement.

Two protection layers per 03_security_design.md §2.1 and deployment-contract.md §CDO Containment:
  1. prod/prod-core/prod-payments → NEVER apply, NEVER stop → force dry-run
  2. data_confidence = LOW (CUR delay) → force dry-run

This is the MOST IMPORTANT layer. Must run BEFORE all other logic.
IAM policy is the second layer at infra level — this code is the first layer at application level.
"""
from __future__ import annotations

import logging

from workers.containment_worker.model.input import (
    ContainmentInput,
    PROD_ENVS,
    MODE_DRY_RUN,
    MODE_TAG,
    DATA_CONFIDENCE_LOW,
    APPROVAL_DENIED,
)

logger = logging.getLogger(__name__)


def enforce_boundaries(inp: ContainmentInput) -> str:
    """
    Check all hard boundaries and return the enforced execution_mode.

    Does not raise exceptions — always returns the safest possible mode.
    If overridden, logs a clear warning for audit purposes.

    Returns:
        execution_mode after enforcement (may differ from inp.execution_mode)
    """
    original_mode = inp.execution_mode
    enforced_mode = original_mode

    # --- Boundary 1: Approval denied → do nothing ---
    if inp.approval_status == APPROVAL_DENIED:
        logger.warning(
            "containment denied by approval_status",
            extra={
                "anomaly_id": inp.anomaly_id,
                "account_id": inp.account_id,
                "approval_status": inp.approval_status,
            },
        )
        return "denied"

    # --- Boundary 2: Production environment → force dry-run ---
    if inp.environment in PROD_ENVS:
        if original_mode == "apply":
            enforced_mode = MODE_DRY_RUN
            logger.warning(
                "prod boundary: execution_mode overridden to dry-run",
                extra={
                    "anomaly_id": inp.anomaly_id,
                    "account_id": inp.account_id,
                    "environment": inp.environment,
                    "original_mode": original_mode,
                    "enforced_mode": enforced_mode,
                },
            )

    # --- Boundary 3: data_confidence = LOW → force dry-run ---
    if inp.data_confidence == DATA_CONFIDENCE_LOW:
        if enforced_mode != MODE_DRY_RUN:
            enforced_mode = MODE_DRY_RUN
            logger.warning(
                "low data_confidence: execution_mode overridden to dry-run",
                extra={
                    "anomaly_id": inp.anomaly_id,
                    "account_id": inp.account_id,
                    "data_confidence": inp.data_confidence,
                    "original_mode": original_mode,
                    "enforced_mode": enforced_mode,
                },
            )

    if enforced_mode != original_mode:
        logger.info(
            "boundary enforcement summary",
            extra={
                "anomaly_id": inp.anomaly_id,
                "original_mode": original_mode,
                "enforced_mode": enforced_mode,
                "environment": inp.environment,
                "data_confidence": inp.data_confidence,
            },
        )

    return enforced_mode


def is_prod_environment(environment: str) -> bool:
    """Helper to quickly check prod environment."""
    return environment in PROD_ENVS

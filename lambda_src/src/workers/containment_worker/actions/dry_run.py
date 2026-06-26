"""
dry_run.py — Simulate containment action, does not call any AWS API.

Dry-run still writes a full audit record because Finance needs to see
"platform would have done X" even when no real action is taken.
Per ADR-005: "dry-run-first containment guardrail"
"""
from __future__ import annotations

import logging

from workers.containment_worker.model.input import ContainmentInput
from workers.containment_worker.model.output import DryRunResult

logger = logging.getLogger(__name__)


def execute_dry_run(inp: ContainmentInput) -> DryRunResult:
    """
    Simulate action — no AWS API call, only describes what would happen.

    Args:
        inp: Full ContainmentInput

    Returns:
        DryRunResult describing the action that would be taken if apply mode
    """
    applied = inp.applied_payload

    logger.info(
        "dry-run executed",
        extra={
            "anomaly_id": inp.anomaly_id,
            "resource_id": inp.resource_id,
            "would_execute": f"{applied.service}.{applied.method}",
            "environment": inp.environment,
        },
    )

    return DryRunResult(
        would_execute_service=applied.service,
        would_execute_method=applied.method,
        would_execute_parameters=applied.parameters,
        simulation_note=(
            f"dry-run: no AWS API call made. "
            f"Would execute {applied.service}.{applied.method} "
            f"on {inp.resource_id} in {inp.environment}."
        ),
    )

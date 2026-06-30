"""
suggester.py — Create suggestion record for Engineering/Finance review.

Suggest action does not touch AWS resources — only creates a record.
This record is used by Alert Lambda to send Slack/Email to the correct channel.
Per 02_infra_design.md §1.4: separate Finance vs Engineering routing.
"""
from __future__ import annotations

import logging

from workers.containment_worker.model.input import ContainmentInput, PROD_ENVS
from workers.containment_worker.model.output import SuggestionRecord

logger = logging.getLogger(__name__)

ROUTE_FINANCE = "finance"
ROUTE_ENGINEERING = "engineering"

ENGINEERING_ANOMALY_TYPES = {"runaway_usage", "idle_resource"}
FINANCE_ANOMALY_TYPES = {"untagged_spend", "sudden_spike", "gradual_drift"}


def execute_suggest(inp: ContainmentInput) -> SuggestionRecord:
    """
    Create suggestion record with correct route target.

    Route logic:
    - runaway_usage, idle_resource → Engineering (needs shutdown/scale-down)
    - untagged_spend, sudden_spike, gradual_drift → Finance (needs cost review)
    - Unknown → Engineering (safer default)
    """
    route_target = _determine_route(inp.anomaly_type, inp.environment)

    record = SuggestionRecord(
        anomaly_id=inp.anomaly_id,
        resource_id=inp.resource_id,
        recommended_action=inp.recommended_containment_mode,
        explanation=inp.explanation,
        route_target=route_target,
        approval_required=_requires_approval(inp.environment, inp.recommended_containment_mode),
    )

    logger.info(
        "suggestion record created",
        extra={
            "anomaly_id": inp.anomaly_id,
            "resource_id": inp.resource_id,
            "route_target": route_target,
            "anomaly_type": inp.anomaly_type,
            "environment": inp.environment,
        },
    )

    return record


def _determine_route(anomaly_type: str, environment: str) -> str:
    if anomaly_type in ENGINEERING_ANOMALY_TYPES:
        return ROUTE_ENGINEERING
    if anomaly_type in FINANCE_ANOMALY_TYPES:
        return ROUTE_FINANCE
    return ROUTE_ENGINEERING


def _requires_approval(environment: str, containment_mode: str) -> bool:
    if environment in PROD_ENVS:
        return True
    if containment_mode == "auto-shutdown":
        return True
    return False

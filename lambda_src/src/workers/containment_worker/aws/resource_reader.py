"""
resource_reader.py — Read before_state of a resource from the member account.

Runs AFTER AssumeRole into the member account.
Result is used to:
  1. Write into audit record (before_state)
  2. Compute proposed_after_state
  3. Compute rollback_path
"""
from __future__ import annotations

import logging
from typing import Any

import boto3

logger = logging.getLogger(__name__)


def read_before_state(
    session: boto3.Session,
    resource_id: str,
    anomaly_type: str,
) -> dict[str, Any]:
    """
    Read current resource state before any action.

    Dispatches to the appropriate reader based on resource_id prefix.
    If unable to read (resource not found or permission error),
    returns empty dict — does not block containment.

    Args:
        session: Member account session (after AssumeRole)
        resource_id: ARN or instance ID
        anomaly_type: Used to choose the appropriate AWS client

    Returns:
        dict describing current resource state
    """
    try:
        if resource_id.startswith("i-"):
            return _read_ec2_instance(session, resource_id)
        elif "rds" in resource_id.lower() or ":db:" in resource_id:
            return _read_rds_instance(session, resource_id)
        elif "sagemaker" in resource_id.lower() or ":notebook-instance:" in resource_id:
            return _read_sagemaker_notebook(session, resource_id)
        else:
            logger.warning(
                "unknown resource type, returning minimal before_state",
                extra={"resource_id": resource_id},
            )
            return {"resource_id": resource_id, "state": "unknown"}
    except Exception as exc:
        logger.warning(
            "failed to read before_state, continuing with empty state",
            extra={"resource_id": resource_id, "error": str(exc)},
        )
        return {"resource_id": resource_id, "state": "read_failed", "error": str(exc)}


def _read_ec2_instance(session: boto3.Session, instance_id: str) -> dict[str, Any]:
    """Read EC2 instance state."""
    ec2 = session.client("ec2")
    resp = ec2.describe_instances(InstanceIds=[instance_id])

    reservations = resp.get("Reservations", [])
    if not reservations:
        return {"resource_id": instance_id, "state": "not_found"}

    instance = reservations[0]["Instances"][0]
    tags = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}

    return {
        "resource_id": instance_id,
        "instance_type": instance.get("InstanceType", ""),
        "state": instance.get("State", {}).get("Name", ""),
        "launch_time": str(instance.get("LaunchTime", "")),
        "tags": tags,
    }


def _read_rds_instance(session: boto3.Session, db_identifier: str) -> dict[str, Any]:
    """Read RDS DB instance state."""
    rds = session.client("rds")
    identifier = db_identifier.split(":")[-1] if ":" in db_identifier else db_identifier

    resp = rds.describe_db_instances(DBInstanceIdentifier=identifier)
    instances = resp.get("DBInstances", [])
    if not instances:
        return {"resource_id": db_identifier, "state": "not_found"}

    db = instances[0]
    return {
        "resource_id": db_identifier,
        "db_instance_class": db.get("DBInstanceClass", ""),
        "state": db.get("DBInstanceStatus", ""),
        "engine": db.get("Engine", ""),
        "multi_az": db.get("MultiAZ", False),
        "tags": {t["Key"]: t["Value"] for t in db.get("TagList", [])},
    }


def _read_sagemaker_notebook(session: boto3.Session, notebook_name: str) -> dict[str, Any]:
    """Read SageMaker notebook instance state."""
    sm = session.client("sagemaker")
    name = notebook_name.split("/")[-1] if "/" in notebook_name else notebook_name

    resp = sm.describe_notebook_instance(NotebookInstanceName=name)
    return {
        "resource_id": notebook_name,
        "instance_type": resp.get("InstanceType", ""),
        "state": resp.get("NotebookInstanceStatus", ""),
        "tags": {},
    }


def compute_proposed_after_state(
    before_state: dict[str, Any],
    execution_mode: str,
    containment_tags: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Compute proposed_after_state based on before_state and execution_mode.

    Used for audit record — Finance sees "what it would look like after action".
    """
    after = dict(before_state)

    if execution_mode == "dry-run":
        after["_note"] = "dry-run: state would not change"
        return after

    if execution_mode == "tag" and containment_tags:
        existing_tags = dict(after.get("tags", {}))
        existing_tags.update(containment_tags)
        after["tags"] = existing_tags
        return after

    if execution_mode == "apply":
        after["state"] = "stopped"
        return after

    return after

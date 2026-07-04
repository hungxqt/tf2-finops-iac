"""
session.py — AWS session management + cross-account AssumeRole.

Containment Lambda runs in the CDO Management Account but needs
to act on resources in Member Accounts.
Flow: CDO Lambda Role → AssumeRole → FinOpsContainmentWorkerRole (member account)
"""
from __future__ import annotations

import logging
import os

import boto3

logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")


def load() -> boto3.Session:
    """Return default boto3 Session with CDO management account credentials."""
    return boto3.Session(region_name=AWS_REGION)


def assume_containment_role(
    session: boto3.Session,
    account_id: str,
    role_name: str,
    anomaly_id: str,
    external_id: str = "",
) -> boto3.Session:
    """
    Assume FinOpsContainmentWorkerRole in a member account.

    Per 03_security_design.md §2.3:
    - Each cross-account role must have an external_id
    - Session name must be traceable to anomaly_id
    - IAM role in member account has explicit deny for prod resources

    Args:
        session: CDO management account session
        account_id: Member AWS account ID
        role_name: IAM role name in member account (e.g. FinOpsContainmentWorkerRole)
        anomaly_id: Used as session name for CloudTrail traceability
        external_id: External ID from Secrets Manager

    Returns:
        boto3.Session with member account credentials
    """
    # If role_name is empty, fallback to the parent session directly (useful in Sandbox/Smoke mode)
    if not role_name:
        logger.warning(
            "role_name is empty. Falling back to parent session credentials (expected in Sandbox/Smoke mode).",
            extra={"account_id": account_id, "anomaly_id": anomaly_id}
        )
        return session

    sts = session.client("sts")
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

    # Session name is traceable — appears in CloudTrail of member account
    session_name = f"finops-containment-{anomaly_id[:20]}"

    kwargs: dict = {
        "RoleArn": role_arn,
        "RoleSessionName": session_name,
    }
    if external_id:
        kwargs["ExternalId"] = external_id

    try:
        resp = sts.assume_role(**kwargs)
    except Exception as exc:
        raise RuntimeError(
            f"ASSUME_ROLE_FAILED account={account_id} role={role_name}: {exc}"
        ) from exc

    creds = resp["Credentials"]
    logger.info(
        "assumed containment role",
        extra={
            "account_id": account_id,
            "role_arn": role_arn,
            "session_name": session_name,
            "anomaly_id": anomaly_id,
        },
    )

    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        region_name=AWS_REGION,
    )

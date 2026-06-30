import os
import re

def get_block(content, start_pattern):
    match = re.search(start_pattern, content)
    if not match:
        return None
    start_idx = match.start()
    brace_count = 0
    started = False
    for i in range(start_idx, len(content)):
        char = content[i]
        if char == '{':
            brace_count += 1
            started = True
        elif char == '}':
            brace_count -= 1
            if started and brace_count == 0:
                return content[start_idx:i+1]
    return None

def test_normalizer_iam_policy_cur_source():
    """Verify that data.aws_iam_policy_document.normalizer has scoped access to CUR source."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    iam_main_tf = os.path.join(base_dir, "modules/iam/main.tf")
    assert os.path.exists(iam_main_tf), f"modules/iam/main.tf not found at {iam_main_tf}"
    
    with open(iam_main_tf, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract normalizer policy document
    normalizer_block = get_block(content, r'data "aws_iam_policy_document" "normalizer"\s*\{')
    assert normalizer_block is not None, "Could not find data.aws_iam_policy_document.normalizer block in modules/iam/main.tf"

    # Check for ListBucket statement
    assert "AllowCURSourceList" in normalizer_block, (
        "normalizer IAM policy missing AllowCURSourceList statement"
    )
    assert "s3:ListBucket" in normalizer_block, (
        "normalizer IAM policy ListBucket statement missing s3:ListBucket action"
    )
    assert "var.cur_source_bucket_arn" in normalizer_block, (
        "normalizer IAM policy ListBucket statement missing var.cur_source_bucket_arn"
    )

    # Check for GetObject and HeadObject statement
    assert "AllowCURSourceGet" in normalizer_block, (
        "normalizer IAM policy missing AllowCURSourceGet statement"
    )
    assert "s3:GetObject" in normalizer_block, (
        "normalizer IAM policy Get statement missing s3:GetObject action"
    )
    assert "s3:HeadObject" in normalizer_block, (
        "normalizer IAM policy Get statement missing s3:HeadObject action"
    )

    # Check scoping requirements: member accounts and export name prefixes
    assert "telemetry_member_account_ids" in normalizer_block, (
        "normalizer IAM policy Get statement must reference telemetry_member_account_ids for scoping"
    )
    assert "cur_export_name" in normalizer_block, (
        "normalizer IAM policy Get statement must reference cur_export_name for prefix scoping"
    )

    # Ensure no unconditional broad CUR read (it should be conditional on length of member accounts)
    # The member account scoping must loop and construct prefix-based resource lists,
    # and only fallback when length(var.telemetry_member_account_ids) == 0.
    assert "length(var.telemetry_member_account_ids) > 0" in normalizer_block, (
        "normalizer IAM policy Get statement must use dynamic scoping conditional on member accounts"
    )
    assert "cur_source_prefix" in normalizer_block, (
        "normalizer IAM policy Get statement must fallback using cur_source_prefix"
    )


def test_iam_boundary_cloudwatch_permissions():
    """Verify that the IAM boundary allows cloudwatch:GetMetricData but not broad cloudwatch:*"""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    iam_main_tf = os.path.join(base_dir, "modules/iam/main.tf")
    assert os.path.exists(iam_main_tf)
    
    with open(iam_main_tf, "r", encoding="utf-8") as f:
        content = f.read()

    boundary_block = get_block(content, r'data "aws_iam_policy_document" "boundary"\s*\{')
    assert boundary_block is not None

    assert "cloudwatch:GetMetricData" in boundary_block, "IAM boundary must allow cloudwatch:GetMetricData"
    assert "cloudwatch:*" not in boundary_block, "IAM boundary must NOT allow broad cloudwatch:*"
    
    cw_matches = re.findall(r'"cloudwatch:[^"]*"', boundary_block)
    for match in cw_matches:
        assert match == '"cloudwatch:GetMetricData"', f"IAM boundary contains disallowed action: {match}"


def test_cost_puller_identity_policy_cloudwatch():
    """Verify that the cost_puller identity policy contains AllowCloudWatchMetricData statement"""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    iam_main_tf = os.path.join(base_dir, "modules/iam/main.tf")
    assert os.path.exists(iam_main_tf)
    
    with open(iam_main_tf, "r", encoding="utf-8") as f:
        content = f.read()

    cost_puller_block = get_block(content, r'data "aws_iam_policy_document" "cost_puller"\s*\{')
    assert cost_puller_block is not None

    assert "AllowCloudWatchMetricData" in cost_puller_block, "cost_puller IAM policy missing AllowCloudWatchMetricData statement"
    assert "cloudwatch:GetMetricData" in cost_puller_block, "cost_puller IAM policy AllowCloudWatchMetricData missing cloudwatch:GetMetricData action"

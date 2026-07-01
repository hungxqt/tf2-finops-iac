import os

def test_cognito_oauth_flows():
    main_tf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../modules/dashboard/main.tf"))
    assert os.path.exists(main_tf_path)
    
    with open(main_tf_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Assert allowed_oauth_flows contains "code" but NOT "implicit"
    assert 'allowed_oauth_flows' in content
    flows_line = [line for line in content.splitlines() if 'allowed_oauth_flows' in line][0]
    assert 'code' in flows_line
    assert 'implicit' not in flows_line

def test_cognito_identity_pool_token_check():
    main_tf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../modules/dashboard/main.tf"))
    with open(main_tf_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Check identity pool token check is true
    assert "server_side_token_check" in content
    token_check_line = [line for line in content.splitlines() if 'server_side_token_check' in line][0]
    assert 'true' in token_check_line

def test_cloudfront_behaviors():
    main_tf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../modules/dashboard/main.tf"))
    outputs_tf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../modules/dashboard/outputs.tf"))
    
    with open(main_tf_path, "r", encoding="utf-8") as f:
        content = f.read()
    with open(outputs_tf_path, "r", encoding="utf-8") as f:
        outputs_content = f.read()
        
    # Assert aws_cloudfront_vpc_origin does not exist
    assert "resource \"aws_cloudfront_vpc_origin\" \"api\"" not in content
    assert "VpcOrigin-API" not in content
    
    # Assert edge_origin_sigv4 is not present in main.tf
    assert "resource \"aws_lambda_function\" \"edge_origin_sigv4\"" not in content
    assert "aws_lambda_function.edge_origin_sigv4.qualified_arn" not in content
    
    # Assert viewer request Lambda@Edge is associated
    assert "aws_lambda_function.edge_viewer_auth.qualified_arn" in content
    
    # Verify ordered cache behaviors for v1 do not exist
    assert "/v1/*" not in content
    
    # Verify viewer request Lambda@Edge auth still protects static/data behaviors
    assert "dashboard_data_prefix" in content
    
    # Assert VPC origin/origin signing outputs do not exist
    assert "edge_auth_origin_lambda_qualified_arn" not in outputs_content
    assert "vpc_origin_id" not in outputs_content
    assert "api_origin_id" not in outputs_content

def test_s3_replication_kms():
    main_tf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../modules/dashboard/main.tf"))
    with open(main_tf_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Assert that S3 replication configuration specifies source_selection_criteria and replica_kms_key_id
    assert "source_selection_criteria" in content
    assert "sse_kms_encrypted_objects" in content
    assert "replica_kms_key_id" in content

def test_dashboard_asset_force_destroy():
    main_tf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../modules/dashboard/main.tf"))
    with open(main_tf_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Assert force_destroy = var.destroyable in dashboard_assets
    assert "force_destroy" in content
    fd_lines = [line for line in content.splitlines() if 'force_destroy' in line]
    # Check that at least one of the force_destroy occurrences uses var.destroyable
    assert any('var.destroyable' in line for line in fd_lines)

def test_readme_unauthenticated_access():
    readme_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../modules/dashboard/README.md"))
    assert os.path.exists(readme_path)
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read().lower()
        
    # Assert README no longer claims unauthenticated shell access is the primary model
    assert "unauthenticated" not in content or "authenticated front door" in content

def test_edge_auth_handlers():
    viewer_auth_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../edge/dashboard_auth/viewer_auth.py"))
    origin_sigv4_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../edge/dashboard_auth/origin_sigv4.py"))
    
    assert os.path.exists(viewer_auth_path), "viewer_auth.py does not exist"
    assert os.path.exists(origin_sigv4_path), "origin_sigv4.py does not exist"
    
    with open(viewer_auth_path, "r", encoding="utf-8") as f:
        viewer_code = f.read()
    with open(origin_sigv4_path, "r", encoding="utf-8") as f:
        origin_code = f.read()
        
    assert "def handler(" in viewer_code
    assert "def handler(" in origin_code
    assert "urllib.request" in viewer_code
    assert "SigV4Auth" in origin_code

def test_cloudfront_logging_bucket_acl():
    main_tf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../modules/dashboard/main.tf"))
    with open(main_tf_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Assert resource "aws_s3_bucket" "cloudfront_logs" exists
    assert 'resource "aws_s3_bucket" "cloudfront_logs"' in content

    # Assert object_ownership = "BucketOwnerPreferred" exists for the CloudFront log bucket
    assert 'object_ownership = "BucketOwnerPreferred"' in content

    # Assert data "aws_cloudfront_log_delivery_canonical_user_id" and resource "aws_s3_bucket_acl" "cloudfront_logs" exist
    assert 'data "aws_cloudfront_log_delivery_canonical_user_id"' in content
    assert 'resource "aws_s3_bucket_acl" "cloudfront_logs"' in content

    # Assert CloudFront logging_config.bucket uses aws_s3_bucket.cloudfront_logs.bucket_domain_name
    assert 'aws_s3_bucket.cloudfront_logs.bucket_domain_name' in content


def test_ad_hoc_trigger_url_cors():
    main_tf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../modules/dashboard/main.tf"))
    with open(main_tf_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the aws_lambda_function_url "ad_hoc_trigger_url" block and assert OPTIONS is not in its allow_methods
    assert "aws_lambda_function_url" in content
    assert "ad_hoc_trigger_url" in content

    import re
    match = re.search(r'resource\s+"aws_lambda_function_url"\s+"ad_hoc_trigger_url"\s+\{(.*?)\}', content, re.DOTALL)
    assert match is not None, "Could not find aws_lambda_function_url ad_hoc_trigger_url resource block"
    block_content = match.group(1)

    assert "cors" in block_content
    allow_methods_lines = [line for line in block_content.splitlines() if "allow_methods" in line]
    assert len(allow_methods_lines) > 0, "Could not find allow_methods inside ad_hoc_trigger_url resource block"

    for line in allow_methods_lines:
        assert "OPTIONS" not in line, "OPTIONS should not be in allow_methods of Function URL CORS configuration"



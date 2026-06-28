import os

def get_module_main_tf():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../modules/ai-runtime-lambda/main.tf"))
    assert os.path.exists(path), f"Module main.tf not found at {path}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def get_sandbox_main_tf():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../environments/sandbox/main.tf"))
    assert os.path.exists(path), f"Sandbox main.tf not found at {path}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def test_codedeploy_app_and_group_exist():
    content = get_module_main_tf()
    # Check aws_codedeploy_app exists with Lambda compute platform
    assert "resource \"aws_codedeploy_app\" \"request\"" in content
    assert "compute_platform = \"Lambda\"" in content

    # Check aws_codedeploy_deployment_group exists
    assert "resource \"aws_codedeploy_deployment_group\" \"request\"" in content
    assert "deployment_config_name = var.codedeploy_deployment_config_name" in content

def test_codedeploy_role_exists():
    content = get_module_main_tf()
    assert "resource \"aws_iam_role\" \"codedeploy\"" in content
    assert "service-role/AWSCodeDeployRoleForLambda" in content

def test_deployment_config_linear():
    sandbox_content = get_sandbox_main_tf()
    # Sandbox should wire CodeDeployDefault.LambdaLinear10PercentEvery1Minute
    assert "codedeploy_deployment_config_name = \"CodeDeployDefault.LambdaLinear10PercentEvery1Minute\"" in sandbox_content

def test_rollback_alarms_and_auto_rollback():
    content = get_module_main_tf()
    
    # Check for the auto rollback config
    assert "auto_rollback_configuration {" in content
    assert '"DEPLOYMENT_FAILURE"' in content
    assert '"ALARM_TO_REVERT"' in content

    # Verify alarms are declared
    assert "aws_cloudwatch_metric_alarm\" \"request_errors\"" in content
    assert "aws_cloudwatch_metric_alarm\" \"request_throttles\"" in content
    assert "aws_cloudwatch_metric_alarm\" \"request_p99_duration\"" in content
    assert "aws_cloudwatch_metric_alarm\" \"alb_target_5xx\"" in content

    # Verify alarms are linked to the deployment group
    assert "aws_cloudwatch_metric_alarm.request_errors[0].alarm_name" in content
    assert "aws_cloudwatch_metric_alarm.request_throttles[0].alarm_name" in content
    assert "aws_cloudwatch_metric_alarm.request_p99_duration[0].alarm_name" in content
    assert "aws_cloudwatch_metric_alarm.alb_target_5xx[0].alarm_name" in content

def test_live_alias_ignores_drift():
    content = get_module_main_tf()
    
    # Locate request alias configuration
    assert "resource \"aws_lambda_alias\" \"request\"" in content
    # Find ignore_changes block for the alias
    assert "ignore_changes = [" in content
    assert "function_version" in content
    assert "routing_config" in content

def test_sandbox_wires_codedeploy():
    sandbox_content = get_sandbox_main_tf()
    
    # Ensure sandbox main.tf instantiates ai_runtime_lambda with correct parameters
    assert "module \"ai_runtime_lambda\"" in sandbox_content
    assert "enable_codedeploy                 = true" in sandbox_content
    assert "codedeploy_alarm_actions          = [module.alerting.engineering_topic_arn]" in sandbox_content

def test_no_one_off_deployments_in_tf():
    module_content = get_module_main_tf()
    sandbox_content = get_sandbox_main_tf()
    
    # Ensure no aws_codedeploy_deployment resource, null_resource, or local-exec is added for one-offs
    assert "resource \"aws_codedeploy_deployment\"" not in module_content
    assert "resource \"aws_codedeploy_deployment\"" not in sandbox_content
    assert "local-exec" not in module_content
    assert "local-exec" not in sandbox_content


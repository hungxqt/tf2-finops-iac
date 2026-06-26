import json
import os
import re
import importlib

def test_step_function_lambda_coverage():
    # Define directories
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    asl_path = os.path.join(base_dir, "modules/orchestration/statemachine.json")
    main_tf_path = os.path.join(base_dir, "modules/orchestration/main.tf")
    compute_lambda_tf = os.path.join(base_dir, "modules/compute-lambda/main.tf")
    package_script_path = os.path.join(base_dir, "scripts/package-lambdas.ps1")
    workers_dir = os.path.join(base_dir, "lambda_src/src/workers")
    
    # 6 source-owned workers
    expected_source_workers = ["state", "cost_puller", "normalizer", "router", "audit_writer", "containment_worker", "vpc_alb_caller"]
    
    # 1. Assert required files exist
    assert os.path.exists(asl_path), "statemachine.json file does not exist"
    assert os.path.exists(main_tf_path), "orchestration main.tf does not exist"
    assert os.path.exists(compute_lambda_tf), "compute-lambda main.tf does not exist"
    assert os.path.exists(package_script_path), "package-lambdas.ps1 does not exist"
    assert os.path.exists(workers_dir), "workers directory does not exist"

    # 2. Extract and assert Lambda placeholders in statemachine.json
    with open(asl_path, "r", encoding="utf-8") as f:
        asl_content = f.read()
    
    # Find all placeholders like ${state_lambda_arn} or ${cost_puller_lambda_arn}
    placeholders = re.findall(r'\$\{([a-zA-Z0-9_]+_lambda_arn)\}', asl_content)
    unique_placeholders = sorted(list(set(placeholders)))
    
    expected_placeholders = [
        "state_lambda_arn",
        "cost_puller_lambda_arn",
        "normalizer_lambda_arn",
        "router_lambda_arn",
        "audit_writer_lambda_arn",
        "containment_worker_lambda_arn",
        "vpc_alb_caller_lambda_arn"
    ]
    
    for p in expected_placeholders:
        assert p in unique_placeholders, f"Missing placeholder in ASL: {p}"
    
    # 3. Assert all expected source workers have directories and valid handlers
    for worker in expected_source_workers:
        worker_path = os.path.join(workers_dir, worker)
        assert os.path.isdir(worker_path), f"Directory for worker '{worker}' does not exist"
        
        # Test handle_request import
        module_name = f"workers.{worker}.handler"
        try:
            module = importlib.import_module(module_name)
            assert hasattr(module, "handle_request"), f"Module '{module_name}' missing 'handle_request'"
            assert callable(getattr(module, "handle_request")), f"handle_request in '{module_name}' is not callable"
        except ImportError as e:
            assert False, f"Could not import {module_name}: {e}"

    # 4. Parse compute-lambda/main.tf and assert workers match exactly
    with open(compute_lambda_tf, "r", encoding="utf-8") as f:
        compute_content = f.read()
    
    # Find workers list: workers            = ["state", "cost_puller", ...]
    match = re.search(r'workers\s*=\s*\[(.*?)\]', compute_content, re.DOTALL)
    assert match, "Could not find workers list in compute-lambda/main.tf"
    workers_str = match.group(1)
    # Extract string values within quotes
    compute_workers = sorted([w.strip().strip('"').strip("'") for w in re.findall(r'["\'](.*?)["\']', workers_str)])
    assert compute_workers == sorted(expected_source_workers), f"compute-lambda workers list {compute_workers} does not match {expected_source_workers}"

    # 5. Parse package-lambdas.ps1 and assert workers match exactly
    with open(package_script_path, "r", encoding="utf-8") as f:
        package_content = f.read()
        
    match_ps = re.search(r'\$Workers\s*=\s*@\((.*?)\)', package_content, re.IGNORECASE)
    assert match_ps, "Could not find $Workers array in package-lambdas.ps1"
    ps_workers_str = match_ps.group(1)
    ps_workers = sorted([w.strip().strip('"').strip("'") for w in re.findall(r'["\'](.*?)["\']', ps_workers_str)])
    assert ps_workers == sorted(expected_source_workers), f"package-lambdas.ps1 workers list {ps_workers} does not match {expected_source_workers}"
    
    # 6. Assert modules/orchestration/main.tf template parameters map all placeholders
    with open(main_tf_path, "r", encoding="utf-8") as f:
        main_tf_content = f.read()
        
    for p in expected_placeholders:
        assert p in main_tf_content, f"orchestration/main.tf does not map placeholder: {p}"

    assert re.search(r'RUN_STATE_TABLE_NAME\s*=\s*lookup\(var\.dynamodb_table_names,\s*"run_state",\s*""\)', compute_content), "state worker missing RUN_STATE_TABLE_NAME env wiring"
    assert re.search(r'ERROR_BUDGET_TABLE_NAME\s*=\s*lookup\(var\.dynamodb_table_names,\s*"error_budget",\s*""\)', compute_content), "state worker missing ERROR_BUDGET_TABLE_NAME env wiring"
    assert 'finops-idempotency-${var.environment}' in main_tf_content, "orchestration run-state table must use finops-idempotency-{env} name"
    assert 'attribute_name = "ttl_expiry"' in main_tf_content, "orchestration idempotency table must enable ttl_expiry"

    # 7. Assert all environment main.tf files configure lambda_function_arns correctly
    environments = ["sandbox", "staging", "prod"]
    for env in environments:
        env_main_tf = os.path.join(base_dir, f"environments/{env}/main.tf")
        assert os.path.exists(env_main_tf), f"main.tf for environment '{env}' does not exist"
        
        with open(env_main_tf, "r", encoding="utf-8") as f:
            env_content = f.read()
            
        # Ensure orchestration module is defined and passes lambda_function_arns mapping compute lambda directly without merge or direct ai_request
        assert 'module "orchestration"' in env_content, f"orchestration module missing in environments/{env}/main.tf"
        assert 'lambda_function_arns         = module.compute_lambda.lambda_alias_arns' in env_content, f"lambda_function_arns mapping missing in environments/{env}/main.tf"
        assert 'lambda_function_arns = merge(' not in env_content, f"lambda_function_arns merge block should be removed in environments/{env}/main.tf"
        assert 'ai_request = module.ai_runtime_lambda.request_lambda_alias_arn' not in env_content, f"direct ai_request mapping should be removed in environments/{env}/main.tf"

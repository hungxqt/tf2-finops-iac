import os
import re

def test_scheduler_enabled_variable_and_state():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    orchestration_vars_tf = os.path.join(base_dir, "modules/orchestration/variables.tf")
    orchestration_main_tf = os.path.join(base_dir, "modules/orchestration/main.tf")
    orchestration_outputs_tf = os.path.join(base_dir, "modules/orchestration/outputs.tf")

    # 1. Assert modules/orchestration/variables.tf defines scheduler_enabled variable with default = false
    assert os.path.exists(orchestration_vars_tf), "orchestration variables.tf does not exist"
    with open(orchestration_vars_tf, "r", encoding="utf-8") as f:
        vars_content = f.read()
    
    assert "variable \"scheduler_enabled\"" in vars_content, "variable 'scheduler_enabled' not declared in modules/orchestration/variables.tf"
    # Ensure default is false
    default_match = re.search(r'variable\s+"scheduler_enabled"\s+\{.*?default\s*=\s*false', vars_content, re.DOTALL)
    assert default_match, "variable 'scheduler_enabled' must have default = false in modules/orchestration/variables.tf"

    # 2. Assert modules/orchestration/main.tf sets scheduler state from scheduler_enabled
    assert os.path.exists(orchestration_main_tf), "orchestration main.tf does not exist"
    with open(orchestration_main_tf, "r", encoding="utf-8") as f:
        main_content = f.read()

    state_match = re.search(r'resource\s+"aws_scheduler_schedule"\s+"run_workflow"\s+\{.*?state\s*=\s*var\.scheduler_enabled\s*\?\s*"ENABLED"\s*:\s*"DISABLED"', main_content, re.DOTALL)
    assert state_match, "aws_scheduler_schedule.run_workflow state must be set using var.scheduler_enabled ? 'ENABLED' : 'DISABLED'"

    # 3. Assert modules/orchestration/outputs.tf defines scheduler_state output
    assert os.path.exists(orchestration_outputs_tf), "orchestration outputs.tf does not exist"
    with open(orchestration_outputs_tf, "r", encoding="utf-8") as f:
        outputs_content = f.read()
    
    assert "output \"scheduler_state\"" in outputs_content, "output 'scheduler_state' not declared in modules/orchestration/outputs.tf"
    value_match = re.search(r'output\s+"scheduler_state"\s+\{.*?value\s*=\s*aws_scheduler_schedule\.run_workflow\.state', outputs_content, re.DOTALL)
    assert value_match, "output 'scheduler_state' must output aws_scheduler_schedule.run_workflow.state"


def test_environments_pass_scheduler_enabled():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    environments = ["sandbox", "staging", "prod"]

    for env in environments:
        env_dir = os.path.join(base_dir, f"environments/{env}")
        main_tf = os.path.join(env_dir, "main.tf")
        variables_tf = os.path.join(env_dir, "variables.tf")
        outputs_tf = os.path.join(env_dir, "outputs.tf")
        tfvars_example = os.path.join(env_dir, "terraform.tfvars.example")

        # Assert environment files exist
        assert os.path.exists(main_tf), f"{env}/main.tf does not exist"
        assert os.path.exists(variables_tf), f"{env}/variables.tf does not exist"
        assert os.path.exists(outputs_tf), f"{env}/outputs.tf does not exist"
        assert os.path.exists(tfvars_example), f"{env}/terraform.tfvars.example does not exist"

        # 1. Assert variables.tf defines scheduler_enabled variable with default = false
        with open(variables_tf, "r", encoding="utf-8") as f:
            vars_content = f.read()
        assert "variable \"scheduler_enabled\"" in vars_content, f"variable 'scheduler_enabled' not declared in {env}/variables.tf"
        default_match = re.search(r'variable\s+"scheduler_enabled"\s+\{.*?default\s*=\s*false', vars_content, re.DOTALL)
        assert default_match, f"variable 'scheduler_enabled' must have default = false in {env}/variables.tf"

        # 2. Assert main.tf passes scheduler_enabled to module.orchestration
        with open(main_tf, "r", encoding="utf-8") as f:
            main_content = f.read()
        
        # Look inside module "orchestration" block
        orch_block_match = re.search(r'module\s+"orchestration"\s+\{(.*?)\}', main_content, re.DOTALL)
        assert orch_block_match, f"module 'orchestration' block not found in {env}/main.tf"
        orch_block = orch_block_match.group(1)
        assert re.search(r'scheduler_enabled\s*=\s*var\.scheduler_enabled', orch_block), f"scheduler_enabled is not passed to module.orchestration in {env}/main.tf"

        # 3. Assert outputs.tf outputs scheduler_state from module.orchestration
        with open(outputs_tf, "r", encoding="utf-8") as f:
            outputs_content = f.read()
        assert "output \"scheduler_state\"" in outputs_content, f"output 'scheduler_state' not declared in {env}/outputs.tf"
        value_match = re.search(r'output\s+"scheduler_state"\s+\{.*?value\s*=\s*module\.orchestration\.scheduler_state', outputs_content, re.DOTALL)
        assert value_match, f"output 'scheduler_state' must output module.orchestration.scheduler_state in {env}/outputs.tf"

        # 4. Assert terraform.tfvars.example sets scheduler_enabled = false
        with open(tfvars_example, "r", encoding="utf-8") as f:
            tfvars_content = f.read()
        assert re.search(r'scheduler_enabled\s*=\s*false', tfvars_content), f"scheduler_enabled = false not found in {env}/terraform.tfvars.example"


def test_no_automatic_execution_trigger():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    
    # We want to scan files to ensure states:start-execution is not invoked automatically.
    # Exclude .md files (guides and demo packs can discuss manual CLI commands) and .py tests.
    extensions_to_check = [".tf", ".yml", ".yaml", ".sh", ".ps1"]
    
    for root, _, files in os.walk(base_dir):
        # Exclude directories like .git, .pytest_cache, .build, .terraform
        if any(ignored in root for ignored in [".git", ".pytest_cache", ".build", ".terraform"]):
            continue
            
        for file in files:
            _, ext = os.path.splitext(file)
            if ext in extensions_to_check:
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                
                # Check for direct calls to stepfunctions start-execution in scripts/worklfows
                if "start-execution" in content.lower():
                    # Allow states:StartExecution inside modules/orchestration/iam.tf (IAM permission)
                    if "modules/orchestration/iam.tf" in file_path.replace("\\", "/"):
                        continue
                    
                    # If found anywhere else, assert it's not invoking it automatically
                    assert False, f"Potential automatic start-execution call found in non-documentation file: {file_path}"

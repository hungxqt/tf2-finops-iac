# Manual Step Functions Execution Runbook

This runbook provides the operator procedure for manually starting, monitoring, and validating the execution of the Orchestrator Step Functions workflow for **Task Force 2 - FinOps Watch**.

---

## 1. Prerequisites

Before triggering a manual run, ensure the following requirements are met:

1. **Deployed Environment**: The target environment (e.g., `sandbox`, `staging`, or `prod`) must be fully deployed using Terraform.
2. **AWS CLI Access**: The operator's shell must be authenticated to the correct AWS account with permissions for:
   * `states:StartExecution`
   * `states:DescribeExecution`
   * `states:GetExecutionHistory`
   * `states:ListStateMachines`
3. **Scheduler Disabled / Enabled**: A manual execution can be run regardless of whether the EventBridge scheduler is active (`scheduler_enabled = true` or `false`).
4. **Active Lambda Workers**: Hyperplane ENIs and container image optimizations must be fully provisioned and in the `ACTIVE` state (refer to Step 2.8 in [GUIDES.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES.md)).
5. **Seeded Account Policies**: Every AWS Account ID targeted for analysis must have a seeded row in the environment's `account-policy` DynamoDB table. If a target is unseeded, the execution loop will fail. Refer to [ACCOUNT_POLICY_SEEDING.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/ACCOUNT_POLICY_SEEDING.md) for seeding procedures.
6. **Telemetry Availability**: Valid telemetry inputs (Cost and Usage Reports in S3, CloudWatch metric logs, or Cost Explorer API access) must be available for the target cost period.

---

## 2. Resolving the State Machine ARN

To start the execution, you need the ARN of the target State Machine. You can retrieve this using either of the following methods:

### Method A: Terraform Output (Recommended)
Navigate to the directory of the target environment and query the output:
```powershell
# For sandbox
terraform -chdir=environments/sandbox output -raw state_machine_arn

# For staging
terraform -chdir=environments/staging output -raw state_machine_arn

# For prod
terraform -chdir=environments/prod output -raw state_machine_arn
```

### Method B: AWS CLI Name Lookup Fallback
If Terraform outputs are not locally available, query the ARN using the state machine's physical naming convention (`tf2-finops-<env>-workflow`):
```powershell
# Replace <env> with sandbox, staging, or prod
$EnvName = "sandbox"
$StateMachineArn = aws stepfunctions list-state-machines `
  --query "stateMachines[?name=='tf2-finops-$EnvName-workflow'].stateMachineArn" `
  --output text
```

---

## 3. PowerShell Manual Execution Flow

Follow this PowerShell command sequence to manually trigger and track the workflow.

### Step 3.1: Define Variables
Specify the execution parameters:
```powershell
$AwsRegion       = "ap-southeast-1"         # Target deployment region
$EnvName         = "sandbox"                # sandbox, staging, or prod
$ProjectName     = "tf2-finops"
$StateMachineArn = "arn:aws:states:$AwsRegion:123456789012:stateMachine:$ProjectName-$EnvName-workflow" # Update Account ID
```

### Step 3.2: Prepare the Execution Input File
Create a temporary JSON input file locally. Choose one of the following execution modes:

#### Option 1: Single-Account Ad Hoc Manual Run
Use this payload to analyze a single target account:
```powershell
$InputJson = @'
{
  "account_id": "444444444444",
  "is_ad_hoc": true
}
'@
$InputJson | Set-Content -Path .\manual_input.json -Encoding utf8
```

#### Option 2: Multi-Account Scheduled Run Emulation
Use this payload to analyze multiple linked member accounts managed by a central account:
```powershell
$InputJson = @'
{
  "management_account_id": "111111111111",
  "analysis_targets": ["222222222222", "333333333333"],
  "trigger_type": "scheduled",
  "is_ad_hoc": false
}
'@
$InputJson | Set-Content -Path .\manual_input.json -Encoding utf8
```

### Step 3.3: Trigger Execution
Start the state machine execution using the JSON input file:
```powershell
$ExecutionArn = aws stepfunctions start-execution `
  --state-machine-arn $StateMachineArn `
  --input file://manual_input.json `
  --query "executionArn" `
  --output text `
  --region $AwsRegion

Write-Host "Started State Machine execution: $ExecutionArn"
```

### Step 3.4: Monitor Execution Status
Retrieve the execution state and details:
```powershell
aws stepfunctions describe-execution `
  --execution-arn $ExecutionArn `
  --region $AwsRegion
```
Look for the `"status"` field in the JSON response (e.g., `RUNNING`, `SUCCEEDED`, `FAILED`, `TIMED_OUT`, `ABORTED`).

### Step 3.5: Query Execution Logs and History
To troubleshoot failures or track transitions, view the top events in the execution history:
```powershell
aws stepfunctions get-execution-history `
  --execution-arn $ExecutionArn `
  --region $AwsRegion `
  --max-items 15 `
  --reverse-order
```
*Note: Clean up the local temporary payload file when finished:*
```powershell
Remove-Item -Path .\manual_input.json -ErrorAction SilentlyContinue
```

---

## 4. Key Constraints & Safety Guardrails

### `force_dry_run` Manual Input Limitation
> [!WARNING]
> Do **NOT** attempt to pass `"force_dry_run": true` (or `false`) within the execution input JSON as a manual override.
>
> The `PrepareRunContext` lambda (`op == "prepare"`) initializes the workflow state and **hardcodes/resets `force_dry_run` to `False`** at the start of execution. Any manually supplied `force_dry_run` value in the input is completely ignored and overwritten.

### Active Safety Mechanisms
Because the operator cannot force a dry-run state via manual execution input, safety relies on the downstream platform guardrails:
1. **DynamoDB Account Policy**: The account's target environment seeding defines the allowed boundaries.
2. **Telemetry Quality Gates**: If telemetry data is detected as stale (delayed > 26 hours), estimated, or incomplete, the workflow automatically degrades execution to dry-run / alert-only containment and writes audit evidence.
3. **Error Budget Locks**: The `check_error_budget` step queries the error budget database. If the error budget is locked due to high alert volumes, a rollback loop, or sandbox thresholds, it will dynamically overwrite `force_dry_run = true` for the containment stage.
4. **Containment Worker Guardrails**: The containment Lambda function evaluates least-privilege AWS policies and checks environment safety flags before executing actual resource teardowns.

# Account Policy DynamoDB Seeding Guide

This guide describes the operator procedure for seeding the `account-policy` DynamoDB table before manually running or enabling the scheduled Orchestrator Step Functions workflow for **Task Force 2 - FinOps Watch**.

---

## 1. Overview

The `LoadAccountPolicy` step in the Step Functions orchestrator retrieves mapping context from DynamoDB using the executing AWS Account ID as the primary key. If this table is unseeded, or if the account ID does not match, the workflow will fail.

### Item Schema
The table expects items conforming to the following JSON schema format:

```json
{
  "account_id": { "S": "123456789012" },
  "environment": { "S": "sandbox" }
}
```

* **`account_id`** (String, Partition Key): The 12-digit AWS Account ID.
* **`environment`** (String): The deployment environment name (e.g., `sandbox`, `staging`, `prod`).

---

## 2. PowerShell AWS CLI Seeding Workflow

Run the following PowerShell sequence to seed or verify the DynamoDB policy table.

### Step 2.1: Define Variables
Set the target parameters for your deployment context:
```powershell
$ProjectName = "tf2-finops"
$EnvName     = "sandbox"               # Target: sandbox, staging, or prod
$AwsRegion   = "ap-southeast-1"        # Change as per target region
$AccountId   = "123456789012"          # Replace with your actual 12-digit AWS Account ID
$TableName   = "$ProjectName-$EnvName-account-policy"
```

### Step 2.2: Confirm Table Existence
Verify that the DynamoDB table exists and is accessible:
```powershell
aws dynamodb describe-table --table-name $TableName --region $AwsRegion
```

### Step 2.3: Seed the Row (Idempotent Insertion)
Insert the item only if the `account_id` does not already exist:
```powershell
aws dynamodb put-item `
  --table-name $TableName `
  --item '{
    "account_id": {"S": "'$AccountId'"},
    "environment": {"S": "'$EnvName'"}
  }' `
  --condition-expression "attribute_not_exists(account_id)" `
  --region $AwsRegion
```

### Step 2.4: Verify the Seeded Row
Read back the item using a consistent read to guarantee visibility:
```powershell
aws dynamodb get-item `
  --table-name $TableName `
  --key '{"account_id": {"S": "'$AccountId'"}}' `
  --consistent-read `
  --region $AwsRegion
```

### Step 2.5: Correcting/Updating an Existing Row
If you need to update the mapping for an existing account ID, run an explicit update command:
```powershell
aws dynamodb update-item `
  --table-name $TableName `
  --key '{"account_id": {"S": "'$AccountId'"}}' `
  --update-expression "SET #env = :val" `
  --expression-attribute-names '{"#env": "environment"}' `
  --expression-attribute-values '{":val": {"S": "'$EnvName'"}}' `
  --region $AwsRegion
```

---

## 3. Troubleshooting & Operator Notes

### JSONPath Extraction Failures
If `get-item` returns an empty response (i.e., no item found matching the executing account ID), the Orchestrator Step Functions execution will fail at `LoadAccountPolicy` with the following error:
> `The JSONPath $.Item.account_id.S could not be found in the input`

This occurs because the `ResultSelector` block relies on these exact fields to extract execution context.

### Account ID Matching
* **Manual Executions**: If you trigger the Step Functions state machine manually, ensure that the execution input contains the seeded `"account_id"` value.
* **Scheduled Executions**: The EventBridge Scheduler triggers the state machine using input containing the deploying/current AWS account ID. The seeded row's primary key must match this value exactly.

### Guardrails
* **`scheduler_enabled`**: Keep `scheduler_enabled = false` in your Terraform configurations until the DynamoDB row has been successfully seeded and verified via consistent read. This prevents scheduled runs from launching in a misconfigured state.

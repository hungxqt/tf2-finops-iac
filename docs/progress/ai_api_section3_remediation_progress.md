# AI API Section 3 Blocker Remediation Progress

**Date**: 2026-06-27  
**Scope**: Section 3 Blocker Remediation (Blockers 1, 2, 4, 5, and 6)

---

## Status: FULLY COMPLIANT

All targeted Section 3 blockers have been remediated across CDO infrastructure, Terraform configuration, Lambda workers, and test suites.

### What Was Implemented

#### 1. Blocker 1: Error-Budget Lock Wiring
- **Status**: COMPLETE
- **Terraform**: Passed `ERROR_BUDGET_TABLE_NAME` env var to the `state` worker via `modules/compute-lambda/main.tf` by looking up the `error_budget` key in `var.dynamodb_table_names`.
- **Lambda**: Updated `lambda_src/src/workers/state/handler.py` to read the real DynamoDB error-budget table.
- **Contract Thresholds**: Implemented strict threshold checks per contract §3.3:
  - `prod` / `prod-*` environments: Lock if 30-day rollback rate $\ge 1\%$.
  - `staging` environment: Lock if 30-day rollback rate $\ge 10\%$.
  - `sandbox` / `dev` environments: Automatic lock disabled.
- **Response Fields**: The handler now returns all required fields: `locked`, `force_dry_run`, `containment_status`, `rollback_rate_30d_pct`, and `lock_threshold_pct`.
- **Tests**: Added tests covering DDB lookup, env threshold locks, and dry-run propagation in `lambda_src/tests/test_state.py`.

#### 2. Blocker 2: Tenant Rate Limit (WAF CUSTOM_KEYS)
- **Status**: COMPLETE
- **WAF Rule 1**: Added `BlockMissingTenantId` (Priority 1) to block any request starting with `/v1/` that does not carry a non-empty `X-Tenant-Id` header.
- **WAF Rule 2**: Added `TenantRateLimit` (Priority 2) utilizing WAF custom keys (`aggregate_key_type = "CUSTOM_KEYS"`) to rate-limit requests to `/v1/` paths on `x-tenant-id` header values (limit: 100 requests per 60 seconds).
- **Secondary Control**: Kept standard IP-abuse rule disabled or secondary.
- **Tests**: Added static tests in `test_vpc_alb_caller.py` verifying CUSTOM_KEYS, evaluation window, limits, and blocking missing headers.

#### 3. Blocker 4: Cross-Account STS Tenant Binding
- **Status**: COMPLETE
- **Lambda**: Updated `cost_puller` to retrieve `TELEMETRY_MEMBER_ROLE_NAME` from environment variables, and passed `ExternalId=tenant_id`, session `Tags=[{Key="tenant_id", Value=tenant_id}]`, and `TransitiveTagKeys=["tenant_id"]` to `sts:AssumeRole`.
- **IAM Policy**: Updated boundary policy and `cost_puller` role policies to allow `sts:TagSession` in addition to `sts:AssumeRole`.
- **Trust Policy**: Hardened the member telemetry role trust policy to require both `sts:ExternalId` and `aws:RequestTag/tenant_id` equals the trusted tenant ID value (using a new variable `trusted_tenant_ids` inside `modules/iam`).
- **Tests**: Added tests in `test_cost_puller.py` verifying ExternalId, session tags, and role name override.

#### 4. Blocker 5: Idempotency Cache Attribute Alignment
- **Status**: COMPLETE
- **Lambda**: Updated `vpc_alb_caller` handler to write responses to the `response_body` DynamoDB attribute instead of `response_cache`.
- **Backward Compatibility**: Implemented a fallback read that checks `response_body` first and falls back to legacy `response_cache` for existing 24-hour TTL records.
- **Tests**: Added tests verifying writing `response_body`, reading `response_body`, and legacy `response_cache` reading fallback.

#### 5. Blocker 6: S3 Pointer Read Access
- **Status**: COMPLETE
- **Terraform Inputs**: Added inputs `ai_request_s3_pointer_bucket_arn` (default `""`) and `ai_request_s3_pointer_prefixes` (default `["ai-input/*"]`) to `modules/ai-runtime-lambda`.
- **IAM Access**: Granted the AI Request Lambda role `s3:ListBucket` with prefix condition and `s3:GetObject` on configured prefixes of the bucket.
- **Environment Wiring**: Configured `sandbox`, `staging`, and `prod` environments to pass `module.lakehouse.lakehouse_bucket_arn` to the module.
- **Tests**: Added static tests to verify that the Request Lambda IAM role receives scoped S3 read privileges on the configured lakehouse bucket.

---

## Verification Results

- **Python Tests**: All 150 python unit/integration tests passed successfully:
  ```powershell
  python -m pytest lambda_src/
  # Result: 150 passed in 0.60s
  ```
- **Terraform Validation**:
  - sandbox: Configuration is valid.
  - staging: Configuration is valid.
  - prod: Configuration is valid.
- **Terraform Format**: Checked and formatted successfully recursively.
- **Trivy / Security Scans**: Verified zero high/critical vulnerabilities introduced.

---

## Rollback Plan

Rollback is safe and non-destructive:
1. Revert edits to `lambda_src/src/workers/state/handler.py`, `lambda_src/src/workers/vpc_alb_caller/handler.py`, and `lambda_src/src/workers/cost_puller/handler.py`.
2. Revert Terraform changes in `modules/ai-runtime-lambda/`, `modules/compute-lambda/`, `modules/iam/`, and `environments/`.
3. Existing idempotency tables will continue to be read using `response_cache`. No database migrations are required.

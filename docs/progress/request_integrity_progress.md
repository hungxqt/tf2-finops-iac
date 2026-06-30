# Request Integrity Progress

**Date**: 2026-06-27  
**Scope**: Section-3 request integrity blockers - IAM permissions, header enforcement, and deployment gate

---

## Status: PARTIALLY COMPLIANT - Deployment Gate Required

### What Was Implemented (CDO/Terraform-Owned)

#### 1. IAM: vpc_alb_caller Dedicated Idempotency Policy
- **Status**: COMPLETE
- **Change**: Added `aws_iam_role_policy.vpc_alb_caller_idempotency` to `modules/iam/main.tf`
- **Scope**: Least-privilege - grants only `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem` on the `ai_payload_idempotency` table ARN specifically (not a wildcard)
- **Variable**: `ai_payload_idempotency_table_arn` added to `modules/iam/variables.tf`
- **Wiring**: All three environments (sandbox, staging, prod) pass `module.orchestration.dynamodb_table_arns["ai_payload_idempotency"]` to the new variable
- **Dependency**: `lambda_role_arns` output `depends_on` includes `aws_iam_role_policy.vpc_alb_caller_idempotency`

#### 2. vpc_alb_caller: SigV4 Fail-Closed for AI Payload Paths
- **Status**: COMPLETE
- **Change**: `lambda_src/src/workers/vpc_alb_caller/handler.py` now raises `ConfigMissingError` when AWS credentials are absent AND the path is in `AI_PAYLOAD_PATHS` (`/v1/detect`, `/v1/decide`, `/v1/verify`) AND `ALLOW_UNSIGNED_AI_REQUESTS != "true"`
- **Safe default**: `ALLOW_UNSIGNED_AI_REQUESTS` defaults to `"false"`. Only unit tests set it to `"true"`. Terraform environment variables MUST NOT set this to `"true"` in any deployed environment.
- **Health exemption**: `/health` path is always allowed without credentials.

#### 3. Request Integrity Headers (X-Payload-SHA256, X-Request-Timestamp, Authorization)
- **Status**: COMPLETE (header construction already existed; tests now formally enforce it)
- **Coverage**: `X-Request-Timestamp` (RFC3339 UTC), `X-Payload-SHA256` (hex SHA256 of exact outbound bytes), `Authorization` (AWS4-HMAC-SHA256 SigV4) are all sent for non-`/health` AI paths when credentials are available

#### 4. Unit Tests
- **Status**: COMPLETE
- **New test groups added to `test_vpc_alb_caller.py`**:
  - `TestRequestIntegrityHeaders`: timestamp RFC3339 format, payload hash matches wire bytes, Authorization present and uses AWS4-HMAC-SHA256
  - `TestCredentialFailClosed`: detect/decide/verify fail-closed, health allowed, ALLOW_UNSIGNED override works
  - `TestStaticIAMPolicyDefinition`: 6 static Terraform checks covering policy resource, actions, resource scope, outputs.tf depends_on, variables.tf declaration, and all 3 environment wirings

#### 5. Deployment Gate Script
- **Status**: COMPLETE
- **Script**: `scripts/test-ai-request-integrity.ps1`
- **Probes**: Positive signed /v1/detect, replay stale timestamp, missing auth, hash mismatch
- **Behavior**: Exits 1 and writes results JSON if any probe fails; blocks image promotion

#### 6. Documentation
- **Status**: COMPLETE
- `docs/GUIDES.md` Section 11: When to run, how to run, probe table, non-compliance handling
- `docs/GUIDES_vi.md` Section 11: Vietnamese translation in sync

---

## Known Limitation: ALB Does Not Enforce SigV4 at Listener Level

**Limitation**: The private internal HTTPS ALB (port 443) does not natively enforce AWS SigV4 authentication at the ALB listener level. The ALB forwards all requests to the Lambda target group without checking the `Authorization` header.

**Impact**: SigV4 correctness is enforced by the AI Request Lambda/container, not the ALB itself. This means:
- A request with a forged or missing `Authorization` header will reach the AI Lambda
- The AI Lambda must validate `Authorization`, `X-Request-Timestamp`, and `X-Payload-SHA256` and return 400/401 contract errors
- The deployment gate (`scripts/test-ai-request-integrity.ps1`) verifies this enforcement via negative probes

**Remediation Status**: The CDO-owned infrastructure (vpc_alb_caller + Terraform IAM) correctly sends all required headers. The enforcement obligation for replay/auth/hash validation at the `/v1/*` contract boundary rests with the AIOps-provided AI Engine container image. The deployment gate blocks promotion if the AI Engine image does not pass the negative probes.

**Capstone Exception**: For the capstone demo, if the AIOps AI Engine image does not implement full replay/auth/hash enforcement, record this as a RUNTIME_NON_COMPLIANT exception and document it explicitly. Do not claim section-3 compliance in this case.

---

## Rollback Notes

Rollback is safe and non-destructive:
- Revert `modules/iam/main.tf`, `modules/iam/variables.tf`, `modules/iam/outputs.tf` changes
- Revert the three environment `main.tf` IAM wiring lines
- Revert `lambda_src/src/workers/vpc_alb_caller/handler.py` credential check block
- No state migration or resource replacement is required (the new IAM policy is additive)

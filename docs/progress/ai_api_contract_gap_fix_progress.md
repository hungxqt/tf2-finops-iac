# AI API Contract Gap Fix — Progress Log

**Date**: 2026-06-27  
**Session**: AI API Contract Gap Fix Plan

## Changes Implemented

### 1. `lambda_src/src/workers/containment_worker/audit/dynamo_cache.py`
- Fixed: `ttl_epoch` → `ttl_expiry` in the rollback cache DDB item

### 2. `lambda_src/src/workers/vpc_alb_caller/handler.py`
- Added module-level constants: `_AI_HTTP_ERROR_CODES`, `_NON_RETRYABLE_ERROR_CODES`, `_RETRYABLE_ERROR_CODES`, `_UNAVAILABLE_ERROR_CODES`
- AI-path HTTP errors now return normalized envelope `{ai_error, http_status, error_code, retryable, unavailable, non_retryable, message, path}`
- Body `error_code` from AI Engine overrides status-code mapping
- Timeout and network errors on AI paths also return normalized envelopes
- Local security/config errors still raise exceptions
- Added `execute_rollback_from_cache()` function: CDO-owned rollback independent of AI Engine

### 3. `modules/orchestration/statemachine.json` + `docs/statemachine.json`
- `CacheRollbackPayload` item now includes `correlation_id` and `boto3_equivalent`
- `ReportVerifyResult.Next` changed to `EvaluateVerifyResult`
- Added: `EvaluateVerifyResult` (Choice), `ExecuteRollbackFromCache`, `NotifyAIRollback`, `WriteRollbackAudit`, `SendRolledBackStatusMessage`, `WriteEscalationAudit`, `SendEscalationAlert`
- Total: 68 states; both files in sync

### 4. Tests
- `test_state_machine.py`: +7 required states; branching/rollback/escalation chain assertions; CacheRollbackPayload item assertions
- `test_step_function_payload_contract.py`: +`TestVerifyBranching` (12 tests), +`TestNormalizedAIErrorEnvelope` (18 tests), +`TestRollbackCacheContract` (7 tests)
- `test_vpc_alb_caller.py`: 5 tests updated to expect normalized envelopes

## Test Results
- **285 passed, 0 failed**

## IaC Validation
- `terraform fmt -check -recursive`: PASSED
- Both ASL JSON files valid, 68 states in sync

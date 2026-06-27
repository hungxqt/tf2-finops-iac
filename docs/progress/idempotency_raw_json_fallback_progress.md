# Telemetry Idempotency and RAW_JSON Fallback Progress

**Date**: 2026-06-27  
**Status**: COMPLETE

## Summary

Gap 1 (AI payload idempotency hot path) and Gap 3 (small-payload RAW_JSON detect branch for CE fallback) are now implemented.

## Changes

### Gap 1 – Contract Idempotency Hot Path

| File | Change |
|---|---|
| `modules/orchestration/main.tf` | Added `aws_dynamodb_table.ai_payload_idempotency` (`finops-idempotency-{env}`, PAY_PER_REQUEST, hash_key=`idempotency_key`, TTL=`ttl_expiry`, SSE-KMS, PITR, tags) |
| `modules/orchestration/outputs.tf` | Added `ai_payload_idempotency` to `dynamodb_table_names`, `dynamodb_table_arns`; added `idempotency_table_name` output |
| `modules/orchestration/iam.tf` | Added `aws_dynamodb_table.ai_payload_idempotency.arn` to SFN DynamoDB `GetItem`/`PutItem`/`UpdateItem` grant |
| `modules/compute-lambda/main.tf` | Added `IDEMPOTENCY_TABLE_NAME` and `RAW_JSON_INLINE_MAX_BYTES` to `vpc_alb_caller` env config |
| `modules/compute-lambda/variables.tf` | Added `raw_json_inline_max_bytes` (default `200000`) |
| `environments/sandbox/main.tf` | Added `ai_payload_idempotency` ARN to IAM `dynamodb_table_arns`; added `idempotency_table_name` to `compute_lambda.dynamodb_table_names` |
| `environments/staging/main.tf` | Same as sandbox |
| `environments/prod/main.tf` | Same as sandbox |
| `lambda_src/src/workers/vpc_alb_caller/handler.py` | Full rewrite with contract idempotency enforcement: IN_PROGRESS PutItem (conditional), COMPLETED UpdateItem on success, ERROR UpdateItem on failure, cache-hit bypass, hash-mismatch/concurrent-IN_PROGRESS fail-closed. No `DeleteItem` (IAM boundary denies deletes). TTL=24h |
| `lambda_src/tests/test_vpc_alb_caller.py` | Added `TestIdempotencyHotPath` class covering: slot claim, cache hit, hash mismatch, concurrent IN_PROGRESS, HTTP error marks ERROR, no DeleteItem |

**Design constraints respected**:
- `run_state` table is untouched (remains Step Functions run-control only).
- No `DeleteItem` anywhere; cleanup via TTL (`ttl_expiry`, 24h).
- Idempotency is inactive (no-op) when `IDEMPOTENCY_TABLE_NAME` env var is empty.

### Gap 3 – RAW_JSON Inline Detect Branch for CE Fallback

| File | Change |
|---|---|
| `lambda_src/src/workers/normalizer/handler.py` | Added `_select_detect_request_mode(payload_bytes, max_inline_bytes)` pure helper; calls it from CE-fallback path to set `detect_request_mode` = `RAW_JSON` or `S3_POINTER` |
| `modules/orchestration/statemachine.json` | Updated `VerifyS3Pointer.Choices[0].Next` from `BuildDetectRequestS3Pointer` → `ChooseDetectRequestMode`; added `ChooseDetectRequestMode` (Choice) and `BuildDetectRequestRawJson` (Pass) states |
| `docs/statemachine.json` | Synced with same changes |
| `lambda_src/tests/fixtures/step_function_payloads.py` | Added `request_timestamp` to `_NORMALIZED_HEALTHY_DETAILS` and `_NORMALIZED_DEGRADED_DETAILS`; updated `POST_BUILD_DETECT_REQUEST_CE_FALLBACK` to use `data_source_type: RAW_JSON` and include `quality` block |
| `lambda_src/tests/test_step_function_payload_contract.py` | Added `ChooseDetectRequestMode` and `BuildDetectRequestRawJson` to required states; fixed `verify_s3_pointer` assertion to `ChooseDetectRequestMode`; added 3 new tests for mode routing and RAW_JSON body structure |
| `lambda_src/tests/test_normalizer.py` | Added `TestDetectRequestModeSelection` class with 4 unit tests on `_select_detect_request_mode` |

**Design constraints respected**:
- CUR-ready path always routes to `BuildDetectRequestS3Pointer` (unchanged).
- `ChooseDetectRequestMode` requires **both** `detect_request_mode == RAW_JSON` AND `telemetry_delay_event == true` to route to `BuildDetectRequestRawJson`, preventing accidental inline routing for CUR-ready payloads.
- `BuildDetectRequestRawJson` omits `aws_cur_line_items` from the Step Functions body (only CE records are included for CE-fallback).
- 200 KB cap (Step Functions limit safe-zone) is configurable via `RAW_JSON_INLINE_MAX_BYTES`; default is `200000`.

## Notes / Discrepancies

- The `VerifyS3Pointer` state now routes via `ChooseDetectRequestMode` in both the template and the docs copy. This is a logic enhancement, not a breaking change to the external API contract.
- The `POST_NORMALIZE_DEGRADED` fixture had stale/incomplete field set (`RAW_JSON_CE_FALLBACK` enum value, missing `schema_version`, `tenant_id`, etc.). These were corrected to match the current normalizer output schema.

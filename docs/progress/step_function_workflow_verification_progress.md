# Step Functions Workflow Verification Progress

## Status: COMPLETED

**Date**: 2026-06-27  
**Author**: Implementation Agent  
**Scope**: lambda_src/tests/test_step_function_payload_contract.py + fixtures  

---

## Objective

Add a repo-local verification layer proving the Step Functions workflow has every required
component, each state consumes the previous state's real output shape, and the implemented
flow matches AGENTS.md, docs/contracts/*, IMPLEMENTATION.md, and the active TF2 docs.

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `lambda_src/tests/fixtures/__init__.py` | Package init for fixtures module |
| `lambda_src/tests/fixtures/step_function_payloads.py` | 21 deterministic fixture dicts covering all workflow boundary scenarios |
| `lambda_src/tests/test_step_function_payload_contract.py` | 77 payload-contract tests in 9 groups (A-I) |

---

## Fixture Inventory (21 fixtures)

1. `SCHEDULED_WORKFLOW_INPUT` - EventBridge Scheduler -> PrepareRunContext input
2. `POST_PREPARE_RUN_CONTEXT` - After state_lambda prepare operation
3. `POST_INGEST_COST_DATA_S3` - CUR-ready ingestion, S3_POINTER mode (contract default)
4. `POST_INGEST_COST_DATA_CE` - CUR delayed, CE fallback active
5. `POST_NORMALIZE_HEALTHY` - High-quality normalization output (completeness >= 0.8)
6. `POST_NORMALIZE_DEGRADED` - Degraded telemetry (completeness < 0.8, triggers dry-run gate)
7. `POST_NORMALIZE_POINTER` - High-quality normalization output with contract-valid S3 pointer
8. `POST_BUILD_DETECT_REQUEST` - BuildDetectRequestRawJson Pass state output ($.ai_detect_request)
9. `POST_BUILD_DETECT_REQUEST_S3_POINTER` - BuildDetectRequestS3Pointer Pass state output
10. `POST_BUILD_DETECT_REQUEST_CE_FALLBACK` - BuildDetectRequestRawJsonCeFallback Pass state output
11. `POST_INVOKE_DETECT_ANOMALY` - /v1/detect returns anomaly detected
12. `POST_INVOKE_DETECT_NO_ANOMALY` - /v1/detect returns clean (no anomaly)
13. `POST_INVOKE_DECIDE` - /v1/decide returns action_plan + rollback_payload
14. `POST_FORMAT_DECIDE_RESULT` - FormatDecideResult Pass state writes $.ai
15. `POST_ROUTER` - RouteAlert writes $.alert with finance+engineering routes
16. `POST_CONTAINMENT_POLICY_APPLY` - sandbox+tag mode -> WritePreActionAudit
17. `POST_CONTAINMENT_POLICY_DENIED_PROD` - prod+terminate -> WriteDeniedAudit
18. `POST_CONTAINMENT_POLICY_DRYRUN_DENIED` - force_dry_run+apply -> WriteDeniedAudit
19. `POST_EXECUTE_CONTAINMENT` - ExecuteContainment result at $.containment
20. `POST_VERIFY_RESULT` - /v1/verify result at $.verify_result
21. `AI_FAIL_CLOSED_CONTEXT` - After SetAIFailClosedError, $.error populated
22. `CUR_DELAY_EXCEEDED_CONTEXT` - After SetCURDelayExceededError, cur_retry.count=4

---

## Test Groups (77 tests, 9 groups)

| Group | Name | Count | Coverage |
|-------|------|-------|---------|
| A | Component Inventory | 15 | ASL states, no-polling check, VPC ALB caller, DynamoDB, SNS, SQS wiring |
| B | Payload Resolution | 18 | JSONPath resolver validates each boundary fixture |
| C | Telemetry Contract | 5 | S3_POINTER default, CE fallback, quality flags |
| D | Detect Path | 10 | /v1/detect shape, stable idempotency key, mode-specific builders, dry-run mode propagation, fail-closed on success=false |
| E | Decide/Cache Path | 6 | /v1/decide body, rollback_payload, CacheRollbackPayload DynamoDB write |
| F | Containment Policy | 4 | Prod+destructive denial, dry-run denial, sandbox+tag safe path |
| G | Verify Path | 5 | /v1/verify body, action_executed.target JSONPath, audit chain |
| H | Fail-Closed Paths | 7 | AI fail-closed audit params, CUR delay audit params, retry count threshold |
| I | SQS/Status Messages | 5 | Only rollback_status queue, APPLIED/DENIED/PENDING status values |

---

## Test Results

```
77 passed in 0.19s (payload contract tests only)
88 passed in 0.45s (payload contract + state machine + lambda coverage + vpc alb caller)
107 passed in 3.93s (full suite, 0 failures)
```

---

## JSONPath Resolver Design

The lightweight ASL resolver in the test file supports the subset used by this state machine:

- `"$"` → entire context dict
- `"$.a.b.c"` → nested key traversal  
- `"$.anomalies_list[0].anomaly_id"` → array index then key
- `"States.Format"` → evaluates intrinsic format string function with resolved JSONPath arguments

This is sufficient to verify all Task.Parameters, Pass state JSONPaths, and Choice variable
paths without requiring a full ASL runtime simulation.

---

## Key Verification Findings

No payload gaps discovered. The following contract properties were verified:

1. **CUR-ready ingestion** - `$.ingestion.details.data_source_type` = `S3_POINTER` (telemetry contract default)
2. **SelectDetectRequestMode** - selects the correct request builder mode based on `detect_request_mode`:
   - `S3_POINTER`: default when valid pointer matches `^s3://company-cdo-[0-9]{12}-telemetry/.+\.json\.gz$`
   - `RAW_JSON`: CUR inline rows fallback when pointer matches fail or is absent
   - `RAW_JSON` CE fallback: cost explorer metrics fallback when `telemetry_delay_event` is true
3. **Stable Idempotency Key** - computed before InvokeDetect using `{tenant_id}:{execution_date}:{batch_type}` instead of `correlation_id`
4. **VpcAlbCallerLambda Dry-run mode** - passes `dry_run_mode` to InvokeDetect to reflect telemetry/error-budget degradation
5. **InvokeDetect** - reads parameters from `$.ai_detect_request` (dynamic, path `/v1/detect`, passes path, tenant_id, stable idempotency key, dry_run_mode, and body)
6. **InvokeDecide body** - `anomaly_context.$` resolves to `$.ai_detect_response.anomalies_list[0]`
7. **CacheRollbackPayload** - DynamoDB putItem with `rollback_payload` serialized via `States.JsonToString`
8. **FormatDecideResult** - reads `action_plan[0].action` and `anomalies_list[0].anomaly_id`
9. **ReportVerifyResult** - `action_executed.target.$` resolves from `anomalies_list[0].resource_id`
10. **FailClosed/WriteCURDelayAudit** - all 9 required audit context fields resolve correctly
11. **EvaluateContainmentPolicy** - prod+destructive denial and dry-run denial both encoded in ASL
12. **SQS** - only `rollback_status_queue_url` queue in ASL; no detection queue

---

## Active Authority Notes

- `ai_poll_interval` in PrepareRunContext Parameters is a legit retry-config field (not a detection queue)
- No ECS, Fargate, detection SQS, or polling loop detected in any verified path
- Active AI Engine integration path verified: Step Functions → VpcAlbCallerLambda → ALB → AI Request Lambda

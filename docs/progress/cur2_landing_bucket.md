# Progress: CUR 2.0 Direct Landing Bucket Implementation

**Date**: 2026-06-28  
**Status**: ✅ COMPLETE — all 51 tests passing

---

## Summary

This session implemented the Direct CUR 2.0 / AWS Data Exports landing bucket plan:
- `cost_puller` now uses a **deterministic manifest key** instead of scanning S3 for manifests.
- `normalizer` now **requires `cur_manifest_uri`** on the CUR-ready path and re-validates reportKeys.
- Terraform wires the new `CUR_EXPORTS_JSON` and `CUR_RAW_EXPORT_PREFIX` env vars.
- Lakehouse module can optionally create a `bcm-data-exports`-restricted landing bucket.
- IAM adds `s3:HeadObject` to the cost_puller read grant.

---

## Files Changed

### Lambda Handler Layer

| File | Change |
|---|---|
| `lambda_src/src/finops_common/aws_clients.py` | Added `head_object(bucket, key) → dict` to `S3Client`, `RealS3`, `FakeS3` |
| `lambda_src/src/workers/cost_puller/handler.py` | Full rewrite: deterministic manifest key (`_build_manifest_key`), `CUR_EXPORTS_JSON` parser, `_resolve_billing_period`, `_validate_manifest_report_keys`, `head_object` manifest readiness check, returns `cur_manifest_uri` + `assembly_id` + `billing_period` + `export_name` + `source_account_id` + `telemetry_delay_event=False` on READY path |
| `lambda_src/src/workers/normalizer/handler.py` | Added `cur_manifest_uri` extraction; CUR-ready path now raises `InvalidInputError` if missing; re-reads and validates manifest reportKeys vs `CUR_RAW_EXPORT_PREFIX` (cross-account and prefix containment); `CUR_RAW_EXPORT_PREFIX` env var injected |

### Terraform Modules

| File | Change |
|---|---|
| `modules/compute-lambda/main.tf` | Added `CUR_EXPORTS_JSON` to cost_puller env; added `CUR_RAW_EXPORT_PREFIX` to normalizer env |
| `modules/compute-lambda/variables.tf` | Added `cur_exports_json` and `cur_raw_export_prefix` variables |
| `modules/iam/main.tf` | Added `s3:HeadObject` to `AllowCURSourceGet` policy statement |
| `modules/lakehouse/main.tf` | Added optional `aws_s3_bucket.cur_export` with `bcm-data-exports.amazonaws.com` bucket policy (DenyHTTP, AllowBCMDataExportsPut scoped to raw prefix with `aws:SourceArn` + `aws:SourceAccount`, DenyWritesToProtectedPrefixes for curated/ai-input/audit/features) |
| `modules/lakehouse/variables.tf` | Added `create_cur_export_bucket`, `cur_export_bucket_name`, `cur_raw_prefix` |
| `modules/lakehouse/outputs.tf` | Added `cur_export_bucket_name` and `cur_export_bucket_arn` outputs |

### Environments

| File | Change |
|---|---|
| `environments/sandbox/variables.tf` | Added `cur_exports_json`, `create_cur_export_bucket`, `cur_export_bucket_name`, `cur_raw_prefix` |
| `environments/sandbox/main.tf` | Wired lakehouse `create_cur_export_bucket` / `cur_export_bucket_name` / `cur_raw_prefix`; IAM uses safe ternary for `cur_source_bucket_arn`; compute_lambda uses safe ternary for `cur_source_bucket`; passes `cur_exports_json` + `cur_raw_export_prefix` |
| `environments/sandbox/terraform.tfvars.example` | Added Option A/B deployment examples with full `cur_exports_json` heredoc example |

### Tests

| File | Change |
|---|---|
| `lambda_src/tests/test_cost_puller_cur2.py` | **NEW**: 8 tests for deterministic manifest path, billing period resolution, reportKey validation, CUR-ready happy path, 404 → CUR_DELAY, malicious reportKey, bucket-name security bypass |
| `lambda_src/tests/test_normalizer_cur2.py` | **NEW**: 6 tests for `cur_manifest_uri` fast-fail, happy-path Athena, cross-account reportKey rejection, prefix containment rejection, malformed S3 URI, CE-fallback still works |
| `lambda_src/tests/test_normalizer.py` | Updated 4 existing CUR-ready tests to pass `cur_manifest_uri` + `get_object_func` returning manifest bytes |

---

## Test Results

```
51 passed, 21 warnings (deprecation only) in 1.31s
```

---

## Manifest Key Contract

```
s3://<CUR_SOURCE_BUCKET>/<prefix>/<export_name>/metadata/BILLING_PERIOD=YYYY-MM/<export_name>-Manifest.json
```

Example:
```
s3://tf2-finops-cur-export-bucket/finops-cur-export/finops-export/metadata/BILLING_PERIOD=2026-06/finops-export-Manifest.json
```

---

## Step Functions Data Flow (Updated)

```
EventBridge → Step Functions
  → cost_puller Lambda
      HEAD s3://<cur_bucket>/<manifest_key>          # deterministic existence check
      GET  s3://<cur_bucket>/<manifest_key>          # validate assemblyId, reportKeys
      validate reportKeys ∈ allowed_raw_prefix
      → returns: cur_manifest_uri, assembly_id, billing_period, export_name, source_account_id
        data_source_type=S3_POINTER, telemetry_delay_event=False
  → normalizer Lambda
      GET  cur_manifest_uri                          # re-validate manifest
      validate reportKeys ∈ CUR_RAW_EXPORT_PREFIX
      Athena query on Glue table
      write curated Parquet → lakehouse/curated/
      write AI detect input → lakehouse/ai-input/
      → returns: s3_bucket_uri (ai-input/), s3_object_checksum
  → router → vpc_alb_caller → /v1/detect
```

---

## Discrepancies / Open Items

None. No stale docs detected. The implementation matches the user's plan and current contracts.

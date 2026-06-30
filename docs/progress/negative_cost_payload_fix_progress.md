# Negative Cost AI Payload Fix Progress

## Status

Implemented and validated.

## Scope

- Fix the `/v1/detect` schema failure by ensuring AI-bound Cost Explorer (CE) and CUR spend arrays never contain negative cost values.
- In `cost_puller`, kept source CE records readable for raw telemetry, but computed `missing_resources` and `current_ce_cost_gap_usd` from execution-date records where `unblended_cost > 0` only.
- Added bounded diagnostics such as `negative_cost_record_count` and `negative_cost_total_usd` to worker details/quality flags without logging full billing rows.
- Clamped/recomputed `current_ce_cost_gap_usd` so it is never negative.
- In `normalizer`, added sanitization helpers for AI-bound cost records (`sanitize_ce_records` and `sanitize_cur_records`) to exclude records where costs are missing, non-numeric, non-finite, or `< 0` (while keeping `0` values).
- Ensured sanitized arrays are used for:
  - RAW_JSON `/v1/detect` body.
  - S3_POINTER AI input JSON written under `ai-input/...`.
  - `normalized.details.aws_cost_explorer_daily` and `normalized.details.aws_cur_line_items`.

## Files Changed

- `lambda_src/src/workers/cost_puller/handler.py`
- `lambda_src/src/workers/normalizer/handler.py`
- `lambda_src/tests/test_cost_puller.py`
- `lambda_src/tests/test_normalizer.py`

## Validation Commands

```powershell
Push-Location lambda_src
python -m pytest tests/test_cost_puller.py tests/test_normalizer.py tests/test_step_function_payload_contract.py -q
python -m pytest -q
Pop-Location
```

## Results

- Addressed negative cost schema failures.
- All 377 unit and integration tests passed successfully.
- No regressions.

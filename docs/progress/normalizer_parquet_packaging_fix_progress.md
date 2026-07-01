# Normalizer Parquet Packaging Fix Progress

## Status

Implemented, tested, and verified.

## Scope

- Updated `scripts/package-lambdas.ps1` to build Lambda ZIPs for Python 3.13 Linux x86_64 using pip platform targeting (such as `--platform manylinux_2_28_x86_64 --only-binary=:all: --implementation cp --python-version 3.13`).
- Split dependencies so only the `normalizer` packages `pyarrow`.
- Created `lambda_src/requirements-normalizer.txt` containing `pyarrow`.
- Updated `lambda_src/requirements.txt` to remove `pyarrow` (leaving only comments) so other worker ZIPs do not contain `pyarrow`, `.dll`, `.pyd`, `win_amd64`, or `pyarrow.libs`.
- Updated `lambda_src/requirements-dev.txt` to include `-r requirements-normalizer.txt` to preserve `pyarrow` for local testing.
- Updated `lambda_src/tests/test_step_function_lambda_coverage.py` to align the expected `ps_workers` count to include the dashboard `trigger` worker function in `package-lambdas.ps1`.
- Replaced the broad Parquet-to-JSON fallback in `lambda_src/src/workers/normalizer/handler.py` with a fail-closed exception to prevent invalid Parquet writes.
- Sanitized `event_data` log statement in `handle_request` by summarizing large arrays (`aws_cur_line_items`, `aws_cost_explorer_daily`, `resource_utilization_metrics`, and `missing_resources`) to prevent raw telemetry logs from leaking into CloudWatch.
- Sanitized `Response:` log statements in `handle_request` to output only a summarized dictionary containing run IDs, S3 URIs, mode, telemetry quality, and item counts.
- Added test cases in `lambda_src/tests/test_normalizer.py`:
  - `test_normalizer_parquet_write_failure_fails_closed`: Proves that Parquet serialization failure fails closed, raising a `RuntimeError` and uploading no curated S3 object.
  - `test_normalizer_logging_sanitized`: Proves that raw CUR-like line items and resource telemetry are excluded from normal success logs, and that the sanitized summary is outputted.
- Updated `docs/GUIDES.md` and `docs/GUIDES_vi.md` to reflect the dependency split and target-platform packaging requirements.

## Files Changed

- `scripts/package-lambdas.ps1`
- `lambda_src/requirements.txt`
- `lambda_src/requirements-normalizer.txt`
- `lambda_src/requirements-dev.txt`
- `lambda_src/src/workers/normalizer/handler.py`
- `lambda_src/tests/test_step_function_lambda_coverage.py`
- `lambda_src/tests/test_normalizer.py`
- `docs/GUIDES.md`
- `docs/GUIDES_vi.md`

## Validation Commands

```powershell
# Run all unit tests
pytest lambda_src/tests

# Run packaging script
.\scripts\package-lambdas.ps1

# Verify zip files contents using Python
python -c "import zipfile; z = zipfile.ZipFile('.build/lambda/normalizer.zip'); names = z.namelist(); pyarrow_names = [n for n in names if 'pyarrow' in n]; dll_names = [n for n in names if '.dll' in n or '.pyd' in n or 'win_amd64' in n]; so_names = [n for n in names if '.so' in n]; print('normalizer.zip: pyarrow =', len(pyarrow_names), ', dlls =', len(dll_names), ', so files =', len(so_names)); z2 = zipfile.ZipFile('.build/lambda/state.zip'); names2 = z2.namelist(); pyarrow_names2 = [n for n in names2 if 'pyarrow' in n]; print('state.zip: pyarrow =', len(pyarrow_names2))"

# Terraform formatting and validation
terraform fmt -check -recursive
terraform -chdir=environments/sandbox validate
```

## Results

- All 388 unit tests in `pytest lambda_src/tests` passed successfully.
- `normalizer.zip` contains 38 Linux native `.so` files for pyarrow, 0 Windows `.dll` or `.pyd` files, and other worker zips (e.g. `state.zip`) contain 0 pyarrow files.
- Terraform configuration is fully formatted and validated.

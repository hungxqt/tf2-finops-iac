# Normalizer Athena Identifier Quoting Fix Progress

## Status

Implemented, tested, and plan generated.

## Scope

- Added a `quote_identifier` helper in `lambda_src/src/workers/normalizer/handler.py` to validate and double-quote database and table identifiers for Athena queries.
- Ensured strict regex validation matching `^[a-zA-Z0-9_-]+\Z` (using `\Z` to reject trailing newlines).
- Modified the dynamic SQL generation in `normalizer` to output double-quoted Glue database and table names in the `FROM` clause: `FROM "database_name"."table_name"`.
- Preserved `QueryExecutionContext={"Database": database}` with the raw, unquoted Glue database name to satisfy client requirements.
- Maintained configuration naming integrity (no Terraform resource or Glue resource renames).
- Added unit and regression tests in `lambda_src/tests/test_normalizer_cur2.py`:
  - `test_normalizer_athena_identifier_quoting`: Validates that the generated Athena query successfully quotes the database and table name.
  - `test_quote_identifier_helper_valid`: Tests valid alphanumeric, hyphens, and underscore identifiers.
  - `test_quote_identifier_helper_invalid_rejections`: Verifies rejections of unsafe input (whitespace, dots, quotes, semicolon statements, trailing newlines).

## Files Changed

- `lambda_src/src/workers/normalizer/handler.py`
- `lambda_src/tests/test_normalizer_cur2.py`

## Validation Commands

```powershell
Push-Location lambda_src
python -m pytest tests/test_normalizer_cur2.py tests/test_normalizer.py -v
python -m pytest
Pop-Location

terraform fmt -check -recursive
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
.\scripts\package-lambdas.ps1
terraform -chdir=environments/sandbox plan -out=normalizer-athena-identifier-fix.tfplan
```

## Results

- All 32 targeted tests for `normalizer` and `normalizer_cur2` passed.
- All 383 repository tests passed.
- Terraform formatting check, initialization, and validation succeeded.
- Lambda functions successfully packaged.
- Sandbox Terraform execution plan generated successfully, showing `source_code_hash` updates for all packaged Lambda functions (including `normalizer`).

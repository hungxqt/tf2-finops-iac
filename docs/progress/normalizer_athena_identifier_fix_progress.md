# Normalizer Athena Identifier Quoting Fix Progress

## Status

Implemented, tested, and plan generated.

## Scope

- Added a `quote_identifier` helper in `lambda_src/src/workers/normalizer/handler.py` to validate and double-quote table identifiers for Athena queries (corrected from backticks).
- Ensured strict regex validation matching `^[a-zA-Z0-9_-]+\Z` (using `\Z` to reject trailing newlines).
- Modified the dynamic SQL generation in `normalizer` to output double-quoted table names in the `FROM` clause: `FROM "table_name"` (omitting database qualification so Athena correctly resolves the table within the database context).
- Preserved `QueryExecutionContext={"Database": database}` with the raw, unquoted Glue database name to supply the required context.
- Maintained configuration naming integrity (no Terraform resource or Glue database/table renames).
- Updated unit and regression tests in `lambda_src/tests/test_normalizer_cur2.py`:
  - `test_normalizer_athena_identifier_quoting`: Validates that the generated Athena query successfully quotes the table name using double quotes, does not include database prefix, does not contain backticks, and passes the database name in `QueryExecutionContext`.
  - `test_quote_identifier_helper_valid`: Tests valid alphanumeric, hyphens, and underscore identifiers returning double-quoted strings.
  - `test_quote_identifier_helper_invalid_rejections`: Verifies rejections of unsafe input (whitespace, dots, quotes, backticks, semicolon statements, trailing newlines).
- Updated regression assertions in `test_normalizer_athena_query_integration` in `lambda_src/tests/test_normalizer.py` to verify that the query string does not contain database prefixes or backticks, uses double-quoted table names, and supplies database context only in `QueryExecutionContext`.

## Files Changed

- `lambda_src/src/workers/normalizer/handler.py`
- `lambda_src/tests/test_normalizer_cur2.py`
- `lambda_src/tests/test_normalizer.py`

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
terraform -chdir=environments/sandbox plan -out="$env:TEMP\normalizer-athena-context-db-fix.tfplan"
```

## Results

- All 32 targeted tests for `normalizer` and `normalizer_cur2` passed.
- All 383 repository tests passed.
- Terraform formatting check, initialization, and validation succeeded.
- Lambda functions successfully packaged.
- Sandbox Terraform execution plan generated successfully to the temp directory without committing any plan artifacts.

# Normalizer CUR Source IAM Update Progress

## Status
Validated (all tests passing, Terraform validation completed)

## Scope
Fix the sandbox AccessDenied error by granting the normalizer Lambda role least-privilege read access to the configured CUR/Data Exports source bucket prefix. Staging and production environments inherit the same correct behavior via the shared `modules/iam`.

Key Changes:
- Added conditional `s3:ListBucket` on `var.cur_source_bucket_arn` inside the `normalizer` policy document in `modules/iam/main.tf`.
- Added conditional `s3:GetObject` and `s3:HeadObject` on member-account scoped CUR prefixes or the fallback `cur_source_prefix` / bucket-wide objects.
- Wrote regression tests in `lambda_src/tests/test_iam_cur_source_policy.py`.

## Files Changed
- [modules/iam/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/iam/main.tf) - Updated `data.aws_iam_policy_document.normalizer` to grant access to the CUR source bucket and prefixes.
- [lambda_src/tests/test_iam_cur_source_policy.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_iam_cur_source_policy.py) - Added regression test verifying the normalizer policy structure and conditions.

## Validation Commands
All validations were executed and passed successfully:

```powershell
# Format check
terraform fmt -check -recursive modules/iam

# Terraform validate (Sandbox)
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate

# Terraform validate (Staging)
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate

# Run pytest suite
python -m pytest tests/test_iam_cur_source_policy.py tests/test_normalizer_cur2.py tests/test_cost_puller_cur2.py

# Run security checks
trivy config modules/iam
checkov -d modules/iam --framework terraform
```

# Tiến độ Synthetic Data Removal

## Trạng thái
Hoàn thành

## Phạm vi
- Gỡ cấu hình Terraform cho flag dự phòng tự tạo telemetry trước đây khỏi module `compute_lambda` và tất cả environment roots.
- Gỡ cơ chế tự động tạo manifest, thông tin xác thực STS, Cost Explorer, CloudWatch traffic, và bản ghi Athena CUR trong các đường chạy Lambda runtime.
- Cập nhật `cost_puller` và `normalizer` để yêu cầu telemetry input đã cấu hình và test fixture rõ ràng.
- Cập nhật unit test để dùng fixture rõ ràng cho fake S3, STS, CloudWatch, Cost Explorer, và Athena.
- Cập nhật tài liệu vận hành để mô tả hành vi fail-closed khi thiếu input CUR, CE, cache, hoặc Athena.

## Các file đã thay đổi
- `modules/compute-lambda/main.tf`
- `modules/compute-lambda/variables.tf`
- `environments/sandbox/main.tf`
- `environments/sandbox/terraform.tfvars` (chỉ là file local bị ignore; đã gỡ cấu hình lỗi thời)
- `environments/sandbox/variables.tf`
- `environments/sandbox/terraform.tfvars.example`
- `environments/staging/main.tf`
- `environments/staging/variables.tf`
- `environments/staging/terraform.tfvars.example`
- `environments/prod/main.tf`
- `environments/prod/variables.tf`
- `environments/prod/terraform.tfvars.example`
- `lambda_src/src/finops_common/aws_clients.py`
- `lambda_src/src/workers/cost_puller/handler.py`
- `lambda_src/src/workers/normalizer/handler.py`
- `lambda_src/tests/test_cost_puller.py`
- `lambda_src/tests/test_normalizer.py`
- `README.md`
- `docs/GUIDES.md`
- `docs/GUIDES_vi.md`
- `docs/progress/cost_puller_telemetry_progress.md`
- `docs/progress/cost_puller_telemetry_progress_vi.md`
- `docs/progress/lambda_python_migration_progress.md`
- `docs/progress/lambda_skeletons_progress.md`

## Lệnh kiểm tra
```powershell
Push-Location lambda_src; python -m pytest tests/test_cost_puller.py tests/test_normalizer.py; Pop-Location
Push-Location lambda_src; python -m pytest; Pop-Location
terraform fmt -check -recursive
terraform -chdir=bootstrap init -backend=false
terraform -chdir=bootstrap validate
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/sandbox plan -destroy -out sandbox-destroy.tfplan
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate
tflint --recursive
trivy config .
checkov -d . --framework terraform
rg --no-ignore -n "<removed-synthetic-runtime-markers>" lambda_src/src lambda_src/tests modules environments README.md docs/GUIDES.md docs/GUIDES_vi.md docs/progress
```

## Kết quả
- Unit test tập trung cho cost-puller và normalizer đã pass: 24 passed.
- Toàn bộ Lambda pytest suite đã pass: 195 passed.
- `terraform fmt -check -recursive` pass.
- Terraform init và validate pass cho `bootstrap`, `environments/sandbox`, `environments/staging`, và `environments/prod`.
- Sandbox destroy plan chạy thành công và báo không có object cần destroy, không có blocker `prevent_destroy`. Artifact `sandbox-destroy.tfplan` đã được xóa sau khi kiểm tra.
- Scan marker synthetic nghiêm ngặt không còn kết quả trong runtime source, tests, modules, environments, guides, README, hoặc progress docs.
- `checkov -d . --framework terraform` pass: 1203 passed, 0 failed, 234 skipped.
- `tflint --recursive` vẫn báo các cảnh báo có sẵn không thuộc phạm vi thay đổi này: `modules/compute-lambda.aws_region` chưa dùng, thiếu provider constraint `archive` trong `modules/dashboard`, và các biến dashboard auth TTL chưa dùng.
- `trivy config .` hoàn tất với exit code 0 nhưng vẫn báo các findings S3 logging/versioning và Lambda@Edge tracing mức low/medium có sẵn, ngoài phạm vi cleanup này.

## Vướng mắc
Không có vướng mắc cho việc gỡ synthetic data.

## Bước tiếp theo
Quyết định riêng việc cleanup các finding tflint và Trivy hiện có.

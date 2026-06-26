# Tiến độ Orchestration

## Trạng thái
Hoàn thành cho phạm vi căn chỉnh state/idempotency.

## Phạm vi
Đã căn chỉnh state worker của CDO và hạ tầng idempotency trong orchestration theo các hợp đồng AI API, telemetry, và deployment đã ký:
- Đổi tên vật lý của bảng run-state/idempotency thành `finops-idempotency-{environment}` nhưng vẫn giữ output key `run_state` để tương thích module.
- Bật DynamoDB TTL trên `ttl_expiry` cho khóa idempotency/run trong 24 giờ.
- Cập nhật định dạng idempotency key của state worker thành `{tenant_id}:{billing_period_date}:{batch_type}`.
- Thêm xử lý mismatch payload hash với semantics trạng thái `ERR_IDEMPOTENCY_MISMATCH`.
- Thêm `FAILED_CONTRACT_CHECK` thông qua operation `fail_contract_check`.
- Thêm kiểm tra trường contract cho AWS account ID 12 chữ số, payload hash SHA-256 chữ thường, và phiên bản contract dạng semantic.
- Wire `ERROR_BUDGET_TABLE_NAME` vào environment của state worker và kiểm thử việc error budget bị khóa ép hệ thống sang dry-run.
- Đã xóa thư mục legacy standalone `services/state-lambda` khỏi workspace gốc capstone sau khi xác nhận state worker trong IAC đã cover hành vi idempotency DynamoDB bắt buộc.

## Các file đã thay đổi
- `lambda_src/src/workers/state/handler.py`
- `lambda_src/src/finops_common/utils.py`
- `lambda_src/src/finops_common/__init__.py`
- `lambda_src/src/finops_common/aws_clients.py`
- `lambda_src/tests/test_state.py`
- `lambda_src/tests/test_finops_common.py`
- `lambda_src/tests/test_step_function_lambda_coverage.py`
- `modules/orchestration/main.tf`
- `modules/compute-lambda/main.tf`
- `environments/sandbox/main.tf`
- `environments/staging/main.tf`
- `environments/prod/main.tf`
- `docs/progress/orchestration_progress.md`
- `docs/progress/orchestration_progress_vi.md`

## Lệnh kiểm tra
```powershell
python -m pytest lambda_src\tests\test_state.py lambda_src\tests\test_finops_common.py lambda_src\tests\test_step_function_lambda_coverage.py -q
terraform fmt -recursive modules\orchestration modules\compute-lambda environments\sandbox environments\staging environments\prod
terraform fmt -check -recursive modules\orchestration modules\compute-lambda environments\sandbox environments\staging environments\prod
python -m pytest
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate
```

## Kết quả
- Bộ kiểm thử Python tập trung: Thành công, 19 passed.
- Định dạng Terraform cho các module/environment đã chạm: Thành công.
- Toàn bộ kiểm thử Python Lambda: Thành công, 43 passed với các warning `datetime.utcnow()` đã có sẵn ở các worker khác.
- Sandbox Terraform init với `-backend=false`: Thành công.
- Sandbox Terraform validate: Thành công, cấu hình hợp lệ.
- Staging Terraform init với `-backend=false`: Thành công.
- Staging Terraform validate: Thành công, cấu hình hợp lệ.
- Prod Terraform init với `-backend=false`: Thành công.
- Prod Terraform validate: Thành công, cấu hình hợp lệ.

## Vướng mắc
Không có trong phạm vi này.

## Bước tiếp theo
Chạy thêm các scan Trivy/Checkov tùy chọn cho bề mặt Terraform đã thay đổi khi cần bằng chứng security scan cho lần bàn giao tiếp theo.
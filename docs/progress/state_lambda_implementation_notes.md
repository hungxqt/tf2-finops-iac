# Ghi chú triển khai State Lambda Idempotency

## Mục tiêu

Thay đổi này căn chỉnh State Lambda trong `tf2-finops-iac` với hợp đồng AI API, Telemetry, và Deployment đã ký. Trọng tâm là đưa idempotency hot path về đúng DynamoDB table `finops-idempotency-{environment}`, dùng TTL 24 giờ, và loại bỏ phụ thuộc vào standalone `services/state-lambda` cũ ở workspace gốc.

## Vì sao cần thay đổi

Trước thay đổi này, state worker đã có hướng đi đúng vì chạy nội bộ trong Step Functions và dùng DynamoDB. Tuy nhiên vẫn còn lệch contract ở vài điểm quan trọng:

- Tên bảng run-state chưa theo pattern `finops-idempotency-{env}`.
- Idempotency key chưa theo format contract `{tenant_id}:{billing_period_date}:{batch_type}`.
- Bảng run-state chưa bật TTL `ttl_expiry` cho lock 24 giờ.
- Chưa xử lý rõ trường hợp cùng idempotency key nhưng payload hash khác nhau.
- State worker chưa nhận `ERROR_BUDGET_TABLE_NAME` để kiểm tra error-budget lock và ép dry-run.
- Standalone `services/state-lambda` cũ dùng luồng riêng và S3 store, không phù hợp với kiến trúc IAC hiện tại.

## Thay đổi chính

### State worker

File chính: `lambda_src/src/workers/state/handler.py`

State worker hiện hỗ trợ các operation sau:

- `prepare`: tạo run context, tenant ID, batch type, và idempotency key chuẩn contract.
- `check`: ghi lock `IN_PROGRESS` nếu chưa tồn tại; trả trạng thái cũ nếu đã có lock.
- `complete`: cập nhật trạng thái `COMPLETED`.
- `failed`: cập nhật trạng thái `FAILED`.
- `fail_contract_check`: cập nhật trạng thái `FAILED_CONTRACT_CHECK`.
- `check_quota`: giới hạn tối đa 5 lượt ad-hoc mỗi tenant/ngày.
- `check_error_budget`: đọc bảng error budget và ép `force_dry_run = true` khi tenant bị lock.

Các field được ghi vào DynamoDB gồm:

- `idempotency_key`
- `payload_sha256`
- `status`
- `run_id`
- `correlation_id`
- `tenant_id`
- `billing_period_date`
- `batch_type`
- `created_at`
- `updated_at`
- `ttl_expiry`
- `failure_code` nếu có lỗi

Nếu cùng `idempotency_key` nhưng `payload_sha256` khác nhau, state worker trả trạng thái `ERR_IDEMPOTENCY_MISMATCH` để ngăn xử lý trùng sai payload.

### Shared helper

Các helper trong `lambda_src/src/finops_common/utils.py` được cập nhật để dùng chung:

- `utc_now()`
- `iso_utc_now()`
- `deterministic_tenant_id(account_id)`
- `idempotency_key(tenant_id, billing_period_date, batch_type)`

`FakeDynamoDB` trong `lambda_src/src/finops_common/aws_clients.py` cũng được mở rộng để test được conditional write và duplicate state mà không cần gọi AWS thật.

### Terraform

`modules/orchestration/main.tf` đổi bảng run-state vật lý thành:

```hcl
name = "finops-idempotency-${var.environment}"
```

Bảng này bật TTL:

```hcl
ttl {
  attribute_name = "ttl_expiry"
  enabled        = true
}
```

`modules/compute-lambda/main.tf` thêm biến môi trường cho state worker:

```hcl
ERROR_BUDGET_TABLE_NAME = lookup(var.dynamodb_table_names, "error_budget", "")
```

Các environment root `sandbox`, `staging`, và `prod` được cập nhật để IAM pre-wiring trỏ đúng bảng `finops-idempotency-{environment}`.

## Legacy service đã loại bỏ

Thư mục standalone sau đã bị xóa khỏi workspace gốc vì không còn là implementation path chính:

```text
services/state-lambda/
```

Lý do loại bỏ:

- Dùng service interface riêng như `ACQUIRE_RUN`, `GET_RUN`, `REDRIVE_RUN` thay vì operation của Step Functions hiện tại.
- Có S3 store riêng cho state, trong khi contract yêu cầu DynamoDB là idempotency hot path.
- Có Terraform/package flow riêng ngoài skeleton `tf2-finops-iac`.
- Dễ gây nhầm lẫn cho team khi triển khai hoặc review.

Logic hữu ích đã được giữ lại ở mức semantics: trạng thái `IN_PROGRESS`, `COMPLETED`, `FAILED`, `FAILED_CONTRACT_CHECK`, kiểm tra schema cơ bản, quota ad-hoc, và mismatch payload hash.

## Test đã cập nhật

Các test chính được cập nhật hoặc bổ sung:

- `lambda_src/tests/test_state.py`
- `lambda_src/tests/test_finops_common.py`
- `lambda_src/tests/test_step_function_lambda_coverage.py`

Các case quan trọng:

- Fresh `check` ghi `IN_PROGRESS` và có `ttl_expiry`.
- Duplicate cùng key trả trạng thái hiện tại.
- Duplicate cùng key nhưng khác `payload_sha256` trả `ERR_IDEMPOTENCY_MISMATCH`.
- `complete`, `failed`, và `fail_contract_check` cập nhật đúng trạng thái.
- `check_quota` chặn lượt ad-hoc thứ 6 trong cùng tenant/ngày.
- `check_error_budget` đọc `ERROR_BUDGET_TABLE_NAME` và ép dry-run khi lock.
- Static coverage đảm bảo compute Lambda có `RUN_STATE_TABLE_NAME` và `ERROR_BUDGET_TABLE_NAME`.

## Validation đã chạy

```powershell
python -m pytest lambda_src\tests\test_state.py lambda_src\tests\test_finops_common.py lambda_src\tests\test_step_function_lambda_coverage.py -q
terraform fmt -check -recursive modules\orchestration modules\compute-lambda environments\sandbox environments\staging environments\prod
python -m pytest
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate
```

Kết quả:

- Focused Python tests: 19 passed.
- Full Lambda tests: 43 passed.
- Terraform fmt check cho các path đã chạm: passed.
- Sandbox, staging, prod Terraform init/validate với `-backend=false`: passed.

## Lưu ý còn lại

- Một số worker khác vẫn có warning `datetime.utcnow()` khi chạy full test. Phần này không thuộc scope State Lambda lần này.
- README hiện còn wording cũ về ECS/Fargate hosting platform. AGENTS/IMPLEMENTATION hiện ưu tiên Lambda container + private internal ALB. README nên được chỉnh ở một PR docs riêng nếu team muốn làm sạch wording.
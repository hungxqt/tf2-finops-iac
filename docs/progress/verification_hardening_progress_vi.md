# Tiến độ Verification and Scanner Hardening

## Trạng thái
Đang thực hiện

## Phạm vi
Khắc phục các lỗi Terraform CI xuất hiện sau khi phần normalizer alignment đã được merge. Bản cập nhật này tập trung vào sáu lỗi Checkov trong GitHub Actions run `28227058326` và xác nhận lỗi unit test Lambda trong run `28227178445` đã được giải quyết trên `origin/main` hiện tại.

## Các file đã thay đổi
- `modules/ai-runtime-lambda/main.tf`: thêm lifecycle `create_before_destroy` cho ACM certificate được tạo tự động.
- `modules/lakehouse/main.tf`: tắt ACL ownership trên S3 logging target bucket bằng `BucketOwnerEnforced`, xóa resource ACL của logging bucket, ghi rõ ngoại lệ SSE-S3 cho cơ chế S3 server access log delivery, và thêm Trivy `AWS-0132` ignore đúng mục tiêu cho resource mã hóa của logging destination này.
- `environments/sandbox/main.tf`: thêm KMS key policy tường minh cho replica key và gắn vào `aws_kms_key.replica`.
- `environments/staging/main.tf`: thêm cùng KMS key policy tường minh cho replica key.
- `environments/prod/main.tf`: thêm cùng KMS key policy tường minh cho replica key.
- `modules/orchestration/main.tf`: áp dụng Terraform formatting mà PR CI yêu cầu sau khi pull `main` mới nhất.

## Lệnh kiểm tra
- `python -m pytest lambda_src\tests\test_cost_puller.py::test_handle_request_remote_session_override`
- `Push-Location lambda_src; python -m pytest; Pop-Location`
- `terraform fmt modules\ai-runtime-lambda\main.tf modules\lakehouse\main.tf environments\sandbox\main.tf environments\staging\main.tf environments\prod\main.tf`
- `terraform -chdir=environments/sandbox init -backend=false`
- `terraform -chdir=environments/staging init -backend=false`
- `terraform -chdir=environments/prod init -backend=false`
- `terraform -chdir=environments/sandbox validate`
- `terraform -chdir=environments/staging validate`
- `terraform -chdir=environments/prod validate`
- `terraform fmt modules\orchestration\main.tf`
- `terraform fmt -check -recursive`
- `git diff --check`
- `trivy config --severity HIGH,CRITICAL .`
- Đã thử: `python -m pip install checkov==3.2.524`

## Kết quả
- Narrow Lambda test đã pass: `1 passed`.
- Toàn bộ Lambda test suite đã pass local: `109 passed`.
- Terraform init đã pass cho sandbox, staging và prod với backend bị tắt.
- Terraform validate đã pass cho sandbox, staging và prod.
- Đã pull `origin/main` mới nhất vào local `main`, rebase nhánh fix, và format `modules/orchestration/main.tf` sau khi CI báo lỗi.
- Đã thêm Trivy ignore đúng mục tiêu cho ngoại lệ SSE-S3 của S3 server access logging destination sau khi PR CI báo `AWS-0132`.
- Trivy local đã pass với 0 misconfiguration HIGH/CRITICAL.
- Terraform format check đã pass cho toàn repo.
- `git diff --check`
- `trivy config --severity HIGH,CRITICAL .` đã pass, chỉ còn cảnh báo line ending.
- Kiểm tra Checkov local đang bị chặn vì PyPI reset kết nối tải package khi cài `checkov==3.2.524`.
- GitHub Actions cần chạy kiểm tra Checkov parity cuối cùng sau khi PR được mở.

## Vướng mắc
- Local chưa có Checkov binary, và `python -m pip install checkov==3.2.524` thất bại với `ConnectionResetError(10054)` từ kết nối tải package.

## Bước tiếp theo
Mở PR sạch từ `origin/main` với các Terraform fix nhắm đúng Checkov và để GitHub Actions xác nhận Checkov scan trên Ubuntu.
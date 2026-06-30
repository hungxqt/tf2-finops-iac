# Tiến độ AI Payload Contract

## Trạng thái

Đã triển khai và kiểm tra cho đường dẫn Step Functions AI payload contract.

## Phạm vi

- Cập nhật các request builder của Step Functions cho `/v1/detect`, `/v1/decide`, và `/v1/verify` trong khi giữ nguyên transport đã được duyệt là `Step Functions -> VpcAlbCallerLambda -> private internal ALB -> AI Request Lambda`.
- Giữ `/v1/detect` theo đường dẫn mặc định `S3_POINTER` và bổ sung các trường còn thiếu theo telemetry contract.
- Đồng bộ giá trị tenant, correlation, idempotency, timestamp, và payload checksum giữa Step Functions parameters, AI request body, và validation của VpcAlbCallerLambda.
- Chuẩn hóa AI input payload từ normalizer để `business_context` là một object theo phạm vi account và các S3 AI input object có tenant context.
- Tăng cường local validation trong VpcAlbCallerLambda cho UUID tenant/correlation, định dạng AI idempotency key, cấu trúc HTTPS ALB base URL, và lỗi lệch context giữa body và top-level.

## Các file đã thay đổi

- `modules/orchestration/statemachine.json`
- `docs/statemachine.json`
- `lambda_src/src/workers/normalizer/handler.py`
- `lambda_src/src/workers/vpc_alb_caller/handler.py`
- `lambda_src/src/workers/state/handler.py`
- `lambda_src/tests/fixtures/step_function_payloads.py`
- `lambda_src/tests/test_normalizer.py`
- `lambda_src/tests/test_state.py`
- `lambda_src/tests/test_state_machine.py`
- `lambda_src/tests/test_step_function_payload_contract.py`
- `lambda_src/tests/test_vpc_alb_caller.py`

## Lệnh kiểm tra

```powershell
python scripts\render-static-asl.py
Push-Location lambda_src; python -m pytest tests/test_vpc_alb_caller.py tests/test_normalizer.py tests/test_state.py tests/test_state_machine.py tests/test_step_function_payload_contract.py; Pop-Location
Push-Location lambda_src; python -m pytest; Pop-Location
terraform fmt -check -recursive modules\orchestration
terraform fmt -check -recursive
terraform -chdir=environments\sandbox init -backend=false
terraform -chdir=environments\sandbox validate
trivy config .
checkov -d modules\ai-runtime-lambda -d modules\orchestration --framework terraform
Push-Location lambda_src; python -m pytest tests/test_state_machine.py tests/test_step_function_payload_contract.py; Pop-Location
git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check
```

## Kết quả

- Regenerate static ASL hoàn tất và tạo JSON hợp lệ.
- Bộ test tập trung cho Lambda và Step Functions contract đã pass: 108 passed, 1 warning.
- Toàn bộ Lambda test suite đã pass: 199 passed, 34 warnings.
- Terraform formatting checks đã pass.
- Sandbox Terraform init ban đầu không truy cập được `registry.terraform.io` trong restricted sandbox, sau đó đã pass với network escalation được phê duyệt.
- Sandbox Terraform validate đã pass.
- Scoped Checkov scan cho `modules/ai-runtime-lambda` và `modules/orchestration` đã pass với 110 passed, 0 failed, và 14 skipped checks.
- `trivy config .` hoàn tất thành công, nhưng vẫn báo các finding có sẵn ngoài phạm vi patch này.
- Post-regeneration ASL contract tests đã pass: 80 passed, 1 warning.
- CRLF-aware diff whitespace check đã pass.

## Vướng mắc

- Không có vướng mắc cho feature này.
- Vẫn còn validation noise từ các warning `datetime.utcnow()` deprecation có sẵn và một pytest cache permission warning.

## Bước tiếp theo

Chạy bộ kiểm tra environment rộng hơn trước khi release nếu patch này được gộp cùng các thay đổi hạ tầng khác.

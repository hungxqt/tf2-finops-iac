# Tiến độ loại bỏ retry_after_seconds khỏi Step Functions Context

## Trạng thái
Hoàn thành

## Phạm vi
Loại bỏ trường `retry_after_seconds` đã lỗi thời khỏi quy trình orchestration (Step Functions), các bài kiểm thử và mô hình sự kiện nội bộ. Quy trình sẽ dựa vào các trạng thái chờ hiện có: `WaitForCURExport.Seconds = var.cur_retry_interval_seconds` và `WaitForCostExplorer.Seconds = 300`. Việc này giúp thu hẹp khoảng cách giữa cấu trúc payload giả lập (fixtures) và dữ liệu đầu vào thực tế từ EventBridge Scheduler.

Chi tiết thay đổi:
- Loại bỏ `retry_after_seconds.$` khỏi các tham số của `EvaluateErrorBudgetLock` và `SetTelemetryForceDryRun` trong file `modules/orchestration/statemachine.json` và file tài liệu đối chiếu `docs/statemachine.json`.
- Bảo toàn việc truyền dữ liệu cho các trường `cur_retry`, `ce_retry`, `ai_retry`, `force_dry_run` và `error_budget_locked`.
- Bổ sung `ce_retry.$` vào `EvaluateErrorBudgetLock` và `SetTelemetryForceDryRun` do trường này trước đó bị thiếu nhưng cần thiết cho các trạng thái thử lại CE.
- Loại bỏ trường `retry_after_seconds` cùng logic phân tích/tuần tự hóa khỏi các lớp `Response` và `Event` trong file `lambda_src/src/finops_common/event.py`.
- Loại bỏ `retry_after_seconds` khỏi fixture `SCHEDULED_WORKFLOW_INPUT` trong file `lambda_src/tests/fixtures/step_function_payloads.py`.
- Thêm bài kiểm thử phân giải payload chứng minh `EvaluateErrorBudgetLock` phân giải thành công với context thực tế đã chuẩn bị sẵn cộng với `error_budget_check` mà không cần `retry_after_seconds`.
- Thêm kiểm thử tĩnh ASL để đảm bảo `retry_after_seconds` không còn xuất hiện trong cả hai file ASL.
- Giữ nguyên các bài kiểm thử hiện có đối với số lần thử lại (`cur_retry`, `ce_retry`) và số giây chờ.

## Nguyên nhân gốc rễ
`retry_after_seconds` là một trường cũ không còn sử dụng trong quy trình orchestration. Việc loại bỏ nó giúp làm sạch dữ liệu payload và ngăn ngừa sự sai lệch giữa cấu trúc dữ liệu kiểm thử và dữ liệu chạy thực tế từ EventBridge Scheduler.

## Các file đã thay đổi
- [modules/orchestration/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/statemachine.json)
- [docs/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/statemachine.json)
- [lambda_src/src/finops_common/event.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/event.py)
- [lambda_src/tests/fixtures/step_function_payloads.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/fixtures/step_function_payloads.py)
- [lambda_src/tests/test_step_function_payload_contract.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_step_function_payload_contract.py)

## Lệnh xác thực
```powershell
Push-Location lambda_src
python -m pytest tests/test_state.py tests/test_state_machine.py tests/test_step_function_payload_contract.py tests/test_finops_common.py
python -m pytest
Pop-Location
terraform -chdir=environments/sandbox validate
trivy config .
checkov -d modules/orchestration --framework terraform
```

## Kết quả
- `terraform -chdir=environments/sandbox validate`: Thành công (Success! The configuration is valid.)
- Kiểm thử unit được chỉ định: Thành công (Vượt qua tất cả 168 bài test)
- Toàn bộ kiểm thử unit: Thành công (Vượt qua tất cả 357 bài test)
- Quét tĩnh Trivy: Thành công (Không phát hiện lỗi nghiêm trọng)
- Quét tĩnh Checkov: Thành công (Tất cả các kiểm tra đều vượt qua)

## Khó khăn/Rào cản
Không có

## Bước tiếp theo
Tiến hành tích hợp liên tục và kiểm thử triển khai pipeline.

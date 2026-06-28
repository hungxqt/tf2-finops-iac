# Tiến độ Orchestration

## Trạng thái
Hoàn thành

## Phạm vi
Cập nhật luồng Step Functions để phù hợp với kho lưu trữ docs/tf2-finops mới: `/v1/detect` đồng bộ, `/v1/decide` đồng bộ để lập kế hoạch hành động, `/v1/verify` để xác thực kết quả, kiểm toán authoritative qua S3, bộ nhớ đệm rollback cache và cơ chế idempotency hot-path trên DynamoDB, loại bỏ việc polling phát hiện qua `/v1/status` trong ASL, và hoạt động bảo toàn đóng (fail-closed) cho containment.

Cụ thể:
- Định nghĩa và tài liệu state machine được cấu hình để điều hướng qua Lambda trung gian VPC ALB caller.
- Sửa lỗi các trạng thái không thể tiếp cận (unreachable states) trong biểu đồ ASL:
  - Cấu hình Next của `SendEscalationAlertForAnomaly` thành `AnomalyEscalated` và Catch block thành `AnomalyPlatformFailed` (tránh trạng thái pending âm thầm khi có lỗi).
  - Thêm xử lý `Catch` cho các trạng thái gửi cảnh báo SNS ở cấp gốc (`SendFailClosedAlert` và `SendCURDelayAlert`) để chuyển tiếp sang `WriteAlertDeliveryFailureAudit` khi SNS bị lỗi, giúp `WriteAlertDeliveryFailureAudit` có thể tiếp cận được.
  - Thay đổi đích đến Catch của Map `ProcessDetectedAnomalies` thành `WriteContainmentFailureAudit`, giúp `WriteContainmentFailureAudit` có thể tiếp cận được.
- Cập nhật các bài test đơn vị Python (`test_state_machine.py`, `test_step_function_payload_contract.py`) để phù hợp luồng chuyển đổi trạng thái mới.
- Thêm kiểm tra hồi quy về tính tiếp cận của các trạng thái (graph reachability regression test) trong `test_state_machine.py` để đảm bảo không có trạng thái nào bị cô lập (unreachable).

## Các file đã thay đổi
- [docs/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/statemachine.json)
- [modules/orchestration/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/statemachine.json)
- [lambda_src/tests/test_state_machine.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_state_machine.py)
- [lambda_src/tests/test_step_function_payload_contract.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_step_function_payload_contract.py)

## Lệnh kiểm tra
```powershell
terraform fmt -check -recursive modules/orchestration
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
Push-Location lambda_src; python -m pytest -q -p no:cacheprovider tests/test_state_machine.py tests/test_step_function_payload_contract.py; Pop-Location
```

## Kết quả
- `terraform fmt -check -recursive`: Thành công (Tất cả các tệp đều được định dạng đúng)
- `environments/sandbox validate`: Thành công (Cấu hình hợp lệ)
- Các kiểm tra Python Lambda: Thành công (137 kiểm tra đều vượt qua, bao gồm cả bài kiểm tra độ phủ đạt được trạng thái ASL)

## Vướng mắc
Không có

## Bước tiếp theo
Tiến hành triển khai hoặc xác thực trên môi trường sandbox.

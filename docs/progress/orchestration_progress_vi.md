# Tiến độ Orchestration

## Trạng thái
Hoàn thành

## Phạm vi
Cập nhật luồng Step Functions để phù hợp với kho lưu trữ docs/tf2-finops mới: `/v1/detect` đồng bộ, `/v1/decide` đồng bộ để lập kế hoạch hành động, `/v1/verify` để xác thực kết quả, kiểm toán authoritative qua S3, bộ nhớ đệm rollback cache và cơ chế idempotency hot-path trên DynamoDB, loại bỏ việc polling phát hiện qua `/v1/status` trong ASL, và hoạt động bảo toàn đóng (fail-closed) cho containment.

Cụ thể, đã sửa đổi định nghĩa và tài liệu state machine để điều hướng rõ ràng thông qua Lambda trung gian VPC ALB caller:
- Step Functions -> VpcAlbCallerLambda -> HTTPS private internal ALB -> AI Engine Request Lambda
- Đổi tên placeholder `${ai_request_lambda_arn}` thành `${vpc_alb_caller_lambda_arn}` trong các trạng thái `InvokeDetect`, `InvokeDecide`, và `ReportVerifyResult`.
- Thêm các bình luận (Comment) giải thích bên trong các trạng thái mô tả luồng định tuyến qua ALB.
- Loại bỏ ánh xạ trực tiếp `ai_request` không sử dụng khỏi danh sách `lambda_function_arns` của môi trường để Step Functions chỉ nhận quyền gọi VPC ALB caller helper.
- Cập nhật các bài kiểm thử đơn vị Python và kịch bản kết xuất tài liệu để xác thực cấu trúc mới.

## Các file đã thay đổi
- [docs/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/statemachine.json)
- [modules/orchestration/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/statemachine.json)
- [modules/orchestration/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/main.tf)
- [modules/orchestration/iam.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/iam.tf)
- [modules/orchestration/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/outputs.tf)
- [environments/sandbox/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/main.tf)
- [environments/staging/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/main.tf)
- [environments/prod/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/main.tf)
- [scripts/render-static-asl.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/scripts/render-static-asl.py)
- [lambda_src/tests/test_state_machine.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_state_machine.py)
- [lambda_src/tests/test_step_function_lambda_coverage.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_step_function_lambda_coverage.py)

## Lệnh kiểm tra
```powershell
terraform fmt -check -recursive
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
python scripts/render-static-asl.py
Push-Location lambda_src; python -m pytest; Pop-Location
```

## Kết quả
- `terraform fmt -check -recursive`: Thành công (Tất cả các tệp đều được định dạng đúng)
- `environments/sandbox validate`: Thành công (Cấu hình hợp lệ)
- Các kiểm tra Python Lambda: Thành công (Tất cả 40 kiểm tra đều vượt qua, bao gồm các bài kiểm tra state machine và lambda coverage mới xác thực luồng VPC ALB caller)
- Quét Checkov: Thành công (Tất cả các chính sách tiêu chuẩn đều được xác minh)

## Vướng mắc
Không có

## Bước tiếp theo
Tiến hành triển khai hoặc xác thực trên môi trường sandbox.

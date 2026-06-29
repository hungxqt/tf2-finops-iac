# Tiến độ Triển khai CodeDeploy cho AI Runtime Lambda

## Trạng thái
Hoàn thành (Đã sửa lỗi sự kiện tự động hoàn tác)

## Phạm vi
Thêm cơ chế CodeDeploy rollout tuyến tính cho AI Engine Request Lambda trong `modules/ai-runtime-lambda`, ban đầu áp dụng cho môi trường `sandbox`:
- Thêm `aws_codedeploy_app` với `compute_platform = "Lambda"`.
- Thêm vai trò dịch vụ IAM CodeDeploy đi kèm với policy quản lý `AWSCodeDeployRoleForLambda`.
- Thêm `aws_codedeploy_deployment_group` hỗ trợ cấu hình động.
- Cấu hình 4 cảnh báo CloudWatch tự động hoàn tác (Lỗi, Nghẽn, Độ trễ P99 > 800ms, và Lỗi ALB 5xx).
- Sửa đổi sự kiện tự động hoàn tác thành `DEPLOYMENT_STOP_ON_ALARM` thay vì sự kiện không hợp lệ `ALARM_TO_REVERT` nhằm khắc phục lỗi InvalidAutoRollbackConfigException.
- Cập nhật Lambda alias để bỏ qua các thay đổi về phiên bản/định tuyến giúp CodeDeploy quản lượng.
- Thêm các biến đầu vào và đầu ra cho module để cấu hình CodeDeploy.
- Tích hợp CodeDeploy vào `environments/sandbox/main.tf` sử dụng chiến lược tuyến tính 10% mỗi 1 phút và SNS topic kỹ thuật.
- Tạo script `scripts/start-ai-lambda-codedeploy.ps1` để tự động hóa việc tạo AppSpec, kích hoạt, thăm dò và đợi CodeDeploy hoàn tất.
- Cập nhật workflow GitHub Actions (`sandbox-deploy.yml` và `terraform-apply.yml`) hỗ trợ phân tách plan/apply và tự động chuyển dịch lưu lượng qua CodeDeploy.
- Thêm các bài kiểm thử unit test trong `lambda_src/tests/test_ai_runtime_codedeploy.py` kiểm tra tĩnh các cấu hình Terraform.

## Các tệp thay đổi
- Tạo mới:
  - `lambda_src/tests/test_ai_runtime_codedeploy.py`
  - `scripts/start-ai-lambda-codedeploy.ps1`
  - `.github/workflows/sandbox-deploy.yml`
- Sửa đổi:
  - `modules/ai-runtime-lambda/main.tf`
  - `modules/ai-runtime-lambda/variables.tf`
  - `modules/ai-runtime-lambda/outputs.tf`
  - `environments/sandbox/main.tf`
  - `environments/sandbox/outputs.tf`
  - `environments/staging/outputs.tf`
  - `environments/prod/outputs.tf`
  - `.github/workflows/terraform-apply.yml`
  - `docs/GUIDES.md`
  - `docs/GUIDES_vi.md`
  - `lambda_src/tests/test_ai_runtime_codedeploy.py`

## Lệnh xác thực
```powershell
terraform fmt -check -recursive modules/ai-runtime-lambda environments/sandbox
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
Push-Location lambda_src; python -m pytest tests/test_ai_runtime_codedeploy.py; Pop-Location
```

## Kết quả
- `terraform fmt -check -recursive`: Thành công
- `environments/sandbox init`: Thành công
- `environments/sandbox validate`: Thành công
- Các bài kiểm thử Python Lambda: Thành công (xác thực các cấu hình deployment style và sự kiện `DEPLOYMENT_STOP_ON_ALARM`)
- Đã xác thực cấu hình auto-rollback với danh sách sự kiện CodeDeploy Lambda hợp lệ của AWS.

## Khó khăn / Điểm nghẽn
Không có

## Bước tiếp theo
Chạy pipeline phát hành sandbox bằng digest image non-prod để xác minh việc chuyển dịch lưu lượng CodeDeploy và logic tự động hoàn tác E2E.

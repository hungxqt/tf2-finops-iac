# Tiến độ AI Runtime Lambda

## Trạng thái
Hoàn thành (Completed)

## Phạm vi
Triển khai module hạ tầng chạy thực tế dựa trên AWS Lambda Container (`modules/ai-runtime-lambda`) để hosting cho AI Engine phát hiện bất thường, thay thế cho kế hoạch ECS/Fargate cũ đã lỗi thời. Phạm vi bao gồm:
- Kho lưu trữ ECR cho các container image digest bất biến do AIOps cung cấp.
- Hàm AI Engine Request Lambda và Worker Lambda sử dụng package_type = "Image".
- Các Lambda alias ("live"), cấu hình reserved concurrency, log groups, và cấu hình ánh xạ nguồn sự kiện SQS (event source mapping) với tham số max concurrency.
- Tích hợp trực tiếp Step Functions với Request Lambda và trực tiếp truy vấn kết quả (getItem) từ DynamoDB.
- Loại bỏ hoàn toàn các ECS task definition, ECS cluster, service, target groups, và các tài nguyên internal ALB.

## Các file đã thay đổi
- Tạo mới:
  - `modules/ai-runtime-lambda/main.tf`
  - `modules/ai-runtime-lambda/outputs.tf`
  - `modules/ai-runtime-lambda/variables.tf`
  - `modules/ai-runtime-lambda/versions.tf`
- Chỉnh sửa:
  - `environments/sandbox/main.tf`
  - `environments/sandbox/variables.tf`
  - `environments/sandbox/outputs.tf`
  - `environments/staging/main.tf`
  - `environments/staging/variables.tf`
  - `environments/staging/outputs.tf`
  - `environments/prod/main.tf`
  - `environments/prod/variables.tf`
  - `environments/prod/outputs.tf`
  - `modules/networking/main.tf`
  - `modules/networking/outputs.tf`
  - `modules/orchestration/main.tf`
  - `modules/orchestration/outputs.tf`
  - `modules/orchestration/statemachine.json`
  - `modules/observability/main.tf`
  - `lambda_src/tests/test_state_machine.py`
  - `docs/statemachine.json`
  - `scripts/render-static-asl.py`

## Lệnh kiểm tra
```powershell
terraform fmt -check -recursive
terraform -chdir=bootstrap validate
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod validate
tflint --recursive
Push-Location lambda_src; python -m pytest; Pop-Location
trivy config .
checkov -d modules/orchestration --framework terraform
```

## Kết quả
- `terraform fmt -check -recursive`: Thành công
- `bootstrap validate`: Thành công
- `environments/sandbox validate`: Thành công
- `environments/staging validate`: Thành công
- `environments/prod validate`: Thành công
- `tflint --recursive`: Thành công
- Các kiểm tra Python Lambda: Thành công (Vượt qua 37/37 kiểm tra, bao gồm kiểm tra xác thực state machine)

## Vướng mắc
Không có

## Bước tiếp theo
Xác nhận việc triển khai AI runtime dựa trên Lambda Container để phục vụ cho kiểm thử tích hợp (integration testing).

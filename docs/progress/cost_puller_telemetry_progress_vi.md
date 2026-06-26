# Tiến độ Cost Puller Telemetry

## Trạng thái
Hoàn thành (Đã cập nhật hỗ trợ liên tài khoản)

## Phạm vi
Triển khai `lambda_src/src/workers/cost_puller` thành worker thu thập dữ liệu thô (raw telemetry):
- Thêm các lớp wrapper client AWS trong `finops_common` cho S3, Cost Explorer, CloudWatch, và STS với quyền tối thiểu.
- Triển khai quá trình thu thập dữ liệu với tính năng phát hiện độ trễ của CUR (CUR freshness) và tự động chuyển hướng sang Cost Explorer nếu CUR trễ > 36 giờ.
- Triển khai phương án dự phòng sử dụng cache S3 khi Cost Explorer bị throttling, trả về trạng thái `READY` với cờ `stale_cost_explorer = true`.
- Tích hợp thu thập CloudWatch metrics dạng best-effort và thiết lập thứ tự ưu tiên dữ liệu traffic (ALB, CloudFront, API Gateway, và dự phòng Synthetic).
- Sửa lỗi import thư viện boto3 trong quá trình giả định vai trò (assume role) liên tài khoản từ xa và tránh nuốt lỗi lập trình.
- Mở rộng module IAM và các môi trường với tùy chọn triển khai vai trò thu thập số liệu liên tài khoản và danh sách vai trò tin cậy.
- Khai báo và cấu hình các biến CUR và CE vào Terraform module `compute_lambda` và các môi trường sandbox/staging/prod.
- Viết bộ kiểm thử unit test hoàn chỉnh bao gồm các trường hợp delay, throttling, dự phòng, bảo mật tenant, validate đường dẫn bucket S3, giả định vai trò STS thành công/thất bại, và ghi đè client trong session từ xa.
- Cập nhật `normalizer` để hỗ trợ giải nén tệp JSON gzipped thô và lưu trữ kết quả dạng Parquet.

## Các tệp thay đổi
- [lambda_src/src/finops_common/aws_clients.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/aws_clients.py)
- [lambda_src/src/finops_common/__init__.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/__init__.py)
- [lambda_src/src/workers/cost_puller/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/cost_puller/handler.py)
- [lambda_src/src/workers/normalizer/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/normalizer/handler.py)
- [lambda_src/tests/test_cost_puller.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_cost_puller.py)
- [lambda_src/tests/test_normalizer.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_normalizer.py)
- [modules/compute-lambda/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/compute-lambda/variables.tf)
- [modules/compute-lambda/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/compute-lambda/main.tf)
- [environments/sandbox/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/variables.tf)
- [environments/sandbox/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/main.tf)
- [environments/sandbox/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/terraform.tfvars.example)
- [environments/staging/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/variables.tf)
- [environments/staging/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/main.tf)
- [environments/staging/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/terraform.tfvars.example)
- [environments/prod/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/variables.tf)
- [environments/prod/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/main.tf)
- [environments/prod/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/terraform.tfvars.example)

## Câu lệnh xác minh
```powershell
# Chạy bộ kiểm thử unit test Python
Push-Location lambda_src; python -m pytest; Pop-Location

# Xác minh cấu hình Terraform
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod validate
```

## Kết quả
- Toàn bộ unit test Pytest cho các lambda workers đều pass (47 test thành công).
- Xác minh HCL của Terraform thành công cho tất cả các môi trường.

## Khó khăn / Điểm nghẽn
Không

## Bước tiếp theo
Xác minh luồng hoạt động của bộ điều phối Orchestration và thực thi Step Functions.

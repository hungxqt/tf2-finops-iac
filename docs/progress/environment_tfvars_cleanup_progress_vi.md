# Tiến trình Dọn dẹp và Bổ sung Giá trị Mẫu tfvars các Môi trường (Environment tfvars Cleanup)

## Trạng thái
Đã xác thực (tất cả các thư mục gốc đã được init, định dạng và validate thành công; tất cả các bài kiểm tra unit test đều vượt qua)

## Phạm vi
Dọn dẹp và hoàn thiện độ bao phủ (coverage) trong tất cả các tệp `terraform.tfvars.example` để biểu diễn mọi biến được khai báo trong tệp `variables.tf` gốc tương ứng bằng các giá trị mẫu an toàn, không chứa bí mật (non-secret). Nhiệm vụ này áp dụng cho `bootstrap`, `environments/sandbox`, `environments/staging`, và `environments/prod`.

## Thay đổi Chính

### Thư mục Bootstrap (`bootstrap/terraform.tfvars.example`)
- Bổ sung biến `tags` để tài liệu hóa hành vi gắn thẻ mặc định.
- Bổ sung biến `destroyable = false` để tăng tính an toàn của môi trường theo mặc định.

### Các Môi trường (`environments/*/terraform.tfvars.example`)
- Bổ sung các biến bị thiếu trên cấu hình của các môi trường sandbox, staging, và prod:
  - `destroyable`: Xác định tài nguyên có thể bị hủy hay không. Đặt là `true` ở `sandbox` nhưng là `false` ở `staging` và `prod`.
  - `telemetry_member_account_ids`: Được cấu hình với ID tài khoản giả định mẫu `["123456789012"]`.
  - `telemetry_member_role_name`: Được cấu hình với `"cdo-telemetry-ingestion-role"`.
  - `cur_source_bucket_arn`: Được cấu hình với `"arn:aws:s3:::company-cdo-123456789012-telemetry"`.
  - `create_member_telemetry_ingestion_role`: Được cấu hình với `false`.
  - `trusted_cost_puller_role_arns`: Được cấu hình với `[]` (danh sách rỗng để đảm bảo an toàn mặc định khi thiết lập cơ chế ủy quyền).
- Bảo toàn Tính An toàn của Môi trường:
  - Staging/prod bắt buộc phải sử dụng `destroyable = false`.
  - Staging/prod bắt buộc phải duy trì `enable_alb_https = true` để tuân thủ bảo mật.

## Các Tệp Đã Sửa Đổi
- [bootstrap/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/terraform.tfvars.example)
- [environments/sandbox/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/terraform.tfvars.example)
- [environments/staging/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/terraform.tfvars.example)
- [environments/prod/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/terraform.tfvars.example)

## Câu lệnh Xác thực
```powershell
# Định dạng mã nguồn
terraform fmt -check -recursive

# Xác thực tất cả các thư mục gốc
./scripts/validate.ps1
```

# Tiến Độ Cập Nhật IAM Cho Normalizer Truy Cập Nguồn CUR

## Trạng thái
Đã xác thực (tất cả các bài kiểm tra đã vượt qua, xác thực Terraform hoàn tất)

## Phạm vi
Khắc phục lỗi AccessDenied ở môi trường sandbox bằng cách cấp quyền đọc least-privilege cho vai trò (role) Lambda normalizer đối với prefix bucket nguồn CUR/Data Exports được cấu hình. Môi trường staging và production sẽ kế thừa hành vi chính xác này thông qua module dùng chung `modules/iam`.

Các thay đổi chính:
- Thêm quyền `s3:ListBucket` có điều kiện trên `var.cur_source_bucket_arn` bên trong tài liệu chính sách `normalizer` tại `modules/iam/main.tf`.
- Thêm quyền `s3:GetObject` và `s3:HeadObject` có điều kiện trên các prefix CUR được phân phạm vi theo tài khoản thành viên (member-account scoped) hoặc prefix dự phòng `cur_source_prefix` / bucket-wide.
- Viết kiểm thử hồi quy tại `lambda_src/tests/test_iam_cur_source_policy.py`.

## Các tệp đã thay đổi
- [modules/iam/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/iam/main.tf) - Cập nhật `data.aws_iam_policy_document.normalizer` để cấp quyền truy cập bucket nguồn CUR và các prefix tương ứng.
- [lambda_src/tests/test_iam_cur_source_policy.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_iam_cur_source_policy.py) - Thêm kiểm thử hồi quy xác thực cấu trúc và điều kiện của chính sách normalizer.

## Các lệnh xác thực
Tất cả các bước xác thực đã được thực hiện thành công:

```powershell
# Kiểm tra định dạng
terraform fmt -check -recursive modules/iam

# Xác thực cấu hình Terraform (Sandbox)
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate

# Xác thực cấu hình Terraform (Staging)
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate

# Chạy bộ kiểm thử pytest
python -m pytest tests/test_iam_cur_source_policy.py tests/test_normalizer_cur2.py tests/test_cost_puller_cur2.py

# Chạy kiểm tra bảo mật
trivy config modules/iam
checkov -d modules/iam --framework terraform
```

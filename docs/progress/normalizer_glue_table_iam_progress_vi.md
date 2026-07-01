# Tiến Độ IAM Cho Bảng Glue Athena Của Normalizer

## Trạng thái
Đã xác thực (tất cả các bài kiểm tra đã vượt qua, xác thực Terraform hoàn tất)

## Phạm vi
Khắc phục lỗi `TABLE_NOT_FOUND` đối với Lambda normalizer bằng cách cập nhật các tài liệu chính sách (policy) và ranh giới quyền (boundary) IAM. Trước đây, vai trò normalizer và ranh giới quyền của nó chỉ cho phép đọc siêu dữ liệu Glue cho bảng `cur_data_table_arn` (bảng được ánh xạ cho dữ liệu chi phí đã tinh lọc - curated cost data). Thay đổi này tổng quát hóa giao diện để chấp nhận một danh sách các ARN bảng (`glue_table_arns`) và cấu hình các môi trường để truyền vào ARN của bảng CUR thô (`raw_cur_table_arn`) - là bảng đích mà normalizer truy vấn.

Các thay đổi chính:
- Thay thế biến đầu vào scalar `cur_data_table_arn` bằng danh sách chuỗi `glue_table_arns` trong module `iam`.
- Cập nhật ranh giới quyền `boundary` và tài liệu chính sách `normalizer` để cấp quyền truy cập vào tất cả các ARN bảng được chỉ định trong `var.glue_table_arns` cho các hành động `glue:GetDatabase`, `glue:GetTable`, và `glue:GetPartitions`.
- Cấu hình các thư mục gốc của môi trường sandbox, staging, và production để truyền `glue_table_arns = [module.lakehouse.raw_cur_table_arn]` vào module `iam`.
- Loại bỏ tham số cũ `cur_data_table_arn` khỏi các khai báo module `iam` ở cấp môi trường.
- Viết các bài kiểm thử hồi quy trong `lambda_src/tests/test_iam_cur_source_policy.py` để đảm bảo việc truyền và sử dụng `glue_table_arns` là chính xác và không còn tham chiếu nào tới `cur_data_table_arn`.

## Các tệp đã thay đổi
- [modules/iam/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/iam/variables.tf) - Thay thế biến `cur_data_table_arn` bằng `glue_table_arns`.
- [modules/iam/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/iam/main.tf) - Cập nhật chính sách `boundary` và `normalizer` để cấp quyền bằng cách sử dụng `var.glue_table_arns`.
- [environments/sandbox/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/main.tf) - Cập nhật liên kết module `iam` để truyền `glue_table_arns = [module.lakehouse.raw_cur_table_arn]`.
- [environments/staging/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/main.tf) - Cập nhật liên kết module `iam` để truyền `glue_table_arns = [module.lakehouse.raw_cur_table_arn]`.
- [environments/prod/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/main.tf) - Cập nhật liên kết module `iam` để truyền `glue_table_arns = [module.lakehouse.raw_cur_table_arn]`.
- [lambda_src/tests/test_iam_cur_source_policy.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_iam_cur_source_policy.py) - Thêm kiểm thử hồi quy xác thực các biến IAM và môi trường đã cập nhật.

## Các lệnh xác thực
Tất cả các bước xác thực đã được thực hiện thành công:

```powershell
# Kiểm tra định dạng
terraform fmt -check -recursive

# Xác thực cấu hình Terraform (Sandbox)
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate

# Xác thực cấu hình Terraform (Staging)
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate

# Xác thực cấu hình Terraform (Production)
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate

# Chạy bộ kiểm thử pytest
python -m pytest tests/test_iam_cur_source_policy.py tests/test_normalizer_cur2.py tests/test_normalizer.py -v
```

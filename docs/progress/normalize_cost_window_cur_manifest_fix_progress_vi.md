# Tiến Độ Sửa Lỗi Manifest CUR Cho NormalizeCostWindow

## Trạng thái
Đã xác thực (tất cả kiểm thử đơn vị đã vượt qua, xác thực Terraform hoàn tất, kiểm thử Terraform module thành công)

## Phạm vi
- Xác thực các cột trong CUR manifest dựa theo Telemetry Contract (line_item_usage_start_date, line_item_usage_account_id, line_item_product_code, line_item_usage_type, line_item_usage_amount, pricing_unit, line_item_unblended_cost, resource_tags_user_environment).
- Hỗ trợ chuẩn hóa định dạng các cột (dạng chuỗi, dạng dict với các khóa 'name', 'ColumnName', hoặc 'columnName').
- Lan truyền lỗi `ContractMismatchError` để dừng sớm (fail-fast) trong quá trình cost pulling và normalization nếu cột không hợp lệ.
- Thêm tài nguyên bảng raw CUR database trong module lakehouse để tách biệt dữ liệu thô (raw) và dữ liệu tinh chỉnh (curated).
- Cấu hình biến môi trường `GLUE_TABLE_NAME` của normalizer trỏ tới tên bảng Glue raw.

## Các tệp đã thay đổi
- [lambda_src/src/finops_common/utils.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/utils.py) - Thêm hàm xác thực `validate_manifest_columns`.
- [lambda_src/src/finops_common/__init__.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/__init__.py) - Công khai hàm `validate_manifest_columns` trong các export của gói.
- [lambda_src/src/workers/cost_puller/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/cost_puller/handler.py) - Gọi hàm `validate_manifest_columns` khi đọc manifest và cho phép lan truyền ngoại lệ.
- [lambda_src/src/workers/normalizer/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/normalizer/handler.py) - Gọi hàm `validate_manifest_columns` ở cả phần sinh câu truy vấn SQL động cục bộ và phần phân tách manifest.
- [modules/lakehouse/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/lakehouse/main.tf) - Thêm bảng Glue Catalog Table `raw_cur_data`.
- [modules/lakehouse/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/lakehouse/outputs.tf) - Xuất các output `raw_cur_table_name` và `raw_cur_table_arn`.
- [modules/lakehouse/lakehouse.tftest.hcl](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/lakehouse/lakehouse.tftest.hcl) - Thêm xác nhận (assertion) cho `raw_cur_data` và sửa đổi xác nhận cho bucket policy khớp với chính sách đường dẫn đơn giản thực tế.
- [environments/sandbox/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/main.tf) - Cấu hình tham số `cur_data_table_name` của compute-lambda trỏ sang output tên bảng raw CUR.
- [environments/staging/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/main.tf) - Cấu hình tham số `cur_data_table_name` và các đầu vào Athena của compute-lambda trỏ sang tên bảng raw CUR và các output tương ứng.
- [environments/prod/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/main.tf) - Cấu hình tham số `cur_data_table_name` và các đầu vào Athena của compute-lambda trỏ sang tên bảng raw CUR và các output tương ứng.
- [lambda_src/tests/test_cost_puller_cur2.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_cost_puller_cur2.py) - Thêm kiểm thử đơn vị `test_cost_puller_rejects_missing_required_column`.
- [lambda_src/tests/test_normalizer_cur2.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_normalizer_cur2.py) - Thêm kiểm thử đơn vị `test_normalizer_rejects_missing_column_manifest` và `test_build_dynamic_select_fields_valid_and_optional_columns`.
- [docs/GUIDES.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES.md) - Tài liệu hóa các điều kiện tiên quyết của thẻ/cột trong AWS Data Export.
- [docs/GUIDES_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES_vi.md) - Tài liệu hóa các điều kiện tiên quyết của thẻ/cột trong AWS Data Export (bản dịch tiếng Việt).

## Các lệnh xác thực
```powershell
python -m pytest tests/test_cost_puller_cur2.py tests/test_normalizer_cur2.py tests/test_normalizer.py
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod validate
cd modules/lakehouse; terraform test
```

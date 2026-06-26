# Tiến độ tích hợp Glue Catalog Schema & Partition Projection

## Trạng thái
Hoàn thành

## Phạm vi công việc
Triển khai các schema trong Glue Catalog cho dữ liệu chi phí đã tinh lọc (curated cost data) và các bản ghi kiểm toán ngăn chặn (containment audit records) sử dụng Athena Partition Projection, không phụ thuộc vào Glue Crawler. Đồng bộ các worker lambda và cập nhật các kịch bản kiểm thử/xác thực.

## Các file đã thay đổi
- [modules/lakehouse/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/lakehouse/main.tf) (Chỉnh sửa: Thêm tài nguyên aws_glue_catalog_table cho cur_data và containment_audit)
- [modules/lakehouse/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/lakehouse/outputs.tf) (Chỉnh sửa: Thêm outputs cho tên bảng và bản đồ cơ sở dữ liệu/bảng)
- [environments/sandbox/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/outputs.tf) (Chỉnh sửa: Lan truyền output glue_catalog_tables)
- [environments/staging/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/outputs.tf) (Chỉnh sửa: Lan truyền output glue_catalog_tables)
- [environments/prod/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/outputs.tf) (Chỉnh sửa: Lan truyền output glue_catalog_tables)
- [lambda_src/requirements.txt](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/requirements.txt) (Chỉnh sửa: Thêm dependency pyarrow)
- [lambda_src/src/workers/normalizer/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/normalizer/handler.py) (Chỉnh sửa: Cập nhật đường dẫn đầu ra bao gồm account_id và phân vùng theo year/month, xuất ra dữ liệu định dạng Parquet thật bằng pyarrow)
- [lambda_src/src/workers/audit_writer/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/audit_writer/handler.py) (Chỉnh sửa: Cập nhật đường dẫn đầu ra phân vùng theo account_id/year/month, bao gồm tất cả các trường metadata bắt buộc và điểm kiểm toán số học)
- [lambda_src/tests/test_normalizer.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_normalizer.py) (Chỉnh sửa: Cập nhật xác nhận đường dẫn, đọc dữ liệu Parquet bằng pyarrow, và xác thực các trường schema)
- [lambda_src/tests/test_audit_writer.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_audit_writer.py) (Chỉnh sửa: Cập nhật xác nhận đường dẫn, kiểm tra các thuộc tính kiểm toán mới trong JSON)
- [scripts/athena_validation.sql](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/scripts/athena_validation.sql) (Tạo mới: Thêm Athena DDL khớp với schema và cấu hình projection)
- [modules/lakehouse/lakehouse.tftest.hcl](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/lakehouse/lakehouse.tftest.hcl) (Tạo mới: Thêm các kiểm thử xác thực Terraform)
- [docs/GUIDES.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES.md) (Chỉnh sửa: Thêm phần hướng dẫn Xác thực Glue Schema & Partition Projection)
- [docs/GUIDES_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES_vi.md) (Chỉnh sửa: Thêm phần hướng dẫn Xác thực Glue Schema & Partition Projection)

## Các lệnh xác thực đã chạy
- Xác thực cấu hình sandbox: `terraform -chdir=environments/sandbox validate` (Thành công)
- Xác thực cấu hình staging: `terraform -chdir=environments/staging validate` (Thành công)
- Xác thực cấu hình prod: `terraform -chdir=environments/prod validate` (Thành công)
- Chạy kiểm thử Terraform: `terraform test` bên trong `modules/lakehouse` (Thành công)
- Chạy unit tests cho các python workers: `python -m pytest` bên trong `lambda_src` (Thành công)
- Quét Trivy: `trivy config modules/lakehouse` (Sạch)
- Quét Checkov: `checkov -d modules/lakehouse --framework terraform` (Sạch cho các bảng mới)

## Kết quả đạt được
- Thêm các bảng ngoại vi `cur_data` và `containment_audit` với tính năng Athena Partition Projection được bật.
- Đầu ra của normalizer tương thích với cấu trúc phân vùng mới, xuất ra định dạng bytes Parquet thật.
- Đầu ra của audit writer phân vùng theo account_id và execution date, ghi lại thông tin chi tiết đầy đủ bao gồm điểm số kiểm toán số học.
- Tất cả các kiểm thử Terraform và python unit tests chạy và vượt qua thành công.

## Khó khăn / Điểm nghẽn
Không có

## Bước tiếp theo
Tích hợp với các quy trình triển khai tự động liên tục (CD pipeline).

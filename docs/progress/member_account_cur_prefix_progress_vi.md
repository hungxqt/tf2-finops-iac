# Tiến trình Cấu hình Prefix CUR theo Tài khoản Thành viên

Tài liệu này theo dõi tiến trình sửa lỗi tìm kiếm manifest CUR 2.0 theo prefix tài khoản thành viên và sửa lỗi dimension trong chế độ dự phòng Cost Explorer (CE).

## Tóm tắt Tiến trình

- **Đã hoàn thành**: Sửa lỗi tìm kiếm manifest CUR 2.0 để hỗ trợ prefix riêng cho từng tài khoản: `s3://<cur_source_bucket>/<account_id>/<cur_export_name>/metadata/BILLING_PERIOD=YYYY-MM/<cur_export_name>-Manifest.json`.
- **Đã hoàn thành**: Tạo `CUR_EXPORTS_JSON` tự động từ `telemetry_member_account_ids` và `cur_export_name` tại mỗi thư mục gốc môi trường để tránh sai lệch cấu hình thủ công.
- **Đã hoàn thành**: Cập nhật IAM policy, S3 bucket policy và lifecycle configuration để giới hạn quyền trong các prefix của tài khoản thành viên được tạo ra.
- **Đã hoàn thành**: Sửa lỗi dimension khi chạy dự phòng Cost Explorer bằng cách chỉ truy vấn 2 dimension (`LINKED_ACCOUNT`, `SERVICE`) và chuẩn hóa region về `"global"`.
- **Đã hoàn thành**: Thêm các test case kiểm tra định dạng tạo khóa manifest, cấu hình đa tài khoản với bucket tùy chỉnh (`tf2-finops-cur-export-bucket-2`), từ chối tài khoản sự kiện chưa cấu hình, và hoạt động dự phòng CE.
- **Đã hoàn thành**: Sửa lỗi S3 bucket policy cho CUR data export để cho phép BCM Data Exports ghi từ tất cả các tài khoản telemetry member được cấu hình và thực thi xác thực ID tài khoản 12 chữ số.
- **Đã hoàn thành**: Triển khai plan-mode regression test cho S3 bucket policy source accounts, SourceArns, và prefixes.

## Chi tiết các Thay đổi

### Các Lambda Worker
- **Cost Puller** (`lambda_src/src/workers/cost_puller/handler.py`):
  - Từ chối các tài khoản sự kiện không có trong cấu hình nếu `CUR_EXPORTS_JSON` có giá trị.
  - Phân tích và trả về `allowed_raw_prefix` trong kết quả chi tiết.
  - Kiểm tra tính hợp lệ của các tệp dữ liệu manifest dựa trên bucket cấu hình (thay vì bucket cứng).
  - Gọi Cost Explorer chỉ với 2 dimension (LINKED_ACCOUNT, SERVICE) và đặt region mặc định là `"global"`.
- **Normalizer** (`lambda_src/src/workers/normalizer/handler.py`):
  - Lấy `allowed_raw_prefix` từ `ingestion.details`.
  - Kiểm tra tính hợp lệ của các tệp dữ liệu dựa trên tên bucket được phân tích từ URI manifest S3.

### Hạ tầng (Terraform)
- **Lakehouse Module** (`modules/lakehouse`):
  - Khai báo các biến `cur_export_name` và `telemetry_member_account_ids`.
  - Cập nhật `aws_s3_bucket_lifecycle_configuration.cur_export` để xóa các tệp cũ theo prefix của từng tài khoản.
  - Sửa statement `AllowBCMDataExportsPut` của bucket policy để hỗ trợ nhiều source accounts và SourceArns được sinh ra từ một local mới `cur_data_export_source_account_ids`.
  - Tránh phụ thuộc vào computed value bằng cách tham chiếu đến ARN S3 bucket được cấu hình tĩnh thông qua local `cur_export_bucket_arn`.
  - Thêm validation cho biến `telemetry_member_account_ids` yêu cầu định dạng AWS account ID phải có 12 chữ số.
- **IAM Module** (`modules/iam`):
  - Khai báo biến `cur_export_name`.
  - Giới hạn tài nguyên trong `AllowCURSourceGet` và `AllowMemberCURGet` về các prefix được tạo ra cho tài khoản thành viên khi có cấu hình `telemetry_member_account_ids`.
- **Các Môi trường** (`sandbox`, `staging`, `prod`):
  - Đồng bộ các biến `cur_export_name`, `cur_exports_json`, `create_cur_export_bucket`, `cur_export_bucket_name`, và `cur_raw_prefix`.
  - Tạo động `local.cur_exports_json` và truyền vào `compute_lambda`.
  - Truyền `cur_export_name` và `telemetry_member_account_ids` vào các module `lakehouse` và `iam`.

### Các Kiểm thử (Tests)
- **Cost Puller Tests** (`lambda_src/tests/test_cost_puller_cur2.py` & `test_cost_puller.py`):
  - Kiểm thử định dạng tạo khóa manifest.
  - Kiểm thử cấu hình đa tài khoản và xác thực trên bucket tùy chỉnh `tf2-finops-cur-export-bucket-2`.
  - Kiểm thử từ chối tài khoản sự kiện chưa được cấu hình.
  - Kiểm thử dimension dự phòng CE và chuẩn hóa region về `"global"`.
- **Normalizer Tests** (`lambda_src/tests/test_normalizer_cur2.py`):
  - Kiểm thử việc chấp nhận prefix tài khoản hợp lệ và từ chối prefix không khớp.
- **Terraform Integration Tests** (`modules/lakehouse/lakehouse.tftest.hcl`):
  - Thêm plan-mode regression test `validate_cur_export_policy_with_members` để kiểm thử xem policy được sinh ra có tự động ánh xạ các biến source account hay không, có giới hạn resource theo định dạng `${account_id}/${var.cur_export_name}/*` hay không, và có giới hạn chính xác điều kiện Condition hay không.

## Kiểm tra Xác thực
- Pytest: 363 bài test đã vượt qua thành công.
- Terraform test: Bộ kiểm thử module chạy thành công với bài test `validate_cur_export_policy_with_members`.
- Terraform validate: Cấu hình Sandbox, Staging, và Prod hợp lệ.
- Kiểm tra tĩnh: Trivy và Checkov đã vượt qua thành công.


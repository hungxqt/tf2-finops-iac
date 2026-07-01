# Tiến độ: Sửa lỗi Đọc Dữ liệu Replay CUR qua Athena

Đã khắc phục lỗi đọc dữ liệu giả lập CUR qua Athena bằng cách đồng bộ hóa cấu trúc bảng Glue thô (raw CUR table projection), các điều kiện truy vấn SQL Athena trong normalizer, schema của Parquet sinh ra, và payload khởi chạy replay.

## Các Thành phần đã Triển khai

1. **Nâng cấp Cấu trúc Bảng Glue Catalog (`modules/lakehouse/main.tf`)**:
   - Thêm hỗ trợ cho chế độ phân vùng tài khoản thành viên (member-account partitioning mode).
   - Khi cấu hình các tài khoản thành viên qua `telemetry_member_account_ids`, bảng CUR thô (`raw_cur_data`) sẽ tự động thêm `source_account_id` làm khóa phân vùng đầu tiên, theo sau bởi `billing_period`.
   - Tiền tố lưu trữ động được cập nhật thành: `s3://${local.cur_export_bucket_name}/$${source_account_id}/${var.cur_export_name}/data/BILLING_PERIOD=$${billing_period}/`.
   - Xuất output `cur_raw_account_partition_key` đại diện cho khóa phân vùng thành viên.

2. **Cấu hình Biến môi trường Compute Lambda (`modules/compute-lambda/main.tf` & `environments/*`)**:
   - Thêm biến `cur_raw_account_partition_key` vào module compute-lambda.
   - Cấu hình biến môi trường `CUR_RAW_ACCOUNT_PARTITION_KEY` cho Lambda normalizer.
   - Liên kết các môi trường (`sandbox`, `staging`, `prod`) để chuyển giá trị khóa phân vùng từ output của module lakehouse.

3. **Thắt chặt Bảo mật Truy vấn SQL Athena trong Normalizer (`normalizer/handler.py`)**:
   - Cập nhật công thức tạo câu lệnh SQL để luôn lọc theo `billing_period = '<YYYY-MM>'`.
   - Tự động chèn thêm điều kiện `source_account_id = '<12-digit-account-id>'` khi cấu hình khóa phân vùng tài khoản thành viên đang bật.
   - Giữ nguyên các bộ lọc khoảng thời gian timestamp dạng typed half-open.
   - Tăng cường bảo mật bằng cách kiểm tra regex nghiêm ngặt đối với tất cả các chuỗi SQL được chèn vào (`billing_period`, `account_id`, `start_ts`, `end_ts`).
   - Loại bỏ việc ghi log chi tiết các dòng dữ liệu CUR thô để ngăn chặn rò rỉ thông tin nhạy cảm.

4. **Sửa đổi các Script Chạy Replay (`scripts/prepare_replay.py` & `scripts/run_replay.py`)**:
   - Cập nhật `prepare_replay.py` để ghi các cột timestamp của CUR (`bill_billing_period_start_date`, `line_item_usage_start_date`, `line_item_usage_end_date`) dưới dạng kiểu dữ liệu `timestamp` của PyArrow (`pa.timestamp('us')`) thay vì kiểu chuỗi (string), đảm bảo khớp với kiểu dữ liệu trong Glue catalog.
   - Cập nhật `run_replay.py` để gửi payload khởi chạy Step Functions có `execution_date` chỉ chứa ngày (`YYYY-MM-DD`) và bao gồm cả `billing_period` (`YYYY-MM`).

5. **Cập nhật Tài liệu & Hướng dẫn**:
   - Cập nhật các tệp `docs/GUIDES.md`, `docs/GUIDES_vi.md`, `docs/synthetic_replay_instructions.md`, và `docs/synthetic_replay_instructions_vi.md` để phản ánh đúng cấu trúc đường dẫn S3 thành viên chuẩn mực và định dạng payload chỉ chứa ngày mới.

## Xác minh bằng Kiểm thử
- Thêm kiểm thử trong `modules/lakehouse/lakehouse.tftest.hcl` để xác minh các khóa phân vùng bảng CUR thô và cấu trúc lưu trữ khi bật chế độ member mode.
- Thêm ca kiểm thử hồi quy `test_normalizer_athena_member_account_mode_query` trong `lambda_src/tests/test_normalizer_cur2.py` để kiểm tra câu lệnh SQL Athena được tạo ra có chứa đúng các điều kiện `source_account_id` và `billing_period`.

# Tiến độ: Tích hợp Replay Dữ liệu Giả lập

Đã tích hợp bộ điều phối thử nghiệm (replay) dữ liệu chi phí lịch sử giả lập chỉ dành cho sandbox để hỗ trợ các kịch bản backtest (smoke, warmup, và full-backtest) trên dữ liệu lịch sử 3 tháng.

## Các thành phần đã triển khai

1. **Script Chuẩn bị dữ liệu (`scripts/prepare_replay.py`)**:
   - Đọc các tệp CSV giả lập độ phân giải cao (`cur_line_items.csv`, `cost_explorer_daily.csv`, và `anomaly_labels_public.csv`).
   - Chuyển đổi dữ liệu CUR thành định dạng Parquet CUR 2.0 phân vùng theo tháng.
   - Tạo tệp manifest metadata CUR 2.0 tương ứng trỏ tới các tệp Parquet.
   - Tạo dữ liệu ngữ cảnh lưu lượng business/traffic (ALB RequestCount) và hiệu năng CPU cho các tài nguyên EC2.
   - Ánh xạ tất cả ID tài khoản giả lập về ID tài khoản sandbox thực tế của bạn, đồng thời giữ nguyên tên/tag gốc trong metadata.
   - Tải các tệp dữ liệu CUR, manifest và tệp `business_context.json` tổng hợp lên các S3 bucket sandbox sử dụng mã hóa KMS.

2. **Script Runner Replay (`scripts/run_replay.py`)**:
   - Ghi cấu hình tài khoản sandbox vào bảng DynamoDB `account-policy`.
   - Kích hoạt chạy Step Functions tuần tự theo từng ngày chi phí.
   - Tự động theo dõi (poll) trạng thái chạy của Step Functions cho đến khi hoàn thành và hiển thị thống kê.
   - Hỗ trợ các chế độ chạy `--mode smoke` (3 ngày), `--mode warmup` (20 ngày), và `--mode full` (92 ngày).

3. **Cập nhật mã nguồn Lambda Worker (`cost_puller/handler.py`)**:
   - Thêm hỗ trợ chế độ replay qua biến môi trường `SYNTHETIC_REPLAY_ENABLED` và `SYNTHETIC_REPLAY_BUSINESS_CONTEXT_URI`.
   - Khi được bật, tự động nạp dữ liệu lưu lượng/hiệu năng từ tệp business context đã chuẩn bị trên S3 thay vì gọi API CloudWatch thực tế, tránh việc bị hạ điểm chất lượng telemetry dẫn đến dry-run bắt buộc.
   - Khi CUR bị trễ, tự động nạp dữ liệu CE từ tệp business context thay vì gọi API Cost Explorer thực tế của AWS.

4. **Các chốt chặn an toàn Terraform (`compute-lambda/variables.tf`, `sandbox/main.tf`)**:
   - Thêm các biến `synthetic_replay_enabled` và `synthetic_replay_business_context_uri`.
   - Thêm quy tắc validation trong module đảm bảo `synthetic_replay_enabled` chỉ có thể đặt thành `true` khi `environment == "sandbox"`. Mọi hành vi cố tình bật chế độ này ở staging hoặc prod sẽ bị Terraform từ chối khi thực hiện plan/validate.

5. **Tài liệu & Hướng dẫn vận hành**:
   - Cập nhật hướng dẫn vận hành chi tiết trong `docs/GUIDES.md` và `docs/GUIDES_vi.md`.

## Kết quả kiểm thử
- Thêm mới các unit test trong `lambda_src/tests/test_synthetic_replay.py` kiểm thử các luồng CUR ready/delayed của cost_puller khi bật chế độ replay.
- Chạy thành công bộ test `pytest`, tất cả 379 test đều pass.

# Tiến độ: Kế hoạch Trình lập lịch Quản trị với các Tài khoản Mục tiêu Phân tích Rõ ràng

Tài liệu này ghi nhận quá trình triển khai kế hoạch hỗ trợ phân tích nhiều tài khoản liên kết (explicit analysis targets).

## 1. Kết quả Đạt được

- **Biến trong Module Orchestration**: Thêm biến `analysis_target_account_ids` (`list(string)`) vào module orchestration.
- **Tích hợp Môi trường**: Cấu hình truyền biến này từ `var.telemetry_member_account_ids` tại tất cả các thư mục gốc môi trường (`sandbox`, `staging`, `prod`).
- **Tài nguyên Xác thực**: Tạo tài nguyên `terraform_data.config_validation` trong `modules/orchestration/main.tf` để kích hoạt lỗi xác thực Terraform nếu scheduler được bật (`scheduler_enabled = true`) nhưng danh sách tài khoản phân tích rỗng.
- **Dữ liệu Đầu vào EventBridge Scheduler**: Cập nhật dữ liệu đầu vào (target input) từ một `account_id` đơn lẻ thành:
  - `management_account_id`: AWS Account ID của tài khoản quản trị thực thi.
  - `analysis_targets`: Lấy từ `var.analysis_target_account_ids`.
- **Lồng ghép State Machine**:
  - Lồng toàn bộ logic chạy cho từng tài khoản vào một trạng thái Map mới `ProcessAnalysisTargets` (chạy tuần tự với `MaxConcurrency = 1`).
  - Khối Item Selector ánh xạ động `account_id` từ `$$.Map.Item.Value.account_id` trong khi vẫn bảo toàn đầy đủ các thông tin ngữ cảnh thực thi (`run_id`, `correlation_id`, `cost_period`, `execution_date`, cơ chế retry, và cờ dry-run).
  - Giữ nguyên trạng thái Map cấp độ bất thường `ProcessDetectedAnomalies` bên trong.
- **Nâng cấp State Lambda**:
  - Cập nhật hàm xử lý `prepare` của state Lambda để chuẩn hóa các tài khoản mục tiêu phân tích (chấp nhận cả danh sách chuỗi lẫn dict) và xác thực chạy tự động.
  - Fail closed các lượt chạy tự động thiếu tài khoản đích bằng cách ném ra lỗi ValueError.
  - Triển khai cơ chế tự động chuyển đổi từ một `account_id` đơn lẻ sang `analysis_targets` cho các lượt chạy thủ công để đảm bảo khả năng tương thích ngược.
- **Củng cố Bộ Kiểm thử**:
  - Thêm các kiểm thử đơn vị cho chạy tự động đa tài khoản, chạy thủ công tương thích ngược và kiểm tra lỗi xác thực.
  - Cập nhật các kiểm thử hợp đồng ASL và kiểm thử reachability cho cấu trúc lồng mới.
- **Cập nhật Tài liệu**:
  - Cập nhật hướng dẫn `ACCOUNT_POLICY_SEEDING_vi.md` và `GUIDES_vi.md` để yêu cầu người vận hành seed dữ liệu policy cho tất cả các phân tích tài khoản liên kết đích, thay vì chỉ mỗi tài khoản quản trị.

## 2. Trạng thái hiện tại

- **Trạng thái**: Hoàn thành / 100% Thành công.
- **Kiểm thử**: Tất cả 341 bài test đều vượt qua thành công.

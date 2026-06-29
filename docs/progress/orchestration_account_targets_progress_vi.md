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

- **Trạng thái**: Hoàn thành / 100% Thành công.
- **Kiểm thử**: Tất cả 346 bài test đều vượt qua thành công.

## 3. Sửa lỗi Lan truyền Ngữ cảnh Tenant (Tenant Context Propagation)

- **Nguyên nhân Gốc rễ**: Trạng thái Map trong Step Functions đã không truyền trường `tenant_id` vào ngữ cảnh (context) của từng mục (item) tài khoản liên kết. Do đó, các trạng thái như `CheckErrorBudgetLock` (vốn phụ thuộc vào `$.tenant_id`) đã gặp lỗi truy vấn JSONPath vì `tenant_id` bị thiếu trong phạm vi của item hoặc bị đọc sai từ tenant của tài khoản quản trị gốc thay vì tài khoản liên kết cụ thể.
- **Các Tệp thay đổi**:
  - `lambda_src/src/workers/state/handler.py`: Cập nhật chuẩn hóa mục tiêu để nhúng `tenant_id` (chỉ định sẵn hoặc suy diễn tự động qua `_default_tenant_id(account_id)`) cho mỗi phân tích tài khoản mục tiêu, tránh broadcast tenant_id quản trị sang tài khoản liên kết.
  - `modules/orchestration/statemachine.json`: Thêm `tenant_id.$ = $$.Map.Item.Value.tenant_id` vào `ProcessAnalysisTargets.ItemSelector` và truyền nó vào `CheckRunState`.
  - `docs/statemachine.json`: Kết xuất lại từ kịch bản render.
  - `lambda_src/tests/test_state.py` & `test_state_machine.py`: Thêm kiểm thử hồi quy xác nhận độc lập tenant theo tài khoản, ánh xạ chạy thủ công tương thích ngược, và kiểm thử độ phân giải tham số ASL.
- **Lệnh Xác thực**:
  - `python scripts/render-static-asl.py`
  - `terraform fmt -check -recursive`
  - `terraform -chdir=environments/sandbox init -backend=false`
  - `Push-Location lambda_src; python -m pytest; Pop-Location`
- **Kết quả**: Tất cả 346 bài kiểm thử đều vượt qua thành công. Xác thực Terraform hoàn tất. File JSON của State machine được xuất chính xác.
- **Bước tiếp theo**: Triển khai các thay đổi thông qua quy trình CI/CD Terraform vào các môi trường sandbox/staging/prod, và chạy kiểm thử để xác thực tích hợp đầu cuối.


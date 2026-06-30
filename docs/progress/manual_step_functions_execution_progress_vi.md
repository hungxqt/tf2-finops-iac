# Tiến độ Hướng dẫn Vận hành Chạy Thủ công Step Functions

## Trạng thái
COMPLETED

## Phạm vi
Triển khai tài liệu hướng dẫn vận hành song ngữ (bilingual) để kích hoạt thủ công, theo dõi và gỡ lỗi quy trình Orchestrator Step Functions cho Task Force 2 - FinOps Watch.

## Các file đã thay đổi
| File | Hành động | Mục đích |
| --- | --- | --- |
| [MANUAL_STEP_FUNCTIONS_EXECUTION.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/MANUAL_STEP_FUNCTIONS_EXECUTION.md) | Khởi tạo | Tài liệu hướng dẫn vận hành tiếng Anh chứa các điều kiện tiên quyết, phương pháp truy vấn State Machine ARN, lệnh PowerShell, payload đầu vào và ranh giới an toàn. |
| [MANUAL_STEP_FUNCTIONS_EXECUTION_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/MANUAL_STEP_FUNCTIONS_EXECUTION_vi.md) | Khởi tạo | Bản dịch tiếng Việt tương ứng, giữ nguyên các tham số kỹ thuật và câu lệnh. |
| [GUIDES.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES.md) | Sửa đổi | Bổ sung liên kết hướng dẫn tại Mục 3.3 dưới phần Post-Deployment GitOps Handoff. |
| [GUIDES_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES_vi.md) | Sửa đổi | Bổ sung liên kết hướng dẫn tại Mục 3.3 bằng tiếng Việt dưới phần Post-Deployment GitOps Handoff. |

## Lệnh kiểm tra
```powershell
# Xác thực sự tồn tại của tài liệu và các từ khóa chính
rg -n "MANUAL_STEP_FUNCTIONS_EXECUTION|start-execution|account-policy|analysis_targets" docs

# Kiểm tra định dạng Git diff
git diff --check

# Chạy xác thực bộ test Python pytest cục bộ
Push-Location lambda_src; python -m pytest tests/test_state.py tests/test_scheduler_configuration.py -q -p no:cacheprovider; Pop-Location
```

## Kết quả
- **Tài liệu hướng dẫn song ngữ**: Khởi tạo thành công tài liệu hướng dẫn vận hành tiếng Anh và tiếng Việt cho việc chạy thủ công Step Functions, đồng thời cập nhật các tài liệu này sử dụng payload đầu vào dạng phẳng (flat payloads) chuẩn hóa.
- **Tương thích ngược Double-Wrap**: Cải tiến `PrepareRunContext` để tự động unwrap một lớp bọc cũ `{ "operation": "prepare", "input": { "operation": "prepare", "input": { ... } } }`, tránh các lỗi "Scheduled run contains no analysis targets".
- **Độ bao phủ kiểm thử (Test Coverage)**: Bổ sung ca kiểm thử chi tiết trong `lambda_src/tests/test_state.py` cho cấu trúc payload double-wrapped cũ.
- **Tài liệu hóa điều kiện tiên quyết**: Nêu rõ yêu cầu về triển khai môi trường, quyền CLI, trạng thái scheduler, các hàm Lambda hoạt động, seed dữ liệu DynamoDB và sự sẵn sàng của dữ liệu telemetry.
- **Cung cấp câu lệnh**: Hướng dẫn chi tiết cách dùng Terraform Output và AWS CLI để truy vấn ARN, tạo file payload, kích hoạt lượt chạy, theo dõi trạng thái và kiểm tra nhật ký chạy.
- **Mẫu Payload**: Cung cấp cấu trúc file JSON đầu vào cho cả chế độ chạy đơn tài khoản và đa tài khoản.
- **Làm rõ ranh giới an toàn**: Làm rõ hạn chế của hệ thống khi tham số `force_dry_run` truyền thủ công bị hàm `PrepareRunContext` ghi đè/đặt lại về `False`, nhấn mạnh tính an toàn dựa trên khóa ngân sách lỗi (error budget lock), chất lượng dữ liệu telemetry, chính sách tài khoản DynamoDB và rào chắn của containment worker.
- **Liên kết tài liệu**: Đã cập nhật liên kết trong cả hai tài liệu hướng dẫn phát triển chính.
- **Bộ kiểm thử (Tests)**: Bộ kiểm thử Python pytest liên quan chạy thành công 100%.

## Vướng mắc
Không có.

## Bước tiếp theo
Nhà vận hành có thể bắt đầu sử dụng tài liệu vận hành này để chạy thử nghiệm và xác minh trên môi trường sandbox hoặc staging bằng payload dạng phẳng gọn gàng hơn, đồng thời hệ thống vẫn tương thích hoàn toàn với các định dạng payload cũ.

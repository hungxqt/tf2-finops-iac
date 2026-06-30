# Tiến độ Cost Puller Telemetry

## Trạng thái
Hoàn thành (Đã cập nhật cơ chế phân tách ranh giới tài khoản và định tuyến dự phòng Normalization)

## Phạm vi
Triển khai `lambda_src/src/workers/cost_puller` thành worker thu thập dữ liệu thô (raw telemetry):
- Thêm các lớp wrapper client AWS trong `finops_common` cho S3, Cost Explorer, CloudWatch, và STS với quyền tối thiểu.
- Triển khai quá trình thu thập dữ liệu với tính năng phát hiện độ trễ của CUR (CUR freshness) và tự động chuyển hướng sang Cost Explorer nếu CUR trễ > 36 giờ.
- Triển khai phương án dự phòng sử dụng cache S3 khi Cost Explorer bị throttling, trả về trạng thái `READY` với cờ `stale_cost_explorer = true`.
- Tích hợp thu thập CloudWatch metrics dạng best-effort và định tuyến ngữ cảnh traffic hợp lệ theo contract. Khi thiếu traffic metrics, hệ thống giảm chất lượng telemetry thay vì tạo dữ liệu traffic dự phòng.
- Sửa lỗi import thư viện boto3 trong quá trình giả định vai trò (assume role) liên tài khoản từ xa và tránh nuốt lỗi lập trình.
- Mở rộng module IAM và các môi trường với tùy chọn triển khai vai trò thu thập số liệu liên tài khoản và danh sách vai trò tin cậy.
- Triển khai và cấu hình các biến CUR và CE vào Terraform module `compute_lambda` và các môi trường sandbox/staging/prod.
- Viết bộ kiểm thử unit test hoàn chỉnh bao gồm các trường hợp delay, throttling, dự phòng, bảo mật tenant, validate đường dẫn bucket S3, giả định vai trò STS thành công/thất bại, và ghi đè client trong session từ xa.
- Cập nhật `normalizer` để hỗ trợ giải nén tệp JSON gzipped thô và lưu trữ kết quả dạng Parquet.
- Triển khai cơ chế fail-closed khi gặp lỗi giả định vai trò liên tài khoản `sts:AssumeRole` (ngăn chặn việc tự động sử dụng quyền hạn của tài khoản quản trị/management mặc định khi giả định vai trò tài khoản thành viên từ xa thất bại).
- Trả về chi tiết phản hồi lỗi cấu trúc `TELEMETRY_AUTH_FAILED` khi việc giả định vai trò liên tài khoản thất bại (bao gồm các trường: target_account_id, current_account_id, role_name, delayed_cur, và fail_closed = true).
- **Phân Tách Ranh Giới Session/Client**: Phân tách các client AWS trong `cost_puller` sao cho session tài khoản thanh toán/quản trị mặc định được dùng cho các thao tác kiểm tra manifest/ghi dữ liệu S3 CUR, trong khi session giả định vai trò tài khoản thành viên chỉ được dùng riêng cho các API telemetry thành viên (`cloudwatch:GetMetricData` và `ce:GetCostAndUsage`).
- **Loại Bỏ Quyền S3 Của Tài Khoản Thành Viên**: Cập nhật chính sách vai trò IAM `member_telemetry_ingestion` để chỉ cho phép truy cập CloudWatch và Cost Explorer, loại bỏ hoàn toàn quyền S3.
- **Xác Thực Manifest S3 Sớm**: Tái cấu trúc `cost_puller` để thực hiện tải, phân tích cú pháp manifest S3 CUR và xác thực metadata tệp dữ liệu ngay từ đầu. Lỗi xác thực manifest (thiếu tệp, cột không hợp lệ, định dạng legacy) giờ đây sẽ tự động kích hoạt chế độ dự phòng Cost Explorer thay vì ném ngoại lệ dừng luồng.
- **Định Tuyến Luồng Lỗi Normalization**: Cập nhật tệp cấu hình Step Functions ASL `modules/orchestration/statemachine.json` và `docs/statemachine.json` để bắt lỗi `States.ALL` từ bước `NormalizeCostWindow` và định tuyến lại sang `IngestCostData` với tham số `force_ce_fallback = true`, đảm bảo lỗi chuẩn hóa dữ liệu CUR tự động kích hoạt fallback sang CE thay vì làm sập luồng. Ngăn chặn vòng lặp vô hạn bằng cách kiểm tra trước cờ `$.force_ce_fallback`.

## Các tệp thay đổi
- [lambda_src/src/finops_common/aws_clients.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/aws_clients.py)
- [lambda_src/src/finops_common/__init__.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/__init__.py)
- [lambda_src/src/workers/cost_puller/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/cost_puller/handler.py)
- [lambda_src/src/workers/normalizer/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/normalizer/handler.py)
- [lambda_src/tests/test_cost_puller.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_cost_puller.py)
- [lambda_src/tests/test_cost_puller_cur2.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_cost_puller_cur2.py)
- [lambda_src/tests/test_normalizer.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_normalizer.py)
- [modules/iam/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/iam/main.tf)
- [modules/orchestration/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/statemachine.json)
- [docs/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/statemachine.json)

## Câu lệnh xác minh
```powershell
# Chạy bộ kiểm thử unit test Python
Push-Location lambda_src; python -m pytest; Pop-Location

# Xác minh cấu hình Terraform
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod validate
```

## Kết quả
- Toàn bộ unit test Pytest cho các lambda workers đều pass (368 test thành công, bao gồm cả xác minh AssumeRole fail-closed, phân tách ranh giới session, xác thực sớm, và định tuyến dự phòng).
- Xác minh HCL của Terraform thành công cho tất cả các môi trường.

## Khó khăn / Điểm nghẽn
Không

## Bước tiếp theo
Xác minh luồng hoạt động của bộ điều phối Orchestration và thực thi Step Functions.

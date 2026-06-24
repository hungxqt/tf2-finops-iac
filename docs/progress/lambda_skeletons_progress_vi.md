# Tiến độ Lambda Skeletons

## Trạng thái
Hoàn thành

## Phạm vi
Triển khai và kiểm tra đơn vị (unit test) cho toàn bộ mã khung (skeleton) Go Lambda worker dựa trên thông số máy trạng thái `docs/statemachine.json`:
- **State Worker (`state`)**: Kiểm tra trạng thái chạy và xử lý ánh xạ hoàn thành, tạo ra chi tiết chạy tiêu chuẩn và khóa idempotency. Được cập nhật để hỗ trợ các hoạt động rõ ràng (`check`, `complete`, `failed`).
- **Cost Puller (`cost_puller`)**: Kéo các báo cáo chi phí thô giả lập. Hỗ trợ mô phỏng chế độ `CUR_DELAY` và `CE_THROTTLED` để kiểm tra các đường dẫn thử lại/chờ trong Step Functions.
- **Normalizer (`normalizer`)**: Định dạng cửa sổ dữ liệu chi phí sang định dạng parquet đã tinh lọc.
- **AI Client (`ai_client`)**: Xác thực endpoint, secret và phiên bản hợp đồng của AI Engine. Mô phỏng chế độ timeout, không khớp hợp đồng, không khả dụng và hành động không an toàn (ví dụ: cố gắng kích hoạt containment trên prod).
- **Router (`router`)**: Điều hướng cảnh báo đến các kênh Engineering/Finance tùy theo mức độ nghiêm trọng của anomaly và kiểm tra yêu cầu hành động.
- **Audit Writer (`audit_writer`)**: Ghi nhận các bản ghi kiểm toán trước khi hành động, sau khi hành động, chờ phê duyệt, bị từ chối và khi thất bại, đảm bảo chính sách lưu giữ tối thiểu 90 ngày và chi tiết tuân thủ. Xác minh ghi S3 và lập chỉ mục DynamoDB thông qua unit test.
- **Containment Worker (`containment_worker`)**: Thực hiện các hành động cô lập một cách an toàn, ghi đè chế độ `dry-run` bắt buộc đối với môi trường production bất kể hành động được yêu cầu để ngăn ngừa việc phá hủy tài nguyên ngoài ý muốn. Thực thi kiểm tra trạng thái phê duyệt (approval status) trên môi trường non-prod (sandbox/staging) và chặn hành động phá hủy (terminate, delete, modify_iam).

## Các file đã thay đổi
- [docs/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/statemachine.json) (Sửa đổi)
- [lambda_src/state/main.go](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/state/main.go) (Sửa đổi)
- [lambda_src/state/main_test.go](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/state/main_test.go) (Sửa đổi)
- [ai_client/main.go](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/ai_client/main.go) (Sửa đổi)
- [ai_client/main_test.go](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/ai_client/main_test.go) (Tạo mới)
- [cost_puller/main.go](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/cost_puller/main.go) (Sửa đổi)
- [cost_puller/main_test.go](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/cost_puller/main_test.go) (Tạo mới)
- [normalizer/main_test.go](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/normalizer/main_test.go) (Tạo mới)
- [router/main.go](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/router/main.go) (Sửa đổi)
- [router/main_test.go](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/router/main_test.go) (Tạo mới)
- [audit_writer/main.go](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/audit_writer/main.go) (Sửa đổi)
- [audit_writer/main_test.go](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/audit_writer/main_test.go) (Sửa đổi)
- [containment_worker/main.go](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/containment_worker/main.go) (Sửa đổi)
- [containment_worker/main_test.go](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/containment_worker/main_test.go) (Sửa đổi)

## Lệnh kiểm tra
- Chạy Go unit test: `Push-Location lambda_src; go test ./...; Pop-Location`
- Định dạng và kiểm tra tổng quát: `pwsh -File .\scripts\validate.ps1`
- Xác thực định nghĩa Step Functions: `aws stepfunctions validate-state-machine-definition --definition file://docs/statemachine.json`

## Kết quả
- Unit tests cho tất cả các package Go Lambda vượt qua thành công (bao gồm cả các kiểm tra cho các hoạt động rõ ràng, sandbox approval, chặn hành động cấm).
- Kiểm tra máy trạng thái thông qua AWS CLI thành công.
- Kiểm tra định dạng repository và Terraform validate cục bộ thành công.
- Các quét Trivy config và Checkov vượt qua với 0 lỗi/cảnh báo bảo mật.

## Vướng mắc
Không có

## Bước tiếp theo
Triển khai các module networking và S3 lakehouse storage dưới thư mục `modules/` và hoàn thiện cấu trúc môi trường `environments/sandbox`.

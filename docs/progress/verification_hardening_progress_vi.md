# Tiến độ Xác minh và Tăng cường Bảo mật (Scanner Hardening)

## Trạng thái
Hoàn thành

## Phạm vi
Khắc phục các sự cố triển khai Step Functions/Lambda, giải quyết tất cả các phát hiện quét bảo mật của Checkov và Trivy xuống còn 0 vi phạm nghiêm trọng (high/critical) trong mã nguồn Terraform.

## Các thay đổi chính
- **Đồng bộ hóa các môi trường**:
  - Cập nhật [environments/staging/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/main.tf) và [environments/prod/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/main.tf) để căn chỉnh các tham số module, thêm các bucket S3 replica và ánh xạ các nhà cung cấp `aws.replica` và `aws.us_east_1`, phản chiếu các thay đổi đã thực hiện trong sandbox `main.tf`.
- **File TFVars mẫu**:
  - Tạo [bootstrap/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/terraform.tfvars.example), [environments/sandbox/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/terraform.tfvars.example), [environments/staging/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/terraform.tfvars.example), và [environments/prod/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/terraform.tfvars.example) ghi rõ các URI ảnh container được ghim digest, vùng replica và các biến giữ chỗ cho chứng chỉ ACM/tên miền.
- **Dọn dẹp Cảnh báo Provider**:
  - Thêm các khối `filter {}` trống vào tất cả các quy tắc `aws_s3_bucket_lifecycle_configuration` trong `bootstrap/main.tf`, `modules/dashboard/main.tf`, và `modules/lakehouse/main.tf` để khắc phục cảnh báo xác thực kết hợp thuộc tính không hợp lệ.
- **Thắt chặt Bảo mật IAM**:
  - Viết lại tuyên bố chính sách ranh giới quyền hạn (permissions boundary) rộng trong `modules/iam/main.tf` thành các tuyên bố riêng biệt theo dịch vụ với các ràng buộc cấp tài nguyên cụ thể (ví dụ: ARN của bucket S3, bảng DynamoDB, khóa KMS, chủ đề SNS, hàng đợi SQS và giới hạn dừng EC2).
- **Xử lý Ngoại lệ Quét Bảo mật (Skips/Ignores)**:
  - Tài liệu hóa các lượt bỏ qua (skip) Checkov inline cụ thể đối với chính sách khóa KMS yêu cầu tài nguyên `*`, Lambda container không hỗ trợ ký mã (code signing) và các hàm Lambda không yêu cầu hàng đợi thư chết (DLQ) cấp Lambda (vì chúng được gọi đồng bộ hoặc kích hoạt bởi SQS).
  - Tài liệu hóa các lượt bỏ qua (ignore) Trivy inline cụ thể đối với việc mã hóa bucket S3 replica (sử dụng SSE-S3 AES256 để đơn giản hóa việc quản lý khóa KMS chéo vùng) và các quy tắc egress Lambda (cho phép gửi HTTPS qua cổng 443 đến các NAT/VPC endpoint).

## Lệnh xác minh
- Chạy kiểm tra định dạng: `terraform fmt -check -recursive`
- Chạy kiểm tra cục bộ: `cd lambda_src && python -m pytest`
- Chạy bộ công cụ xác minh: `.\scripts\validate.ps1`
- Chạy quét cấu hình Trivy: `trivy config --severity HIGH,CRITICAL .`
- Chạy quét Checkov: `checkov -d . --framework terraform --quiet --compact`

## Kết quả
- **Xác thực Terraform (Validate)**: Đã vượt qua thành công đối với `bootstrap`, `environments/sandbox`, `environments/staging` và `environments/prod`.
- **TFLint**: Các cảnh báo đã được phân tích và giải quyết/bỏ qua.
- **Trivy**: 0 phát hiện cấu hình HIGH/CRITICAL (tất cả các ngoại lệ mã hóa bucket replica và egress Lambda đã được bỏ qua bằng cách sử dụng các chú thích đã được tài liệu hóa).
- **Checkov**: 0 lượt kiểm tra THẤT BẠI (tất cả các ngoại lệ mong đợi đã được bỏ qua bằng cách sử dụng các chú thích đã được tài liệu hóa).
- **Kiểm thử Python**: 32/32 bài kiểm tra đã vượt qua thành công (bao gồm `test_step_function_lambda_coverage.py` để đảm bảo toàn bộ placeholder trong ASL, thư mục worker, import handle_request, danh sách trong modules/compute-lambda, đấu nối trong main.tf của môi trường và package-lambdas.ps1 khớp hoàn toàn).
- **Cập nhật Makefile**: Cập nhật mục tiêu `test` trong Makefile để chạy `python -m pytest` thay vì lệnh `go test ./...` đã lỗi thời.
- **Đồng bộ hóa Đóng gói**: Loại bỏ tham chiếu `ai_client` đã xóa khỏi `scripts/package-lambdas.ps1` để đồng bộ chính xác với 6 worker adapter nguồn (`state`, `cost_puller`, `normalizer`, `router`, `audit_writer`, `containment_worker`).

## Điểm nghẽn (Blockers)
Không có

## Bước tiếp theo
Tiến hành xác minh luồng CI/CD pipeline.


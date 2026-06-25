# Tiến độ Tích hợp Private ALB cho AI Engine

## Trạng thái
Đã kiểm tra (tất cả các unit tests và xác thực cấu hình tĩnh đều thành công; tạo bản nháp plan cấu hình thành công)

## Phạm vi
Tích hợp Private HTTPS ALB vào luồng gọi AI Engine:
- Step Functions -> VpcAlbCallerLambda -> private internal ALB -> AI Engine Request Lambda (live alias)
- Đảm bảo phân quyền IAM tối thiểu (least-privilege) và cô lập mạng an toàn (internal-only, HTTPS-only listener, các security groups với các rule riêng biệt, WAF rate-limit baseline).
- Chạy các lệnh kiểm tra cấu hình tĩnh và pytest. Không thực hiện terraform apply trên môi trường.

## Các file đã thay đổi
- `AGENTS.md` - Cập nhật hướng dẫn luồng tích hợp sử dụng Private ALB làm tiêu chuẩn chính thức.
- `modules/ai-runtime-lambda/variables.tf` - Khai báo biến đầu vào cho VPC, Certificate, Route 53, và Logging.
- `modules/ai-runtime-lambda/main.tf` - Bổ sung tài nguyên internal ALB, Target Group, Target Group Attachment, HTTPS Listener, Lambda Permission, WAFv2 Web ACL, và Route 53 A record.
- `modules/ai-runtime-lambda/outputs.tf` - Xuất ra các giá trị ALB DNS name, ARN, và Security Group ID.
- `lambda_src/src/workers/vpc_alb_caller/handler.py` - Tạo worker Python xử lý ký SigV4 và gọi ALB.
- `lambda_src/src/workers/vpc_alb_caller/__init__.py` - Đánh dấu module trống.
- `lambda_src/tests/test_vpc_alb_caller.py` - Viết các test case cho happy path, xác thực đầu vào, và xử lý fail-closed.
- `scripts/package-lambdas.ps1` - Đưa `vpc_alb_caller` vào danh sách đóng gói Lambda.
- `modules/compute-lambda/variables.tf` - Thêm biến `alb_base_url` và `sigv4_service_name`.
- `modules/compute-lambda/main.tf` - Khai báo cấu hình worker `vpc_alb_caller` trong local config.
- `modules/orchestration/main.tf` - Thay thế việc gọi trực tiếp `ai_request` bằng việc gọi qua `vpc_alb_caller` trong State Machine.
- `environments/sandbox/variables.tf` - Khai báo biến cert, DNS, và service name cho sandbox.
- `environments/sandbox/main.tf` - Cấu hình truyền biến ALB cho `ai_runtime_lambda` và base URL/service name cho `compute_lambda`.
- `environments/sandbox/outputs.tf` - Xuất ra các thông số private ALB cho sandbox.
- `environments/sandbox/terraform.tfvars` - Khai báo giá trị biến cho sandbox.
- `environments/sandbox/terraform.tfvars.example` - Khai báo giá trị mẫu cho sandbox.
- `environments/staging/variables.tf` - Khai báo biến cert, DNS, và service name cho staging.
- `environments/staging/main.tf` - Cấu hình truyền biến ALB cho các module trong staging.
- `environments/staging/outputs.tf` - Xuất ra các thông số private ALB cho staging.
- `environments/staging/terraform.tfvars.example` - Khai báo giá trị mẫu cho staging.
- `environments/prod/variables.tf` - Khai báo biến cert, DNS, và service name cho prod.
- `environments/prod/main.tf` - Cấu hình truyền biến ALB cho các module trong prod.
- `environments/prod/outputs.tf` - Xuất ra các thông số private ALB cho prod.
- `environments/prod/terraform.tfvars.example` - Khai báo giá trị mẫu cho prod.
- `docs/GUIDES.md` - Cập nhật hướng dẫn nhà phát triển bằng tiếng Anh.
- `docs/GUIDES_vi.md` - Cập nhật hướng dẫn nhà phát triển bằng tiếng Việt.

## Lệnh kiểm tra
```powershell
# Định dạng mã nguồn
terraform fmt -check -recursive

# Xác thực cấu hình
terraform -chdir=bootstrap init -backend=false
terraform -chdir=bootstrap validate
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate

# Chạy unit tests
cd lambda_src
python -m pytest
cd ..
```

## Kết quả
- `terraform fmt -check -recursive`: Thành công (không có lỗi định dạng).
- `terraform validate` (bootstrap/sandbox/staging/prod): Thành công (tất cả các module biên dịch và xác thực thành công).
- `python -m pytest` (lambda_src): Thành công (40/40 test cases đã pass, bao gồm 8 test cases mới cho `vpc_alb_caller`).

## Vướng mắc
Không có.

## Bước tiếp theo
Chuẩn bị tài liệu mô tả kế hoạch triển khai để xem xét.

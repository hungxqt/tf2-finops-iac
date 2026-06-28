# Tiến độ Phát hành Image Wrapper bằng CodeBuild

## Trạng thái
Đã hoàn thành (thư mục gốc độc lập `codebuild/` quản lý duy nhất một dự án CodeBuild dùng chung và một target ECR repository dùng chung đã được triển khai và xác thực thành công).

## Phạm vi công việc
Triển khai một thư mục gốc độc lập do Terraform quản lý (`codebuild/`) để xây dựng và xuất bản container image wrapper cho Lambda Web Adapter:
- Tạo thư mục gốc `codebuild/` quản lý chính xác một dự án CodeBuild dùng chung (`tf2-finops-ai-wrapper-build`), một CodeBuild IAM role/policy, một CodeBuild log group và một target ECR repository dùng chung (`tf2-finops-ai-wrapper`) cho tất cả các môi trường.
- Tái cấu trúc module `modules/ai-wrapper-build` để tự quản lý việc tạo ECR repository, repository policy, dự án CodeBuild, IAM role, log group, buildspec và cập nhật SSM Parameter Store.
- Tái cấu trúc module `modules/ai-runtime-lambda` để loại bỏ hoàn toàn việc tạo ECR repository, giữ nguyên việc tập trung vào triển khai Lambda runtime (qua `var.request_image_uri`) và thăng cấp phiên bản.
- Loại bỏ toàn bộ phần khai báo module xây dựng wrapper, các biến đầu vào và đầu ra khỏi các thư mục gốc môi trường (`environments/sandbox`, `environments/staging`, `environments/prod`).
- Cấu trúc buildspec để xác thực `UPSTREAM_IMAGE_URI` bắt buộc ghim bằng digest, đăng nhập vào registry, tự động bỏ qua build nếu tag đích (`wrapped-<upstream-digest-short>`) đã tồn tại trong ECR repo đích và ghi nhận URI đầu ra vào một SSM Parameter dùng chung (`/tf2-finops/shared/ai-wrapper/latest-image-uri` và `/tf2-finops/shared/ai-wrapper/latest-upstream-image-uri`).
- Cập nhật tài liệu hướng dẫn vận hành bằng tiếng Anh (`docs/GUIDES.md`) và tiếng Việt (`docs/GUIDES_vi.md`) để làm rõ thứ tự các bước triển khai mới.

## Các file đã thay đổi
- `modules/ai-runtime-lambda/main.tf`
- `modules/ai-runtime-lambda/outputs.tf`
- `modules/ai-wrapper-build/main.tf`
- `modules/ai-wrapper-build/variables.tf`
- `modules/ai-wrapper-build/outputs.tf`
- `codebuild/main.tf`
- `codebuild/variables.tf`
- `codebuild/outputs.tf`
- `codebuild/versions.tf`
- `codebuild/providers.tf`
- `codebuild/backend.tf`
- `codebuild/README.md`
- `environments/sandbox/variables.tf`
- `environments/sandbox/main.tf`
- `environments/sandbox/outputs.tf`
- `environments/staging/variables.tf`
- `environments/staging/main.tf`
- `environments/staging/outputs.tf`
- `environments/prod/variables.tf`
- `environments/prod/main.tf`
- `environments/prod/outputs.tf`
- `docs/GUIDES.md`
- `docs/GUIDES_vi.md`
- `docs/progress/ai_wrapper_build_progress.md`
- `docs/progress/ai_wrapper_build_progress_vi.md`

## Các lệnh xác thực
```powershell
# Kiểm tra định dạng (format)
terraform fmt -recursive

# Xác thực root codebuild
terraform -chdir=codebuild init -backend=false
terraform -chdir=codebuild validate

# Xác thực các môi trường chính
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod validate

# Chạy phân tích tĩnh Trivy và Checkov
trivy config .
checkov -d codebuild -d modules/ai-wrapper-build -d modules/ai-runtime-lambda --framework terraform
```

## Kết quả
- `terraform fmt -recursive`: Thành công (không có lỗi định dạng).
- `terraform validate` (codebuild/sandbox/staging/prod): Thành công (tất cả các môi trường xác thực thành công).
- Phân tích tĩnh (Trivy/Checkov): Thành công (tất cả các tài nguyên mới đều được quét và tuân thủ).

## Khó khăn / Vướng mắc
Không có.

## Bước tiếp theo
Kích hoạt thủ công các bản build wrapper CodeBuild bằng CLI.

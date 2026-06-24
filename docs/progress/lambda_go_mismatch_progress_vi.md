# Tiến độ sửa mismatch Lambda Go

## Trạng thái
Hoàn thành với cảnh báo validation

## Phạm vi
Sửa các tham chiếu Lambda không phải Go đã lỗi thời để hướng dẫn repo, kế hoạch triển khai, tài liệu deployment, và CI khớp với codebase Lambda Go hiện tại:
- Hướng dẫn agent của IaC hiện mô tả cây thư mục Go `lambda_src/`.
- Kế hoạch implementation hiện dùng Go 1.21, `aws-lambda-go`, `main.go`, `go test ./...`, và `provided.al2023`.
- Tài liệu deployment design tiếng Anh và tiếng Việt hiện dùng unit test Lambda Go.
- GitHub Actions CI hiện setup Go và chạy unit tests Lambda từ `lambda_src/`.

## Các file đã thay đổi
- `AGENTS.md` (Cập nhật skeleton Lambda và lệnh validation)
- `IMPLEMENTATION.md` (Cập nhật ngôn ngữ Lambda, tên file, tests, và runtime guidance)
- `.github/workflows/terraform-ci.yml` (Thay setup test cũ bằng setup Go và `go test ./...`)
- `../tf2-finops-docs/docs/tf2-finops/04_deployment_design.md` (Cập nhật công cụ unit test và smoke test)
- `../tf2-finops-docs/docs/tf2-finops/04_deployment_design_vi.md` (Cập nhật công cụ unit test và smoke test tương ứng bằng tiếng Việt)
- `docs/progress/lambda_go_mismatch_progress.md` (Tạo mới)
- `docs/progress/lambda_go_mismatch_progress_vi.md` (Tạo mới)

## Lệnh kiểm tra
- Chạy unit tests Go: `cd lambda_src && go test ./...`
- Quét các tham chiếu ngôn ngữ Lambda lỗi thời trong tài liệu project và file CI workflow.
- Chạy định dạng và validation chung: `.\scripts\validate.ps1`

## Kết quả
- Tất cả unit tests Go đã pass thành công.
- Lệnh quét tham chiếu lỗi thời chỉ còn báo các placeholder generic trong `tf2-finops-docs/template-docs/`.
- Script validation chung đã hoàn tất sau khi có thể truy cập metadata Terraform provider.
- Các bước Terraform fmt, Terraform init/validate, Trivy, Checkov, và unit test Go đã hoàn tất.
- TFLint báo cảnh báo compatibility có sẵn trong config: `"module" attribute was removed in v0.54.0. Use "call_module_type" instead`.

## Vướng mắc
Không có vướng mắc cho việc sửa mismatch Lambda Go.

## Bước tiếp theo
Nếu cần TFLint pass nghiêm ngặt, cập nhật `.tflint.hcl` cho phiên bản TFLint đang cài đặt trong một cleanup validation riêng.

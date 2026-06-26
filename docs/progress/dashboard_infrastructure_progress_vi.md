# Tiến độ Nền tảng hạ tầng Dashboard

## Trạng thái
Hoàn thành (Đã Thắt chặt Bảo mật)

## Scope
Khắc phục lỗi và thắt chặt bảo mật cho hạ tầng lưu trữ Dashboard tài chính, định tuyến API, và truy cập dữ liệu sử dụng AWS S3, CloudFront VPC Origin, Cognito PKCE, và Lambda@Edge.

## Các file đã thay đổi
* `modules/dashboard/main.tf` (Thay đổi)
* `modules/dashboard/variables.tf` (Thay đổi)
* `modules/dashboard/outputs.tf` (Thay đổi)
* `modules/dashboard/versions.tf` (Thay đổi)
* `modules/dashboard/README.md` (Thay đổi)
* `modules/ai-runtime-lambda/main.tf` (Thay đổi)
* `environments/sandbox/main.tf` (Thay đổi)
* `environments/staging/main.tf` (Thay đổi)
* `environments/prod/main.tf` (Thay đổi)
* `lambda_src/edge/dashboard_auth/viewer_auth.py` (Tạo mới)
* `lambda_src/edge/dashboard_auth/origin_sigv4.py` (Tạo mới)
* `lambda_src/tests/test_dashboard_infrastructure.py` (Tạo mới)
* `scripts/package-lambdas.ps1` (Thay đổi)

## Lệnh kiểm tra
```powershell
terraform fmt -check -recursive modules/dashboard modules/ai-runtime-lambda environments/sandbox environments/staging environments/prod
powershell -ExecutionPolicy Bypass -File ./scripts/package-lambdas.ps1
cd lambda_src
python -m pytest tests/test_dashboard_infrastructure.py
```

## Kết quả
* Khắc phục lỗi bỏ qua xác thực và luồng OAuth không an toàn: Loại bỏ implicit flow; bắt buộc sử dụng Cognito Code + PKCE tại CloudFront edge qua Lambda@Edge.
* Các đường dẫn S3 data và API được bảo mật dưới cổng xác thực của CloudFront (viewer-request kiểm tra cookies và xác thực claims/UserInfo với Cognito).
* Định tuyến tới private ALB thông qua CloudFront VPC Origin, tắt bộ nhớ đệm (cache) cho các request `/v1/*` và loại bỏ cookies Cognito trước khi chuyển tiếp.
* Thắt chặt bảo mật S3 replication: Bật source KMS selection và mã hóa destination KMS key cho các replica buckets assets và data.
* Giải quyết phạm vi ảnh hưởng khi hủy môi trường sandbox (teardown blast radius) bằng cách cấu hình `force_destroy = var.destroyable` cho bucket dashboard_assets.
* Khắc phục trôi lệch phiên bản (provider drift) bằng cách cập nhật phiên bản AWS provider yêu cầu `>= 5.100`.
* Định dạng và xác thực Terraform (fmt/validate) thành công.
* Toàn bộ 7 trường hợp kiểm thử hồi quy (regression tests) chạy thành công trong pytest.

## Vướng mắc
Không có

## Bước tiếp theo
Tiếp tục kiểm tra các trạng thái chạy của máy trạng thái orchestration và cơ chế fallback của AI API.

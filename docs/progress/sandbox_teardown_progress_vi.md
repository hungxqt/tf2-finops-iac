# Tiến độ Hủy Toàn bộ Môi trường Sandbox

## Trạng thái
Hoàn thành (tất cả các bài kiểm tra và xác thực tĩnh đã vượt qua; các biến đầu vào destroyable và tài nguyên bảo vệ đã được kết nối thành công).

## Phạm vi
Làm cho môi trường `environments/sandbox` có thể bị hủy hoàn toàn trong khi vẫn đảm bảo `staging` và `prod` được bảo vệ:
- Thêm biến đầu vào `destroyable` chung vào các module `lakehouse`, `orchestration`, `dashboard`, và `ai-runtime-lambda`.
- Truyền giá trị `destroyable = true` từ `environments/sandbox` và `destroyable = false` từ staging/prod.
- Loại bỏ các khối `prevent_destroy = true` tĩnh khỏi tất cả các tài nguyên của các module cốt lõi (khóa KMS, bucket S3, và bảng DynamoDB).
- Thêm tài nguyên tuần tra bảo vệ `destroy_guard` có điều kiện (`terraform_data`) trong cả bốn module cốt lõi để chặn việc hủy hoàn toàn ở các môi trường non-sandbox.
- Cấu hình `force_destroy = var.destroyable` cho các bucket S3 bao gồm logging, lakehouse, audit, dữ liệu dashboard, và các bucket replica S3.
- Cấu hình `force_delete = var.destroyable` cho kho lưu trữ ECR.
- Sửa đổi thời gian chờ xóa khóa KMS `deletion_window_in_days = var.destroyable ? 7 : 30`.
- Cấu hình Object Lock có điều kiện cho sandbox: tắt cấu hình S3 Object Lock khi `var.destroyable` là true để cho phép dọn dẹp sandbox sạch sẽ, đồng thời giữ nguyên cấu hình Object Lock chế độ Tuân thủ 90 ngày cho staging/prod.
- Cập nhật `docs/GUIDES.md` và `docs/GUIDES_vi.md` để ghi nhận quy trình hủy sandbox và các giới hạn kỹ thuật cứng của AWS Object Lock.

## Các file đã thay đổi
- `modules/lakehouse/variables.tf`
- `modules/lakehouse/main.tf`
- `modules/dashboard/variables.tf`
- `modules/dashboard/main.tf`
- `modules/orchestration/variables.tf`
- `modules/orchestration/main.tf`
- `modules/ai-runtime-lambda/variables.tf`
- `modules/ai-runtime-lambda/main.tf`
- `environments/sandbox/variables.tf`
- `environments/sandbox/main.tf`
- `environments/staging/variables.tf`
- `environments/staging/main.tf`
- `environments/prod/variables.tf`
- `environments/prod/main.tf`
- `docs/GUIDES.md`
- `docs/GUIDES_vi.md`

## Lệnh kiểm tra
```powershell
# Kiểm tra định dạng
terraform fmt -check -recursive

# Xác thực cấu hình
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate

# Chạy kiểm thử đơn vị
cd lambda_src
python -m pytest
cd ..
```

## Kết quả
- `terraform fmt -check -recursive`: Thành công.
- `terraform validate` (sandbox/staging/prod): Thành công.
- `python -m pytest`: Thành công (Tất cả 40 bài kiểm thử đều vượt qua sạch sẽ).

## Vướng mắc
Không có.

## Bước tiếp theo
Môi trường Sandbox đã sẵn sàng để kiểm tra quy trình giải phóng tài nguyên.

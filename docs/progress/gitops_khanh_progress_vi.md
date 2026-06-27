# Tiến độ GitOps Khanh

## Trạng thái

Đã tạo bộ workflow GitOps song song với tên `khanh-*`. Các workflow hiện tại không bị chỉnh sửa.

## Phạm vi

Bộ workflow bao phủ pull request validation, apply bằng plan artifact, và scheduled drift detection cho sandbox, staging, và prod.

## Các file đã thay đổi

- `.github/workflows/khanh-terraform-ci.yml`
- `.github/workflows/khanh-terraform-apply.yml`
- `.github/workflows/khanh-drift-detection.yml`
- `docs/GUIDES_khanh.md`
- `docs/GUIDES_khanh_vi.md`
- `docs/progress/gitops_khanh_progress.md`
- `docs/progress/gitops_khanh_progress_vi.md`

## Lệnh kiểm tra

```powershell
git diff --check -- .github/workflows/khanh-terraform-ci.yml .github/workflows/khanh-terraform-apply.yml .github/workflows/khanh-drift-detection.yml docs/GUIDES_khanh.md docs/GUIDES_khanh_vi.md
```

## Kết quả

Whitespace validation đã pass. Chưa chạy workflow đầy đủ vì GitHub Actions workflows cần chạy trên GitHub với OIDC role và repository variables đã được cấu hình.

## Vướng mắc

Repo hiện tại có lỗi Terraform formatting ở `modules/lakehouse/lakehouse.tftest.hcl`; CI mới giữ `terraform fmt -check -recursive` là hard gate, nên lỗi hiện có này cần được sửa trước khi CI mới có thể pass.

## Bước tiếp theo

Cấu hình các GitHub variables `KHANH_*`, cấu hình `KHANH_AWS_ROLE_TO_ASSUME`, rồi chạy `Khanh GitOps CI` hoặc `Khanh GitOps Apply` từ GitHub Actions.

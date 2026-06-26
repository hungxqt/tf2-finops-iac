# Hướng dẫn Khanh GitOps

Hướng dẫn này mô tả workflow GitOps song song được triển khai bởi các file GitHub Actions `khanh-*`. Bộ workflow này không thay thế workflow hiện tại.

## 1. Files

- `.github/workflows/khanh-terraform-ci.yml`: kiểm tra pull request.
- `.github/workflows/khanh-terraform-apply.yml`: tạo Terraform plan, upload plan thành artifact, rồi apply đúng plan đã được duyệt.
- `.github/workflows/khanh-drift-detection.yml`: chạy drift check định kỳ và mở GitHub issue khi AWS khác với Git.

## 2. GitHub Variables bắt buộc

Cấu hình các repository hoặc organization variables này trước khi chạy workflow:

```text
KHANH_AWS_ROLE_TO_ASSUME
KHANH_SANDBOX_REQUEST_IMAGE_URI
KHANH_SANDBOX_WORKER_IMAGE_URI
KHANH_SANDBOX_ALB_CERTIFICATE_ARN
KHANH_SANDBOX_CLOUDFRONT_ACM_CERTIFICATE_ARN
KHANH_SANDBOX_CLOUDFRONT_ALIASES_JSON
KHANH_STAGING_REQUEST_IMAGE_URI
KHANH_STAGING_WORKER_IMAGE_URI
KHANH_STAGING_ALB_CERTIFICATE_ARN
KHANH_STAGING_CLOUDFRONT_ACM_CERTIFICATE_ARN
KHANH_STAGING_CLOUDFRONT_ALIASES_JSON
KHANH_PROD_REQUEST_IMAGE_URI
KHANH_PROD_WORKER_IMAGE_URI
KHANH_PROD_ALB_CERTIFICATE_ARN
KHANH_PROD_CLOUDFRONT_ACM_CERTIFICATE_ARN
KHANH_PROD_CLOUDFRONT_ALIASES_JSON
```

Variables tùy chọn:

```text
KHANH_SANDBOX_PRIVATE_HOSTED_ZONE_ID
KHANH_SANDBOX_PRIVATE_DNS_NAME
KHANH_STAGING_PRIVATE_HOSTED_ZONE_ID
KHANH_STAGING_PRIVATE_DNS_NAME
KHANH_PROD_PRIVATE_HOSTED_ZONE_ID
KHANH_PROD_PRIVATE_DNS_NAME
```

`KHANH_AWS_ROLE_TO_ASSUME` có thể được lưu dưới dạng repository secret thay vì variable.

`KHANH_*_CLOUDFRONT_ALIASES_JSON` phải là JSON hợp lệ, ví dụ:

```json
["dashboard.sandbox.example.com"]
```

Image URI phải được pin bằng digest:

```text
123456789012.dkr.ecr.ap-southeast-1.amazonaws.com/tf2-finops-sandbox-ai-request@sha256:<64-hex>
```

## 3. Branch Mapping

```text
develop -> sandbox
main    -> staging
manual workflow_dispatch -> sandbox, staging, hoặc prod
```

Production được để manual có chủ đích. Hãy cấu hình GitHub Environment `prod` với required reviewers.

## 4. Cách sử dụng

Mở pull request vào `develop` hoặc `main`. CI workflow kiểm tra Terraform, package Lambda code, chạy Lambda tests, và chạy security scans.

Merge vào `develop` để deploy sandbox. Merge vào `main` để deploy staging. Apply workflow tạo plan artifact và apply đúng artifact đó sau GitHub Environment gate.

Chạy production thủ công từ workflow `Khanh GitOps Apply` và chọn `prod`.

## 5. Drift Detection

Drift workflow chạy hằng ngày cho sandbox, staging, và prod. Nếu `terraform plan -detailed-exitcode` trả về `2`, workflow sẽ mở GitHub issue. Workflow này không bao giờ auto-apply drift.

## 6. Lưu ý hiện tại

Repo hiện tại đang có lỗi Terraform formatting ở `modules/lakehouse/lakehouse.tftest.hcl`. Khanh CI workflow giữ `terraform fmt -check -recursive` là hard gate, nên file đó cần được format trước khi CI mới có thể pass.

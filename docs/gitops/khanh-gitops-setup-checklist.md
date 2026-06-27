# Khanh GitOps Setup Checklist

Danh sách đầy đủ những gì cần cấu hình trước khi workflow `khanh-*` có thể chạy thành công trên GitHub Actions.

---

## 1. AWS: OIDC Identity Provider

GitHub Actions dùng OIDC để lấy AWS credentials mà không cần access key tĩnh. Bước này chỉ cần làm **một lần** cho mỗi AWS account.

- [ ] Vào **AWS IAM → Identity providers → Add provider**
  - Provider type: `OpenID Connect`
  - Provider URL: `https://token.actions.githubusercontent.com`
  - Audience: `sts.amazonaws.com`
- [ ] Lặp lại cho từng account (sandbox, staging, prod) nếu mỗi env là account riêng

---

## 2. AWS: IAM Role cho GitHub Actions

Tạo một IAM role cho mỗi environment. Role này sẽ được GitHub Actions assume qua OIDC.

- [ ] Tạo role với **trust policy** sau (thay `OWNER/REPO` và `BRANCH`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::{ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:OWNER/REPO:*"
        }
      }
    }
  ]
}
```

- [ ] Gắn policy đủ quyền để Terraform plan/apply (thường là `AdministratorAccess` cho sandbox, restricted hơn cho prod)
- [ ] Lấy Role ARN → dùng ở bước 4

---

## 3. Terraform: Kiểm tra version

- [ ] Mở [`.terraform-version`](.terraform-version) xem version ghi là bao nhiêu
- [ ] Đối chiếu với `terraform_version: "1.15.6"` trong các workflow file
  - Nếu khác nhau → sửa workflow cho khớp với `.terraform-version`
  - Nếu `1.15.6` chưa tồn tại → `hashicorp/setup-terraform` sẽ fail, cần hạ xuống version thực tế

Files cần kiểm tra:
- [`.github/workflows/khanh-terraform-ci.yml`](../../.github/workflows/khanh-terraform-ci.yml) dòng 34
- [`.github/workflows/khanh-terraform-apply.yml`](../../.github/workflows/khanh-terraform-apply.yml) dòng 98
- [`.github/workflows/khanh-drift-detection.yml`](../../.github/workflows/khanh-drift-detection.yml) dòng 79

---

## 4. GitHub: Secrets

Vào **GitHub repo → Settings → Secrets and variables → Actions → Secrets**

- [ ] `KHANH_AWS_ROLE_TO_ASSUME` — ARN của IAM role tạo ở bước 2

  Ví dụ: `arn:aws:iam::123456789012:role/github-actions-khanh-sandbox`

  > Workflow đọc `secrets.KHANH_AWS_ROLE_TO_ASSUME || vars.KHANH_AWS_ROLE_TO_ASSUME` — có thể đặt ở secret hoặc variable tùy mức độ nhạy cảm.

---

## 5. GitHub: Variables

Vào **GitHub repo → Settings → Secrets and variables → Actions → Variables**

Cần set đủ cho **mỗi environment** (sandbox, staging, prod). Tên variable theo pattern `KHANH_{ENV}_{KEY}`:

### Sandbox

| Variable | Ví dụ giá trị | Ghi chú |
|---|---|---|
| `KHANH_SANDBOX_REQUEST_IMAGE_URI` | `123456789012.dkr.ecr.ap-southeast-1.amazonaws.com/tf2-finops-sandbox-ai-request@sha256:abc...` | Digest-pinned ECR URI |
| `KHANH_SANDBOX_WORKER_IMAGE_URI` | `123456789012.dkr.ecr.ap-southeast-1.amazonaws.com/tf2-finops-sandbox-ai-worker@sha256:abc...` | Digest-pinned ECR URI |
| `KHANH_SANDBOX_ALB_CERTIFICATE_ARN` | `arn:aws:acm:ap-southeast-1:123456789012:certificate/...` | ACM cert ở `ap-southeast-1` |
| `KHANH_SANDBOX_CLOUDFRONT_ACM_CERTIFICATE_ARN` | `arn:aws:acm:us-east-1:123456789012:certificate/...` | ACM cert **bắt buộc ở `us-east-1`** |
| `KHANH_SANDBOX_CLOUDFRONT_ALIASES_JSON` | `["dashboard.sandbox.example.com"]` | JSON array string |
| `KHANH_SANDBOX_PRIVATE_HOSTED_ZONE_ID` | `Z1234567890ABC` | Optional — để trống nếu không dùng Route 53 private |
| `KHANH_SANDBOX_PRIVATE_DNS_NAME` | `ai-engine.internal` | Optional — để trống nếu không dùng |

### Staging

| Variable | Ghi chú |
|---|---|
| `KHANH_STAGING_REQUEST_IMAGE_URI` | Giống sandbox, khác ECR repo/tag |
| `KHANH_STAGING_WORKER_IMAGE_URI` | |
| `KHANH_STAGING_ALB_CERTIFICATE_ARN` | |
| `KHANH_STAGING_CLOUDFRONT_ACM_CERTIFICATE_ARN` | Phải ở `us-east-1` |
| `KHANH_STAGING_CLOUDFRONT_ALIASES_JSON` | Ví dụ: `["dashboard.staging.example.com"]` |
| `KHANH_STAGING_PRIVATE_HOSTED_ZONE_ID` | Optional |
| `KHANH_STAGING_PRIVATE_DNS_NAME` | Optional |

### Prod

| Variable | Ghi chú |
|---|---|
| `KHANH_PROD_REQUEST_IMAGE_URI` | |
| `KHANH_PROD_WORKER_IMAGE_URI` | |
| `KHANH_PROD_ALB_CERTIFICATE_ARN` | |
| `KHANH_PROD_CLOUDFRONT_ACM_CERTIFICATE_ARN` | Phải ở `us-east-1` |
| `KHANH_PROD_CLOUDFRONT_ALIASES_JSON` | Ví dụ: `["dashboard.example.com"]` |
| `KHANH_PROD_PRIVATE_HOSTED_ZONE_ID` | Optional |
| `KHANH_PROD_PRIVATE_DNS_NAME` | Optional |

---

## 6. GitHub: Environments

Vào **GitHub repo → Settings → Environments**

- [ ] Tạo environment **`sandbox`**
  - Không cần required reviewers (auto-deploy từ `develop`)
- [ ] Tạo environment **`staging`**
  - Khuyến nghị: thêm 1-2 required reviewers để có approval gate trước khi apply
- [ ] Tạo environment **`prod`**
  - Bắt buộc: thêm required reviewers
  - Tùy chọn: thêm deployment branch rule chỉ cho phép `main`

> Nếu không tạo Environments, job `apply` vẫn chạy nhưng **không có gate** — apply thẳng vào staging/prod mà không cần ai approve.

---

## 7. Terraform: S3 Backend

Backend S3 phải tồn tại trước khi `terraform init` có thể chạy trong CI.

- [ ] Xác nhận bucket S3 state đã được tạo (xem [`bootstrap/`](../../bootstrap/) hoặc [`docs/GUIDES.md`](../GUIDES.md))
- [ ] Xác nhận mỗi environment có backend config đúng trong `environments/{env}/backend.tf`
- [ ] CI dùng `-backend=false` (không cần backend), nhưng job `plan`/`apply` cần backend thật

---

## 8. Terraform: Formatting

Workflow CI chạy `terraform fmt -check -recursive` và fail nếu có file không đúng format.

- [ ] Chạy locally để kiểm tra:
  ```powershell
  terraform fmt -check -recursive
  ```
- [ ] Nếu có lỗi format, fix bằng:
  ```powershell
  terraform fmt -recursive
  ```
- [ ] Commit kết quả trước khi mở PR

> **Known issue:** File `modules/lakehouse/lakehouse.tftest.hcl` có thể đang vi phạm fmt check — xem [progress note](../progress/gitops_khanh_progress.md).

---

## 9. First run: Kích hoạt workflow

Sau khi đã setup xong các bước trên:

- [ ] Push branch `khanh` lên remote (nếu chưa)
- [ ] Mở PR từ `khanh` → `develop` để kích hoạt `Khanh GitOps CI`
- [ ] Kiểm tra CI pass hết các gate
- [ ] Merge PR vào `develop` → kích hoạt `Khanh GitOps Apply` cho sandbox
- [ ] Vào **Actions tab** theo dõi job `plan` → kiểm tra plan output
- [ ] Nếu GitHub Environment `sandbox` không có required reviewers, job `apply` chạy tự động sau `plan`
- [ ] Kiểm tra AWS console xem resources đã được tạo

---

## 10. Verify drift detection

- [ ] Vào **Actions → Khanh GitOps Drift Detection → Run workflow**
- [ ] Chọn environment để test (ví dụ: `sandbox`)
- [ ] Chờ workflow chạy xong
  - exitcode 0 → không có drift, không tạo issue
  - exitcode 2 → có drift, xem GitHub Issues

---

## Tóm tắt thứ tự setup

```
1. AWS OIDC Provider (mỗi account, 1 lần)
2. AWS IAM Role (mỗi account, ghi lại ARN)
3. Kiểm tra Terraform version khớp
4. GitHub Secret: KHANH_AWS_ROLE_TO_ASSUME
5. GitHub Variables: KHANH_{ENV}_* (7 biến × 3 env = tối đa 21 variables)
6. GitHub Environments: sandbox / staging / prod (+ reviewers)
7. Xác nhận S3 backend đã tồn tại
8. Fix terraform fmt nếu có lỗi
9. Mở PR → chạy CI → merge → verify apply
10. Test drift detection bằng workflow_dispatch
```

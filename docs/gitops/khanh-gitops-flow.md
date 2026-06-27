# Khanh GitOps Flow

Tài liệu này mô tả cách ba workflow GitHub Actions `khanh-*` phối hợp để tạo thành vòng lặp GitOps hoàn chỉnh: từ khi developer mở PR cho đến khi Terraform apply lên AWS.

---

## Tổng quan ba workflow

| Workflow file | Trigger | Mục đích |
|---|---|---|
| `khanh-terraform-ci.yml` | PR → `develop` / `main` | Validate tĩnh: format, validate, lint, scan, unit test |
| `khanh-terraform-apply.yml` | Push → `develop` / `main` hoặc manual dispatch | Plan + Apply Terraform lên AWS |
| `khanh-drift-detection.yml` | Daily 00:00 UTC hoặc manual dispatch | Phát hiện drift giữa Git và AWS, tạo Issue |

---

## Flow end-to-end

```
Developer
  │
  ├─── mở PR → develop hoặc main
  │         │
  │         └─── [khanh-terraform-ci] ──────────────────────────────────┐
  │                    │                                                 │
  │               validate:                                              │
  │               ├── terraform fmt -check -recursive                   │
  │               ├── terraform init -backend=false (mọi root)          │
  │               ├── terraform validate                                 │
  │               ├── python -m pytest (lambda unit tests)              │
  │               ├── tflint --recursive                                │
  │               ├── trivy config scan (CRITICAL/HIGH → fail)         │
  │               └── checkov -d . --framework terraform                │
  │                                                                      │
  │         CI pass ✓ → reviewer approve → merge                        │
  │                                                                ──────┘
  │
  ├─── push/merge → develop  ──── target: sandbox
  │                                        │
  ├─── push/merge → main     ──── target: staging
  │                                        │
  └─── workflow_dispatch     ──── target: sandbox | staging | prod
                                           │
                              [khanh-terraform-apply]
                                           │
                              ┌────────────┴─────────────┐
                              │                          │
                         [job: plan]               [job: apply]
                              │                     (needs: plan)
                         ├── OIDC auth AWS         ├── OIDC auth AWS
                         ├── package lambdas        ├── download plan artifact
                         ├── write khanh.auto       ├── download lambda artifact
                         │    .tfvars.json          ├── terraform init
                         ├── terraform init         └── terraform apply
                         ├── terraform validate          (plan đã review)
                         ├── terraform plan -out
                         ├── upload plan artifact
                         └── upload lambda artifact

                              [khanh-drift-detection] (chạy độc lập, daily)
                                           │
                              ├── OIDC auth AWS
                              ├── write khanh.auto.tfvars.json
                              ├── terraform init
                              ├── terraform plan -detailed-exitcode
                              │       exitcode=0 → no drift
                              │       exitcode=1 → error → fail workflow
                              │       exitcode=2 → drift → tạo GitHub Issue
                              └── Issue: title "Terraform drift detected in {env}"
```

---

## Chi tiết từng workflow

### 1. CI (`khanh-terraform-ci.yml`)

**Trigger:** mọi PR nhắm vào `develop` hoặc `main`, nếu có thay đổi ở các path liên quan (`.github/workflows/khanh-*.yml`, `environments/**`, `modules/**`, v.v.).

**Quan trọng:** CI **không** cần AWS credentials. Terraform init chạy với `-backend=false` để validate cú pháp mà không đụng đến S3 backend hay AWS.

**Gates cứng (hard fail):**
- `terraform fmt` không sạch → fail
- `terraform validate` lỗi → fail
- Bất kỳ pytest nào fail → fail
- Trivy phát hiện CRITICAL hoặc HIGH → fail
- Checkov phát hiện vi phạm → fail

### 2. Apply (`khanh-terraform-apply.yml`)

**Cơ chế chọn environment:**

```
event = workflow_dispatch  →  dùng input.environment (sandbox/staging/prod)
branch = develop           →  sandbox
branch = main              →  staging
```

**Prod không bao giờ được auto-deploy.** Prod chỉ chạy qua `workflow_dispatch` manual.

**Tách plan / apply:**

Job `plan` và job `apply` chạy tách biệt. Terraform plan được lưu thành artifact (`khanh-{env}.tfplan`), job `apply` download về rồi mới chạy `apply`. Điều này đảm bảo:
- Plan được tạo ra từ đúng code đã commit
- Apply không re-compute plan mới (tránh drift giữa hai lần)

**Write GitOps tfvars:**

Workflow tự động sinh file `khanh.auto.tfvars.json` vào thư mục environment trước khi plan. File này được build từ GitHub Variables (`KHANH_{ENV}_*`) nên không cần commit tfvars chứa giá trị thật vào repo.

**GitHub Environments gate:**

Job `apply` khai báo `environment: {target}`. Nếu GitHub Environment được cấu hình với "required reviewers", apply sẽ chờ approval trước khi chạy — đây là cơ chế bảo vệ staging/prod.

### 3. Drift Detection (`khanh-drift-detection.yml`)

Chạy mỗi ngày lúc 00:00 UTC cho cả ba environment (`sandbox`, `staging`, `prod`) song song (matrix). Mỗi environment:

1. Auth AWS qua OIDC
2. Sinh tfvars từ GitHub Variables
3. `terraform plan -detailed-exitcode`
4. Nếu exitcode = 2 (có thay đổi) → tạo GitHub Issue với label `terraform`, `drift`, `{env}`

Issue chỉ thông báo, **không auto-apply**. Reviewer phải đọc plan, quyết định import/revert/fix-manual, rồi mới merge qua Git.

---

## Branch strategy và environment mapping

```
feature/* ──── PR ──→ develop ──── merge ──→ main
                         │                     │
                      [sandbox]           [staging]
                                               │
                                         manual dispatch
                                               │
                                           [prod]
```

| Branch | Environment target | Auto-deploy |
|---|---|---|
| `develop` | sandbox | Có |
| `main` | staging | Có |
| manual dispatch | sandbox / staging / prod | Có (prod cần manual) |

---

## OIDC authentication

Workflow không dùng AWS access key tĩnh. Thay vào đó:

1. GitHub Actions yêu cầu OIDC token từ GitHub
2. AWS STS nhận token, verify với GitHub's JWKS endpoint
3. AWS trả về short-lived credentials cho role `KHANH_AWS_ROLE_TO_ASSUME`

Role này phải được tạo sẵn trên AWS với trust policy cho phép GitHub repo này assume.

---

## Artifact flow giữa plan và apply

```
[job: plan]
  └── terraform plan -out khanh-{env}.tfplan
  └── upload artifact: khanh-{env}-tfplan (retention 7 ngày)
  └── upload artifact: khanh-lambda-packages-{env}

[job: apply]  (chạy sau plan, cùng workflow run)
  └── download artifact: khanh-{env}-tfplan
  └── download artifact: khanh-lambda-packages-{env}
  └── terraform apply khanh-{env}.tfplan
```

Lambda zip được upload cùng tfplan để apply job không cần re-package — đảm bảo binary apply đúng với binary plan đã review.

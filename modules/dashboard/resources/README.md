# Dashboard UI Shell

Thu muc nay chua static Frontend UI shell cho Finance Dashboard cua TF2 FinOps Watch.

## Muc dich

UI nay la lop hien thi SQL-free cho Finance va squad leads. No doc cau hinh runtime tu `dashboard_runtime_config.json`, sau do doc cac JSON summaries da duoc CDO pipeline tao san trong dashboard data bucket.

Terraform khong tu dong publish cac file UI trong thu muc nay len S3. Terraform chi provision ha tang dashboard va tao `dashboard_runtime_config.json`. Viec build va upload UI shell phai duoc thuc hien doc lap vao dashboard asset bucket.

## Cau truc file

```text
resources/
|-- index.html
|-- README.md
`-- assets/
    |-- app.js
    `-- styles.css
```

- `index.html`: khung giao dien dashboard va cac vung hien thi KPI, chart, anomaly, impacted owners, containment status.
- `assets/styles.css`: layout, mau sac, responsive behavior, bang va controls.
- `assets/app.js`: load runtime config, load summary data, render chart/cac bang, va goi action endpoints neu viewer co role operator.

## Cach deploy UI

Sau khi Terraform apply xong module dashboard:

1. Lay output dashboard asset bucket:
   ```powershell
   terraform output
   ```
2. Build frontend neu co build step rieng. UI hien tai la static HTML/CSS/JS nen co the upload truc tiep.
3. Upload noi dung thu muc `modules/dashboard/resources/` vao S3 bucket asset cua dashboard, giu nguyen duong dan:
   ```text
   index.html
   assets/styles.css
   assets/app.js
   ```
4. Truy cap dashboard qua CloudFront URL, khong truy cap truc tiep S3 bucket.

## Runtime config

Frontend ky vong file `dashboard_runtime_config.json` ton tai tai root cua asset bucket. File nay do Terraform tao qua resource `aws_s3_object.runtime_config` va chua cac truong khong phai secret:

- `aws_region`
- `user_pool_id`
- `user_pool_client_id`
- `identity_pool_id`
- `hosted_ui_domain`
- `data_bucket_name`
- `data_prefix`
- `cloudfront_domain`

Khong dat secret, token, API key, webhook URL that, hay AWS credentials trong frontend assets.

## Data summaries

`assets/app.js` hien tai doc file:

```text
${data_prefix}dashboard-summary.json
```

Voi default prefix cua module, duong dan la:

```text
summaries/dashboard-summary.json
```

Neu data writer dung nhieu file summary khac nhau trong prefix `summaries/`, can cap nhat `assets/app.js` de map dung ten file. Neu file summary chua ton tai, UI se dung synthetic sample data de review giao dien.

## Summary schema toi thieu

```json
{
  "environment": "sandbox",
  "viewer_role": "finance",
  "generated_at": "2026-06-26T09:00:00Z",
  "containment_locked": true,
  "lock_reason": "error_budget_exceeded_threshold",
  "lock_since": "2026-06-24T08:00:00Z",
  "error_budget_remaining_pct": 0.8,
  "spend_trend": [["2026-06-26", 1194, 988, false]],
  "anomalies": [],
  "impacted": [],
  "containment": [],
  "approvals": [],
  "alert_previews": [],
  "audit_diffs": [],
  "admin_settings": []
}
```

### `spend_trend`

Moi row co dang:

```json
["YYYY-MM-DD", actual_cost_usd, baseline_cost_usd, is_anomaly]
```

### `anomalies[]`

Cac field UI dang dung:

- `anomaly_id`
- `severity`
- `account_id`
- `account_name`
- `service`
- `squad`
- `owner_tag_status`
- `confidence_score`
- `data_confidence`
- `evidence_window_start`
- `evidence_window_end`
- `cost_delta_usd_per_day`
- `explanation`

### `impacted[]`

Cac field UI dang dung:

- `name`
- `type`
- `spend_delta_usd_per_day`
- `owner_tag_status`

### `containment[]`

Cac field UI dang dung:

- `audit_id`
- `resource_id`
- `account_id`
- `squad`
- `action_type`
- `execution_mode`
- `status`
- `containment_locked`
- `error_budget_remaining_pct`
- `audit_record_uri`
- `actions_log[]`


### `approvals[]`

Dung cho Manual Approval UI doi voi non-production apply-mode actions:

- `approval_id`
- `audit_id`
- `environment`
- `requested_action`
- `execution_mode`
- `status`
- `owner`
- `justification`
- `requested_at`

### `alert_previews[]`

Dung cho Finance va Engineering alert routing previews:

- `audience`
- `channel`
- `anomaly_id`
- `summary`
- `data_confidence`
- `action_visibility`
- `audit_link_label`

### `audit_diffs[]`

Dung cho visual audit diff, khong hien raw JSON hoac command payload:

- `audit_id`
- `before[]`
- `after[]`
- `correlation_id`
- `idempotency_key`

### `admin_settings[]`

Dung cho Access Settings UI cua CDO admin:

- `name`
- `value`
- `status`
## Role va action behavior

UI mac dinh xem `viewer_role = "finance"` la read-only. Cac action Verify/Rollback, Manual Approval, va Access Settings chi bat khi summary khai bao role operator/admin nhu:

- `engineering`
- `cdo`
- `admin`

Verify goi endpoint:

```text
POST /v1/verify
```

Rollback goi endpoint:

```text
POST /v1/audit/{audit_id}/rollback
```

Neu `containment_locked = true` hoac `execution_mode = "dry-run"`, Rollback bi disable. Finance users khong duoc thay raw rollback scripts, CLI commands, hay execution plans.

## Kiem tra nhanh

Chay syntax check cho JavaScript:

```powershell
node --check modules\dashboard\resources\assets\app.js
```

Mo local file `index.html` de review layout tinh. Khi review thong qua CloudFront, can dam bao `dashboard_runtime_config.json` va summary JSON da duoc upload dung path.




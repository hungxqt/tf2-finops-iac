# Change Plan — Telemetry Contract Bucket Update

**Contract version**: 3.2.0 → 3.3.0 (minor bump — thêm/sửa S3 bucket references, không breaking schema)  
**Ngày lập**: 2026-06-30  
**Lý do**: Kiến trúc chuyển sang centralized lakehouse; bucket `company-cdo-{account_id}-telemetry` thay bằng `tf2-finops-sandbox-lakehouse-bucket`

---

## Bối cảnh kiến trúc

| Bucket | Role | Writer | Reader |
|---|---|---|---|
| `tf2-finops-cur-export-bucket` | Raw CUR 2.0 source | AWS Data Exports (automatic) | CDO `cost_puller` (internal only) |
| `tf2-finops-sandbox-lakehouse-bucket` | Data lake — processed output | CDO Lambda, AI Engine | AI Engine via S3_POINTER |

**Nguyên tắc**: `tf2-finops-cur-export-bucket` là internal CDO concern — AI Engine không tương tác trực tiếp. Contract chỉ tham chiếu `tf2-finops-sandbox-lakehouse-bucket`.

---

## Files cần sửa

Cả hai file có nội dung giống nhau — apply đúng 4 change bên dưới cho mỗi file:

1. `tf2-finops-docs/docs/contracts/telemetry-contract.md`
2. `tf2-finops-iac/docs/contracts/telemetry-contract.md`

---

## Change 1 — §4: Rewrite "S3 Bucket Naming" subsection

**Xóa toàn bộ block này:**

```
**S3 Bucket Naming — Multi-CDO isolation**

S3 bucket name là **globally unique**. Hai team CDO không thể dùng chung tên bucket cố định.

| Kịch bản | Convention | Ví dụ |
|---|---|---|
| **Khác AWS account** | `company-cdo-{account_id}-telemetry` | `company-cdo-200000000010-telemetry` |
| **Cùng account, nhiều CDO** | Chia **namespace prefix** trong bucket chung | `idempotency/cdo-01/`, `idempotency/cdo-02/`, `cur/cdo-01/`, `features/cdo-02/` |

​```
s3://company-cdo-{account_id}-telemetry/
├── idempotency/cdo-01/{idempotency_key}.json   ← fallback audit only; hot path = DynamoDB
├── idempotency/cdo-02/
├── cur/{YYYY-MM-DD}.json.gz
└── features/{resource_id}/{YYYY-MM-DD}.json
​```
```

**Thay bằng:**

```
**S3 Bucket Layout — Centralized Lakehouse**

Hệ thống dùng hai bucket cố định trong payer account:

| Bucket | Role | Writer | Reader |
|---|---|---|---|
| `tf2-finops-cur-export-bucket` | Raw CUR 2.0 source | AWS Data Exports | CDO `cost_puller` (internal) |
| `tf2-finops-sandbox-lakehouse-bucket` | Data lake — processed output | CDO Lambda, AI Engine | AI Engine (S3_POINTER) |

AI Engine chỉ tương tác với `tf2-finops-sandbox-lakehouse-bucket`.
`tf2-finops-cur-export-bucket` là internal CDO concern — contract không tham chiếu.

CDO namespace isolation dùng S3 key prefix (`cdo-01/`, `cdo-02/`) trong lakehouse bucket:

​```
s3://tf2-finops-sandbox-lakehouse-bucket/
├── normalized/cdo-01/{linked_account_id}/year=YYYY/month=MM/day=DD/{run_id}.json.gz  ← S3_POINTER target
├── ce-cache/cdo-01/{linked_account_id}/{YYYY-MM-DD}.json.gz                          ← CE fallback cache
├── cw-metrics/cdo-01/{linked_account_id}/{resource_id}/{YYYY-MM-DD}.json.gz          ← CloudWatch (optional)
├── idempotency/cdo-01/{idempotency_key}.json                                         ← fallback audit; hot path = DynamoDB
└── features/cdo-01/{resource_id}/{YYYY-MM-DD}.json                                   ← AI Engine Feature Store
​```
```

---

## Change 2 — §5: `s3_bucket_uri` regex pattern

**Vị trí**: JSON Schema field `s3_bucket_uri.pattern`

| | Value |
|---|---|
| **Xóa** | `^s3://company-cdo-[0-9]{12}-telemetry/.+\.json\.gz$` |
| **Thay bằng** | `^s3://tf2-finops-sandbox-lakehouse-bucket/normalized/cdo-[0-9]{2}/.+\.json\.gz$` |

---

## Change 3 — §5: `s3_allowed_buckets` trong Constraints table

**Vị trí**: Bảng Constraints bên dưới JSON Schema

| | Value |
|---|---|
| **Xóa** | `` `company-cdo-{account_id}-telemetry` (globally unique per AWS account) `` |
| **Thay bằng** | `` `tf2-finops-sandbox-lakehouse-bucket` `` |

---

## Change 4 — §20: Feature Store bucket references

**Chỗ 1** — dòng mở đầu section (heading text):

| | Value |
|---|---|
| **Xóa** | `bucket \`s3://company-cdo-{account_id}-telemetry/features/\`` |
| **Thay bằng** | `bucket \`s3://tf2-finops-sandbox-lakehouse-bucket/features/\`` |

**Chỗ 2** — path trong mục 1 "Ghi nhận dữ liệu":

| | Value |
|---|---|
| **Xóa** | `s3://company-cdo-{account_id}-telemetry/features/{cdo_namespace}/{resource_id}/{YYYY-MM-DD}.json` |
| **Thay bằng** | `s3://tf2-finops-sandbox-lakehouse-bucket/features/{cdo_namespace}/{resource_id}/{YYYY-MM-DD}.json` |

---

## Tổng hợp

| Change | §4 | §5 regex | §5 table | §20 |
|---|---|---|---|---|
| **tf2-finops-docs** | rewrite block | patch | patch | patch ×2 |
| **tf2-finops-iac** | rewrite block | patch | patch | patch ×2 |

**Không thay đổi**: TenantContext JSON schema (tenant_id, account_id, correlation_id, idempotency_key, ttl_expiry giữ nguyên). DynamoDB idempotency store giữ nguyên. Idempotency Rules giữ nguyên.

**Version bump**: 3.2.0 → 3.3.0 (minor — add/update bucket references, backward compatible).

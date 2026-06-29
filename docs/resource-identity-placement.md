# Resource Identity Contract — Placement Analysis

> **Kết luận:** Resource Identity (Section 9) nên được inject vào payload của `/v1/detect`, **không phải** `/v1/decide`.

---

## 1. Bối cảnh: Resource Identity Contract là gì?

Theo Section 9 của TF2 FinOps Telemetry Contract, `ResourceIdentity` là schema chuẩn hóa định danh tài nguyên AWS theo OpenTelemetry semantic conventions. Mục đích chính:

- **Multi-tenant routing**: định tuyến đúng anomaly về đúng tenant/account
- **RCA drill-down**: truy vết root cause từ anomaly → resource → team/owner/cost_center

### Schema (required fields)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ResourceIdentity",
  "required": ["resource_id", "resource_type", "aws_service", "account_id", "region", "environment"],
  "properties": {
    "resource_id":    { "type": "string",   "description": "line_item_resource_id (ARN hoặc instance ID)" },
    "resource_type":  { "type": "string",   "description": "e.g. aws:ec2:instance, aws:rds:db" },
    "aws_service":    { "type": "string",   "description": "line_item_product_code" },
    "account_id":     { "type": "string",   "pattern": "^[0-9]{12}$" },
    "account_name":   { "type": "string" },
    "region":         { "type": "string" },
    "environment":    { "type": "string",   "enum": ["prod", "prod-core", "prod-payments", "staging", "dev", "sandbox", "ml-research"] },
    "owner":          { "type": ["string", "null"] },
    "team":           { "type": ["string", "null"] },
    "cost_center":    { "type": ["string", "null"] }
  }
}
```

---

## 2. Luồng workflow tổng quan

```
IngestCostData (cost_puller)
        ↓
NormalizeCostWindow (normalizer)
        ↓
VerifyS3Pointer
        ↓
BuildDetectRequest (S3_POINTER hoặc RAW_JSON)
        ↓
InvokeDetect ──────────────→ POST /v1/detect
        ↓                         ↓
EvaluateDetectResponse     trả về anomalies_list[]
        ↓
ProcessDetectedAnomalies (Map, MaxConcurrency=1)
        ↓
InvokeDecideForAnomaly ────→ POST /v1/decide  (per anomaly)
        ↓
CacheRollbackPayload → RouteAlert → EvaluateContainmentPolicy → ExecuteContainment
```

---

## 3. Phân tích từng endpoint

### 3.1. `/v1/detect` — nơi Resource Identity **phải có**

**Vai trò:** Nhận toàn bộ cost data của một account trong một batch period → phân tích → trả về danh sách anomaly.

Tại bước này, AI Engine cần biết:
- Resource nào đang gây ra chi phí bất thường? (`resource_id`, `resource_type`)
- Thuộc service gì? (`aws_service`)
- Thuộc account/region/environment nào? (để multi-tenant routing)
- Ai là owner/team? (để RCA drill-down và routing alert)

**Payload hiện tại trong `BuildDetectRequestS3Pointer`:**

```json
{
  "schema_version": "3.2.0",
  "tenant_id": "...",
  "account_id": "...",
  "account_name": "...",        ← đây là environment, chưa có resource-level identity
  "data_source_type": "S3_POINTER",
  "s3_bucket_uri": "...",
  "aws_cost_explorer_daily": "...",
  "missing_resources": "...",
  "resource_utilization_metrics": "...",
  "comparison_window": "...",
  "business_context": "..."
}
```

`missing_resources` và `resource_utilization_metrics` đã mang thông tin resource, nhưng **chưa theo chuẩn ResourceIdentity**. Việc nhúng `resource_identity` chuẩn hóa vào đây giúp AI Engine có context đầy đủ để:

1. Gán đúng `resource_type` cho từng line item khi phân tích CUR
2. Embed `owner`/`team`/`cost_center` vào anomaly output ngay từ detect
3. Hỗ trợ multi-tenant routing khi nhiều account chạy song song

### 3.2. `/v1/decide` — **không cần** inject thêm Resource Identity

**Vai trò:** Nhận một anomaly đã được detect → quyết định containment action.

**Payload hiện tại trong `InvokeDecideForAnomaly`:**

```json
{
  "correlation_id": "...",
  "idempotency_key": "...",
  "dry_run_mode": false,
  "anomaly_context": { ...anomaly object từ detect response... }
}
```

`anomaly_context` **đã là output của `/v1/detect`**. Nếu detect đã nhúng `ResourceIdentity` chuẩn, thì `anomaly_context` sẽ chứa sẵn:
- `anomaly.resource_id`
- `anomaly.resource_type`
- `anomaly.aws_service`
- `anomaly.environment`
- `anomaly.owner` / `anomaly.team`

Decide engine không cần nhận lại ResourceIdentity riêng — nó đã có đủ context để quyết định action (ví dụ: không `terminate` resource ở `prod`, chỉ `tag` hoặc `suggest`).

---

## 4. So sánh trực tiếp

| Tiêu chí | `/v1/detect` | `/v1/decide` |
|---|---|---|
| Xử lý bao nhiêu resource? | **Toàn bộ batch** (nhiều resource) | **1 anomaly** (1 resource đã biết) |
| Cần biết resource identity để làm gì? | Phân loại, phát hiện pattern bất thường | Đã có trong `anomaly_context` |
| Multi-tenant routing | ✅ Cần — nhiều account/tenant | ❌ Không cần — đã routed từ detect |
| RCA drill-down | ✅ Cần — embed vào anomaly output | ❌ Không cần — đã có trong anomaly |
| Payload size concern | Lớn (batch data) — identity giúp index | Nhỏ (1 anomaly) — không cần thêm |
| Nếu thiếu identity | AI không biết resource thuộc team nào | Không ảnh hưởng (đã có từ detect) |

---

## 5. Cách implement trong State Machine

### Bước `BuildDetectRequestS3Pointer` — thêm `resource_identity`

```json
"BuildDetectRequestS3Pointer": {
  "Type": "Pass",
  "Parameters": {
    "path": "/v1/detect",
    "method": "POST",
    "body": {
      "schema_version": "3.2.0",
      "tenant_id.$": "$.tenant_id",
      "account_id.$": "$.account_id",
      "account_name.$": "$.environment",
      "data_source_type": "S3_POINTER",
      "s3_bucket_uri.$": "$.normalized.details.s3_bucket_uri",

      "resource_identity": {
        "resource_id.$":   "$.normalized.details.line_item_resource_id",
        "resource_type.$": "$.normalized.details.resource_type",
        "aws_service.$":   "$.normalized.details.line_item_product_code",
        "account_id.$":    "$.account_id",
        "account_name.$":  "$.environment",
        "region.$":        "$.normalized.details.region",
        "environment.$":   "$.environment",
        "owner.$":         "$.normalized.details.owner",
        "team.$":          "$.normalized.details.team",
        "cost_center.$":   "$.normalized.details.cost_center"
      },

      "aws_cost_explorer_daily.$": "$.normalized.details.aws_cost_explorer_daily",
      "missing_resources.$":       "$.normalized.details.missing_resources",
      "comparison_window.$":       "$.normalized.details.comparison_window",
      "business_context.$":        "$.normalized.details.business_context",
      "resource_utilization_metrics.$": "$.normalized.details.resource_utilization_metrics"
    }
  }
}
```

Tương tự cho `BuildDetectRequestRawJson` — thêm cùng block `resource_identity`.

### Không thay đổi gì ở `InvokeDecideForAnomaly`

```json
"InvokeDecideForAnomaly": {
  "Parameters": {
    "path": "/v1/decide",
    "body": {
      "correlation_id.$": "$.correlation_id",
      "dry_run_mode.$":   "$.force_dry_run",
      "anomaly_context.$": "$.anomaly"
      // ← anomaly đã chứa resource_identity từ detect output
      // ← KHÔNG cần inject thêm resource_identity ở đây
    }
  }
}
```

---

## 6. Lợi ích sau khi implement

### 6.1. Multi-tenant routing chính xác

Khi `ProcessDetectedAnomalies` Map chạy song song nhiều account, mỗi anomaly trong `anomalies_list` đã mang sẵn `environment` và `team` → `router` Lambda có thể gửi alert đúng kênh (finance vs engineering) mà không cần lookup thêm.

### 6.2. RCA drill-down đầy đủ

Audit trail từ `audit_writer` sẽ có đủ:
```
anomaly.resource_id   → ARN resource cụ thể
anomaly.owner         → người chịu trách nhiệm
anomaly.cost_center   → để chargeback
anomaly.team          → để page đúng team
```

### 6.3. Containment decision đúng target

`EvaluateContainmentPolicyForAnomaly` hiện check `account_policy.environment`. Với `resource_identity.environment` trong anomaly, decide engine có thể phân biệt resource-level environment (ví dụ: một resource `prod` trong account `sandbox`) → tránh false containment.

### 6.4. `/v1/verify` cũng hưởng lợi

`ReportVerifyResultForAnomaly` dùng `anomaly.resource_id` làm `target` trong `action_executed`. Khi resource_id đã chuẩn hóa theo OpenTelemetry convention, verify engine có thể xác nhận đúng resource đã được xử lý.

---

## 7. Tóm tắt quyết định

```
ResourceIdentity inject vào:   /v1/detect   ✅
ResourceIdentity inject vào:   /v1/decide   ❌ (không cần, đã có trong anomaly_context)
```

**Nguyên tắc:** Identity được enriched **một lần** tại detect, **lan truyền** xuống decide → verify → audit → alert thông qua `anomaly` object. Không duplicate, không inconsistency.

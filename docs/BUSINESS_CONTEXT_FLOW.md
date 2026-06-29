# Business Context Flow - CDO Implementation Guide

> Scope: giải thích cách `business_context` trong `telemetry-contract.md` section 11 đang được triển khai trong repo IaC/CDO, từ lúc lấy CloudWatch traffic đến lúc gửi `/v1/detect`.


## 1. Kết luận nhanh

`business_context` là lớp dữ liệu giúp AI phân biệt:

- Chi phí tăng vì nhu cầu kinh doanh thật: flash sale, campaign, migration, load test.
- Chi phí tăng bất thường thật: traffic không tăng nhưng cost tăng.

Trong contract, trường quan trọng nhất là `traffic_volume`. CDO phải gửi `traffic_volume` trong mỗi DetectRequest để AI Engine tự tính `cost_per_request`.

Luồng hiện tại của CDO:

```text
EventBridge / manual run
  -> Step Functions
  -> cost_puller Lambda
       -> CloudWatch GetMetricData: AWS/ApplicationELB RequestCount 24h
       -> build business_context
       -> write features envelope to S3
  -> normalizer Lambda
       -> normalize/select business_context for account_id
       -> build AI detect payload object and S3 AI input pointer
  -> Step Functions BuildDetectRequestRawJson / BuildDetectRequestS3Pointer
       -> pass business_context to /v1/detect
  -> vpc_alb_caller Lambda
       -> signed HTTPS request to private ALB
  -> AI Engine
       -> derive cost_per_request = daily_cost / max(traffic_volume, 1)
```

## 2. Contract section 11 yêu cầu 

`BusinessContext` để giảm false positive. Logic chính:

```text
cost tăng + traffic tăng  = normal growth
cost tăng + traffic flat  = anomaly
```

Schema yêu cầu các field sau:

| Field | Bắt buộc | Ý nghĩa |
|---|---:|---|
| `linked_account_id` | Yes | Account AWS được áp business context. Phải khớp `line_item_usage_account_id` trong CUR. |
| `traffic_volume` | Yes | Tổng request volume trong 24h. Đây là field cốt lõi để normalize cost. |
| `traffic_source` | Yes | Nguồn metric: `ALB`, `CloudFront`, `ApiGateway`, `Synthetic`, hoặc `Mixed`. |
| `campaign_flag` | Yes | Đánh dấu đang có campaign marketing. |
| `load_test_flag` | Yes | Đánh dấu đang chạy performance/load test. |
| `migration_flag` | Yes | Đánh dấu đang migration. |
| `active_users` | No | Concurrent active users nếu hệ thống có nguồn dữ liệu app/business. |
| `orders_count` | No | Transaction count 24h nếu hệ thống có nguồn dữ liệu app/business. |

Granularity của telemetry contract là 1 context cho mỗi linked account trong mỗi batch day. Ở boundary runtime hiện tại, `cost_puller` có thể giữ dạng mảng để hỗ trợ multi-account, nhưng `normalizer` phải chọn đúng account và xuất ra một object `business_context` theo `ai-api-contract.md` v1.4.0.

## 3. Nguồn dữ liệu business context theo kiến trúc

Contract định nghĩa thứ tự ưu tiên nguồn traffic như sau:

| Priority | Source | Metric | Namespace |
|---:|---|---|---|
| 1 | Application Load Balancer | `RequestCount` | `AWS/ApplicationELB` |
| 2 | CloudFront | `Requests` | `AWS/CloudFront` |
| 3 | API Gateway | `Count` | `AWS/ApiGateway` |
| 4 | Capstone fallback | synthetic traffic | `traffic_source: Synthetic` |

Implementation hiện tại trong `cost_puller` đang lấy nguồn priority 1:

```text
CloudWatch GetMetricData
  Namespace  = AWS/ApplicationELB
  MetricName = RequestCount
  Period     = 86400
  Stat       = Sum
  StartTime  = execution_date - 1 day
  EndTime    = execution_date
```

Nếu CloudWatch client không có, metric không có value, hoặc query lỗi, implementation trả:

```json
{
  "traffic_volume": 0.0,
  "traffic_source": "ALB",
  "missing_traffic": true
}
```

Sau đó `missing_traffic` được gộp vào `missing_cloudwatch`, làm giảm `completeness_score` và có thể ép workflow sang dry-run.

## 4. cost_puller đóng gói business_context như thế nào

Trong cả hai nhánh CUR delay và CUR ready, `cost_puller` đều tạo `business_context` dạng mảng:

```json
[
  {
    "linked_account_id": "<event.account_id>",
    "traffic_volume": "<traffic_volume từ CloudWatch>",
    "traffic_source": "<traffic_source>",
    "campaign_flag": false,
    "load_test_flag": false,
    "migration_flag": false
  }
]
```

Nhánh CUR delay:

- CDO dùng Cost Explorer fallback.
- Raw envelope có `aws_cost_explorer_daily`, `resource_utilization_metrics`, `business_context`, `quality`.
- Envelope được gzip và ghi vào S3 dưới prefix `cur/account_id=...`.
- Features envelope riêng cũng được ghi vào S3 dưới prefix `features/account_id=...`.

Nhánh CUR ready:

- CDO dùng CUR manifest/Athena path.
- Không cần Cost Explorer fallback.
- Vẫn ghi features envelope chứa `resource_utilization_metrics` và `business_context` vào S3.
- `business_context` được trả trong `ingestion.details` để normalizer dùng tiếp.

## 5. normalizer xử lý business_context như thế nào

`normalizer` lấy `business_context` từ:

```text
event_data.ingestion.details.business_context
```

Sau đó normalize theo `account_id`:

- Nếu input là object: dùng object đó.
- Nếu input là list: chọn item có `linked_account_id == event.account_id`.
- Nếu không tìm thấy: dùng item đầu tiên.
- Nếu không có business context: tạo default.

Default hiện tại:

```json
{
  "linked_account_id": "<account_id>",
  "traffic_volume": 0,
  "traffic_source": "ALB",
  "campaign_flag": false,
  "load_test_flag": false,
  "migration_flag": false
}
```

Điểm quan trọng: nếu `raw_bc` không tồn tại, `normalizer` đánh dấu `missing_cloudwatch = true` và nếu chưa có completeness score rõ ràng thì hạ `completeness_score` xuống tối đa `0.5`. Tức là hệ thống không silently bỏ qua thiếu business context; nó biến thành tín hiệu chất lượng dữ liệu kém.

Output quan trọng của bước này là `normalized.details.business_context` dạng object:

```json
{
  "linked_account_id": "<account_id>",
  "traffic_volume": 120000,
  "traffic_source": "ALB",
  "campaign_flag": false,
  "load_test_flag": false,
  "migration_flag": false
}
```

Với nhánh CUR ready, normalizer còn ghi object AI input đã gzip vào:

```text
s3://<lakehouse_bucket>/ai-input/account_id=<account_id>/year=<yyyy>/month=<mm>/day=<dd>/<run_id>_input.json.gz
```

Object này chứa `business_context` đã normalize để AI Engine có thể đọc lại khi body `/v1/detect` dùng `S3_POINTER`.

## 6. Step Functions đưa business_context vào AI DetectRequest

Sau `NormalizeCostWindow`, Step Functions kiểm tra chất lượng telemetry:

- `completeness_score < 0.8`
- hoặc `delayed_cur = true`
- hoặc `stale_cost_explorer = true`
- hoặc `missing_cloudwatch = true`
- hoặc `estimated_billing = true`

Nếu một trong các điều kiện này đúng, workflow set:

```json
{
  "force_dry_run": true
}
```

Sau đó workflow chọn mode gửi request:

| Mode | Khi nào dùng | business_context đi đâu |
|---|---|---|
| `RAW_JSON` | CE fallback nhỏ, payload nằm trong giới hạn inline Step Functions | Gửi trực tiếp trong body `/v1/detect`. |
| `S3_POINTER` | CUR ready hoặc CE fallback vượt ngưỡng inline | Gửi pointer S3 kèm metadata; `business_context` vẫn nằm trong body metadata và cũng nằm trong object S3 AI input. |

Ngưỡng implementation hiện tại của `normalizer` là `RAW_JSON_INLINE_MAX_BYTES`, mặc định `200000` bytes. Đây là giới hạn an toàn cho Step Functions state, nhỏ hơn giới hạn 10 MB của AI API contract.

Cả `BuildDetectRequestRawJson` và `BuildDetectRequestS3Pointer` đều map:

```json
"business_context.$": "$.normalized.details.business_context"
```

Vì vậy, AI Engine nhận `business_context` ở boundary `/v1/detect` nếu normalizer produce thành công. Với mode `S3_POINTER`, body vẫn có metadata context, còn payload đầy đủ trong S3 cũng có cùng object này.

## 7. AI Engine dùng business_context như thế nào

CDO không tính `cost_per_request`. Contract ghi rõ AI Engine phải derive feature này:

```python
daily_cost = sum(line_item_unblended_cost)
cost_per_request = daily_cost / max(traffic_volume, 1)
```

Ý nghĩa:

| Scenario | Cost | Traffic | Kết quả |
|---|---|---|---|
| Flash sale benign | Tăng | Tăng tương ứng | `cost_per_request` ổn định, không coi là anomaly. |
| True leak | Tăng | Không tăng | `cost_per_request` tăng, coi là anomaly. |
| Offline/batch workload | Có cost | `traffic_volume = 0` | AI dùng absolute cost và `usage_density_24h` thay vì traffic. |

Nếu `campaign_flag = true` hoặc `cost_per_request` ổn định trong khoảng +-15%, AI có thể classify là `BENIGN_DEMAND_SURGE` và không auto-contain.

## 8. Điểm cần nắm cho team CDO

Business context hiện tại chủ yếu là traffic context, chưa phải full business event system.

CDO hiện đang làm tốt các phần sau:

- Có field bắt buộc `traffic_volume` trong payload.
- Có `linked_account_id` để join với CUR account.
- Có đường truyền qua cả raw envelope, features S3, normalizer output, và DetectRequest.
- Có quality gate: thiếu traffic/CloudWatch sẽ làm giảm confidence và ép dry-run.
- Không để AI Engine tự pull CloudWatch/AWS APIs; CDO vẫn là source of truth.

Các điểm implementation hiện tại còn hẹp hơn contract:

| Contract mong muốn | Implementation hiện tại |
|---|---|
| Ưu tiên ALB, CloudFront, API Gateway, Synthetic | Mới query ALB `RequestCount` từ CloudWatch. |
| Multi-ALB same account -> `traffic_source: Mixed` | Chưa thấy logic enumerate/sum nhiều ALB theo dimension; query hiện tại không khai báo dimension. |
| `campaign_flag`, `load_test_flag`, `migration_flag` lấy từ business/event source | Hiện hard-code `false`. |
| `active_users`, `orders_count` có thể lấy từ app/business telemetry | Hiện chưa populate. |
| Synthetic backtest từ script `tools/generate_synthetic_traffic.py` | Contract nhắc tới, nhưng repo CDO hiện chưa thấy path script này trong luồng runtime. |

## 9. Cách giải thích trong buổi team review

Nói ngắn gọn:

> Section 11 không yêu cầu CDO dự đoán anomaly. CDO chỉ có trách nhiệm lấy business context đáng tin cậy, đặc biệt là request volume theo account/ngày, rồi gửi kèm DetectRequest. AI Engine dùng dữ liệu đó để normalize cost thành `cost_per_request`. Nhờ vậy hệ thống không báo nhầm các ngày business tăng hợp lệ như flash sale, migration hoặc load test.

Nói chi tiết hơn:

> Trong kiến trúc hiện tại, `cost_puller` là nơi thu business context. Nó gọi CloudWatch để lấy ALB `RequestCount` 24h, đóng gói thành `business_context`, lưu vào S3 feature envelope và trả về cho Step Functions. `normalizer` chọn context đúng `account_id`, đảm bảo default nếu thiếu, rồi publish vào `normalized.details.business_context`. Step Functions đưa field này vào cả RAW_JSON và S3_POINTER DetectRequest. Nếu traffic metric thiếu, workflow đánh dấu `missing_cloudwatch`, hạ `completeness_score`, và ép dry-run để tránh containment sai.

## 10. File/code liên quan

| File | Vai trò |
|---|---|
| `tf2-finops-iac/docs/contracts/telemetry-contract.md` | Section 11 định nghĩa schema, nguồn dữ liệu ưu tiên và rule `cost_per_request`. |
| `tf2-finops-iac/docs/contracts/ai-api-contract.md` | Section 5.1 yêu cầu DetectRequest có `business_context` object với `traffic_volume`. |
| `tf2-finops-iac/lambda_src/src/workers/cost_puller/handler.py` | Query CloudWatch ALB `RequestCount`, build `business_context`, ghi features/raw envelope. |
| `tf2-finops-iac/lambda_src/src/workers/normalizer/handler.py` | Normalize/select `business_context`, hạ quality nếu thiếu, build AI input và chọn `RAW_JSON`/`S3_POINTER`. |
| `tf2-finops-iac/modules/orchestration/statemachine.json` | Quality gate, force dry-run, và map `business_context` vào `/v1/detect`. |
| `tf2-finops-iac/lambda_src/tests/test_step_function_payload_contract.py` | Test bảo vệ Step Functions payload contract: `business_context` có mặt trong request builder. |
| `tf2-finops-iac/docs/tf2-finops/04_deployment_design.md` | Deployment gate kiểm tra payload có `business_context`, `traffic_volume`, và AI derive `cost_per_request`. |

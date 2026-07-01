# Dashboard Summary Writer

## 1. Mục đích

Finance Dashboard là một website tĩnh được phân phối qua CloudFront. Frontend
không truy vấn trực tiếp Athena hoặc DynamoDB mà đọc một snapshot JSON tại:

```text
s3://<dashboard-data-bucket>/summaries/dashboard-summary.json
```

`dashboard_summary_writer` tự động tạo lại snapshot này sau mỗi lần FinOps
Step Functions workflow chạy thành công. Nhờ đó dashboard nhận dữ liệu mới mà
không cần thành viên trong nhóm chạy script thủ công hằng ngày.

## 2. Luồng hoạt động

```text
EventBridge Scheduler (24 giờ)
        |
        v
FinOps Step Functions workflow
        |
        | trạng thái SUCCEEDED
        v
EventBridge status-change rule
        |
        v
Dashboard Summary Writer Lambda
        |
        +--> Athena: chi phí curated và spend trend
        +--> DynamoDB: run state, anomaly, audit và dashboard views
        +--> S3 Lakehouse: nguồn dự phòng khi truy vấn curated
        |
        v
S3 dashboard data bucket
  summaries/dashboard-summary.json
        |
        v
CloudFront Finance Dashboard
```

EventBridge chỉ gọi Lambda khi toàn bộ workflow có trạng thái `SUCCEEDED`.
Workflow thất bại hoặc đang chạy không ghi đè snapshot đang phục vụ người dùng.

## 3. Thành phần source code

| Thành phần | Vị trí | Vai trò |
|---|---|---|
| Lambda handler | `lambda_src/src/workers/dashboard_summary_writer/handler.py` | Chuyển biến môi trường thành cấu hình và gọi bộ materialize dùng chung |
| Summary materializer | `scripts/publish-dashboard-summary.py` | Đọc các nguồn dữ liệu, xây dựng data contract và ghi snapshot lên S3 |
| Lambda packaging | `scripts/package-lambdas.ps1` | Đóng gói handler và materializer vào cùng Lambda ZIP |
| Lambda resource | `modules/compute-lambda/main.tf` | Khai báo runtime, timeout, memory và biến môi trường |
| IAM policy | `modules/iam/main.tf` | Cấp quyền đọc Athena, Glue, DynamoDB, lakehouse và ghi summary |
| EventBridge trigger | `modules/orchestration/main.tf` | Gọi Lambda sau khi Step Functions thành công |
| Unit test | `lambda_src/tests/test_dashboard_summary_writer.py` | Kiểm tra handler, packaging và EventBridge wiring |

## 4. Nguồn dữ liệu

Lambda tổng hợp dữ liệu từ:

- Athena/Glue curated cost: spend trend và dữ liệu chi phí theo account,
  service, squad.
- DynamoDB run-state: lần chạy thành công gần nhất và trạng thái workflow.
- DynamoDB anomaly: anomaly đang mở, severity, confidence và waste impact.
- DynamoDB audit: containment, rollback và audit evidence.
- DynamoDB dashboard views: trạng thái view đã materialize.
- S3 lakehouse: nguồn đọc dự phòng khi cần xây spend trend.

Snapshot đầu ra tuân theo data contract mà frontend đang sử dụng, bao gồm các
trường như `generated_at`, `last_successful_run_id`, `workflow_status`,
`data_freshness_status`, `spend_trend`, `anomalies` và `containment`.

## 5. Biến môi trường

| Biến | Ý nghĩa |
|---|---|
| `ENVIRONMENT` | Môi trường `sandbox`, `staging` hoặc `prod` |
| `PROJECT_NAME` | Tên dự án |
| `TENANT_ID` | Tenant của snapshot |
| `DASHBOARD_VIEWER_ROLE` | Role hiển thị trên dashboard |
| `DASHBOARD_ACCOUNT_ID` | AWS account được tổng hợp |
| `DASHBOARD_DATA_BUCKET` | Bucket chứa snapshot cho CloudFront |
| `DASHBOARD_SUMMARY_KEY` | Mặc định `summaries/dashboard-summary.json` |
| `DASHBOARD_LOOKBACK_DAYS` | Khoảng dữ liệu chi phí cần tổng hợp |
| `GLUE_DATABASE_NAME` | Glue database chứa curated table |
| `ATHENA_WORKGROUP_NAME` | Athena workgroup thực thi query |
| `ATHENA_RESULTS_BUCKET_NAME` | Bucket chứa kết quả Athena |
| `LAKEHOUSE_BUCKET_NAME` | Bucket chứa dữ liệu lakehouse |
| `RUN_STATE_TABLE_NAME` | DynamoDB run-state table |
| `ANOMALY_TABLE_NAME` | DynamoDB anomaly table |
| `AUDIT_TABLE_NAME` | DynamoDB audit table |
| `DASHBOARD_VIEWS_TABLE_NAME` | DynamoDB dashboard views table |

Các giá trị được Terraform truyền từ từng environment, không hard-code thông
tin sandbox trong Lambda handler.

## 6. Quyền IAM

Lambda áp dụng least privilege cho các nhóm quyền sau:

- `dynamodb:GetItem`, `Query`, `Scan` trên các bảng operational state.
- Chỉ `s3:PutObject` vào prefix `summaries/*` của dashboard data bucket.
- Chạy và đọc kết quả query trong Athena workgroup được cấu hình.
- Đọc Glue database/table metadata.
- Đọc S3 lakehouse và đọc/ghi Athena results.
- `kms:Decrypt`, `Encrypt`, `GenerateDataKey` trên các KMS key được truyền vào.

Lambda không có quyền xóa object, thay đổi IAM hoặc thực hiện containment.

## 7. Triển khai

Thay đổi source không tự tạo tài nguyên AWS. Sau khi Pull Request được review,
merge và CI thành công, pipeline hoặc người có quyền triển khai mới chạy
Terraform cho environment mục tiêu.

Trước khi apply:

```bash
cd environments/sandbox
terraform init
terraform plan
```

Chỉ chạy `terraform apply` khi plan đã được nhóm review và xác nhận sử dụng
đúng backend state của environment.

## 8. Kiểm tra sau khi triển khai

### Kiểm tra Lambda tồn tại

```bash
aws lambda get-function \
  --function-name tf2-finops-sandbox-dashboard_summary_writer
```

### Kiểm tra snapshot mới nhất

```bash
aws s3api head-object \
  --bucket tf2-finops-sandbox-dashboard-data \
  --key summaries/dashboard-summary.json
```

`LastModified` phải mới hơn hoặc bằng thời điểm workflow thành công gần nhất.

### Kiểm tra nội dung chính

```bash
aws s3 cp \
  s3://tf2-finops-sandbox-dashboard-data/summaries/dashboard-summary.json \
  dashboard-summary.json
```

Kiểm tra `generated_at`, `last_successful_run_id`, `workflow_status`,
`data_freshness_status`, số dòng `spend_trend` và danh sách `anomalies`.

### Kiểm tra log

```bash
aws logs tail \
  /aws/lambda/tf2-finops-sandbox-dashboard_summary_writer \
  --since 1h
```

Log thành công có thông báo `Dashboard summary published after workflow
completion`.

## 9. Xử lý sự cố

| Hiện tượng | Kiểm tra |
|---|---|
| Snapshot không cập nhật | Xác nhận Step Functions có trạng thái `SUCCEEDED` và EventBridge rule đang enabled |
| Lambda không được gọi | Kiểm tra EventBridge target và Lambda resource-based permission |
| Athena query thất bại | Kiểm tra database, workgroup, curated table và Athena results bucket |
| DynamoDB AccessDenied | Kiểm tra ARN các bảng truyền vào IAM module |
| S3/KMS AccessDenied | Kiểm tra dashboard bucket ARN và KMS key ARN |
| Dashboard vẫn hiển thị dữ liệu cũ | So sánh `generated_at`, S3 `LastModified` và tải lại trang |
| Lambda timeout | Kiểm tra Athena query; Lambda hiện có timeout 300 giây |

Khi Lambda thất bại, snapshot cũ vẫn được giữ lại. Không upload dữ liệu mẫu để
che lỗi vì điều đó có thể khiến Finance hiểu nhầm dữ liệu minh họa là dữ liệu
thật.

## 10. Chạy thủ công khi cần khắc phục

Script materializer vẫn được giữ để hỗ trợ kiểm tra hoặc khôi phục có kiểm
soát:

```bash
python scripts/publish-dashboard-summary.py --help
```

Đây là đường chạy hỗ trợ vận hành, không phải cơ chế cập nhật hằng ngày.
Cơ chế mặc định là EventBridge tự gọi `dashboard_summary_writer` sau workflow
thành công.

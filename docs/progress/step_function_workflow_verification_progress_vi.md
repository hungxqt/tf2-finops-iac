# Tiến Trình Xác Minh Quy Trình Step Functions

## Trạng Thái: HOÀN THÀNH

**Ngày**: 2026-06-27  
**Tác Giả**: Implementation Agent  
**Phạm Vi**: lambda_src/tests/test_step_function_payload_contract.py + fixtures  

---

## Mục Tiêu

Thêm lớp xác minh cục bộ (repo-local) chứng minh quy trình Step Functions có đủ mọi
thành phần yêu cầu, mỗi state tiêu thụ đúng hình dạng đầu ra thực tế của state trước,
và luồng được triển khai khớp với AGENTS.md, docs/contracts/*, IMPLEMENTATION.md, và
tài liệu TF2 đang hoạt động.

---

## Các File Được Tạo/Sửa Đổi

| File | Mục Đích |
|------|----------|
| `lambda_src/tests/fixtures/__init__.py` | Package init cho module fixtures |
| `lambda_src/tests/fixtures/step_function_payloads.py` | 21 fixture dict xác định cho mọi ranh giới quy trình |
| `lambda_src/tests/test_step_function_payload_contract.py` | 77 bài kiểm tra payload-contract trong 9 nhóm (A-I) |

---

## Danh Sách Fixtures (21 fixtures)

1. `SCHEDULED_WORKFLOW_INPUT` - EventBridge Scheduler -> PrepareRunContext đầu vào
2. `POST_PREPARE_RUN_CONTEXT` - Sau thao tác prepare của state_lambda
3. `POST_INGEST_COST_DATA_S3` - Ingestion CUR sẵn sàng, chế độ S3_POINTER (mặc định hợp đồng)
4. `POST_INGEST_COST_DATA_CE` - CUR bị trễ, CE fallback hoạt động
5. `POST_NORMALIZE_HEALTHY` - Đầu ra chuẩn hóa chất lượng cao (completeness >= 0.8)
6. `POST_NORMALIZE_DEGRADED` - Telemetry bị suy giảm (completeness < 0.8, kích hoạt cổng dry-run)
7. `POST_NORMALIZE_POINTER` - Đầu ra chuẩn hóa chất lượng cao với con trỏ S3 hợp lệ theo hợp đồng
8. `POST_BUILD_DETECT_REQUEST` - Đầu ra Pass state BuildDetectRequestRawJson ($.ai_detect_request)
9. `POST_BUILD_DETECT_REQUEST_S3_POINTER` - Đầu ra Pass state BuildDetectRequestS3Pointer
10. `POST_BUILD_DETECT_REQUEST_CE_FALLBACK` - Đầu ra Pass state BuildDetectRequestRawJsonCeFallback
11. `POST_INVOKE_DETECT_ANOMALY` - /v1/detect trả về có bất thường
12. `POST_INVOKE_DETECT_NO_ANOMALY` - /v1/detect trả về sạch (không có bất thường)
13. `POST_INVOKE_DECIDE` - /v1/decide trả về action_plan + rollback_payload
14. `POST_FORMAT_DECIDE_RESULT` - FormatDecideResult Pass state ghi $.ai
15. `POST_ROUTER` - RouteAlert ghi $.alert với cả hai tuyến finance+engineering
16. `POST_CONTAINMENT_POLICY_APPLY` - sandbox+tag mode -> WritePreActionAudit
17. `POST_CONTAINMENT_POLICY_DENIED_PROD` - prod+terminate -> WriteDeniedAudit
18. `POST_CONTAINMENT_POLICY_DRYRUN_DENIED` - force_dry_run+apply -> WriteDeniedAudit
19. `POST_EXECUTE_CONTAINMENT` - Kết quả ExecuteContainment tại $.containment
20. `POST_VERIFY_RESULT` - Kết quả /v1/verify tại $.verify_result
21. `AI_FAIL_CLOSED_CONTEXT` - Sau SetAIFailClosedError, $.error được điền
22. `CUR_DELAY_EXCEEDED_CONTEXT` - Sau SetCURDelayExceededError, cur_retry.count=4

---

## Nhóm Kiểm Tra (77 bài kiểm tra, 9 nhóm)

| Nhóm | Tên | Số Lượng | Phạm Vi |
|------|-----|----------|---------|
| A | Kiểm Kê Thành Phần | 15 | ASL states, kiểm tra không có polling, VPC ALB caller, DynamoDB, SNS, SQS |
| B | Giải Quyết Payload | 18 | JSONPath resolver xác minh từng fixture ranh giới |
| C | Hợp Đồng Telemetry | 5 | Mặc định S3_POINTER, CE fallback, cờ chất lượng |
| D | Đường Detect | 10 | Hình dạng /v1/detect, khóa idempotency ổn định, các builder theo chế độ, truyền chế độ dry-run, fail-closed khi success=false |
| E | Đường Decide/Cache | 6 | Body /v1/decide, rollback_payload, ghi DynamoDB CacheRollbackPayload |
| F | Chính Sách Containment | 4 | Từ chối prod+destructive, từ chối dry-run, đường an toàn sandbox+tag |
| G | Đường Verify | 5 | Body /v1/verify, JSONPath action_executed.target, chuỗi audit |
| H | Đường Fail-Closed | 7 | Tham số audit AI fail-closed, CUR delay audit, ngưỡng số lần thử lại |
| I | Thông Điệp SQS/Trạng Thái | 5 | Chỉ có hàng đợi rollback_status, giá trị trạng thái APPLIED/DENIED/PENDING |

---

## Kết Quả Kiểm Tra

```
77 passed in 0.19s (chỉ kiểm tra payload contract)
88 passed in 0.45s (payload contract + state machine + lambda coverage + vpc alb caller)
107 passed in 3.93s (toàn bộ suite, 0 thất bại)
```

---

## Thiết Kế Bộ Giải Quyết JSONPath

Bộ giải quyết ASL nhẹ trong file kiểm tra hỗ trợ tập con được sử dụng bởi state machine này:

- `"$"` -> toàn bộ dict context  
- `"$.a.b.c"` -> duyệt key lồng nhau  
- `"$.anomalies_list[0].anomaly_id"` -> chỉ số mảng sau đó key
- `"States.Format"` -> đánh giá hàm intrinsic format string với các đối số JSONPath được giải quyết

Điều này đủ để xác minh tất cả Task.Parameters, JSONPaths của Pass state, và đường dẫn
biến Choice mà không cần mô phỏng runtime ASL đầy đủ.

---

## Phát Hiện Xác Minh Chính

Không phát hiện khoảng trống payload nào. Các thuộc tính hợp đồng sau đây đã được xác minh:

1. **Ingestion CUR sẵn sàng** - `$.ingestion.details.data_source_type` = `S3_POINTER` (mặc định hợp đồng telemetry)
2. **SelectDetectRequestMode** - chọn đúng chế độ request builder dựa trên `detect_request_mode`:
   - `S3_POINTER`: mặc định khi con trỏ hợp lệ khớp với `^s3://company-cdo-[0-9]{12}-telemetry/.+\.json\.gz$`
   - `RAW_JSON`: fallback dòng CUR khi khớp con trỏ thất bại hoặc vắng mặt
   - `RAW_JSON` CE fallback: fallback metrics cost explorer khi `telemetry_delay_event` là true
3. **Khóa Idempotency Ổn Định** - được tính toán trước InvokeDetect bằng cách sử dụng `{tenant_id}:{execution_date}:{batch_type}` thay vì `correlation_id`
4. **VpcAlbCallerLambda Dry-run mode** - truyền `dry_run_mode` vào InvokeDetect để phản ánh suy giảm telemetry/hạn mức lỗi
5. **InvokeDetect** - đọc các tham số từ `$.ai_detect_request` (động, đường dẫn `/v1/detect`, truyền path, tenant_id, khóa idempotency ổn định, dry_run_mode, và body)
6. **Body InvokeDecide** - `anomaly_context.$` giải quyết thành `$.ai_detect_response.anomalies_list[0]`
7. **CacheRollbackPayload** - DynamoDB putItem với `rollback_payload` được tuần tự hóa qua `States.JsonToString`
8. **FormatDecideResult** - đọc `action_plan[0].action` và `anomalies_list[0].anomaly_id`
9. **ReportVerifyResult** - `action_executed.target.$` giải quyết từ `anomalies_list[0].resource_id`
10. **FailClosed/WriteCURDelayAudit** - tất cả 9 trường ngữ cảnh audit yêu cầu giải quyết đúng
11. **EvaluateContainmentPolicy** - từ chối prod+destructive và từ chối dry-run đều được mã hóa trong ASL
12. **SQS** - chỉ có hàng đợi `rollback_status_queue_url` trong ASL; không có hàng đợi detection

---

## Ghi Chú Thẩm Quyền Đang Hoạt Động

- `ai_poll_interval` trong Parameters của PrepareRunContext là trường cấu hình thử lại hợp lệ (không phải hàng đợi detection)
- Không phát hiện ECS, Fargate, detection SQS, hoặc vòng lặp polling trong bất kỳ đường dẫn nào được xác minh
- Đường tích hợp AI Engine đang hoạt động được xác minh: Step Functions → VpcAlbCallerLambda → ALB → AI Request Lambda

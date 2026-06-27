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

## Các File Được Tạo

| File | Mục Đích |
|------|----------|
| `lambda_src/tests/fixtures/__init__.py` | Package init cho module fixtures |
| `lambda_src/tests/fixtures/step_function_payloads.py` | 19 fixture dict xác định cho mọi ranh giới quy trình |
| `lambda_src/tests/test_step_function_payload_contract.py` | 73 bài kiểm tra payload-contract trong 9 nhóm (A-I) |

---

## Danh Sách Fixtures (19 fixtures)

1. `SCHEDULED_WORKFLOW_INPUT` - EventBridge Scheduler -> PrepareRunContext đầu vào
2. `POST_PREPARE_RUN_CONTEXT` - Sau thao tác prepare của state_lambda
3. `POST_INGEST_COST_DATA_S3` - Ingestion CUR sẵn sàng, chế độ S3_POINTER (mặc định hợp đồng)
4. `POST_INGEST_COST_DATA_CE` - CUR bị trễ, CE fallback hoạt động
5. `POST_NORMALIZE_HEALTHY` - Đầu ra chuẩn hóa chất lượng cao (completeness >= 0.8)
6. `POST_NORMALIZE_DEGRADED` - Telemetry bị suy giảm (completeness < 0.8, kích hoạt cổng dry-run)
7. `POST_BUILD_DETECT_REQUEST` - Đầu ra Pass state BuildDetectRequest ($.ai_detect_request)
8. `POST_INVOKE_DETECT_ANOMALY` - /v1/detect trả về có bất thường
9. `POST_INVOKE_DETECT_NO_ANOMALY` - /v1/detect trả về sạch (không có bất thường)
10. `POST_INVOKE_DECIDE` - /v1/decide trả về action_plan + rollback_payload
11. `POST_FORMAT_DECIDE_RESULT` - FormatDecideResult Pass state ghi $.ai
12. `POST_ROUTER` - RouteAlert ghi $.alert với cả hai tuyến finance+engineering
13. `POST_CONTAINMENT_POLICY_APPLY` - sandbox+tag mode -> WritePreActionAudit
14. `POST_CONTAINMENT_POLICY_DENIED_PROD` - prod+terminate -> WriteDeniedAudit
15. `POST_CONTAINMENT_POLICY_DRYRUN_DENIED` - force_dry_run+apply -> WriteDeniedAudit
16. `POST_EXECUTE_CONTAINMENT` - Kết quả ExecuteContainment tại $.containment
17. `POST_VERIFY_RESULT` - Kết quả /v1/verify tại $.verify_result
18. `AI_FAIL_CLOSED_CONTEXT` - Sau SetAIFailClosedError, $.error được điền
19. `CUR_DELAY_EXCEEDED_CONTEXT` - Sau SetCURDelayExceededError, cur_retry.count=4

---

## Nhóm Kiểm Tra (73 bài kiểm tra, 9 nhóm)

| Nhóm | Tên | Số Lượng | Phạm Vi |
|------|-----|----------|---------|
| A | Kiểm Kê Thành Phần | 15 | ASL states, kiểm tra không có polling, VPC ALB caller, DynamoDB, SNS, SQS |
| B | Giải Quyết Payload | 18 | JSONPath resolver xác minh từng fixture ranh giới |
| C | Hợp Đồng Telemetry | 5 | Mặc định S3_POINTER, CE fallback, cờ chất lượng |
| D | Đường Detect | 6 | Hình dạng /v1/detect, fail-closed khi success=false và data_confidence=LOW |
| E | Đường Decide/Cache | 6 | Body /v1/decide, rollback_payload, ghi DynamoDB CacheRollbackPayload |
| F | Chính Sách Containment | 4 | Từ chối prod+destructive, từ chối dry-run, đường an toàn sandbox+tag |
| G | Đường Verify | 5 | Body /v1/verify, JSONPath action_executed.target, chuỗi audit |
| H | Đường Fail-Closed | 7 | Tham số audit AI fail-closed, CUR delay audit, ngưỡng số lần thử lại |
| I | Thông Điệp SQS/Trạng Thái | 5 | Chỉ có hàng đợi rollback_status, giá trị trạng thái APPLIED/DENIED/PENDING |

---

## Kết Quả Kiểm Tra

```
73 passed in 0.14s (chỉ kiểm tra payload contract)
84 passed in 0.39s (payload contract + state machine + lambda coverage + vpc alb caller)
187 passed in 5.74s (toàn bộ suite, 0 thất bại)
```

---

## Thiết Kế Bộ Giải Quyết JSONPath

Bộ giải quyết ASL nhẹ trong file kiểm tra hỗ trợ tập con được sử dụng bởi state machine này:

- `"$"` -> toàn bộ dict context  
- `"$.a.b.c"` -> duyệt key lồng nhau  
- `"$.anomalies_list[0].anomaly_id"` -> chỉ số mảng sau đó key

Điều này đủ để xác minh tất cả Task.Parameters, JSONPaths của Pass state, và đường dẫn
biến Choice mà không cần mô phỏng runtime ASL đầy đủ.

---

## Phát Hiện Xác Minh Chính

Không phát hiện khoảng trống payload nào. Các thuộc tính hợp đồng sau đây đã được xác minh:

1. **Ingestion CUR sẵn sàng** - `$.ingestion.details.data_source_type` = `S3_POINTER` (mặc định hợp đồng telemetry)
2. **BuildDetectRequest** - `$.normalized.details.aws_cur_line_items` có thể đọc và không rỗng trong chuẩn hóa tốt
3. **InvokeDetect** - đọc `path` từ `$.ai_detect_request.path` (động, xác nhận `/v1/detect`)
4. **Body InvokeDecide** - `anomaly_context.$` giải quyết thành `$.ai_detect_response.anomalies_list[0]`
5. **CacheRollbackPayload** - DynamoDB putItem với `rollback_payload` được tuần tự hóa qua `States.JsonToString`
6. **FormatDecideResult** - đọc `action_plan[0].action` và `anomalies_list[0].anomaly_id`
7. **ReportVerifyResult** - `action_executed.target.$` giải quyết từ `anomalies_list[0].resource_id`
8. **FailClosed/WriteCURDelayAudit** - tất cả 9 trường ngữ cảnh audit yêu cầu giải quyết đúng
9. **EvaluateContainmentPolicy** - từ chối prod+destructive và từ chối dry-run đều được mã hóa trong ASL
10. **SQS** - chỉ có hàng đợi `rollback_status_queue_url` trong ASL; không có hàng đợi detection

---

## Ghi Chú Thẩm Quyền Đang Hoạt Động

- `ai_poll_interval` trong Parameters của PrepareRunContext là trường cấu hình thử lại hợp lệ (không phải hàng đợi detection)
- Không phát hiện ECS, Fargate, detection SQS, hoặc vòng lặp polling trong bất kỳ đường dẫn nào được xác minh
- Đường tích hợp AI Engine đang hoạt động được xác minh: Step Functions → VpcAlbCallerLambda → ALB → AI Request Lambda

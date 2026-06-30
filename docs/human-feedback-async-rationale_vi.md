# Vì sao tách Human Feedback thành luồng bất đồng bộ riêng

## Tóm tắt quyết định

Human feedback cho `POST /v1/feedback` được triển khai thành một Step Functions workflow riêng, bất đồng bộ với daily FinOps detection workflow.

Workflow chính vẫn phụ trách chuỗi xử lý có tính thời gian thực theo batch: kéo telemetry, normalize, gọi `/v1/detect`, `/v1/decide`, `/v1/verify`, route alert, containment dry-run/apply theo guardrail, và ghi audit. Feedback của SRE/Engineer được gửi sau đó qua một execution riêng, bắt đầu từ Slack hoặc dashboard backend khi có người review kết quả anomaly.

## Bối cảnh

Theo `docs/contracts/telemetry-contract.md` section 15, `HumanFeedback` là payload để CDO/SRE gửi về AI Engine nhằm calibrate detection trong active learning loop. Payload gồm:

```json
{
  "anomaly_id": "ANM-2026-0628A",
  "reviewer_id": "U12345678",
  "verdict": "FALSE_POSITIVE",
  "reason": "Spike came from approved campaign traffic.",
  "reviewed_at": "2026-06-28T10:15:00Z"
}
```

Các giá trị `verdict` hợp lệ là:

- `TRUE_POSITIVE`
- `FALSE_POSITIVE`
- `BENIGN_EVENT`

Điểm quan trọng: feedback là tín hiệu hậu kiểm của con người. Nó giúp AI Engine học và giảm false positive trong tương lai, nhưng không phải dữ liệu bắt buộc để hoàn tất lần detect hiện tại.

## Lý do tách riêng

### 1. Không chặn critical path của detection

Daily workflow là đường xử lý chính của hệ thống FinOps Watch. Nó cần hoàn thành theo cadence 24h, phát hiện bất thường, route cảnh báo, ghi audit, và bảo toàn trạng thái fail-closed.

Human feedback phụ thuộc vào thao tác của con người. Review có thể xảy ra sau vài phút, vài giờ, hoặc thậm chí ngày hôm sau. Nếu nhúng `/v1/feedback` vào workflow chính, execution chính sẽ phải chờ một sự kiện không xác định thời điểm, làm tăng timeout risk và làm phức tạp trạng thái batch.

Tách riêng giúp workflow chính kết thúc sạch sau khi đã hoàn tất detection/alert/audit.

### 2. Feedback không quyết định containment hiện tại

Containment phải dựa trên kết quả `/v1/detect`, `/v1/decide`, `/v1/verify`, telemetry quality, policy guardrails, error budget, và môi trường chạy. Feedback của SRE/Engineer là tín hiệu để cải thiện model hoặc rule trong các lần sau.

Nếu feedback nằm trong workflow chính, dễ tạo hiểu nhầm rằng hệ thống cần feedback trước khi containment hoặc audit được coi là hoàn tất. Điều đó không đúng với vai trò của section 15.

### 3. Tách failure domain

Nếu AI Engine endpoint `/v1/feedback` lỗi, timeout, hoặc bị rate limit, lỗi đó không nên làm daily detection workflow thất bại. Detection đã hoàn thành thì audit detection vẫn phải giữ nguyên.

Với workflow riêng:

- Lỗi gửi feedback chỉ làm fail execution feedback.
- Hệ thống vẫn ghi audit `human-feedback-delivery-failed`.
- Daily workflow không bị rollback trạng thái hoặc bị đánh dấu thất bại sai.

### 4. Dễ retry và idempotency hơn

Feedback có pattern retry riêng. Một reviewer có thể submit lại cùng feedback, hoặc Slack/dashboard backend có thể retry khi gặp lỗi mạng.

Workflow hiện tại tạo `idempotency_key` theo dạng:

```text
{tenant_id}:{anomaly_id}:{reviewer_id}:feedback
```

Cách này giúp AI Engine deduplicate theo từng reviewer và anomaly, độc lập với idempotency key của detect batch. Nếu feedback nằm chung workflow chính, idempotency của batch detection và idempotency của review event sẽ bị trộn lẫn.

### 5. Audit rõ ràng hơn

Feedback là một audit event riêng, có actor riêng (`reviewer_id`), timestamp riêng (`reviewed_at`), lý do riêng (`reason`), và kết quả riêng (`verdict`).

Tách workflow cho phép ghi các action rõ ràng:

- `human-feedback-submitted`
- `human-feedback-delivery-failed`
- `human-feedback-invalid`

Như vậy audit trail phân biệt được:

- Hệ thống đã detect gì.
- Hệ thống đã quyết định/alert/containment như thế nào.
- Con người review kết quả đó sau này ra sao.

### 6. Phù hợp với nguồn phát sinh feedback

Feedback không phát sinh từ scheduler 24h. Nó phát sinh từ UI/operator flow, ví dụ:

- SRE bấm confirm trong Slack.
- Engineer đánh dấu false positive trên dashboard.
- Finance hoặc owner xác nhận spike là campaign hợp lệ.

Các nguồn này nên gọi `StartExecution` vào `feedback_state_machine_arn` thay vì cố gắng đẩy event ngược vào execution daily đã kết thúc.

### 7. Giữ workflow chính đơn giản và dễ kiểm chứng

Daily state machine đã có nhiều nhánh quan trọng: telemetry quality, CUR delay, detect/decide/verify, alert routing, containment guardrails, rollback cache, audit evidence.

Nếu thêm feedback vào cùng state machine, workflow chính sẽ phải chứa thêm các nhánh không thuộc batch detection. Điều đó làm ASL khó review hơn, test khó hơn, và tăng nguy cơ thay đổi feedback làm ảnh hưởng đường containment.

Tách riêng giúp test rõ ràng:

- `docs/statemachine.json` không chứa `/v1/feedback`.
- `docs/feedback-statemachine.json` chỉ xử lý feedback.
- Unit test có thể đảm bảo hai workflow không bị trộn.

## Luồng triển khai đề xuất

Luồng bất đồng bộ hiện tại:

```text
Slack/Dashboard Review
  -> StartExecution(feedback_state_machine_arn)
  -> ValidateHumanFeedback
  -> VpcAlbCallerLambda POST /v1/feedback
  -> WriteHumanFeedbackAudit
  -> FeedbackCompleted
```

Khi payload không hợp lệ:

```text
StartExecution
  -> ValidateHumanFeedback
  -> WriteInvalidHumanFeedbackAudit
  -> FeedbackFailed
```

Khi gửi `/v1/feedback` thất bại:

```text
StartExecution
  -> ValidateHumanFeedback
  -> SubmitHumanFeedback retry
  -> WriteHumanFeedbackFailureAudit
  -> FeedbackFailed
```

## Payload execution mẫu

```json
{
  "run_id": "feedback-2026-06-28-001",
  "tenant_id": "11111111-1111-4111-8111-111111111111",
  "correlation_id": "22222222-2222-4222-8222-222222222222",
  "account_id": "123456789012",
  "cost_period": "2026-06-28",
  "execution_date": "2026-06-29",
  "ai_contract_version": "v1",
  "human_feedback": {
    "anomaly_id": "ANM-2026-0628A",
    "reviewer_id": "U12345678",
    "verdict": "FALSE_POSITIVE",
    "reason": "Traffic spike was caused by an approved launch campaign.",
    "reviewed_at": "2026-06-28T10:15:00Z"
  }
}
```

Workflow sẽ gọi `VpcAlbCallerLambda` với payload đến AI Engine:

```json
{
  "path": "/v1/feedback",
  "method": "POST",
  "tenant_id": "11111111-1111-4111-8111-111111111111",
  "correlation_id": "22222222-2222-4222-8222-222222222222",
  "idempotency_key": "11111111-1111-4111-8111-111111111111:ANM-2026-0628A:U12345678:feedback",
  "ai_contract_version": "v1",
  "dry_run_mode": true,
  "body": {
    "anomaly_id": "ANM-2026-0628A",
    "reviewer_id": "U12345678",
    "verdict": "FALSE_POSITIVE",
    "reason": "Traffic spike was caused by an approved launch campaign.",
    "reviewed_at": "2026-06-28T10:15:00Z"
  }
}
```

## Vì sao không gọi `/v1/feedback` trực tiếp từ dashboard hoặc Slack

Dashboard/Slack backend có thể là nơi khởi phát feedback, nhưng không nên gọi thẳng AI Engine nếu muốn giữ cùng guardrail với CDO platform.

Đi qua Step Functions giúp:

- Validate payload trước khi gọi AI Engine.
- Chuẩn hóa tenant/correlation/idempotency context.
- Retry theo policy thống nhất.
- Ghi audit cho cả success, invalid payload, và delivery failure.
- Không phải nhúng logic gọi private ALB/SigV4 vào từng UI integration.

## Trade-off

Tách riêng workflow làm tăng thêm một state machine và một output Terraform (`feedback_state_machine_arn`). Tuy nhiên chi phí vận hành này nhỏ hơn lợi ích về isolation, auditability, retry, và khả năng review.

Điểm cần lưu ý là Slack/dashboard backend phải biết gọi đúng `feedback_state_machine_arn` thay vì kỳ vọng workflow daily còn đang chạy.

## Kết luận

Tách `/v1/feedback` thành luồng bất đồng bộ riêng là hướng hợp lý nhất vì feedback là tín hiệu hậu kiểm, phụ thuộc con người, không thuộc critical path của detection/containment, và cần audit/retry/idempotency riêng.

Cách này giữ workflow chính ổn định, giảm blast radius khi feedback endpoint lỗi, và vẫn đáp ứng telemetry-contract section 15 cho active learning loop.

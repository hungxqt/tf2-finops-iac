# Tiến độ Cập nhật AGENTS.md cho Lambda Container

## Trạng thái
Hoàn thành (Completed)

## Phạm vi
Cập nhật tài liệu điều khiển AGENTS.md, thay thế toàn bộ hướng dẫn hosting AI bằng ECS/Fargate/ALB sang hướng dẫn hosting bằng Lambda container image. Không thay đổi tài nguyên Terraform hoặc state. Không chỉnh sửa `docs/contracts/**` hoặc `docs/tf2-finops/**`.

Các thay đổi chính:
- Thay thế phạm vi hosting ECS/Fargate bằng phạm vi hosting Lambda container (`modules/ai-runtime-lambda`).
- Làm rõ rằng nội dung ECS/ALB/API Gateway trong `docs/contracts/**` là nội dung transport đã lỗi thời (stale).
- Xác định `docs/tf2-finops/01, 02, 04, 08_adrs.md` là nguồn sự thật (source of truth) cho nền tảng runtime.
- Cập nhật thứ tự triển khai: `modules/ai-runtime-lambda` được thêm vào bước 8, trước `modules/orchestration`.
- Cập nhật danh sách kiểm tra validation với các mục đặc thù cho Lambda container (ECR digest pinning, scan-on-push, aliases, reserved concurrency, `maximum_concurrency`, KMS-encrypted logs, X-Ray, VPC private subnets).
- Cập nhật các quy tắc bảo mật: thay thế các quy tắc internal ALB/HTTPS endpoint bằng các hạn chế VPC private subnet/Lambda function URL và ECR digest pinning.
- Cập nhật xử lý xung đột (conflict handling) với danh sách loại trừ công nghệ lỗi thời rõ ràng và hướng dẫn bảo toàn ý định hành vi (behavioral-intent).
- Cập nhật phần AI API contract: mô tả direct Lambda invocation và DynamoDB getItem polling là cách triển khai ngữ nghĩa `/v1/detect`.

## Các file đã thay đổi
- Chỉnh sửa:
  - `AGENTS.md`

## Lệnh kiểm tra
```powershell
rg -n "ECS|Fargate|ALB|EKS|Kubernetes|k8s|Argo|API Gateway" AGENTS.md
rg -n "Lambda container|Request Lambda|Worker Lambda|SQS|DLQ|DynamoDB|ECR|reserved concurrency|modules/ai-runtime-lambda" AGENTS.md
```

## Kết quả
- Kiểm tra thuật ngữ cũ: Các tham chiếu ECS/ALB/EKS/API Gateway chỉ xuất hiện trong phần xử lý xung đột (dòng 290-292) nơi chúng được liệt kê rõ ràng là **không** thuộc nền tảng hiện tại, và trong quy tắc bảo mật (dòng 499) cấm public API Gateways. Không còn hướng dẫn hosting AI cơ bản nào cho các thuật ngữ đó.
- Kiểm tra thuật ngữ Lambda: Tất cả các trách nhiệm Lambda container cần thiết đều có mặt trong các phần Repository Scope, Implementation Rules, Contract Handling, AI API Contract, Deployment/SLO, Implementation Order, Validation, và Security Rules.

## Vướng mắc
Không có

## Bước tiếp theo
Không cần hành động thêm cho thay đổi tài liệu điều khiển này. Các thay đổi Terraform trong tương lai cần tuân theo hướng dẫn AGENTS.md đã cập nhật.

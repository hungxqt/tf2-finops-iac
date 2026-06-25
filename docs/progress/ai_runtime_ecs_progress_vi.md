# Tiến độ AI Runtime ECS

## Trạng thái
ĐÃ BỊ THAY THẾ (SUPERSEDED) bởi Lambda Container Runtime

## Phạm vi
Triển khai module hạ tầng chạy thực tế ECS/Fargate (`modules/ai-runtime-ecs`) để hosting cho AI Engine phát hiện bất thường, thay thế cho kế hoạch EKS cũ đã lỗi thời.

> [!NOTE]
> Module này đã bị thay thế hoàn toàn bởi `modules/ai-runtime-lambda` do mô hình triển khai của AI Engine chuyển sang AWS Lambda Container Images.

## Các file đã thay đổi
- Đã xóa:
  - `modules/ai-runtime-ecs/main.tf`
  - `modules/ai-runtime-ecs/outputs.tf`
  - `modules/ai-runtime-ecs/variables.tf`
  - `modules/ai-runtime-ecs/versions.tf`
  - `modules/ai-runtime-ecs/README.md`

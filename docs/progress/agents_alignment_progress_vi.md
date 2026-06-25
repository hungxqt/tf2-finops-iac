# Tiến độ đồng bộ hóa hợp đồng AGENTS.md

## Trạng thái
Completed

## Phạm vi
Cập nhật AGENTS.md để đồng bộ với cấu trúc và hợp đồng hiện tại trong `docs/tf2-finops`, giải quyết các điểm mâu thuẫn và chi tiết hóa ánh xạ endpoint logic, bộ nhớ cache trạng thái/lưu trữ, cách sử dụng SQS, các chế độ ingestion telemetry và mục tiêu dashboard.

## Các file đã thay đổi
- [AGENTS.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/AGENTS.md) (Modified)

## Lệnh kiểm tra
- Chạy kiểm tra git diff: `git diff --check -- AGENTS.md`
- Grep các thuật ngữ bắt buộc:
  `rg -n "finops-idempotency|finops-rollback-cache|company-cdo-|S3_POINTER|RAW_JSON|SigV4|/v1/detect|/v1/decide|/v1/verify|/v1/status|/v1/audit" AGENTS.md`
- Grep kiểm tra các thuật ngữ cũ/bị thay thế:
  `rg -n "Private API Gateway|ECS Cluster|Fargate capacity|Argo CD|Kubernetes|primary detection polling|/v1/status.*detection" AGENTS.md`

## Kết quả
- Các kiểm tra non-apply đã chạy thành công.
- Các kiểm tra diff không có lỗi định dạng hay khoảng trắng thừa.
- Các thuật ngữ và ngữ nghĩa hợp đồng bắt buộc được cập nhật chính xác trong AGENTS.md.
- Các thuật ngữ nền tảng cũ được đưa vào ngữ cảnh là từ ngữ cũ/bị thay thế (stale/superseded) một cách chính xác.

## Vướng mắc
None

## Bước tiếp theo
Duy trì quy trình kiểm tra module tiêu chuẩn trong các lần cập nhật tiếp theo.

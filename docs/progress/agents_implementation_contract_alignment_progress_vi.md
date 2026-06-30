# Tiến độ Đồng bộ Hợp đồng và Hướng dẫn triển khai

## Trạng thái
Completed

## Phạm vi
Cập nhật `AGENTS.md` và `IMPLEMENTATION.md` để các hoạt động phát triển tiếp theo tuân thủ theo các hợp đồng hành vi hiện tại trong `docs/contracts/**` và `docs/tf2-finops/**`: IaC nền tảng AWS do Terraform làm chủ, AI Engine chạy trên nền tảng Lambda container đặt sau một private internal ALB, cơ chế `/v1/detect` đồng bộ, không có hàng đợi SQS phát hiện hoặc vòng lặp polling kết quả, CDO thực thi rollback trực tiếp, và các giá trị mặc định của dashboard sử dụng S3 + CloudFront + Cognito. Đồng thời cập nhật tài liệu hướng dẫn về thông tin bàn giao và xác thực.

## Các file đã thay đổi
- [AGENTS.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/AGENTS.md)
- [IMPLEMENTATION.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/IMPLEMENTATION.md)
- [docs/GUIDES.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES.md)
- [docs/GUIDES_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES_vi.md)

## Lệnh kiểm tra
```powershell
# Grep tìm các thuật ngữ mới để đảm bảo chúng đã được ghi nhận như yêu cầu hoạt động hiện tại
rg -n "vpc_alb_caller|private internal ALB|S3_POINTER|RAW_JSON|finops-idempotency|finops-rollback-cache|rollback_payload.boto3_equivalent|data_confidence|use_lockfile" AGENTS.md IMPLEMENTATION.md

# Grep tìm các thuật ngữ cũ/lỗi thời để đảm bảo chúng không hiển thị như yêu cầu hoạt động hiện tại
rg -n "ai_client|SQS detection queue|DynamoDB result-polling|Function URL|Private API Gateway|ECS Cluster|Fargate capacity" AGENTS.md IMPLEMENTATION.md
```

## Kết quả
- Các truy vấn grep xác nhận rằng tất cả các yêu cầu hoạt động đều chỉ định luồng đồng bộ private ALB sử dụng `vpc_alb_caller`, với `finops-idempotency` và `finops-rollback-cache` được ghi chép đúng đắn.
- Không có thuật ngữ cũ (`ai_client` hoặc `SQS detection queue` / vòng lặp polling) xuất hiện dưới dạng yêu cầu hoạt động; chúng chỉ được nhắc đến trong các ghi chú xử lý xung đột như các thuật ngữ tham chiếu hoặc đã bị thay thế.
- Các tài liệu hướng dẫn `docs/GUIDES.md` và `docs/GUIDES_vi.md` đã được cập nhật với các thông tin bàn giao và lệnh kiểm tra Checkov tương ứng.
- Không yêu cầu kiểm tra hạ tầng (infrastructure validation) đối với các thay đổi chỉ liên quan đến tài liệu này.

## Vướng mắc
None

## Bước tiếp theo
Tiến hành triển khai các tác vụ hạ tầng dựa trên backlog đã đồng bộ.

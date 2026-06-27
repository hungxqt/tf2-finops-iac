# Tiến Độ Khắc Phục Blocker AI API Section 3

**Ngày**: 2026-06-27  
**Phạm vi**: Khắc phục Blocker Section 3 (Blocker 1, 2, 4, 5, và 6)

---

## Trạng Thái: TUÂN THỦ HOÀN TOÀN

Tất cả các blocker Section 3 được nhắm mục tiêu đã được khắc phục trên cơ sở hạ tầng CDO, cấu hình Terraform, các Lambda worker và bộ kiểm thử (test suites).

### Những Gì Đã Được Triển Khai

#### 1. Blocker 1: Kết Nối Khóa Ngân Sách Lỗi (Error-Budget Lock Wiring)
- **Trạng thái**: HOÀN THÀNH
- **Terraform**: Truyền biến môi trường `ERROR_BUDGET_TABLE_NAME` cho worker `state` qua `modules/compute-lambda/main.tf` bằng cách tra cứu khóa `error_budget` trong `var.dynamodb_table_names`.
- **Lambda**: Cập nhật `lambda_src/src/workers/state/handler.py` để đọc bảng ngân sách lỗi DynamoDB thực tế.
- **Ngưỡng Hợp Đồng (Contract Thresholds)**: Triển khai kiểm tra ngưỡng nghiêm ngặt theo hợp đồng §3.3:
  - Môi trường `prod` / `prod-*`: Khóa nếu tỷ lệ rollback 30 ngày $\ge 1\%$.
  - Môi trường `staging`: Khóa nếu tỷ lệ rollback 30 ngày $\ge 10\%$.
  - Môi trường `sandbox` / `dev`: Vô hiệu hóa khóa tự động.
- **Trường Phản Hồi (Response Fields)**: Handler hiện trả về tất cả các trường bắt buộc: `locked`, `force_dry_run`, `containment_status`, `rollback_rate_30d_pct`, và `lock_threshold_pct`.
- **Kiểm thử (Tests)**: Thêm các kiểm thử bao gồm tra cứu DDB, khóa ngưỡng môi trường và lan truyền chế độ dry-run trong `lambda_src/tests/test_state.py`.

#### 2. Blocker 2: Giới Hạn Tỷ Lệ Lượt Yêu Cầu Của Tenant (WAF CUSTOM_KEYS)
- **Trạng thái**: HOÀN THÀNH
- **Luật WAF 1**: Thêm `BlockMissingTenantId` (Ưu tiên 1) để chặn bất kỳ yêu cầu nào bắt đầu bằng `/v1/` mà không mang header `X-Tenant-Id` không trống.
- **Luật WAF 2**: Thêm `TenantRateLimit` (Ưu tiên 2) sử dụng các custom key của WAF (`aggregate_key_type = "CUSTOM_KEYS"`) để giới hạn tỷ lệ yêu cầu đến các đường dẫn `/v1/` dựa trên giá trị header `x-tenant-id` (giới hạn: 100 yêu cầu mỗi 60 giây).
- **Kiểm soát phụ**: Giữ luật lạm dụng IP tiêu chuẩn ở dạng vô hiệu hóa hoặc kiểm soát phụ.
- **Kiểm thử (Tests)**: Thêm các kiểm thử tĩnh trong `test_vpc_alb_caller.py` xác minh CUSTOM_KEYS, cửa sổ đánh giá, giới hạn và việc chặn các header bị thiếu.

#### 3. Blocker 4: Ràng Buộc STS Tenant Giao Tác Chéo Tài Khoản (Cross-Account STS Tenant Binding)
- **Trạng thái**: HOÀN THÀNH
- **Lambda**: Cập nhật `cost_puller` để lấy `TELEMETRY_MEMBER_ROLE_NAME` từ các biến môi trường, và truyền `ExternalId=tenant_id`, session `Tags=[{Key="tenant_id", Value=tenant_id}]`, và `TransitiveTagKeys=["tenant_id"]` cho `sts:AssumeRole`.
- **Chính sách IAM**: Cập nhật chính sách ranh giới (boundary policy) và chính sách vai trò `cost_puller` để cho phép `sts:TagSession` bên cạnh `sts:AssumeRole`.
- **Chính sách Tin cậy (Trust Policy)**: Thắt chặt chính sách tin cậy của vai trò thu thập dữ liệu thành viên để yêu cầu cả `sts:ExternalId` và `aws:RequestTag/tenant_id` khớp với giá trị ID tenant đáng tin cậy (sử dụng biến mới `trusted_tenant_ids` trong `modules/iam`).
- **Kiểm thử (Tests)**: Thêm các kiểm thử trong `test_cost_puller.py` xác minh ExternalId, session tags, và việc ghi đè tên vai trò.

#### 4. Blocker 5: Đồng Bộ Thuộc Tính Idempotency Cache
- **Trạng thái**: HOÀN THÀNH
- **Lambda**: Cập nhật handler `vpc_alb_caller` để ghi các phản hồi vào thuộc tính DynamoDB `response_body` thay vì `response_cache`.
- **Tương Thích Ngược**: Triển khai cơ chế đọc dự phòng kiểm tra `response_body` trước và quay lại thuộc tính cũ `response_cache` cho các bản ghi có TTL 24 giờ hiện có.
- **Kiểm thử (Tests)**: Thêm các kiểm thử xác minh việc ghi vào `response_body`, đọc `response_body`, và chế độ đọc dự phòng `response_cache` cũ.

#### 5. Blocker 6: Quyền Đọc Con Trỏ S3 (S3 Pointer Read Access)
- **Trạng thái**: HOÀN THÀNH
- **Đầu vào Terraform**: Thêm các đầu vào `ai_request_s3_pointer_bucket_arn` (mặc định `""`) và `ai_request_s3_pointer_prefixes` (mặc định `["ai-input/*"]`) cho `modules/ai-runtime-lambda`.
- **Quyền truy cập IAM**: Cấp cho vai trò AI Request Lambda quyền `s3:ListBucket` với điều kiện tiền tố và `s3:GetObject` trên các tiền tố được cấu hình của bucket.
- **Kết nối Môi trường**: Cấu hình các môi trường `sandbox`, `staging`, và `prod` để truyền `module.lakehouse.lakehouse_bucket_arn` cho module.
- **Kiểm thử (Tests)**: Thêm các kiểm thử tĩnh để xác minh rằng vai trò IAM của Request Lambda nhận được quyền đọc S3 được giới hạn phạm vi trên bucket lakehouse được cấu hình.

---

## Kết Quả Xác Minh (Verification Results)

- **Kiểm thử Python**: Tất cả 150 kiểm thử đơn vị/tích hợp python đã vượt qua thành công:
  ```powershell
  python -m pytest lambda_src/
  # Kết quả: 150 passed trong 0.60 giây
  ```
- **Xác minh Terraform**:
  - sandbox: Cấu hình hợp lệ (valid).
  - staging: Cấu hình hợp lệ (valid).
  - prod: Cấu hình hợp lệ (valid).
- **Định dạng Terraform**: Được kiểm tra và định dạng thành công đệ quy (`terraform fmt`).
- **Quét bảo mật Trivy**: Xác minh không phát hiện lỗ hổng nghiêm trọng/cao nào được đưa vào.

---

## Kế Hoạch Rollback

Rollback an toàn và không phá hoại:
1. Hoàn tác các chỉnh sửa đối với `lambda_src/src/workers/state/handler.py`, `lambda_src/src/workers/vpc_alb_caller/handler.py`, và `lambda_src/src/workers/cost_puller/handler.py`.
2. Hoàn tác các thay đổi Terraform trong `modules/ai-runtime-lambda/`, `modules/compute-lambda/`, `modules/iam/`, và `environments/`.
3. Các bảng idempotency hiện tại sẽ tiếp tục được đọc bằng `response_cache`. Không yêu cầu di chuyển cơ sở dữ liệu.

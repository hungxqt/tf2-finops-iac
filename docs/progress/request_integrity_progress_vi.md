# Tiến Độ Tính Toàn Vẹn Yêu Cầu

**Ngày**: 2026-06-27  
**Phạm vi**: Các blocker tính toàn vẹn yêu cầu Section-3 - Quyền IAM, thực thi header, và cổng triển khai

---

## Trạng Thái: TUÂN THỦ TỪNG PHẦN - Cần Cổng Triển Khai

### Những Gì Đã Được Triển Khai (Thuộc Sở Hữu CDO/Terraform)

#### 1. IAM: Chính Sách Idempotency Riêng Cho vpc_alb_caller
- **Trạng thái**: HOÀN THÀNH
- **Thay đổi**: Thêm `aws_iam_role_policy.vpc_alb_caller_idempotency` vào `modules/iam/main.tf`
- **Phạm vi**: Đặc quyền tối thiểu - chỉ cấp `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem` trên ARN bảng `ai_payload_idempotency` cụ thể (không phải wildcard)
- **Biến**: `ai_payload_idempotency_table_arn` thêm vào `modules/iam/variables.tf`
- **Kết nối**: Cả ba môi trường (sandbox, staging, prod) truyền `module.orchestration.dynamodb_table_arns["ai_payload_idempotency"]` cho biến mới
- **Phụ thuộc**: Output `lambda_role_arns` `depends_on` bao gồm `aws_iam_role_policy.vpc_alb_caller_idempotency`

#### 2. vpc_alb_caller: SigV4 Fail-Closed cho Đường Dẫn AI Payload
- **Trạng thái**: HOÀN THÀNH
- **Thay đổi**: `lambda_src/src/workers/vpc_alb_caller/handler.py` giờ raise `ConfigMissingError` khi thiếu thông tin xác thực AWS VÀ đường dẫn thuộc `AI_PAYLOAD_PATHS` VÀ `ALLOW_UNSIGNED_AI_REQUESTS != "true"`
- **Mặc định an toàn**: `ALLOW_UNSIGNED_AI_REQUESTS` mặc định là `"false"`. Chỉ unit test đặt thành `"true"`. Biến môi trường Terraform KHÔNG ĐƯỢC đặt thành `"true"` trong bất kỳ môi trường triển khai nào.
- **Ngoại lệ health**: Đường dẫn `/health` luôn được phép không cần thông tin xác thực.

#### 3. Header Tính Toàn Vẹn Yêu Cầu (X-Payload-SHA256, X-Request-Timestamp, Authorization)
- **Trạng thái**: HOÀN THÀNH (cấu trúc header đã tồn tại; test giờ thực thi chính thức)
- **Phạm vi**: `X-Request-Timestamp` (RFC3339 UTC), `X-Payload-SHA256` (hex SHA256 của bytes gửi đi chính xác), `Authorization` (AWS4-HMAC-SHA256 SigV4) đều được gửi cho các đường dẫn AI không phải `/health` khi có thông tin xác thực

#### 4. Unit Tests
- **Trạng thái**: HOÀN THÀNH
- **Nhóm test mới thêm vào `test_vpc_alb_caller.py`**:
  - `TestRequestIntegrityHeaders`: định dạng RFC3339 timestamp, hash payload khớp bytes wire, Authorization hiện diện và dùng AWS4-HMAC-SHA256
  - `TestCredentialFailClosed`: detect/decide/verify fail-closed, health được phép, override ALLOW_UNSIGNED hoạt động
  - `TestStaticIAMPolicyDefinition`: 6 kiểm tra Terraform tĩnh bao gồm policy resource, actions, resource scope, outputs.tf depends_on, khai báo variables.tf, và 3 wiring môi trường

#### 5. Script Cổng Triển Khai
- **Trạng thái**: HOÀN THÀNH
- **Script**: `scripts/test-ai-request-integrity.ps1`
- **Probe**: /v1/detect có ký dương tính, timestamp replay cũ, thiếu auth, không khớp hash
- **Hành vi**: Thoát 1 và ghi JSON kết quả nếu bất kỳ probe nào thất bại; chặn thăng cấp image

#### 6. Tài Liệu
- **Trạng thái**: HOÀN THÀNH
- `docs/GUIDES.md` Mục 11: Khi nào chạy, cách chạy, bảng probe, xử lý không tuân thủ
- `docs/GUIDES_vi.md` Mục 11: Bản dịch tiếng Việt đồng bộ

---

## Hạn Chế Đã Biết: ALB Không Thực Thi SigV4 Ở Cấp Listener

**Hạn chế**: HTTPS ALB nội bộ riêng tư (cổng 443) không tự thực thi xác thực AWS SigV4 ở cấp ALB listener. ALB chuyển tiếp tất cả yêu cầu đến nhóm mục tiêu Lambda mà không kiểm tra header `Authorization`.

**Tác động**: Tính đúng đắn của SigV4 được thực thi bởi AI Request Lambda/container, không phải ALB. Điều này có nghĩa là:
- Yêu cầu có `Authorization` giả mạo hoặc thiếu vẫn đến được AI Lambda
- AI Lambda phải xác thực `Authorization`, `X-Request-Timestamp`, và `X-Payload-SHA256` và trả về lỗi hợp đồng 400/401
- Cổng triển khai (`scripts/test-ai-request-integrity.ps1`) xác minh việc thực thi này qua các probe âm tính

**Trạng thái Khắc Phục**: Cơ sở hạ tầng thuộc sở hữu CDO (vpc_alb_caller + Terraform IAM) gửi đúng tất cả các header cần thiết. Nghĩa vụ thực thi xác thực replay/auth/hash tại ranh giới hợp đồng `/v1/*` thuộc về container image AI Engine do AIOps cung cấp. Cổng triển khai chặn thăng cấp nếu image AI Engine không vượt qua các probe âm tính.

**Ngoại Lệ Capstone**: Cho demo capstone, nếu image AI Engine của AIOps không triển khai đầy đủ thực thi replay/auth/hash, ghi lại điều này như một ngoại lệ RUNTIME_NON_COMPLIANT và tài liệu hóa rõ ràng. Không tuyên bố tuân thủ section-3 trong trường hợp này.

---

## Ghi Chú Rollback

Rollback an toàn và không phá hoại:
- Revert các thay đổi `modules/iam/main.tf`, `modules/iam/variables.tf`, `modules/iam/outputs.tf`
- Revert dòng kết nối IAM trong ba `main.tf` môi trường
- Revert khối kiểm tra thông tin xác thực trong `lambda_src/src/workers/vpc_alb_caller/handler.py`
- Không cần di chuyển state hoặc thay thế tài nguyên (chính sách IAM mới là bổ sung)

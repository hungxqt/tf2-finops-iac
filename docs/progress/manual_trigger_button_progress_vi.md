# Tiến độ Manual Report Trigger

## Trạng thái

Đã triển khai hoàn tất và được xác thực. Phần wiring backend đã hoàn thành, và lỗi apply CORS trên Lambda Function URL đã được khắc phục.

## Phạm vi

Thêm nút "Run report now" vào Topbar của dashboard, cho phép các role CDO/admin/engineering
kích hoạt thủ công một lần chạy phát hiện FinOps ad-hoc. Nút thực thi giới hạn
5 lần/ngày/tenant đã được wired sẵn trong Step Functions state machine
(state `CheckAdHocQuota`) và Lambda `state/handler.py` (operation `check_quota`).

## Những thứ đã có sẵn (không thay đổi)

- `state/handler.py` – operation `check_quota` kiểm tra quota 5 lần/ngày qua DynamoDB.
- `docs/statemachine.json` – luồng `CheckAdHocQuotaDecision` → `CheckAdHocQuota` →
  `EvaluateAdHocQuota` → `SetQuotaExceededError` đã wired đầy đủ.
- `docs/MANUAL_STEP_FUNCTIONS_EXECUTION.md` – runbook dành cho operator chạy ad-hoc qua CLI.

## Các file đã thay đổi

- `modules/dashboard/frontend/src/schema.ts`
  - Thêm `trigger_api_url` (optional) vào `runtimeConfigSchema`.
  - Thêm `ad_hoc_quota_used` (int 0-5, mặc định 0) vào `dashboardSummarySchema`.
- `modules/dashboard/frontend/src/sampleData.ts`
  - Thêm `ad_hoc_quota_used: 2` vào sample data để thử nghiệm local dev.
- `modules/dashboard/frontend/src/data.ts`
  - Thêm hàm `triggerAdHocRun(tenantId, accountId)` gọi POST đến `trigger_api_url`
    từ runtime config. Trong local dev (không có URL), hàm mô phỏng trigger sau 1.5s.
- `modules/dashboard/frontend/src/components/ui/ManualTriggerButton.tsx` (MỚI)
  - Component nút "Run report now" tự chứa, bao gồm:
    - Badge quota (ví dụ "2/5") hiển thị số lần đã dùng hôm nay.
    - Dialog xác nhận với cảnh báo số lần còn lại.
    - Spinner loading khi chờ backend.
    - Toast thành công hiển thị execution ARN.
    - Banner cảnh báo quota-exceeded.
    - Banner lỗi cho các lỗi không mong đợi.
    - Nút tự vô hiệu hóa khi hết quota.
- `modules/dashboard/frontend/src/components/layout/Topbar.tsx`
  - Import `ManualTriggerButton`.
  - Thêm hàm `canTrigger()` kiểm tra role (admin, cdo, engineering thấy nút;
    finance-readonly không thấy).
  - Render nút trong vùng bên phải của Topbar.

## Wiring backend (Terraform – Đã triển khai)

Frontend gọi `trigger_api_url` từ runtime config. URL này trỏ đến AWS Lambda Function URL (`aws_lambda_function_url.ad_hoc_trigger_url`) thực hiện:

1. Nhận POST với `{ is_ad_hoc: true, tenant_id?, account_id? }`.
2. Gọi `StepFunctions:StartExecution` với state machine ARN và body làm input JSON (có `is_ad_hoc: true`).
3. Trả về `{ execution_arn: "..." }` nếu thành công, hoặc lỗi có trường `message` mô tả (ví dụ quota exceeded) để nút hiển thị lên UI.

Tài nguyên `trigger_api_url` được Terraform ghi ra dưới dạng cấu hình runtime của dashboard (`dashboard_runtime_config.json`) được upload lên S3 data bucket.

### Sửa lỗi cấu hình CORS của Lambda Function URL

Trong quá trình deploy backend lúc đầu, lệnh Terraform apply bị lỗi đối với tài nguyên `aws_lambda_function_url.ad_hoc_trigger_url` do lỗi xác thực cấu hình CORS:
- **Lỗi**: AWS Lambda Function URL CORS từ chối phương thức `OPTIONS` trong `cors.allow_methods`.
- **Nguyên nhân gốc rễ**: Cấu hình CORS của AWS Lambda Function URL tự động xử lý preflight (OPTIONS) và không hỗ trợ/cho phép khai báo trực tiếp phương thức `OPTIONS` trong `allow_methods` nếu đó là request xử lý ở mức ứng dụng. Nó chỉ yêu cầu khai báo các phương thức nghiệp vụ thực tế (ví dụ: `POST`).
- **Khắc phục**: Loại bỏ `"OPTIONS"` khỏi `allow_methods`, chỉ để lại `["POST"]`.
- **Trạng thái validation**: Quá trình apply thành công không có lỗi và cấu hình trigger backend đã được lưu trữ chính xác.

## Lệnh kiểm tra

```powershell
# Kiểm tra TypeScript
npm run typecheck

# Chạy unit test Vitest
npm run test

# Dev server (kiểm tra visual tại http://127.0.0.1:5173)
npm run dev
```

## Kết quả

- TypeScript typecheck: đang chờ kết quả.
- Vitest: đang chờ kết quả.
- Kiểm tra visual qua dev server: đang chờ.

## Vướng mắc

- Lambda + API Gateway cho `trigger_api_url` phía Terraform chưa implement.
  Nút mô phỏng trigger trong local dev mode.

## Bước tiếp theo

Không có bước tiếp theo. Nút manual trigger và hạ tầng backend đi kèm đã được triển khai hoàn chỉnh, xác thực và kích hoạt thành công.

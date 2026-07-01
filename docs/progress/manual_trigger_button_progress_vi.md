# Tiến độ Manual Report Trigger

## Trạng thái

Đã triển khai, đang chờ xác nhận (npm install đang chạy).

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

## Wiring backend (Terraform – chưa implement)

Frontend gọi `trigger_api_url` từ runtime config. URL này phải trỏ đến một endpoint
API Gateway (hoặc Lambda Function URL sau CloudFront) thực hiện:

1. Nhận POST với `{ is_ad_hoc: true, tenant_id?, account_id? }`.
2. Gọi `StepFunctions:StartExecution` với state machine ARN và body làm input JSON
   (có `is_ad_hoc: true`).
3. Trả về `{ execution_arn: "..." }` nếu thành công, hoặc lỗi có trường `message`
   mô tả (ví dụ quota exceeded) để nút hiển thị lên UI.

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

1. Chờ `npm run typecheck` và `npm run test` xác nhận 0 lỗi.
2. Implement Lambda trigger mỏng phía Terraform (gọi `StepFunctions:StartExecution`).
3. Wire `trigger_api_url` vào output runtime config của dashboard.
4. Cập nhật progress file sau khi validation qua.

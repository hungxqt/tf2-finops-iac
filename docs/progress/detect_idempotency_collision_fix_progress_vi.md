# Tiến trình Khắc phục Sự cố Trùng lặp Khóa Idempotency Detect trong Ngày (Same-Day)

**Ngày**: 30-06-2026  
**Trạng thái**: HOÀN THÀNH

## Tóm tắt

Triển khai giải pháp theo hợp đồng nghiêm ngặt (strict-contract) để giải quyết sự cố trùng lặp khóa idempotency đối với yêu cầu detect trong cùng ngày:
- Lượt chạy daily theo lịch `/v1/detect` được giữ nguyên cơ chế chạy một lần duy nhất cho mỗi tenant/ngày.
- Các lượt chạy daily tiếp theo trong cùng ngày sẽ bị chặn và định tuyến trực tiếp sang `AccountDuplicateIgnored` thay vì chạy lại `InvokeDetect`.
- Các lượt chạy lại có chủ đích trong cùng ngày phải sử dụng chế độ chạy ad-hoc (`is_ad_hoc = true`), cơ chế này sẽ tạo khóa ad-hoc duy nhất và tiêu tốn hạn ngạch ad-hoc hàng ngày của tenant.
- Cơ chế fail-closed khi phát hiện sai khác mã băm (hash-mismatch) vẫn được giữ nguyên để đảm bảo an toàn.
- Không xóa hoặc ghi đè bất kỳ bản ghi nào trong bảng `finops-idempotency-{env}`.

## Các thay đổi chính

### 1. Khóa Trạng thái (Run-State Key) & Xử lý Trùng lặp

| Tệp tin | Thay đổi |
| --- | --- |
| `lambda_src/src/workers/state/handler.py` | Cập nhật logic khóa trạng thái chạy (run-state key): Nếu là lượt chạy ad-hoc, khóa trạng thái sẽ bao gồm cả `run_id` để đảm bảo tính duy nhất giữa các lượt chạy thủ công/ad-hoc. Khóa trạng thái của lượt chạy daily theo lịch vẫn giữ định dạng tương thích cũ (`account_id:period:date`). |
| `modules/orchestration/statemachine.json` | Cập nhật trạng thái lựa chọn `DuplicateRun` để các lượt chạy daily bị `FAILED` trước đó trong ngày cũng được định tuyến sang trạng thái kết thúc `AccountDuplicateIgnored`, tránh chạy lại `InvokeDetect` và gây lỗi trùng lặp idempotency. |
| `docs/statemachine.json` | Cập nhật bản sao tĩnh ASL bằng kịch bản render để đồng bộ với các thay đổi trong template `statemachine.json`. |

### 2. Chuẩn hóa Telemetry & Xác thực Khóa API

| Tệp tin | Thay đổi |
| --- | --- |
| `lambda_src/src/workers/normalizer/handler.py` | Cập nhật logic chọn `batch_type` của normalizer: trả về `daily` cho các lượt chạy daily theo lịch, và `adhoc-<safe-run-id>` cho lượt chạy ad-hoc (trong đó `safe_run_id` được làm sạch chỉ giữ ký tự chữ-số, dấu gạch ngang và dấu gạch dưới). |
| `lambda_src/src/workers/vpc_alb_caller/handler.py` | Cập nhật biểu thức chính quy (regex) `AI_IDEMPOTENCY_KEY_PATTERN` và thông báo lỗi `InvalidInputError` tương ứng để chấp nhận định dạng khóa ad-hoc mới `tenant_id:execution_date:adhoc-<safe-run-id>`, đồng thời vẫn thực hiện xác thực tenant/ngày và tính nhất quán của payload. |

### 3. Kiểm thử & Tài liệu Hướng dẫn

| Tệp tin | Thay đổi |
| --- | --- |
| `docs/GUIDES.md` | Cập nhật Bước 3.3 để ghi nhận việc chặn các lượt chạy daily trùng ngày, và hướng dẫn sử dụng lượt chạy ad-hoc khi cần chạy lại. |
| `docs/GUIDES_vi.md` | Cập nhật bản dịch tiếng Việt của Bước 3.3 tương ứng. |
| `docs/MANUAL_STEP_FUNCTIONS_EXECUTION.md` | Thêm phần cảnh báo chi tiết về cơ chế chặn chạy daily trùng ngày và cách chạy ad-hoc trong mục Các Giới hạn & Biện pháp Bảo vệ. |
| `docs/MANUAL_STEP_FUNCTIONS_EXECUTION_vi.md` | Thêm phần bản dịch tiếng Việt tương ứng. |
| `lambda_src/tests/test_state.py` | Thêm bài kiểm thử `test_state_adhoc_run_state_key_uniqueness` để xác minh khóa ad-hoc run-state là duy nhất. |
| `lambda_src/tests/test_normalizer.py` | Thêm bài kiểm thử `test_normalizer_batch_type_emissions` và cập nhật các khẳng định (assertions) kiểm thử cũ để tương thích với định dạng `adhoc-<safe-run-id>`. |
| `lambda_src/tests/test_vpc_alb_caller.py` | Thêm bài kiểm thử `test_vpc_alb_caller_adhoc_key_validation` để xác minh cơ chế kiểm tra định dạng khóa ad-hoc mới. |
| `lambda_src/tests/test_state_machine.py` | Thêm bài kiểm thử `test_state_machine_failed_run_duplicate_handling` nhằm đảm bảo kiểm tra trùng lặp lượt chạy FAILED daily được chuyển sang `AccountDuplicateIgnored`. |

## Kết quả Xác minh

- Chạy thành công kịch bản render `python scripts/render-static-asl.py`.
- Xác minh thành công cú pháp Terraform:
  - `terraform fmt -check -recursive modules/orchestration modules/compute-lambda modules/iam` (Thành công)
  - `terraform -chdir=environments/sandbox init -backend=false` (Thành công)
  - `terraform -chdir=environments/sandbox validate` (Thành công)
- Chạy thành công toàn bộ suite kiểm thử Python:
  - Chạy tập trung các file kiểm thử bị ảnh hưởng: `219 bài kiểm thử vượt qua`
  - Chạy toàn bộ suite: `374 bài kiểm thử vượt qua, không có lỗi`

## Các bước tiếp theo

- Tiến hành áp dụng (deploy) cấu hình hạ tầng mới vào môi trường sandbox và staging.
- Phổ biến cho người vận hành sử dụng tham số `"is_ad_hoc": true` khi cần chạy lại thủ công trong ngày thay vì can thiệp xóa các hàng trong DynamoDB.

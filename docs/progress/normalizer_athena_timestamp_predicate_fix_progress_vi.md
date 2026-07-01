# Tiến độ Sửa lỗi Timestamp Predicate trong Athena của Normalizer

## Trạng thái

Đã triển khai, kiểm thử và xác minh thành công.

## Phạm vi

- Thêm hàm helper `get_athena_timestamp_window` trong `lambda_src/src/workers/normalizer/handler.py` giúp chuyển đổi ngày thực thi có định dạng YYYY-MM-DD đã được xác thực thành một khoảng timestamp half-open sử dụng các hằng số timestamp có kiểu dữ liệu (`TIMESTAMP 'YYYY-MM-DD 00:00:00'`).
- Thay thế các mệnh đề so sánh chuỗi (`line_item_usage_start_date >= '{start_date}'` và `line_item_usage_start_date <= '{end_date}'`) bằng các mệnh đề khoảng timestamp half-open an toàn cho Athena:
  - `line_item_usage_start_date >= TIMESTAMP 'YYYY-MM-DD 00:00:00'` (ngày bắt đầu, bao gồm)
  - `line_item_usage_start_date < TIMESTAMP 'YYYY-MM-DD 00:00:00'` (ngày tiếp theo, loại trừ)
- Giữ nguyên toàn bộ việc trích dẫn định danh (identifier quoting), ngữ cảnh cơ sở dữ liệu và các bước xác thực đầu vào hiện có.
- Thêm bài kiểm thử hồi quy `test_normalizer_athena_timestamp_predicate_regression` trong `lambda_src/tests/test_normalizer_cur2.py` để khẳng định:
  - Truy vấn chứa `TIMESTAMP '2026-06-24 00:00:00'`
  - Truy vấn chứa `TIMESTAMP '2026-06-25 00:00:00'`
  - Truy vấn không chứa `line_item_usage_start_date <= '2026-06-24'`
  - Truy vấn không so sánh cột timestamp với một chuỗi ngày được bao trong nháy đơn thuần túy.
- Đã chạy toàn bộ unit tests của kho chứa và unit tests riêng cho normalizer.

## Các file đã thay đổi

- `lambda_src/src/workers/normalizer/handler.py`
- `lambda_src/tests/test_normalizer_cur2.py`

## Lệnh kiểm tra

```powershell
Push-Location lambda_src
python -m pytest tests/test_normalizer_cur2.py tests/test_normalizer.py -v
python -m pytest
Pop-Location

terraform fmt -check -recursive
```

## Kết quả

- Toàn bộ 15 test nhắm mục tiêu trong `test_normalizer_cur2.py` đã pass.
- Toàn bộ 385 test trong dự án đã pass thành công.
- Bước kiểm tra định dạng Terraform (fmt) thành công.

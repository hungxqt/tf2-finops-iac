# Tiến độ Sửa lỗi Negative Cost AI Payload

## Trạng thái

Đã triển khai và xác thực thành công.

## Phạm vi

- Sửa lỗi schema `/v1/detect` bằng cách đảm bảo các mảng chi phí Cost Explorer (CE) và CUR gửi tới AI không bao giờ chứa giá trị chi phí âm.
- Trong `cost_puller`, giữ nguyên các bản ghi CE gốc cho telemetry thô, nhưng tính toán `missing_resources` và `current_ce_cost_gap_usd` chỉ từ các bản ghi có ngày thực thi có `unblended_cost > 0`.
- Bổ sung thông tin chẩn đoán giới hạn như `negative_cost_record_count` và `negative_cost_total_usd` vào details/quality flags của worker mà không log toàn bộ các dòng thanh toán thô.
- Giới hạn/tính toán lại `current_ce_cost_gap_usd` để không bao giờ âm.
- Trong `normalizer`, thêm các helper dọn dẹp cho các bản ghi chi phí gửi tới AI (`sanitize_ce_records` và `sanitize_cur_records`) để loại bỏ các bản ghi bị thiếu, phi số, vô hạn hoặc `< 0` (trong khi vẫn giữ các giá trị bằng `0`).
- Đảm bảo các mảng đã dọn dẹp được sử dụng cho:
  - Body `/v1/detect` dạng `RAW_JSON`.
  - File JSON AI input dạng `S3_POINTER` được ghi dưới đường dẫn `ai-input/...`.
  - `normalized.details.aws_cost_explorer_daily` và `normalized.details.aws_cur_line_items`.

## Các file đã thay đổi

- `lambda_src/src/workers/cost_puller/handler.py`
- `lambda_src/src/workers/normalizer/handler.py`
- `lambda_src/tests/test_cost_puller.py`
- `lambda_src/tests/test_normalizer.py`

## Lệnh kiểm tra

```powershell
Push-Location lambda_src
python -m pytest tests/test_cost_puller.py tests/test_normalizer.py tests/test_step_function_payload_contract.py -q
python -m pytest -q
Pop-Location
```

## Kết quả

- Giải quyết triệt để lỗi schema do chi phí âm.
- Toàn bộ 377 unit và integration tests đã pass thành công.
- Không có lỗi regression.

# Tiến độ Sửa lỗi Đóng gói Parquet của Normalizer

## Trạng thái

Đã triển khai, kiểm thử và xác minh.

## Phạm vi

- Cập nhật `scripts/package-lambdas.ps1` để xây dựng các tệp ZIP của Lambda cho môi trường Python 3.13 Linux x86_64 sử dụng các cờ nhắm mục tiêu của pip (như `--platform manylinux_2_28_x86_64 --only-binary=:all: --implementation cp --python-version 3.13`).
- Tách biệt phụ thuộc để chỉ worker `normalizer` mới đóng gói `pyarrow`.
- Tạo tệp `lambda_src/requirements-normalizer.txt` chứa `pyarrow`.
- Cập nhật `lambda_src/requirements.txt` để loại bỏ `pyarrow` (chỉ để lại bình luận) nhằm đảm bảo các tệp ZIP của các worker khác không chứa `pyarrow`, `.dll`, `.pyd`, `win_amd64` hoặc `pyarrow.libs`.
- Cập nhật `lambda_src/requirements-dev.txt` bao gồm `-r requirements-normalizer.txt` để giữ `pyarrow` cho mục đích chạy kiểm thử cục bộ.
- Cập nhật `lambda_src/tests/test_step_function_lambda_coverage.py` nhằm điều chỉnh số lượng `ps_workers` kỳ vọng bao gồm cả hàm worker `trigger` của dashboard trong `package-lambdas.ps1`.
- Thay thế cơ chế tự động chuyển sang JSON khi lỗi Parquet trong `lambda_src/src/workers/normalizer/handler.py` bằng một ngoại lệ fail-closed để ngăn việc ghi các byte Parquet không hợp lệ.
- Làm sạch các câu lệnh nhật ký `event_data` trong `handle_request` bằng cách tóm tắt các mảng lớn (`aws_cur_line_items`, `aws_cost_explorer_daily`, `resource_utilization_metrics` và `missing_resources`) nhằm tránh rò rỉ dữ liệu telemetry thô vào CloudWatch.
- Làm sạch các câu lệnh nhật ký `Response:` trong `handle_request` để chỉ xuất ra từ điển tóm tắt chứa thông tin về run IDs, S3 URIs, chế độ, chất lượng dữ liệu telemetry và số lượng phần tử.
- Thêm các ca kiểm thử trong `lambda_src/tests/test_normalizer.py`:
  - `test_normalizer_parquet_write_failure_fails_closed`: Chứng minh rằng việc lỗi tuần tự hóa Parquet sẽ thực hiện cơ chế fail-closed, ném ra ngoại lệ `RuntimeError` và không tải tệp curated nào lên S3.
  - `test_normalizer_logging_sanitized`: Chứng minh rằng các chi tiết dòng chi phí CUR thô và telemetry tài nguyên không xuất hiện trong nhật ký chạy thành công, và tóm tắt đã được làm sạch được ghi lại.
- Cập nhật các tệp `docs/GUIDES.md` và `docs/GUIDES_vi.md` phản ánh việc phân tách phụ thuộc và các yêu cầu đóng gói nhắm mục tiêu nền tảng.

## Các tệp thay đổi

- `scripts/package-lambdas.ps1`
- `lambda_src/requirements.txt`
- `lambda_src/requirements-normalizer.txt`
- `lambda_src/requirements-dev.txt`
- `lambda_src/src/workers/normalizer/handler.py`
- `lambda_src/tests/test_step_function_lambda_coverage.py`
- `lambda_src/tests/test_normalizer.py`
- `docs/GUIDES.md`
- `docs/GUIDES_vi.md`

## Các lệnh xác minh

```powershell
# Chạy tất cả các kiểm thử cục bộ
pytest lambda_src/tests

# Chạy kịch bản đóng gói
.\scripts\package-lambdas.ps1

# Xác minh nội dung tệp zip bằng Python
python -c "import zipfile; z = zipfile.ZipFile('.build/lambda/normalizer.zip'); names = z.namelist(); pyarrow_names = [n for n in names if 'pyarrow' in n]; dll_names = [n for n in names if '.dll' in n or '.pyd' in n or 'win_amd64' in n]; so_names = [n for n in names if '.so' in n]; print('normalizer.zip: pyarrow =', len(pyarrow_names), ', dlls =', len(dll_names), ', so files =', len(so_names)); z2 = zipfile.ZipFile('.build/lambda/state.zip'); names2 = z2.namelist(); pyarrow_names2 = [n for n in names2 if 'pyarrow' in n]; print('state.zip: pyarrow =', len(pyarrow_names2))"

# Kiểm tra định dạng và xác thực cấu hình Terraform
terraform fmt -check -recursive
terraform -chdir=environments/sandbox validate
```

## Kết quả

- Tất cả 388 kiểm thử đơn vị trong `pytest lambda_src/tests` đều vượt qua thành công.
- `normalizer.zip` chứa đúng 38 tệp `.so` gốc Linux cho pyarrow, 0 tệp Windows `.dll` hay `.pyd`, và các tệp zip worker khác (như `state.zip`) contain đúng 0 tệp pyarrow.
- Cấu hình Terraform đã được định dạng và xác thực thành công.

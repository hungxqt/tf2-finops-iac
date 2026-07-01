# Tiến độ Sửa lỗi Quoting Athena Identifier trong Normalizer

## Trạng thái

Đã triển khai, kiểm thử và tạo Terraform plan thành công.

## Phạm vi

- Thêm helper `quote_identifier` trong `lambda_src/src/workers/normalizer/handler.py` để kiểm tra và đặt dấu nháy kép (double quotes - ") cho các định danh table của Athena (sửa đổi từ dấu nháy ngược trước đó).
- Đảm bảo kiểm tra regex nghiêm ngặt khớp với `^[a-zA-Z0-9_-]+\Z` (sử dụng `\Z` để từ chối các ký tự xuống dòng ở cuối).
- Sửa đổi phần tạo SQL động trong `normalizer` để xuất ra tên Glue table được bao bởi dấu nháy kép trong mệnh đề `FROM`: `FROM "table_name"` (loại bỏ tiền tố tên database để Athena phân giải chính xác bảng trong ngữ cảnh cơ sở dữ liệu đã chọn).
- Giữ nguyên `QueryExecutionContext={"Database": database}` với tên Glue database thô (không có dấu nháy) để cung cấp ngữ cảnh bắt buộc.
- Duy trì tính toàn vẹn của cấu hình tên (không đổi tên tài nguyên Terraform hoặc Glue database/table).
- Cập nhật unit và regression tests trong `lambda_src/tests/test_normalizer_cur2.py`:
  - `test_normalizer_athena_identifier_quoting`: Xác thực câu lệnh Athena được tạo ra bọc chính xác tên table trong dấu nháy kép, không chứa tiền tố database, không chứa dấu nháy ngược và truyền tên database trong `QueryExecutionContext`.
  - `test_quote_identifier_helper_valid`: Kiểm thử các định danh hợp lệ chứa chữ cái, số, dấu gạch ngang và dấu gạch dưới, trả về chuỗi bọc trong dấu nháy kép.
  - `test_quote_identifier_helper_invalid_rejections`: Kiểm tra việc từ chối các đầu vào không an toàn (khoảng trắng, dấu chấm, dấu nháy kép/đơn, dấu nháy ngược, lệnh chấm phẩy, ký tự xuống dòng ở cuối).
- Cập nhật các khẳng định hồi quy (regression assertions) trong `test_normalizer_athena_query_integration` trong `lambda_src/tests/test_normalizer.py` để xác minh câu lệnh truy vấn không chứa tiền tố database hoặc dấu nháy ngược, sử dụng dấu nháy kép bọc tên table và chỉ cung cấp database context trong `QueryExecutionContext`.

## Các file đã thay đổi

- `lambda_src/src/workers/normalizer/handler.py`
- `lambda_src/tests/test_normalizer_cur2.py`
- `lambda_src/tests/test_normalizer.py`

## Lệnh kiểm tra

```powershell
Push-Location lambda_src
python -m pytest tests/test_normalizer_cur2.py tests/test_normalizer.py -v
python -m pytest
Pop-Location

terraform fmt -check -recursive
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
.\scripts\package-lambdas.ps1
terraform -chdir=environments/sandbox plan -out="$env:TEMP\normalizer-athena-context-db-fix.tfplan"
```

## Kết quả

- Toàn bộ 32 test nhắm mục tiêu cho `normalizer` và `normalizer_cur2` đã pass.
- Toàn bộ 383 unit tests trong dự án đã pass.
- Các bước kiểm tra format Terraform, init và validate đều thành công.
- Đóng gói các hàm Lambda thành công.
- Tạo execution plan cho sandbox thành công vào thư mục tạm, không lưu trữ artifacts file plan trong git repository.

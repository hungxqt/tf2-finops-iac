# Tiến độ Sửa lỗi Quoting Athena Identifier trong Normalizer

## Trạng thái

Đã triển khai, kiểm thử và tạo Terraform plan thành công.

## Phạm vi

- Thêm helper `quote_identifier` trong `lambda_src/src/workers/normalizer/handler.py` để kiểm tra và đặt dấu nháy kép cho các định danh database và table của Athena.
- Đảm bảo kiểm tra regex nghiêm ngặt khớp với `^[a-zA-Z0-9_-]+\Z` (sử dụng `\Z` để từ chối các ký tự xuống dòng ở cuối).
- Sửa đổi phần tạo SQL động trong `normalizer` để xuất ra tên Glue database và table được bao bởi dấu nháy kép trong mệnh đề `FROM`: `FROM "database_name"."table_name"`.
- Giữ nguyên `QueryExecutionContext={"Database": database}` với tên Glue database thô (không có dấu nháy) để đáp ứng yêu cầu của client.
- Duy trì tính toàn vẹn của cấu hình tên (không đổi tên tài nguyên Terraform hoặc Glue database).
- Bổ sung unit và regression tests trong `lambda_src/tests/test_normalizer_cur2.py`:
  - `test_normalizer_athena_identifier_quoting`: Xác thực câu lệnh Athena được tạo ra bọc chính xác tên database và table trong dấu nháy kép.
  - `test_quote_identifier_helper_valid`: Kiểm thử các định danh hợp lệ chứa chữ cái, số, dấu gạch ngang và dấu gạch dưới.
  - `test_quote_identifier_helper_invalid_rejections`: Kiểm tra việc từ chối các đầu vào không an toàn (khoảng trắng, dấu chấm, dấu nháy, lệnh chấm phẩy, ký tự xuống dòng ở cuối).

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
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
.\scripts\package-lambdas.ps1
terraform -chdir=environments/sandbox plan -out=normalizer-athena-identifier-fix.tfplan
```

## Kết quả

- Toàn bộ 32 test nhắm mục tiêu cho `normalizer` và `normalizer_cur2` đã pass.
- Toàn bộ 383 unit tests trong dự án đã pass.
- Các bước kiểm tra format Terraform, init và validate đều thành công.
- Đóng gói các hàm Lambda thành công.
- Tạo execution plan cho sandbox thành công, hiển thị cập nhật `source_code_hash` cho toàn bộ các hàm Lambda được đóng gói (bao gồm cả `normalizer`).

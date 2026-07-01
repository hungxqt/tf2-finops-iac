# Hướng dẫn Vận hành Replay Dữ liệu Giả lập

Tài liệu này hướng dẫn chi tiết các bước chuẩn bị, cấu hình, chạy thử nghiệm (replay) và hoàn tác bộ kiểm thử dữ liệu chi phí lịch sử giả lập trong môi trường AWS Sandbox.

---

## 1. Điều kiện tiên quyết

Trước khi bắt đầu, hãy đảm bảo rằng:
1. Bạn có thông tin xác thực local với quyền quản trị viên tới tài khoản AWS Sandbox (`336805808730`).
2. Đã cài đặt Python (>= 3.13) và Terraform (>= 1.10).
3. Môi trường Sandbox đã được triển khai hoặc khởi tạo:
   ```powershell
   cd environments/sandbox
   terraform init
   cd ../..
   ```

---

## 2. Các bước Thực hiện

### Bước 2.1: Tạo ngữ cảnh Business Context JSON
Bộ sinh ngữ cảnh (context generator) sẽ tạo tệp JSON ngữ cảnh lưu lượng (traffic_source được đặt thành `Synthetic`) và các số liệu hiệu năng CPU EC2/RDS.

* **Lựa chọn A: Toàn bộ tập dữ liệu 92 ngày (Khuyến nghị cho kiểm thử cuối cùng)**
  Sinh dữ liệu cho 92 ngày (01/03/2026 đến 31/05/2026) và tải trực tiếp lên bucket lakehouse Sandbox:
  ```powershell
  python ./scripts/generate_business_context.py --scope full --account-id 336805808730 --upload
  ```

* **Lựa chọn B: Tập dữ liệu Smoke Test (Dành cho xác minh nhanh)**
  Sinh một tập con gồm 16 ngày bao phủ các khung phát sinh bất thường (A2, B2, A6) cùng với đệm lookback 30 ngày cho Cost Explorer:
  ```powershell
  python ./scripts/generate_business_context.py --scope smoke --account-id 336805808730 --upload
  ```

* **Lựa chọn C: Sinh dữ liệu cục bộ trước**
  Để xem trước tệp dữ liệu trước khi tải lên S3:
  ```powershell
  python ./scripts/generate_business_context.py --scope full --account-id 336805808730 --output .build/synthetic-replay/business_context.json
  ```
  Sau đó thực hiện tải lên thủ công hoặc chạy lại với cờ `--upload`.

---

### Bước 2.2: Chuẩn bị và tải dữ liệu CUR lên S3
Script chuẩn bị dữ liệu sẽ chuyển đổi các bản ghi CSV thô thành các tệp Parquet snappy phân chia theo tháng, tạo manifest và tải lên bucket S3 CUR:
```powershell
python ./scripts/prepare_replay.py --account-id 336805808730
```
Script này sẽ tải lên các tệp tin sử dụng cấu trúc tiền tố (prefix) tài khoản thành viên chuẩn mực:
* Dữ liệu CUR: `s3://<cur-bucket>/<account_id>/<cur_export_name>/data/BILLING_PERIOD=<YYYY-MM>/....`
* Manifest CUR: `s3://<cur-bucket>/<account_id>/<cur_export_name>/metadata/BILLING_PERIOD=<YYYY-MM>/<cur_export_name>-Manifest.json`

---

### Bước 2.3: Cấu hình và Triển khai các Biến Terraform
Bật chế độ replay trong Terraform để hướng dẫn các Lambda worker đọc dữ liệu đo lường hiệu năng và chi phí từ tệp business context thay vì gọi API thực tế của AWS.

1. Mở tệp `environments/sandbox/terraform.tfvars`.
2. Cấu hình các tham số sau (thay thế tên bucket nếu bucket lakehouse sandbox của bạn có tên khác):
   ```hcl
   synthetic_replay_enabled              = true
   synthetic_replay_business_context_uri = "s3://tf2-finops-sandbox-lakehouse/replay/business_context.json"
   ```
3. Triển khai cấu hình mới:
   ```powershell
   cd environments/sandbox
   terraform apply
   cd ../..
   ```

---

### Bước 2.4: Chạy Replay Runner
Kích hoạt các luồng chạy thử nghiệm. Bộ runner sẽ tạo bản ghi cấu hình tài khoản trong DynamoDB, khởi chạy Step Functions tuần tự theo từng ngày, và theo dõi trạng thái cho đến khi hoàn thành.

Payload truyền vào Step Functions được cấu hình như sau:
```json
{
  "run_id": "rep-YYYY-MM-DD-...",
  "correlation_id": "corr-rep-YYYY-MM-DD-...",
  "account_id": "<account_id>",
  "execution_date": "YYYY-MM-DD",
  "billing_period": "YYYY-MM",
  "cost_period": "YYYY-MM-DD",
  "is_ad_hoc": true,
  "tenant_id": "tenant-default"
}
```
Lưu ý rằng `execution_date` sử dụng định dạng chỉ chứa ngày (`YYYY-MM-DD`) và `billing_period` được bao gồm (`YYYY-MM`).

* **Chế độ Smoke (3 ngày, 01/03/2026 đến 03/03/2026)**
  ```powershell
  python ./scripts/run_replay.py --mode smoke
  ```

* **Chế độ Warmup (20 days, 01/03/2026 đến 20/03/2026)**
  Chạy đến ngày xảy ra sự cố RDS orphan DB instance (A2).
  ```powershell
  python ./scripts/run_replay.py --mode warmup
  ```

* **Chế độ Full (92 ngày, 01/03/2026 đến 31/05/2026)**
  Thử nghiệm lại toàn bộ khoảng thời gian lịch sử 3 tháng.
  ```powershell
  python ./scripts/run_replay.py --mode full
  ```

---

## 3. Xác minh & Giám sát

Trong khi quá trình chạy replay diễn ra, hãy xác minh các lượt thực thi và dữ liệu đo lường:
1. **Console AWS Step Functions**: Tìm workflow `tf2-finops-sandbox-workflow` và kiểm tra các lượt chạy bắt đầu bằng tiền tố `replay-`.
2. **Các bảng DynamoDB**:
   - Kiểm tra bảng `tf2-finops-sandbox-account-policy` để xác nhận tài khoản `336805808730` đã được tạo.
   - Kiểm tra bảng `finops-idempotency-sandbox` để xác nhận các ad-hoc run duy nhất được xử lý thành công.
3. **S3 Audit Trail**: Xác nhận các bản ghi thô nén gzip và nhật ký hành động ngăn chặn (containment audit trails) được ghi lại dưới đường dẫn `s3://tf2-finops-sandbox-lakehouse/audit/`.

---

## 4. Dọn dẹp & Hoàn tác

Sau khi hoàn tất quá trình kiểm thử, khôi phục môi trường sandbox về chế độ hoạt động tiêu chuẩn:

1. Mở tệp `environments/sandbox/terraform.tfvars`.
2. Đưa các tham số về giá trị mặc định:
   ```hcl
   synthetic_replay_enabled              = false
   synthetic_replay_business_context_uri = ""
   ```
3. Triển khai lại thay đổi:
   ```powershell
   cd environments/sandbox
   terraform apply
   cd ../..
   ```
4. (Tùy chọn) Xóa tệp business context khỏi S3:
   ```powershell
   aws s3 rm s3://tf2-finops-sandbox-lakehouse/replay/business_context.json
   ```

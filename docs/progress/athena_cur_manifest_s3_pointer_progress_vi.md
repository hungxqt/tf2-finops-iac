# Báo cáo Tiến độ: Triển khai Athena CUR Manifest sang S3_POINTER

## 1. Tóm tắt Dự án

Chúng tôi đã triển khai thành công quy trình chuyển đổi sẵn sàng cho AI:
`S3 CUR manifest` -> `cost_puller metadata` -> `normalizer Athena query` -> `AI detect payload JSON` -> `gzip` -> `S3` -> `Step Functions S3_POINTER` -> `VpcAlbCallerLambda` -> `AI Engine Lambda`.

Tất cả 193 kiểm thử pytest (bao gồm kiểm thử đơn vị, kiểm thử máy trạng thái và kiểm thử hợp đồng) trong `lambda_src` đều đã vượt qua thành công. Các công cụ phân tích tĩnh (checkov, trivy và `terraform validate`) xác nhận cấu hình hạ tầng là hợp lệ về mặt cú pháp, an toàn và sẵn sàng cho môi trường production.

---

## 2. Chi tiết Triển khai

### 2.1 cost_puller
- **Phát hiện CUR Manifest**: Thay thế việc kiểm tra giả lập bằng cơ chế phát hiện manifest thực tế, quét các đường dẫn có tiền tố để tìm file `manifest.json` hoặc `-Manifest.json`.
- **Xác thực**: Lấy dữ liệu manifest từ S3, xác thực cấu trúc JSON, kiểm tra sự tồn tại của `assemblyId` và trích xuất các `reportKeys` mục tiêu.
- **Dữ liệu đầu ra**: Trả về siêu dữ liệu quan trọng (`cur_manifest_uri`, `source_bucket`, `source_prefix`, `account_id`, `run_window`, `freshness_flags` và `quality_flags`) khi CUR hoạt động bình thường.
- **Phương án dự phòng CE**: Khi CUR bị trễ (>36 giờ), truy vấn AWS Cost Explorer, đóng gói dữ liệu vào `raw_envelope` chứa các chỉ số sử dụng và ngữ cảnh kinh doanh, nén bằng gzip và ghi vào `_raw.json.gz`.

### 2.2 normalizer
- **Truy vấn Athena**: Trong trường hợp CUR bình thường, thực thi truy vấn SELECT được tham số hóa đối với database Glue và bảng CUR sử dụng các biến `ATHENA_WORKGROUP_NAME` và `ATHENA_RESULTS_BUCKET_NAME`.
- **Quét trạng thái & Phân trang**: Thăm dò trạng thái truy vấn (thành công/thất bại/hết giờ) và phân trang qua tập kết quả.
- **Tuần tự hóa Payload AI**: Tuần tự hóa payload phát hiện của AI, nén bằng gzip và tải lên S3 tại đường dẫn `ai-input/account_id=..._input.json.gz`.
- **Xác thực SQL**: Triển khai xác thực biểu thức chính quy nghiêm ngặt (`^[a-zA-Z0-9_-]+$`) cho các đầu vào SQL để ngăn chặn chèn mã SQL độc hại hoặc tấn công duyệt đường dẫn (path traversal).
- **Tính tương thích dự phòng**: Chỉ giải nén các file từ S3 khi chúng có tiêu đề magic gzip (`b'\x1f\x8b'`), giữ tính tương thích với các mảng JSON không nén trong các kiểm thử giả lập.

### 2.3 Step Functions & ASL
- **Đường dẫn S3_POINTER**: Sử dụng đầu ra `s3_bucket_uri` từ `normalizer` làm con trỏ S3, truyền đồng bộ tới `VpcAlbCallerLambda` để gọi endpoint `/v1/detect`.
- **Cơ chế Fail Closed**: Máy trạng thái sẽ thực thi `SetS3PointerMissingError` và chuyển sang trạng thái thất bại (FailClosed) nếu không có con trỏ `.json.gz` nào được tạo ra bởi `normalizer`.

### 2.4 Terraform & Quyền IAM
- **Ranh giới Quyền hạn (Permissions Boundary)**: Cập nhật chính sách ranh giới quyền hạn `boundary` trong `modules/iam/main.tf` để cho phép Lambda thực hiện:
  - Các hành động S3 `GetObject`, `PutObject`, `ListBucket` và `GetBucketLocation` trên bucket kết quả Athena.
  - Các hành động KMS `Encrypt`, `Decrypt` và `GenerateDataKey` trên các khóa CMK.
  - Các lệnh gọi API Athena (`StartQueryExecution`, `GetQueryExecution`, `GetQueryResults`, v.v.).
  - Các lệnh gọi API Glue Catalog (`GetDatabase`, `GetTable`, `GetPartitions`).
- **Đồng bộ hóa Đa Môi trường**: Cấu hình các biến này cho `module.iam` trong `environments/staging/main.tf` và `environments/prod/main.tf` để đồng bộ hóa cấu hình Staging và Production với Sandbox.

---

## 3. Nhật ký Kiểm thử & Xác thực

Tất cả các kiểm thử đã được chạy và xác minh cục bộ:
1. **Bộ kiểm thử Pytest**: 193/193 kiểm thử thành công (bao gồm kiểm thử truy vấn Athena, phân trang, nén gzip, máy trạng thái và tuân thủ hợp đồng).
2. **Terraform Format & Validate**: Các lệnh `terraform fmt -check` và `terraform validate` thành công với 0 lỗi.
3. **Phân tích An ninh Tĩnh**:
   - Checkov: 0 lỗi, tất cả các cảnh báo được bỏ qua đều được ghi tài liệu đầy đủ.
   - Trivy: 0 lỗi ở mức nghiêm trọng/cao.

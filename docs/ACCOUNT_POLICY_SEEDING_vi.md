# Hướng dẫn Khởi tạo dữ liệu Bảng Account Policy trong DynamoDB

Tài liệu này hướng dẫn quy trình dành cho người vận hành (operator) để khởi tạo dữ liệu (seed) cho bảng DynamoDB `account-policy` trước khi chạy thủ công hoặc kích hoạt quy trình tự động Scheduled Orchestrator Step Functions cho **Task Force 2 - FinOps Watch**.

---

## 1. Tổng quan

Bước `LoadAccountPolicy` trong Orchestrator Step Functions sẽ truy vấn thông tin ánh xạ ngữ cảnh từ DynamoDB bằng cách sử dụng AWS Account ID của tài khoản liên kết (linked account) đang được phân tích làm khóa chính. Vì bộ điều phối (orchestrator) lặp qua tất cả các tài khoản đích được định nghĩa trong `analysis_target_account_ids` (được cấu hình qua `telemetry_member_account_ids`), tất cả các tài khoản liên kết được phân tích phải được seed policy trong bảng này. Nếu bảng này chưa được seed cho bất kỳ tài khoản đích nào, quy trình cho tài khoản đó sẽ thất bại.

### Cấu trúc DynamoDB Item
Bảng yêu cầu các bản ghi (item) tuân thủ cấu trúc định dạng JSON sau:

```json
{
  "account_id": { "S": "123456789012" },
  "environment": { "S": "sandbox" }
}
```

* **`account_id`** (String, Partition Key): Mã số AWS Account ID gồm 12 chữ số.
* **`environment`** (String): Tên môi trường triển khai (ví dụ: `sandbox`, `staging`, `prod`).

---

## 2. Quy trình PowerShell AWS CLI để Seed dữ liệu

Chạy chuỗi lệnh PowerShell sau để seed dữ liệu hoặc xác minh bảng policy DynamoDB.

### Bước 2.1: Định nghĩa các Biến
Thiết lập các tham số mục tiêu phù hợp với ngữ cảnh triển khai của bạn:
```powershell
$ProjectName = "tf2-finops"
$EnvName     = "sandbox"               # Mục tiêu: sandbox, staging, hoặc prod
$AwsRegion   = "ap-southeast-1"        # Thay đổi theo khu vực triển khai thực tế
$AccountId   = "123456789012"          # Thay thế bằng 12 chữ số AWS Account ID thực tế của bạn
$TableName   = "$ProjectName-$EnvName-account-policy"
```

### Bước 2.2: Xác minh Bảng tồn tại
Đảm bảo rằng bảng DynamoDB đã tồn tại và có thể truy cập:
```powershell
aws dynamodb describe-table --table-name $TableName --region $AwsRegion
```

### Bước 2.3: Seed Dòng Dữ liệu (Ghi Idempotent)
Thêm item mới chỉ khi `account_id` chưa tồn tại trong bảng:
```powershell
aws dynamodb put-item `
  --table-name $TableName `
  --item '{
    "account_id": {"S": "'$AccountId'"},
    "environment": {"S": "'$EnvName'"}
  }' `
  --condition-expression "attribute_not_exists(account_id)" `
  --region $AwsRegion
```

### Bước 2.4: Xác minh Dòng dữ liệu đã Seed
Đọc lại bản ghi bằng phương thức đọc nhất quán (consistent read) để đảm bảo tính hiển thị tức thời của dữ liệu:
```powershell
aws dynamodb get-item `
  --table-name $TableName `
  --key '{"account_id": {"S": "'$AccountId'"}}' `
  --consistent-read `
  --region $AwsRegion
```

### Bước 2.5: Sửa đổi/Cập nhật Dòng Dữ liệu đã có
Nếu bạn cần thay đổi thông tin môi trường ánh xạ cho một Account ID đã có, chạy lệnh update cụ thể sau:
```powershell
aws dynamodb update-item `
  --table-name $TableName `
  --key '{"account_id": {"S": "'$AccountId'"}}' `
  --update-expression "SET #env = :val" `
  --expression-attribute-names '{"#env": "environment"}' `
  --expression-attribute-values '{":val": {"S": "'$EnvName'"}}' `
  --region $AwsRegion
```

---

## 3. Khắc phục Sự cố & Lưu ý Vận hành

### Lỗi Trích xuất dữ liệu bằng JSONPath
Nếu lệnh `get-item` trả về kết quả rỗng (không tìm thấy item khớp với AWS Account ID đang thực thi), việc chạy Orchestrator Step Functions sẽ thất bại tại bước `LoadAccountPolicy` với thông báo lỗi:
> `The JSONPath $.Item.account_id.S could not be found in the input`

Lỗi này xảy ra vì khối `ResultSelector` của Task yêu cầu chính xác các trường này để trích xuất ngữ cảnh vận hành.

### Đồng bộ Account ID
* **Chạy Thủ công**: Nếu bạn kích hoạt Step Functions State Machine thủ công, hãy đảm bảo dữ liệu đầu vào (input) của lần chạy có chứa giá trị đơn lẻ `"account_id"` hoặc danh sách `"analysis_targets"` đại diện cho các tài khoản bạn muốn phân tích. Các Account ID này phải được seed sẵn.
* **Chạy Tự động qua Scheduler**: Trình lập lịch EventBridge Scheduler sẽ kích hoạt State Machine bằng cách truyền đầu vào chứa `management_account_id` và `analysis_targets` (là một danh sách các linked account ID). Hãy đảm bảo mỗi Account ID có trong danh sách `analysis_targets` đều đã có dòng dữ liệu tương ứng được seed trong bảng.

### Biện pháp Phòng ngừa (Guardrails)
* **`scheduler_enabled`**: Hãy cấu hình `scheduler_enabled = false` trong các tệp Terraform của bạn cho đến khi dòng dữ liệu DynamoDB được seed thành công và xác minh qua cơ chế consistent read. Điều này giúp ngăn chặn các lịch chạy tự động bắt đầu khi hệ thống chưa được cấu hình đúng.

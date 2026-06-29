# Tài liệu Hướng dẫn Vận hành Chạy Thủ công Step Functions

Tài liệu này cung cấp quy trình dành cho người vận hành (operator) để kích hoạt, theo dõi và xác minh thủ công các lượt chạy của quy trình điều phối Orchestrator Step Functions cho **Task Force 2 - FinOps Watch**.

---

## 1. Điều kiện Tiên quyết

Trước khi kích hoạt chạy thủ công, hãy đảm bảo các yêu cầu sau được đáp ứng:

1. **Môi trường đã triển khai**: Môi trường đích (ví dụ: `sandbox`, `staging`, hoặc `prod`) phải được triển khai hoàn chỉnh bằng Terraform.
2. **Quyền truy cập AWS CLI**: Shell của người vận hành phải được xác thực với tài khoản AWS chính xác và có quyền thực thi các hành động:
   * `states:StartExecution`
   * `states:DescribeExecution`
   * `states:GetExecutionHistory`
   * `states:ListStateMachines`
3. **Trình Lập lịch Tắt/Bật**: Lượt chạy thủ công có thể thực hiện bất kể trình lập lịch EventBridge Scheduler đang được kích hoạt hay không (`scheduler_enabled = true` hoặc `false`).
4. **Các Lambda Worker đã sẵn sàng**: Các Hyperplane ENI và việc tối ưu hóa container image phải được hoàn tất và ở trạng thái `ACTIVE` (tham khảo Bước 2.8 trong [GUIDES_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES_vi.md)).
5. **Đã Seed Account Policy**: Mỗi AWS Account ID mục tiêu được phân tích phải có một dòng dữ liệu tương ứng trong bảng DynamoDB `account-policy` của môi trường. Nếu một tài khoản đích chưa được seed dữ liệu, lượt chạy sẽ thất bại. Xem [ACCOUNT_POLICY_SEEDING_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/ACCOUNT_POLICY_SEEDING_vi.md) để biết quy trình seed dữ liệu.
6. **Sự sẵn có của Dữ liệu Telemetry**: Đầu vào dữ liệu telemetry hợp lệ (Báo cáo Chi phí và Sử dụng - CUR trong S3, logs chỉ số CloudWatch, hoặc quyền truy cập API Cost Explorer) phải có sẵn cho khoảng thời gian chi phí cần phân tích.

---

## 2. Truy vấn State Machine ARN

Để bắt đầu chạy, bạn cần biết mã ARN của State Machine mục tiêu. Bạn có thể lấy thông tin này bằng một trong hai phương pháp sau:

### Phương pháp A: Sử dụng giá trị đầu ra (Output) của Terraform (Khuyến nghị)
Di chuyển đến thư mục của môi trường mục tiêu và truy vấn giá trị output:
```powershell
# Cho sandbox
terraform -chdir=environments/sandbox output -raw state_machine_arn

# Cho staging
terraform -chdir=environments/staging output -raw state_machine_arn

# Cho prod
terraform -chdir=environments/prod output -raw state_machine_arn
```

### Phương pháp B: Tìm kiếm bằng AWS CLI
Nếu không có sẵn mã nguồn Terraform cục bộ, truy vấn mã ARN bằng cách tìm kiếm theo quy tắc đặt tên vật lý của state machine (`tf2-finops-<env>-workflow`):
```powershell
# Thay thế <env> bằng sandbox, staging, hoặc prod
$EnvName = "sandbox"
$StateMachineArn = aws stepfunctions list-state-machines `
  --query "stateMachines[?name=='tf2-finops-$EnvName-workflow'].stateMachineArn" `
  --output text
```

---

## 3. Quy trình Chạy Thủ công bằng PowerShell

Chạy chuỗi lệnh PowerShell sau để kích hoạt và theo dõi quy trình làm việc.

### Bước 3.1: Khởi tạo các Biến
Chỉ định các tham số thực thi:
```powershell
$AwsRegion       = "ap-southeast-1"         # Vùng triển khai mục tiêu
$EnvName         = "sandbox"                # sandbox, staging, hoặc prod
$ProjectName     = "tf2-finops"
$StateMachineArn = "arn:aws:states:$AwsRegion:123456789012:stateMachine:$ProjectName-$EnvName-workflow" # Cập nhật đúng Account ID của bạn
```

### Bước 3.2: Chuẩn bị tệp dữ liệu đầu vào (Input File)
Tạo một tệp JSON tạm thời cục bộ. Chọn một trong hai chế độ thực thi sau:

#### Lựa chọn 1: Chạy thủ công Ad Hoc cho một Tài khoản
Sử dụng payload này để phân tích một tài khoản đích duy nhất:
```powershell
$InputJson = @'
{
  "operation": "prepare",
  "input": {
    "account_id": "444444444444",
    "is_ad_hoc": true
  }
}
'@
$InputJson | Set-Content -Path .\manual_input.json -Encoding utf8
```

#### Lựa chọn 2: Giả lập lượt chạy theo Lịch trình cho nhiều Tài khoản (Multi-Account)
Sử dụng payload này để phân tích nhiều tài khoản liên kết (member accounts) được quản lý bởi một tài khoản trung tâm:
```powershell
$InputJson = @'
{
  "operation": "prepare",
  "input": {
    "management_account_id": "111111111111",
    "analysis_targets": ["222222222222", "333333333333"],
    "trigger_type": "scheduled",
    "is_ad_hoc": false
  }
}
'@
$InputJson | Set-Content -Path .\manual_input.json -Encoding utf8
```

### Bước 3.3: Kích hoạt Lượt chạy
Bắt đầu chạy state machine sử dụng tệp đầu vào JSON vừa tạo:
```powershell
$ExecutionArn = aws stepfunctions start-execution `
  --state-machine-arn $StateMachineArn `
  --input file://manual_input.json `
  --query "executionArn" `
  --output text `
  --region $AwsRegion

Write-Host "Started State Machine execution: $ExecutionArn"
```

### Bước 3.4: Theo dõi Trạng thái Lượt chạy
Truy vấn trạng thái và thông tin chi tiết của lượt chạy:
```powershell
aws stepfunctions describe-execution `
  --execution-arn $ExecutionArn `
  --region $AwsRegion
```
Tìm kiếm trường `"status"` trong phản hồi JSON (ví dụ: `RUNNING`, `SUCCEEDED`, `FAILED`, `TIMED_OUT`, `ABORTED`).

### Bước 3.5: Kiểm tra Nhật ký và Lịch sử Thực thi
Để khắc phục sự cố hoặc theo dõi các bước chuyển trạng thái, xem các sự kiện hàng đầu trong lịch sử chạy:
```powershell
aws stepfunctions get-execution-history `
  --execution-arn $ExecutionArn `
  --region $AwsRegion `
  --max-items 15 `
  --reverse-order
```
*Lưu ý: Xóa tệp JSON tạm thời sau khi hoàn tất:*
```powershell
Remove-Item -Path .\manual_input.json -ErrorAction SilentlyContinue
```

---

## 4. Các Giới hạn & Biện pháp Bảo vệ An toàn

### Giới hạn ghi đè `force_dry_run` qua Tham số đầu vào
> [!WARNING]
> **KHÔNG** cố gắng truyền tham số `"force_dry_run": true` (hoặc `false`) vào trong payload JSON đầu vào để ghi đè chế độ chạy thử.
>
> Hàm Lambda `PrepareRunContext` (`op == "prepare"`) khởi tạo trạng thái quy trình và **luôn thiết lập cứng/đặt lại `force_dry_run` về `False`** khi bắt đầu chạy. Mọi giá trị `force_dry_run` được truyền thủ công từ bên ngoài sẽ bị bỏ qua và ghi đè hoàn toàn.

### Các cơ chế Bảo vệ Chủ động
Do người vận hành không thể ép buộc trạng thái dry-run trực tiếp từ tham số đầu vào, tính an toàn của hệ thống phụ thuộc hoàn toàn vào các rào chắn bảo vệ tự động sau:
1. **Chính sách Tài khoản DynamoDB**: Việc seed bảng DynamoDB xác định ranh giới cho phép của môi trường đối với từng tài khoản.
2. **Cổng Kiểm định Chất lượng Telemetry**: Nếu phát hiện dữ liệu telemetry bị trễ (quá 26 giờ), là dữ liệu ước tính, hoặc không đầy đủ, quy trình sẽ tự động hạ cấp xuống chế độ chạy thử dry-run / chỉ cảnh báo (alert-only containment) và ghi nhận nhật ký bằng chứng kiểm toán (audit evidence).
3. **Khóa Ngân sách Lỗi (Error Budget Lock)**: Bước `check_error_budget` sẽ kiểm tra cơ sở dữ liệu ngân sách lỗi. Nếu ngân sách lỗi bị khóa do lượng cảnh báo lớn, do vòng lặp rollback, hoặc vượt ngưỡng an toàn của sandbox, hệ thống sẽ tự động thiết lập `force_dry_run = true` cho giai đoạn thực thi containment.
4. **Rào chắn của Containment Worker**: Hàm Lambda thực hiện containment luôn đánh giá lại quyền hạn IAM tối thiểu và kiểm tra các cờ an toàn môi trường trước khi thực thi hủy hoặc giảm cấp tài nguyên AWS thực tế.

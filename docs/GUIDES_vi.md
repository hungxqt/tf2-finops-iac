# Hướng dẫn dành cho Nhà phát triển TF2 FinOps IaC

Tài liệu này trình bày chi tiết quy trình làm việc từng bước dành cho các nhà phát triển và vận hành hệ thống làm việc với kho lưu trữ Infrastructure as Code (IaC) **Task Force 2 - FinOps Watch**.

---

## 1. Yêu cầu hệ thống
Hãy đảm bảo bạn đã cài đặt và cấu hình đầy đủ các công cụ sau:
* **Terraform** (>= 1.10)
* **AWS CLI** (được cấu hình với quyền Administrator cho AWS Account đích)
* **Python** (>= 3.13) & `pip` (để chạy các thử nghiệm worker cục bộ)
* **PowerShell** (để chạy script đóng gói trên môi trường Windows)

### 1.1 Điều kiện tiên quyết đối với Thu thập số liệu liên tài khoản (Tùy chọn)
Nếu triển khai của bạn liên quan đến việc thu thập số liệu chi phí và sử dụng (telemetry) từ các tài khoản thành viên AWS (member accounts) riêng biệt:
1. **Cấu hình tại Tài khoản Payer/CDO**:
   - Thiết lập biến đầu vào `telemetry_member_account_ids` là danh sách các ID của tài khoản thành viên.
   - Cấu hình bucket và tiền tố CUR nguồn bằng cách sử dụng `cur_source_bucket_arn` và `cur_source_prefix` trong các tham số của module `iam`.
2. **Cấu hình Vai trò (Role) tại Tài khoản Thành viên**:
   - Mỗi tài khoản thành viên phải triển khai vai trò IAM thu thập dữ liệu (`cdo-telemetry-ingestion-role`).
   - Chính sách ủy thác (trust policy) của vai trò này phải cho phép ARN của vai trò IAM CDO cost-puller từ tài khoản Payer/CDO giả định (assume role).
   - Chính sách phân quyền của vai trò phải cấp quyền đọc (`s3:ListBucket`, `s3:GetObject`) đối với bucket/tiền tố CUR cục bộ, và cho phép truy vấn Cost Explorer (`ce:GetCostAndUsage`) và số liệu CloudWatch (`cloudwatch:GetMetricData`).

---

## 2. Quy trình triển khai từng bước

### Bước 2.1: Chạy các kiểm tra cục bộ (Unit Tests)
Xác minh rằng các hàm adapter tuân thủ đúng hợp đồng bằng cách chạy bộ kiểm tra Python pytest:
```powershell
cd lambda_src
pip install -r requirements-dev.txt
python -m pytest
cd ..
```

### Bước 2.2: Khởi tạo Backend State và vai trò OIDC
Quy trình bootstrap giúp thiết lập xác thực không cần khóa (OIDC) qua GitHub và tạo S3 bucket lưu trữ state từ xa một cách bảo mật.

#### Lựa chọn A: Thiết lập ban đầu / Triển khai Bootstrap lần đầu (Thực hiện một lần duy nhất)
Nếu đây là lần đầu tiên thiết lập dự án và S3 backend chưa được kích hoạt:
1. **Triển khai bootstrap cục bộ**:
   Đảm bảo rằng khối `backend "s3"` trong [bootstrap/backend.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/backend.tf) đã được chú thích (comment out), sau đó chạy:
   ```powershell
   cd bootstrap
   terraform init
   terraform apply
   ```
2. **Di chuyển State lên S3**:
   - Sao chép ARN của KMS Key dùng cho state được xuất ra từ terminal.
   - Mở tệp [bootstrap/backend.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/backend.tf), bỏ chú thích khối cấu hình `terraform` backend và thay thế giá trị `kms_key_id` bằng ARN của bạn:
     ```hcl
     terraform {
       backend "s3" {
         bucket       = "tf2-finops-state-bucket"
         key          = "bootstrap/terraform.tfstate"
         region       = "ap-southeast-1"
         encrypt      = true
         kms_key_id   = "arn:aws:kms:ap-southeast-1:093490087544:key/f0382479-e89e-41af-8041-89d10f275bf4"
         use_lockfile = true
       }
     }
     ```
   - Thực hiện lệnh di chuyển trạng thái (migrate state) lên S3 bucket từ xa:
     ```powershell
     terraform init -migrate-state
     ```

#### Lựa chọn B: Dành cho các thành viên khác tiếp tục làm việc (Subsequent Developers)
Nếu bootstrap đã được chạy trước đó và cấu hình S3 backend đã được kích hoạt trong kho lưu trữ:
1. **Khởi tạo Backend**:
   Khởi tạo trực tiếp Terraform. Terraform sẽ tự động nhận diện khối cấu hình S3 backend đang hoạt động trong [bootstrap/backend.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/backend.tf) và kết nối tới remote state hiện có:
   ```powershell
   cd bootstrap
   terraform init
   ```
   *Lưu ý: Các thành viên khác không cần chạy `apply` hoặc `migrate-state` trong thư mục bootstrap trừ khi cần thực hiện thay đổi đối với chính hạ tầng bootstrap.*

### Bước 2.3: Đóng gói các hàm Lambda dưới dạng tệp Zip
Đóng gói 7 hàm adapter Python vào thư mục `.build/lambda/`:
```powershell
cd ..
.\scripts\package-lambdas.ps1
```

### Bước 2.4: Triển khai các Môi trường (Environment Compositions)
Triển khai các môi trường theo tuần tự (Sandbox trước, sau đó là Staging và Prod).

#### Thiết lập Backend và Biến cho Môi trường:
* **Kết nối Remote State**: Khối cấu hình remote state backend đã được thiết lập sẵn trong tệp `backend.tf` của mỗi môi trường (`sandbox/terraform.tfstate`, `staging/terraform.tfstate`, `prod/terraform.tfstate`). Bạn chỉ cần chạy lệnh `terraform init` để tự động kết nối với S3 remote state chung.
* **Cấu hình Biến (Variables)**: Trước khi lập kế hoạch (plan) hoặc áp dụng (apply), bạn phải sao chép tệp `terraform.tfvars.example` trong thư mục môi trường thành tệp `terraform.tfvars` cục bộ (tệp này được bỏ qua bởi git) và cập nhật các giá trị (chẳng hạn như ECR Image URIs và ACM Certificate ARNs) cho phù hợp với triển khai của bạn.

1. **Triển khai Sandbox**:
   ```powershell
   cd environments/sandbox
   # Sao chép tệp biến mẫu và cập nhật giá trị
   cp terraform.tfvars.example terraform.tfvars
   # Khởi tạo và kết nối tới remote state
   terraform init
   # Cung cấp biến alb_certificate_arn bắt buộc (qua tfvars hoặc dòng lệnh)
   terraform plan -out=sandbox.tfplan
   terraform apply sandbox.tfplan
   ```
2. **Triển khai Staging**:
   ```powershell
   cd ../staging
   cp terraform.tfvars.example terraform.tfvars
   terraform init
   terraform plan -out=staging.tfplan
   terraform apply staging.tfplan
   ```
3. **Triển khai Production** (Yêu cầu xem xét và phê duyệt kế hoạch trước):
   ```powershell
   cd ../prod
   cp terraform.tfvars.example terraform.tfvars
   terraform init
   terraform plan -out=prod.tfplan
   # Áp dụng cho môi trường Production cần được phê duyệt và kích hoạt qua GitHub Environments
   terraform apply prod.tfplan
   ```

### Bước 2.5: Chẩn đoán trạng thái Lambda sau khi triển khai
Các hàm Lambda được gắn VPC (cả worker dạng zip và AI runtime dạng container) yêu cầu AWS khởi tạo các Hyperplane ENI và tối ưu hóa container image ở chế độ bất đồng bộ. Quá trình này diễn ra sau khi Terraform apply hoàn thành và có thể mất vài phút.

Chạy vòng lặp lệnh AWS CLI sau để kiểm tra trạng thái của tất cả 9 hàm Lambda:

Dành cho PowerShell (Windows):
```powershell
$workers = "state", "cost_puller", "normalizer", "router", "audit_writer", "containment_worker", "vpc_alb_caller", "ai-request", "ai-worker"
foreach ($w in $workers) {
    aws lambda get-function --function-name "tf2-finops-sandbox-$w" --query "Configuration.[FunctionName, State, StateReason, LastUpdateStatus]" --output json
}
```

Dành cho Bash (macOS/Linux):
```bash
for fn in state cost_puller normalizer router audit_writer containment_worker vpc_alb_caller ai-request ai-worker; do
  aws lambda get-function --function-name tf2-finops-sandbox-$fn --query "Configuration.[FunctionName, State, StateReason, LastUpdateStatus]" --output table
done
```

**Tiêu chí xác minh:**
* **State**: Cuối cùng sẽ chuyển sang `Active`. (Nếu hiển thị `Pending`, hãy đợi 1-2 phút để AWS hoàn tất quá trình thiết lập ENI/Image).
* **StateReason**: Phải trống hoặc null. Nếu có thông tin lỗi liên quan đến thiết lập ENI hoặc thiếu quyền, hãy kiểm tra lại cấu hình IAM Roles và Security Groups.
* **LastUpdateStatus**: Cuối cùng sẽ là `Successful`.

### 2.4. Hủy / Giải phóng môi trường Sandbox (Teardown / Destroy Sandbox)

Để hủy bỏ môi trường sandbox nhằm dọn dẹp hoặc kiểm tra quy trình giải phóng tài nguyên:
1. Tạo kế hoạch hủy tài nguyên:
   ```powershell
   cd environments/sandbox
   terraform plan -destroy -out=sandbox-destroy.tfplan
   ```
2. Xem xét kỹ kế hoạch hủy đã tạo để đảm bảo các tài nguyên bị hủy là chính xác.
3. Áp dụng kế hoạch hủy:
   ```powershell
   terraform apply sandbox-destroy.tfplan
   ```

> [!WARNING]
> **Giới hạn kỹ thuật của AWS Object Lock**:
> Nếu bucket audit sandbox đã chứa các phiên bản đối tượng được giữ lại theo chế độ Tuân thủ (Compliance-mode), AWS sẽ áp dụng một hạn chế cứng ngăn việc xóa các đối tượng này cho đến khi thời hạn lưu trữ hết hạn. Trong trường hợp đó, Terraform sẽ thất bại khi xóa bucket audit. Mặc dù Object Lock chế độ Tuân thủ đã được tắt cho các bucket audit sandbox *mới tạo* để cho phép dọn dẹp, nhưng nếu Object Lock đã được cấu hình trước đó và có dữ liệu, các đối tượng này phải hết hạn trước khi có thể dọn dẹp hoàn toàn.
>
> **Độ trễ khi giải phóng ENI VPC Lambda**:
> Khi hủy môi trường Lambda được gắn VPC, AWS Lambda sẽ giữ các cổng mạng Hyperplane ENI trong bộ nhớ cache tối đa 20 phút sau khi các hàm Lambda đã bị xóa. Trong thời gian chờ này, Terraform sẽ hiển thị thông báo `Still destroying...` và có thể bị treo ở bước xóa các private subnets cũng như Lambda security group vì chúng vẫn đang liên kết với các ENI này. Đây là hành vi kiểm soát bình thường của AWS. Vui lòng không ngắt lệnh; khi AWS tự động giải phóng các ENI (thường trong vòng 10 đến 15 phút), các subnet và security group sẽ được xóa thành công và quá trình hủy tài nguyên sẽ hoàn tất.

Các môi trường Staging và Production được bảo vệ nghiêm ngặt bằng tài nguyên tuần tra `destroy_guard` (terraform_data) và không thể bị xóa thông qua kế hoạch hủy thông thường.

---

## 3. Bàn giao sau khi triển khai cho GitOps (`tf2-finops-gitops`)
Sau khi quá trình deploy hoàn tất, hãy lấy các dữ liệu đầu ra để cấu hình cho tầng ứng dụng (Workload Layer) trong kho lưu trữ `tf2-finops-gitops`:
```powershell
terraform output
```

* `private_alb_endpoint`: URL HTTPS cơ sở để truy cập private ALB (qua Route 53 private DNS alias hoặc DNS name của internal ALB).
* `private_alb_dns_name`: Tên miền DNS thô của internal ALB.
* `private_alb_security_group_id`: ID security group của internal ALB.
* `request_lambda_function_name`: Tên của hàm AI Engine Request Lambda (chạy bằng container image, được gọi qua target group của internal ALB trên cổng 443).
* `worker_lambda_function_name`: Tên của hàm AI Engine Worker Lambda (chạy bằng container image, xử lý việc nhập bất thường bất đồng bộ).
* `ecr_repository_url`: URL của kho lưu trữ ECR để push container image cho Lambda.
* `state_machine_arn`: ARN của Orchestrator State Machine.
* `dynamodb_table_names`: Các tên bảng DynamoDB phục vụ cho việc lưu trữ trạng thái chạy, kết quả, audit, và rollback cache.
* `synchronous_ai_endpoints`: Các endpoint `/v1/detect`, `/v1/decide`, và `/v1/verify` là các hoạt động đồng bộ được gọi qua `VpcAlbCallerLambda` và Route 53 private DNS alias. `/v1/status/{id}` chỉ dành cho remediation audit/status, không dùng cho việc polling phát hiện. Không có hàng đợi SQS detect hoặc vòng lặp polling trong luồng mặc định; SQS được giới hạn cho việc thử lại cảnh báo và thông báo hoàn thành audit `finops-watch-rollback`.


### Bước 3.1: Triển khai Dashboard & Bàn giao Tài nguyên (Asset Handoff)
Sau khi mã nguồn Terraform được áp dụng (apply), hạ tầng Dashboard đã sẵn sàng. Quy trình bàn giao tuân theo các quy tắc sau:
1. **Vai trò của Terraform**: Terraform khởi tạo các tài nguyên AWS nền tảng (S3 buckets, CloudFront distribution với VPC Origin và liên kết Lambda@Edge, Cognito Identity & User Pools, các Athena named queries và vai trò IAM).
2. **Cổng Xác thực (Authenticated Front Door)**: Tất cả tài nguyên tĩnh và tệp tóm tắt JSON (dưới `/${dashboard_data_prefix}*`) được phục vụ qua CloudFront và bảo vệ bởi hàm Lambda@Edge viewer-request sử dụng xác thực Cognito PKCE.
3. **Định tuyến API qua VPC Origin**: Các yêu cầu gửi tới `/v1/*` được ký bằng AWS SigV4 thông qua Lambda@Edge origin-request trước khi chuyển tiếp tới private internal ALB, đồng thời loại bỏ các cookie Cognito.
4. **Tải lên Tài nguyên Static (Asset Upload)**: Các tài nguyên static của frontend (ứng dụng giao diện UI) phải được tải lên riêng biệt vào S3 bucket chứa static assets (được cấu hình trong giá trị đầu ra `dashboard_asset_bucket_name`).
5. **Nhóm Cognito (Cognito Groups)**: Người dùng cần được thêm vào các nhóm Cognito tương ứng (`finops-finance-readonly`, `finops-engineering-operator`, `finops-cdo-admin`) để kiểm soát quyền hạn.
6. **Sinh dữ liệu (Data Generation)**: Các công cụ ghi dữ liệu chi phí phải tải các tệp tóm tắt JSON lên tiền tố đã cấu hình (ví dụ: `summaries/`) trong S3 bucket chứa dữ liệu dashboard (được cấu hình trong giá trị đầu ra `dashboard_data_bucket_name`).


---

## 4. Kiểm tra tích hợp liên tục và xác thực mã nguồn (CI/CD)
Trước khi commit và push mã nguồn, hãy chạy toàn bộ các lệnh kiểm tra lỗi cục bộ sau:
```powershell
# Định dạng mã nguồn
terraform fmt -check -recursive

# Xác thực cấu hình cú pháp
terraform -chdir=bootstrap validate
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod validate

# Quét phân tích bảo mật tĩnh
trivy config .
checkov -d . --framework terraform
```

---

## 5. Xác thực Glue Schema & Partition Projection

Để hỗ trợ truy vấn tự động và tối ưu chi phí mà không cần duy trì các crawler tiêu tốn tài nguyên hoặc lập lịch các truy vấn sửa chữa phân vùng thủ công (MSCK REPAIR), lakehouse sử dụng tính năng Athena Partition Projection.

### Bước 5.1: Xác thực cấu hình bảng Glue trong Terraform
Chạy các kiểm thử tập trung cho module để kiểm tra các khóa phân vùng, định dạng đầu vào/đầu ra và cấu hình bảng tĩnh:
```powershell
cd modules/lakehouse
terraform init
terraform test
cd ../..
```

### Bước 5.2: Kiểm tra DDL Athena khớp với Schema
Để kiểm tra, gỡ lỗi hoặc tạo thủ công các bảng Parquet `cur_data` và JSON `containment_audit`, xem file script xác thực:
* [scripts/athena_validation.sql](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/scripts/athena_validation.sql)

Đảm bảo phạm vi projection của bảng (ví dụ: `2024,2035`), định dạng và đường dẫn phân vùng S3 khớp chính xác với đường dẫn đầu ra của worker.

---

## 7. Cấu hình và Xác thực Thu thập Dữ liệu Telemetry

Worker `cost_puller` đảm nhận việc thu thập dữ liệu chi phí (billing) và hiệu năng (utilization) thô. Nó hoạt động ở chế độ thu thập hỗn hợp (hybrid ingestion), đọc các tệp CUR từ S3 source bucket hoặc tự động chuyển sang Cost Explorer khi CUR bị trễ.

### Bước 7.1: Các tham số cấu hình
Hành vi thu thập dữ liệu được kiểm soát bởi các biến Terraform được truyền vào module `compute_lambda`:
* `cur_source_bucket`: Bucket S3 nơi AWS CUR được lưu trữ.
* `cur_source_prefix`: Đường dẫn prefix trong source bucket cho các tệp CUR.
* `cur_delay_threshold_hours`: Ngưỡng thời gian trễ (tính bằng giờ) trước khi chuyển sang chế độ dự phòng CE (mặc định: `36`).
* `ce_lookback_window_days`: Số ngày lịch sử CE cần lấy khi chạy dự phòng (mặc định: `30`).
* `traffic_metric_identifiers`: Định danh dùng để truy vấn dữ liệu traffic vật lý (ví dụ: tên ALB).
* `synthetic_fallback_enabled`: Bật/tắt chế độ tự động tạo dữ liệu giả lập cho local tests/simulations (mặc định: `true`).

### Bước 7.2: Xác minh và Giả lập
Người vận hành có thể xác minh luồng retry/wait và xử lý lỗi của State Machine thông qua các hành động giả lập (simulation actions) trong event thực thi:
* **Giả lập CUR bị trễ**: Gửi `"action": "simulate-cur-delay"` để ép trạng thái trễ CUR và kích hoạt luồng dự phòng Cost Explorer.
* **Giả lập CE bị throttling**: Gửi `"action": "simulate-ce-throttled"` để kích hoạt lỗi rate limit cho CE. Nếu có dữ liệu cache trong destination bucket, hệ thống sẽ khôi phục dữ liệu từ cache và đặt cờ chất lượng `stale_cost_explorer = true`; nếu không sẽ trả về lỗi `CE_THROTTLED`.

Xác minh các tệp JSON gzipped được tạo ra bằng cách kiểm tra các đường dẫn prefix S3:
* Cost Telemetry chính: `s3://<lakehouse-bucket>/cur/account_id=<id>/year=YYYY/month=MM/day=DD/<run-id>_raw.json.gz`
* Utilization Features: `s3://<lakehouse-bucket>/features/account_id=<id>/year=YYYY/month=MM/day=DD/<run-id>_features.json.gz`

---

## 8. Containment Worker — Phát triển cục bộ & Kiểm thử

`containment_worker` là một Lambda production-grade thực thi các containment action trên
resource của member account. Vì nó thực hiện các lời gọi AWS thật (EC2, RDS, SageMaker, STS, S3,
DynamoDB), toàn bộ test suite dùng **moto** để mock tầng AWS — không cần AWS credentials hay
resource thật để chạy local.

### 8.1 Cài đặt Dev Dependencies

```powershell
cd lambda_src
pip install -r requirements-dev.txt
```

Lệnh này cài `moto[ec2,rds,s3,dynamodb,sts]>=5.0.0` cùng với `pytest` và `boto3`.

### 8.2 Chạy toàn bộ Tests

```powershell
# Từ thư mục gốc của repo
Push-Location lambda_src; python -m pytest; Pop-Location
```

### 8.3 Chạy chỉ Tests của Containment Worker

```powershell
Push-Location lambda_src
# Toàn bộ containment suite
python -m pytest tests/test_containment_worker.py -v

# Chỉ hard-boundary tests (không cần moto — chạy nhanh)
python -m pytest tests/test_containment_worker.py -v -k "boundary"

# Chỉ audit/S3/DynamoDB tests (yêu cầu moto)
python -m pytest tests/test_containment_worker.py -v -k "audit"

# Chỉ action-dispatch tests (yêu cầu moto)
python -m pytest tests/test_containment_worker.py -v -k "actions"
Pop-Location
```

### 8.4 Hard Boundaries cần kiểm tra

| Kịch bản | Input | `execution_mode_applied` kỳ vọng | `status` kỳ vọng |
|---|---|---|---|
| Môi trường prod + apply | `environment=prod`, `execution_mode=apply` | `dry-run` | `dry-run` |
| Low confidence | `data_confidence=LOW`, `execution_mode=apply` | `dry-run` | `dry-run` |
| Approval denied | `approval_status=denied` | `denied` | `denied` |
| Sandbox apply (đã duyệt) | `environment=sandbox`, `approval_status=approved` | `apply` | `completed` |
| Prod tag (được phép) | `environment=prod`, `execution_mode=tag` | `tag` | `completed` |

### 8.5 Xác minh S3 và DynamoDB Audit sau khi chạy thật (Sandbox)

Sau khi invoke Lambda trên môi trường sandbox bằng test events từ
`containment-lambda/test-events/`:

```bash
aws lambda invoke \
  --function-name tf2-finops-sandbox-containment_worker \
  --payload file://containment-lambda/test-events/01_dry_run_sandbox.json \
  --cli-binary-format raw-in-base64-out \
  output.json && cat output.json
```

**S3 Audit** — phải có hai file (pre-action + post-action):
```
s3://company-cdo-{account_id}-telemetry/audit/year=YYYY/month=MM/{audit_id}.json
s3://company-cdo-{account_id}-telemetry/audit/year=YYYY/month=MM/{audit_id}_post.json
```

**DynamoDB Dashboard Cache** — một item cho mỗi anomaly:
```
Table : finops-dashboard-cache-{env}
Key   : anomaly_id = "<anomaly_id từ event>"
Fields: status, execution_mode_applied, audit_record_s3_uri
```

**DynamoDB Rollback Cache** — được cache trước khi thực thi action:
```
Table : finops-rollback-cache
Key   : anomaly_id = "<anomaly_id từ event>"
Fields: boto3_equivalent, ttl_epoch (TTL 90 ngày)
```

> **Lưu ý (kịch bản Denied):** Khi `approval_status=denied` Lambda trả về ngay lập tức.
> Không có gì được ghi vào S3 hay DynamoDB — đây là hành vi đúng và mong đợi.

---

## 9. Bảo trì tài liệu hướng dẫn
Tài liệu hướng dẫn dành cho nhà phát triển này phải luôn được cập nhật. Các agent và người đóng góp trong tương lai phải cập nhật cả `docs/GUIDES.md` và `docs/GUIDES_vi.md` trong cùng một thay đổi bất kỳ khi nào có quy trình làm việc của developer/operator, chuỗi lệnh, quy trình xác thực (validation path), script, CI job, bước triển khai (deployment step) hoặc thủ tục bàn giao (handoff procedure) mới được thêm vào hoặc thay đổi.

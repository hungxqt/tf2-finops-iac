# Hướng dẫn dành cho Nhà phát triển TF2 FinOps IaC

Tài liệu này trình bày chi tiết quy trình làm việc từng bước dành cho các nhà phát triển và vận hành hệ thống làm việc với kho lưu trữ Infrastructure as Code (IaC) **Task Force 2 - FinOps Watch**.

---

## 1. Yêu cầu hệ thống
Hãy đảm bảo bạn đã cài đặt và cấu hình đầy đủ các công cụ sau:
* **Terraform** (>= 1.10)
* **AWS CLI** (được cấu hình với quyền Administrator cho AWS Account đích)
* **Python** (>= 3.13) & `pip` (để chạy các thử nghiệm worker cục bộ)
* **PowerShell** (để chạy script đóng gói trên môi trường Windows)

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

### Bước 3.1: Triển khai Dashboard & Bàn giao Tài nguyên (Asset Handoff)
Sau khi mã nguồn Terraform được áp dụng (apply), hạ tầng Dashboard đã sẵn sàng. Quy trình bàn giao tuân theo các quy tắc sau:
1. **Vai trò của Terraform**: Terraform chỉ khởi tạo các tài nguyên AWS nền tảng (S3 buckets, CloudFront distribution, Cognito Identity & User Pools, các Athena named queries và vai trò IAM truy cập dữ liệu).
2. **Tải lên Tài nguyên Static (Asset Upload)**: Các tài nguyên static của frontend (ứng dụng giao diện UI) phải được tải lên riêng biệt vào S3 bucket chứa static assets (được cấu hình trong giá trị đầu ra `dashboard_asset_bucket_name`).
3. **Quản trị Cognito**: Các tài khoản người dùng, nhóm (groups) và mật khẩu thật trong Cognito phải được quản trị trực tiếp trên AWS Console hoặc qua Cognito API/CLI bên ngoài Terraform.
4. **Sinh dữ liệu (Data Generation)**: Các công cụ ghi/tóm hợp dữ liệu chi phí (ví dụ: Lambda hoặc các batch jobs) phải tải các tệp tóm tắt JSON lên tiền tố đã cấu hình (ví dụ: `summaries/`) trong S3 bucket chứa dữ liệu dashboard (được cấu hình trong giá trị đầu ra `dashboard_data_bucket_name`).

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
checkov -d modules/orchestration --framework terraform
```

---

## 5. Bảo trì tài liệu hướng dẫn
Tài liệu hướng dẫn dành cho nhà phát triển này phải luôn được cập nhật. Các agent và người đóng góp trong tương lai phải cập nhật cả `docs/GUIDES.md` và `docs/GUIDES_vi.md` trong cùng một thay đổi bất kỳ khi nào có quy trình làm việc của developer/operator, chuỗi lệnh, quy trình xác thực (validation path), script, CI job, bước triển khai (deployment step) hoặc thủ tục bàn giao (handoff procedure) mới được thêm vào hoặc thay đổi.


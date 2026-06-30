# HÆ°á»›ng dáº«n dÃ nh cho NhÃ  phÃ¡t triá»ƒn TF2 FinOps IaC

TÃ i liá»‡u nÃ y trÃ¬nh bÃ y chi tiáº¿t quy trÃ¬nh lÃ m viá»‡c tá»«ng bÆ°á»›c dÃ nh cho cÃ¡c nhÃ  phÃ¡t triá»ƒn vÃ  váº­n hÃ nh há»‡ thá»‘ng lÃ m viá»‡c vá»›i kho lÆ°u trá»¯ Infrastructure as Code (IaC) **Task Force 2 - FinOps Watch**.

---

## 1. YÃªu cáº§u há»‡ thá»‘ng
HÃ£y Ä‘áº£m báº£o báº¡n Ä‘Ã£ cÃ i Ä‘áº·t vÃ  cáº¥u hÃ¬nh Ä‘áº§y Ä‘á»§ cÃ¡c cÃ´ng cá»¥ sau:
* **Terraform** (>= 1.10)
* **AWS CLI** (Ä‘Æ°á»£c cáº¥u hÃ¬nh vá»›i quyá»n Administrator cho AWS Account Ä‘Ã­ch)
* **Python** (>= 3.13) & `pip` (Ä‘á»ƒ cháº¡y cÃ¡c thá»­ nghiá»‡m worker cá»¥c bá»™)
* **PowerShell** (Ä‘á»ƒ cháº¡y script Ä‘Ã³ng gÃ³i trÃªn mÃ´i trÆ°á»ng Windows)

### 1.1 Äiá»u kiá»‡n tiÃªn quyáº¿t Ä‘á»‘i vá»›i Thu tháº­p sá»‘ liá»‡u liÃªn tÃ i khoáº£n (TÃ¹y chá»n)
Náº¿u triá»ƒn khai cá»§a báº¡n liÃªn quan Ä‘áº¿n viá»‡c thu tháº­p sá»‘ liá»‡u chi phÃ­ vÃ  sá»­ dá»¥ng (telemetry) tá»« cÃ¡c tÃ i khoáº£n thÃ nh viÃªn AWS (member accounts) riÃªng biá»‡t:
1. **Cáº¥u hÃ¬nh táº¡i TÃ i khoáº£n Payer/CDO**:
   - Thiáº¿t láº­p biáº¿n Ä‘áº§u vÃ o `telemetry_member_account_ids` lÃ  danh sÃ¡ch cÃ¡c ID cá»§a tÃ i khoáº£n thÃ nh viÃªn.
   - Cáº¥u hÃ¬nh bucket vÃ  tiá»n tá»‘ CUR nguá»“n báº±ng cÃ¡ch sá»­ dá»¥ng `cur_source_bucket_arn` vÃ  `cur_source_prefix` trong cÃ¡c tham sá»‘ cá»§a module `iam`.
2. **Cáº¥u hÃ¬nh Vai trÃ² (Role) táº¡i TÃ i khoáº£n ThÃ nh viÃªn**:
   - Má»—i tÃ i khoáº£n thÃ nh viÃªn pháº£i triá»ƒn khai vai trÃ² IAM thu tháº­p dá»¯ liá»‡u (`cdo-telemetry-ingestion-role`).
   - ChÃ­nh sÃ¡ch á»§y thÃ¡c (trust policy) cá»§a vai trÃ² nÃ y pháº£i cho phÃ©p ARN cá»§a vai trÃ² IAM CDO cost-puller tá»« tÃ i khoáº£n Payer/CDO giáº£ Ä‘á»‹nh (assume role).
   - ChÃ­nh sÃ¡ch phÃ¢n quyá»n cá»§a vai trÃ² pháº£i cáº¥p quyá»n Ä‘á»c (`s3:ListBucket`, `s3:GetObject`) Ä‘á»‘i vá»›i bucket/tiá»n tá»‘ CUR cá»¥c bá»™, vÃ  cho phÃ©p truy váº¥n Cost Explorer (`ce:GetCostAndUsage`) vÃ  sá»‘ liá»‡u CloudWatch (`cloudwatch:GetMetricData`).

---

## 2. Quy trÃ¬nh triá»ƒn khai tá»«ng bÆ°á»›c

### BÆ°á»›c 2.1: Cháº¡y cÃ¡c kiá»ƒm tra cá»¥c bá»™ (Unit Tests)
XÃ¡c minh ráº±ng cÃ¡c hÃ m adapter tuÃ¢n thá»§ Ä‘Ãºng há»£p Ä‘á»“ng báº±ng cÃ¡ch cháº¡y bá»™ kiá»ƒm tra Python pytest:
```powershell
cd lambda_src
pip install -r requirements-dev.txt
python -m pytest
cd ..
```

### BÆ°á»›c 2.2: Khá»Ÿi táº¡o Backend State vÃ  vai trÃ² OIDC
Quy trÃ¬nh bootstrap giÃºp thiáº¿t láº­p xÃ¡c thá»±c khÃ´ng cáº§n khÃ³a (OIDC) qua GitHub vÃ  táº¡o S3 bucket lÆ°u trá»¯ state tá»« xa má»™t cÃ¡ch báº£o máº­t.

#### Lá»±a chá»n A: Thiáº¿t láº­p ban Ä‘áº§u / Triá»ƒn khai Bootstrap láº§n Ä‘áº§u (Thá»±c hiá»‡n má»™t láº§n duy nháº¥t)
Náº¿u Ä‘Ã¢y lÃ  láº§n Ä‘áº§u tiÃªn thiáº¿t láº­p dá»± Ã¡n vÃ  S3 backend chÆ°a Ä‘Æ°á»£c kÃ­ch hoáº¡t:
1. **Triá»ƒn khai bootstrap cá»¥c bá»™**:
   Äáº£m báº£o ráº±ng khá»‘i `backend "s3"` trong [bootstrap/backend.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/backend.tf) Ä‘Ã£ Ä‘Æ°á»£c chÃº thÃ­ch (comment out), sau Ä‘Ã³ cháº¡y:
   ```powershell
   cd bootstrap
   terraform init
   terraform apply
   ```
2. **Di chuyá»ƒn State lÃªn S3**:
   - Sao chÃ©p ARN cá»§a KMS Key dÃ¹ng cho state Ä‘Æ°á»£c xuáº¥t ra tá»« terminal.
   - Má»Ÿ tá»‡p [bootstrap/backend.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/backend.tf), bá» chÃº thÃ­ch khá»‘i cáº¥u hÃ¬nh `terraform` backend vÃ  thay tháº¿ giÃ¡ trá»‹ `kms_key_id` báº±ng ARN cá»§a báº¡n:
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
   - Thá»±c hiá»‡n lá»‡nh di chuyá»ƒn tráº¡ng thÃ¡i (migrate state) lÃªn S3 bucket tá»« xa:
     ```powershell
     terraform init -migrate-state
     ```

#### Lá»±a chá» n B: DÃ nh cho cÃ¡c thÃ nh viÃªn khÃ¡c tiáº¿p tá»¥c lÃ m viá»‡c (Subsequent Developers)
Náº¿u bootstrap Ä‘Ã£ Ä‘Æ°á»£c cháº¡y trÆ°á»›c Ä‘Ã³ vÃ  cáº¥u hÃ¬nh S3 backend Ä‘Ã£ Ä‘Æ°á»£c kÃ­ch hoáº¡t trong kho lÆ°u trá»¯:
1. **Khá»Ÿi táº¡o Backend**:
   Khá»Ÿi táº¡o trá»±c tiáº¿p Terraform. Terraform sáº½ tá»± Ä‘á»™ng nháº­n diá»‡n khá»‘i cáº¥u hÃ¬nh S3 backend Ä‘ang hoáº¡t Ä‘á»™ng trong [bootstrap/backend.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/backend.tf) vÃ  káº¿t ná»‘i tá»›i remote state hiá»‡n cÃ³:
   ```powershell
   cd bootstrap
   terraform init
   ```
   *LÆ°u Ã½: CÃ¡c thÃ nh viÃªn khÃ¡c khÃ´ng cáº§n cháº¡y `apply` hoáº·c `migrate-state` trong thÆ° má»¥c bootstrap trá»« khi cáº§n thá»±c hiá»‡n thay Ä‘á»•i Ä‘á»‘i vá»›i chÃ­nh háº¡ táº§ng bootstrap.*

### BÆ°á»›c 2.3: Ä Ã³ng gÃ³i cÃ¡c hÃ m Lambda dÆ°á»›i dáº¡ng tá»‡p Zip
Ä Ã³ng gÃ³i 7 hÃ m adapter Python vÃ o thÆ° má»¥c `.build/lambda/`:
```powershell
cd ..
.\scripts\package-lambdas.ps1
```

### Bước 2.4: Triển khai Layer Publishing CodeBuild
Thư mục gốc `codebuild` sở hữu ECR repository chung và pipeline xuất bản image wrapper CodeBuild. Áp dụng root này trước khi triển khai các môi trường chính.
```powershell
cd codebuild
terraform init
terraform apply
```

### Bước 2.5: Xây dựng Image Wrapper Lambda Web Adapter
Kích hoạt thủ công dự án CodeBuild với một digest AIOps thượng nguồn hợp lệ:
```powershell
aws codebuild start-build   --project-name tf2-finops-ai-wrapper-build   --environment-variables-override name=UPSTREAM_IMAGE_URI,value=200000000012.dkr.ecr.ap-southeast-1.amazonaws.com/tf2/finops-ai-engine@sha256:456c2438cb20d88047915518b209d88047915518b209d88047915518b209d880,type=PLAINTEXT
```

### Bước 2.6: Đọc URI Image Wrapper Đã Triển Khai
Đọc URI image được ghim bằng digest mới nhất từ SSM Parameter Store:
```powershell
aws ssm get-parameter --name "/tf2-finops/shared/ai-wrapper/latest-image-uri" --query "Parameter.Value" --output text
```

### Bước 2.7: Triển khai các Môi trường (Environment Compositions)
Triển khai các môi trường theo tuần tự (Sandbox trước, sau đó là Staging và Prod).

#### Thiết lập Backend và Biến cho Môi trường:
* **Kết nối Remote State**: Khối cấu hình remote state backend đã được thiết lập sẵn trong tệp `backend.tf` của mỗi môi trường (`sandbox/terraform.tfstate`, `staging/terraform.tfstate`, `prod/terraform.tfstate`). Bạn chỉ cần chạy lệnh `terraform init` để tự động kết nối với S3 remote state chung.
* **Cấu hình Biến (Variables)**: Trước khi lập kế hoạch (plan) hoặc áp dụng (apply), bạn phải sao chép tệp `terraform.tfvars.example` trong thư mục môi trường thành tệp `terraform.tfvars` cục bộ (tệp này được bỏ qua bởi git) và cập nhật các giá trị. Bạn BẮT BUỘC phải đặt `request_image_uri` bằng URI của image wrapper đã lấy được từ SSM Parameter Store ở Bước 2.6.
* **Cơ chế kích hoạt EventBridge Scheduler (Activation Guard)**: Theo mặc định, lịch trình chạy hàng ngày của EventBridge Scheduler sẽ bị vô hiệu hóa (`scheduler_enabled = false`) để tránh tự động thực thi Step Functions ngay sau khi áp dụng hạ tầng ban đầu. Xác nhận rằng outputs hiển thị `scheduler_state = "DISABLED"`. Việc kích hoạt lịch trình chạy hàng ngày yêu cầu một bản thay đổi kế hoạch riêng biệt được phê duyệt với `scheduler_enabled = true`.

1. **Triển khai Sandbox**:
   ```powershell
   cd ../environments/sandbox
   # Sao chép tệp biến mẫu và cập nhật giá trị
   cp terraform.tfvars.example terraform.tfvars
   # Khởi tạo và kết nối tới remote state
   terraform init
   # Lập kế hoạch và áp dụng
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

### BÆ°á»›c 2.5: Cháº©n Ä‘oÃ¡n tráº¡ng thÃ¡i Lambda sau khi triá»ƒn khai
CÃ¡c hÃ m Lambda Ä‘Æ°á»£c gáº¯n VPC (cáº£ worker dáº¡ng zip vÃ  AI runtime dáº¡ng container) yÃªu cáº§u AWS khá»Ÿi táº¡o cÃ¡c Hyperplane ENI vÃ  tá»‘i Æ°u hÃ³a container image á»Ÿ cháº¿ Ä‘á»™ báº¥t Ä‘á»“ng bá»™. QuÃ¡ trÃ¬nh nÃ y diá»…n ra sau khi Terraform apply hoÃ n thÃ nh vÃ  cÃ³ thá»ƒ máº¥t vÃ i phÃºt.

Cháº¡y vÃ²ng láº·p lá»‡nh AWS CLI sau Ä‘á»ƒ kiá»ƒm tra tráº¡ng thÃ¡i cá»§a táº¥t cáº£ 9 hÃ m Lambda:

DÃ nh cho PowerShell (Windows):
```powershell
$workers = "state", "cost_puller", "normalizer", "router", "audit_writer", "containment_worker", "vpc_alb_caller", "ai-request", "ai-worker"
foreach ($w in $workers) {
    aws lambda get-function --function-name "tf2-finops-sandbox-$w" --query "Configuration.[FunctionName, State, StateReason, LastUpdateStatus]" --output json
}
```

DÃ nh cho Bash (macOS/Linux):
```bash
for fn in state cost_puller normalizer router audit_writer containment_worker vpc_alb_caller ai-request ai-worker; do
  aws lambda get-function --function-name tf2-finops-sandbox-$fn --query "Configuration.[FunctionName, State, StateReason, LastUpdateStatus]" --output table
done
```

**TiÃªu chÃ­ xÃ¡c minh:**
* **State**: Cuá»‘i cÃ¹ng sáº½ chuyá»ƒn sang `Active`. (Náº¿u hiá»ƒn thá»‹ `Pending`, hÃ£y Ä‘á»£i 1-2 phÃºt Ä‘á»ƒ AWS hoÃ n táº¥t quÃ¡ trÃ¬nh thiáº¿t láº­p ENI/Image).
* **StateReason**: Pháº£i trá»‘ng hoáº·c null. Náº¿u cÃ³ thÃ´ng tin lá»—i liÃªn quan Ä‘áº¿n thiáº¿t láº­p ENI hoáº·c thiáº¿u quyá»n, hÃ£y kiá»ƒm tra láº¡i cáº¥u hÃ¬nh IAM Roles vÃ  Security Groups.
* **LastUpdateStatus**: Cuá»‘i cÃ¹ng sáº½ lÃ  `Successful`.

### 2.4. Há»§y / Giáº£i phÃ³ng mÃ´i trÆ°á»ng Sandbox (Teardown / Destroy Sandbox)

Äá»ƒ há»§y bá» mÃ´i trÆ°á»ng sandbox nháº±m dá»n dáº¹p hoáº·c kiá»ƒm tra quy trÃ¬nh giáº£i phÃ³ng tÃ i nguyÃªn:
1. Táº¡o káº¿ hoáº¡ch há»§y tÃ i nguyÃªn:
   ```powershell
   cd environments/sandbox
   terraform plan -destroy -out=sandbox-destroy.tfplan
   ```
2. Xem xÃ©t ká»¹ káº¿ hoáº¡ch há»§y Ä‘Ã£ táº¡o Ä‘á»ƒ Ä‘áº£m báº£o cÃ¡c tÃ i nguyÃªn bá»‹ há»§y lÃ  chÃ­nh xÃ¡c.
3. Ãp dá»¥ng káº¿ hoáº¡ch há»§y:
   ```powershell
   terraform apply sandbox-destroy.tfplan
   ```

> [!WARNING]
> **Giá»›i háº¡n ká»¹ thuáº­t cá»§a AWS Object Lock**:
> Náº¿u bucket audit sandbox Ä‘Ã£ chá»©a cÃ¡c phiÃªn báº£n Ä‘á»‘i tÆ°á»£ng Ä‘Æ°á»£c giá»¯ láº¡i theo cháº¿ Ä‘á»™ TuÃ¢n thá»§ (Compliance-mode), AWS sáº½ Ã¡p dá»¥ng má»™t háº¡n cháº¿ cá»©ng ngÄƒn viá»‡c xÃ³a cÃ¡c Ä‘á»‘i tÆ°á»£ng nÃ y cho Ä‘áº¿n khi thá»i háº¡n lÆ°u trá»¯ háº¿t háº¡n. Trong trÆ°á»ng há»£p Ä‘Ã³, Terraform sáº½ tháº¥t báº¡i khi xÃ³a bucket audit. Máº·c dÃ¹ Object Lock cháº¿ Ä‘á»™ TuÃ¢n thá»§ Ä‘Ã£ Ä‘Æ°á»£c táº¯t cho cÃ¡c bucket audit sandbox *má»›i táº¡o* Ä‘á»ƒ cho phÃ©p dá»n dáº¹p, nhÆ°ng náº¿u Object Lock Ä‘Ã£ Ä‘Æ°á»£c cáº¥u hÃ¬nh trÆ°á»›c Ä‘Ã³ vÃ  cÃ³ dá»¯ liá»‡u, cÃ¡c Ä‘á»‘i tÆ°á»£ng nÃ y pháº£i háº¿t háº¡n trÆ°á»›c khi cÃ³ thá»ƒ dá»n dáº¹p hoÃ n toÃ n.
>
> **Äá»™ trá»… khi giáº£i phÃ³ng ENI VPC Lambda**:
> Khi há»§y mÃ´i trÆ°á»ng Lambda Ä‘Æ°á»£c gáº¯n VPC, AWS Lambda sáº½ giá»¯ cÃ¡c cá»•ng máº¡ng Hyperplane ENI trong bá»™ nhá»› cache tá»‘i Ä‘a 20 phÃºt sau khi cÃ¡c hÃ m Lambda Ä‘Ã£ bá»‹ xÃ³a. Trong thá»i gian chá» nÃ y, Terraform sáº½ hiá»ƒn thá»‹ thÃ´ng bÃ¡o `Still destroying...` vÃ  cÃ³ thá»ƒ bá»‹ treo á»Ÿ bÆ°á»›c xÃ³a cÃ¡c private subnets cÅ©ng nhÆ° Lambda security group vÃ¬ chÃºng váº«n Ä‘ang liÃªn káº¿t vá»›i cÃ¡c ENI nÃ y. ÄÃ¢y lÃ  hÃ nh vi kiá»ƒm soÃ¡t bÃ¬nh thÆ°á»ng cá»§a AWS. Vui lÃ²ng khÃ´ng ngáº¯t lá»‡nh; khi AWS tá»± Ä‘á»™ng giáº£i phÃ³ng cÃ¡c ENI (thÆ°á»ng trong vÃ²ng 10 Ä‘áº¿n 15 phÃºt), cÃ¡c subnet vÃ  security group sáº½ Ä‘Æ°á»£c xÃ³a thÃ nh cÃ´ng vÃ  quÃ¡ trÃ¬nh há»§y tÃ i nguyÃªn sáº½ hoÃ n táº¥t.

CÃ¡c mÃ´i trÆ°á»ng Staging vÃ  Production Ä‘Æ°á»£c báº£o vá»‡ nghiÃªm ngáº·t báº±ng tÃ i nguyÃªn tuáº§n tra `destroy_guard` (terraform_data) vÃ  khÃ´ng thá»ƒ bá»‹ xÃ³a thÃ´ng qua káº¿ hoáº¡ch há»§y thÃ´ng thÆ°á»ng.

---

## 3. BÃ n giao sau khi triá»ƒn khai cho GitOps (`tf2-finops-gitops`)
Sau khi quÃ¡ trÃ¬nh deploy hoÃ n táº¥t, hÃ£y láº¥y cÃ¡c dá»¯ liá»‡u Ä‘áº§u ra Ä‘á»ƒ cáº¥u hÃ¬nh cho táº§ng á»©ng dá»¥ng (Workload Layer) trong kho lÆ°u trá»¯ `tf2-finops-gitops`:
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
1. **Vai trò của Terraform**: Terraform khởi tạo các tài nguyên AWS nền tảng (S3 buckets, CloudFront distribution không bao gồm cấu hình VPC Origin/origin Lambda@Edge, Cognito Identity & User Pools, các Athena named queries và vai trò IAM).
2. **Cổng Xác thực (Authenticated Front Door)**: Tất cả tài nguyên tĩnh và tệp tóm tắt JSON (dưới `/${dashboard_data_prefix}*`) được phục vụ qua CloudFront và bảo vệ bởi hàm Lambda@Edge viewer-request sử dụng xác thực Cognito PKCE.
3. **Không định tuyến API trực tiếp (Đã tắt)**: Việc định tuyến proxy API `/v1/*` trực tiếp qua CloudFront đã bị tắt do AWS không hỗ trợ liên kết các hàm Lambda@Edge origin-request với các phân phối CloudFront sử dụng VPC Origin. Các truy vấn AI trực tiếp và hành động ngăn chặn (containment) tiếp tục chạy an toàn qua tích hợp `VpcAlbCallerLambda`.
4. **Tải lên Tài nguyên Static (Asset Upload)**: Các tài nguyên static của frontend (ứng dụng giao diện UI) phải được tải lên riêng biệt vào S3 bucket chứa static assets (được cấu hình trong giá trị đầu ra `dashboard_asset_bucket_name`).
5. **Nhóm Cognito (Cognito Groups)**: Người dùng cần được thêm vào các nhóm Cognito tương ứng (`finops-finance-readonly`, `finops-engineering-operator`, `finops-cdo-admin`) để kiểm soát quyền hạn.
6. **Sinh dữ liệu (Data Generation)**: Các công cụ ghi dữ liệu chi phí phải tải các tệp tóm tắt JSON lên tiền tố đã cấu hình (ví dụ: `summaries/`) trong S3 bucket chứa dữ liệu dashboard (được cấu hình trong giá trị đầu ra `dashboard_data_bucket_name`).


### Bước 3.2: Khởi tạo dữ liệu bảng DynamoDB Account Policy (Account Policy Seeding)
Trước khi chạy hoặc kích hoạt quy trình Orchestrator Step Functions (chạy thủ công hoặc thông qua trình lập lịch EventBridge), bạn phải khởi tạo dữ liệu (seed) cho bảng DynamoDB `account-policy` của môi trường.
Với tính năng hỗ trợ nhiều tài khoản phân tích mục tiêu (analysis targets), orchestrator sẽ chạy trên tài khoản quản trị (management/CDO account) nhưng phân nhánh và chạy song song trên các tài khoản liên kết (linked member accounts) được chỉ định trong `analysis_target_account_ids` (được cấu hình qua `telemetry_member_account_ids` ở gốc môi trường).
Do đó, bạn phải seed một dòng dữ liệu cho mỗi AWS Account ID của tài khoản liên kết đích được phân tích, chứ không chỉ cho tài khoản quản trị thực thi.
Xem tài liệu hướng dẫn chi tiết [ACCOUNT_POLICY_SEEDING_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/ACCOUNT_POLICY_SEEDING_vi.md) để biết thêm thông tin cấu trúc item, chuỗi lệnh PowerShell và cách khắc phục sự cố xác minh.

### Bước 3.3: Hướng dẫn Vận hành Chạy Thủ công Step Functions (Manual Step Functions Execution Runbook)
Khi cấu hình `scheduler_enabled = false`, hoặc khi cần thực hiện các lượt chạy kiểm thử (ad-hoc) và xác minh, quy trình Orchestrator Step Functions có thể được kích hoạt thủ công.
Xem tài liệu hướng dẫn vận hành chi tiết tại [MANUAL_STEP_FUNCTIONS_EXECUTION_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/MANUAL_STEP_FUNCTIONS_EXECUTION_vi.md) để nắm rõ các điều kiện tiên quyết, định dạng payload đầu vào (cho cả chạy đơn tài khoản và đa tài khoản), chuỗi lệnh PowerShell thực thi và cách theo dõi trạng thái lượt chạy.


---

## 4. Kiá»ƒm tra tÃ­ch há»£p liÃªn tá»¥c vÃ  xÃ¡c thá»±c mÃ£ nguá»“n (CI/CD)
TrÆ°á»›c khi commit vÃ  push mÃ£ nguá»“n, hÃ£y cháº¡y toÃ n bá»™ cÃ¡c lá»‡nh kiá»ƒm tra lá»—i cá»¥c bá»™ sau:
```powershell
# Äá»‹nh dáº¡ng mÃ£ nguá»“n
terraform fmt -check -recursive

# XÃ¡c thá»±c cáº¥u hÃ¬nh cÃº phÃ¡p
terraform -chdir=bootstrap validate
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod validate

# QuÃ©t phÃ¢n tÃ­ch báº£o máº­t tÄ©nh
trivy config .
checkov -d . --framework terraform
```

---

## 5. XÃ¡c thá»±c Glue Schema & Partition Projection

Äá»ƒ há»— trá»£ truy váº¥n tá»± Ä‘á»™ng vÃ  tá»‘i Æ°u chi phÃ­ mÃ  khÃ´ng cáº§n duy trÃ¬ cÃ¡c crawler tiÃªu tá»‘n tÃ i nguyÃªn hoáº·c láº­p lá»‹ch cÃ¡c truy váº¥n sá»­a chá»¯a phÃ¢n vÃ¹ng thá»§ cÃ´ng (MSCK REPAIR), lakehouse sá»­ dá»¥ng tÃ­nh nÄƒng Athena Partition Projection.

### BÆ°á»›c 5.1: XÃ¡c thá»±c cáº¥u hÃ¬nh báº£ng Glue trong Terraform
Cháº¡y cÃ¡c kiá»ƒm thá»­ táº­p trung cho module Ä‘á»ƒ kiá»ƒm tra cÃ¡c khÃ³a phÃ¢n vÃ¹ng, Ä‘á»‹nh dáº¡ng Ä‘áº§u vÃ o/Ä‘áº§u ra vÃ  cáº¥u hÃ¬nh báº£ng tÄ©nh:
```powershell
cd modules/lakehouse
terraform init
terraform test
cd ../..
```

### BÆ°á»›c 5.2: Kiá»ƒm tra DDL Athena khá»›p vá»›i Schema
Äá»ƒ kiá»ƒm tra, gá»¡ lá»—i hoáº·c táº¡o thá»§ cÃ´ng cÃ¡c báº£ng Parquet `cur_data` vÃ  JSON `containment_audit`, xem file script xÃ¡c thá»±c:
* [scripts/athena_validation.sql](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/scripts/athena_validation.sql)

Äáº£m báº£o pháº¡m vi projection cá»§a báº£ng (vÃ­ dá»¥: `2024,2035`), Ä‘á»‹nh dáº¡ng vÃ  Ä‘Æ°á»ng dáº«n phÃ¢n vÃ¹ng S3 khá»›p chÃ­nh xÃ¡c vá»›i Ä‘Æ°á»ng dáº«n Ä‘áº§u ra cá»§a worker.

---

## 7. Cáº¥u hÃ¬nh vÃ  XÃ¡c thá»±c Thu tháº­p Dá»¯ liá»‡u Telemetry

Worker `cost_puller` Ä‘áº£m nháº­n viá»‡c thu tháº­p dá»¯ liá»‡u chi phÃ­ (billing) vÃ  hiá»‡u nÄƒng (utilization) thÃ´. NÃ³ hoáº¡t Ä‘á»™ng á»Ÿ cháº¿ Ä‘á»™ thu tháº­p há»—n há»£p (hybrid ingestion), Ä‘á»c cÃ¡c tá»‡p CUR tá»« S3 source bucket hoáº·c tá»± Ä‘á»™ng chuyá»ƒn sang Cost Explorer khi CUR bá»‹ trá»….

### Bước 7.1: Các tham số cấu hình
Hành vi thu thập dữ liệu được kiểm soát bởi các biến Terraform được truyền vào các module `compute_lambda`, `lakehouse`, và `iam`:
* `cur_source_bucket` / `cur_source_bucket_arn`: Bucket S3 nơi AWS CUR được lưu trữ.
* `cur_raw_prefix` / `cur_source_prefix`: S3 prefix dưới CUR export bucket nơi AWS Data Exports ghi dữ liệu raw CUR 2.0 Parquet.
* `cur_export_name`: Tên của AWS Data Exports (ví dụ: mặc định là `accountCUR`) dùng để tạo đường dẫn account thành viên một cách xác định.
* `telemetry_member_account_ids`: Danh sách các ID tài khoản thành viên để CDO lấy telemetry. Theo mặc định, `CUR_EXPORTS_JSON` được tạo động từ danh sách này dưới dạng: `account_id -> { source_account_id=account_id, prefix=account_id, export_name=cur_export_name, allowed_raw_prefix="${account_id}/${cur_export_name}" }`.
* `cur_exports_json`: Một chuỗi JSON cấu hình ghi đè thủ công cho CUR 2.0. Nếu được thiết lập rõ ràng, nó sẽ ghi đè cấu hình được tạo tự động từ `telemetry_member_account_ids` và `cur_export_name`. Chỉ dùng cho mục đích nâng cao hoặc cấu hình tường minh.
* `cur_delay_threshold_hours`: Ngưỡng thời gian trễ (tính bằng giờ) trước khi chuyển sang chế độ dự phòng CE (mặc định: `36`).
* `ce_lookback_window_days`: Số ngày lịch sử CE cần lấy khi chạy dự phòng (mặc định: `30`).
* `traffic_metric_identifiers`: Định danh dùng để truy vấn dữ liệu traffic vật lý (ví dụ: tên ALB).

Không còn cơ chế tự động tạo telemetry dự phòng. `cost_puller` yêu cầu cấu hình lakehouse bucket và CUR source bucket cho luồng thu thập thông thường. Nếu CUR bị trễ và Cost Explorer không trả về bản ghi, hoặc cache telemetry không có sẵn khi CE bị throttling, worker trả về `CUR_DELAY` hoặc `CE_THROTTLED` và workflow phải giữ chế độ dry-run/alert-only.

### Bước 7.2: Xác minh và Giả lập
Người vận hành có thể xác minh luồng retry/wait và xử lý lỗi của State Machine thông qua các hành động giả lập (simulation actions) trong event thực thi:
* **Giả lập CUR bị trễ**: Gửi `"action": "simulate-cur-delay"` để ép trạng thái trễ CUR và kích hoạt luồng dự phòng Cost Explorer. Worker vẫn cần bản ghi Cost Explorer thật hoặc telemetry cache để tiếp tục.
* **Giả lập CE bị throttling**: Gửi `"action": "simulate-ce-throttled"` để kích hoạt lỗi rate limit cho CE. Nếu có dữ liệu cache trong destination bucket, hệ thống sẽ khôi phục dữ liệu từ cache và đặt cờ chất lượng `stale_cost_explorer = true`; nếu không sẽ trả về lỗi `CE_THROTTLED`.

XÃ¡c minh cÃ¡c tá»‡p JSON gzipped Ä‘Æ°á»£c táº¡o ra báº±ng cÃ¡ch kiá»ƒm tra cÃ¡c Ä‘Æ°á»ng dáº«n prefix S3:
* Cost Telemetry chÃ­nh: `s3://<lakehouse-bucket>/cur/account_id=<id>/year=YYYY/month=MM/day=DD/<run-id>_raw.json.gz`
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


---

## 10. Xác Minh Quy Trình Step Functions

Bộ kiểm tra `test_step_function_payload_contract.py` cung cấp **lớp xác minh cục bộ, không cần AWS** chứng minh:

- ASL có đủ mọi state yêu cầu (kiểm tra 44+ state).
- Không có state polling phát hiện bất thường async lỗi thời, hàng đợi detection, hoặc tham chiếu SQS detection.
- Mọi state Task/Pass đều có thể giải quyết các tham chiếu JSONPath của mình dựa trên dữ liệu fixture thực tế từ đầu ra của state trước.
- Hợp đồng telemetry được tôn trọng (mặc định S3_POINTER, CE fallback, cổng chất lượng).
- Hình dạng lời gọi /v1/detect, /v1/decide, /v1/verify khớp với hợp đồng AI API đang hoạt động.
- Các chế độ containment prod+destructive bị từ chối; các đường dẫn bắt buộc dry-run bị từ chối.
- Chỉ có hàng đợi SQS `rollback_status_queue` tồn tại (không có hàng đợi detection).
- Chuỗi audit fail-closed và CUR-delay-exceeded mang đầy đủ các trường ngữ cảnh yêu cầu.

### 10.1 Chạy Chỉ Kiểm Tra Payload Contract

```powershell
Push-Location lambda_src
python -m pytest tests/test_step_function_payload_contract.py -v
Pop-Location
```

### 10.2 Chạy Tất Cả Kiểm Tra Xác Minh Step Functions

```powershell
Push-Location lambda_src
python -m pytest -q tests/test_step_function_payload_contract.py tests/test_state_machine.py tests/test_step_function_lambda_coverage.py tests/test_vpc_alb_caller.py
Pop-Location
```

### 10.3 Chạy Toàn Bộ Suite

```powershell
Push-Location lambda_src
python -m pytest
Pop-Location
```

Kết quả mong đợi: **tất cả kiểm tra đều vượt qua, không có lỗi**.

### 10.4 Tài Liệu Tham Khảo Fixture

Các fixture xác định có trong [`lambda_src/tests/fixtures/step_function_payloads.py`](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/fixtures/step_function_payloads.py).
Mỗi fixture là một dict Python thuần túy đại diện cho ngữ cảnh thực thi Step Functions (`$`) tại một ranh giới quy trình cụ thể.
Thêm một state mới hoặc thay đổi Parameters/ResultPath của một state hiện có yêu cầu cập nhật fixture tương ứng và thêm/cập nhật bài kiểm tra liên quan.

### 10.5 Bộ Giải Quyết JSONPath Nhẹ

Helper `_resolve_path(ctx, path)` trong file kiểm tra giải quyết:

| Biểu Thức | Ý Nghĩa |
|-----------|---------|
| `"$"` | Toàn bộ dict context |
| `"$.a.b.c"` | Duyệt key lồng nhau |
| `"$.anomalies_list[0].anomaly_id"` | Chỉ số mảng 0, sau đó key |

Điều này đủ cho tất cả `Parameters` (JSONPath `key.$`) và biểu thức biến `Choice` được sử dụng bởi state machine này, không cần runtime ASL đầy đủ.

---

## 11. Cổng Kiểm Tra Tính Toàn Vẹn Yêu Cầu AI

Script `scripts/test-ai-request-integrity.ps1` là một **cổng triển khai sau khi apply** xác nhận tính toàn vẹn yêu cầu của đường dẫn `VpcAlbCallerLambda` → ALB nội bộ riêng tư → AI Request Lambda trước khi thăng cấp container image sang môi trường tiếp theo.

### 11.1 Khi Nào Cần Chạy

Chạy cổng này **sau mỗi lần `terraform apply`** thay đổi bất kỳ điều nào sau đây:
- `modules/compute-lambda` (mã hàm vpc_alb_caller hoặc biến môi trường)
- `modules/ai-runtime-lambda` (image AI Request Lambda hoặc cấu hình ALB)
- `modules/iam` (vai trò thực thi vpc_alb_caller hoặc chính sách idempotency)
- Thăng cấp container image AI Engine từ sandbox → staging → prod

### 11.2 Cách Chạy

```powershell
# Sau khi apply sandbox (cổng tối thiểu trước khi thăng cấp lên staging)
.\scripts\test-ai-request-integrity.ps1 -Environment sandbox

# Sau khi apply staging (bắt buộc trước khi thăng cấp prod)
.\scripts\test-ai-request-integrity.ps1 -Environment staging

# Với tên hàm tùy chỉnh
.\scripts\test-ai-request-integrity.ps1 -Environment sandbox -LambdaFunctionName my-vpc-alb-caller
```

> [!IMPORTANT]
> Script yêu cầu AWS CLI được cấu hình với thông tin xác thực có thể gọi hàm Lambda mục tiêu.

### 11.3 Các Loại Probe và Tiêu Chí Chấp Nhận

Cổng chạy bốn probe. **Tất cả phải pass** để môi trường được coi là tuân thủ:

| # | Probe | Loại | Tiêu Chí Chấp Nhận |
|---|-------|------|---------------------|
| 1 | `POSITIVE_DETECT` | Dương tính | Lệnh gọi `/v1/detect` có ký phải thành công (không FunctionError, không 5xx) |
| 2 | `REPLAY_STALE_TS` | Âm tính | `X-Request-Timestamp` cũ phải fail closed (FunctionError hoặc 400 `ERR_REPLAY_DETECTED`) |
| 3 | `MISSING_AUTH` | Âm tính | Thiếu thông tin xác thực phải raise `ConfigMissingError` / `ERR_AUTH_FAILED` (fail-closed) |
| 4 | `HASH_MISMATCH` | Âm tính | `X-Payload-SHA256` không khớp phải fail closed (FunctionError hoặc 4xx `ERR_PAYLOAD_HASH`) |

> [!NOTE]
> **Ranh Giới ALB/SigV4**: ALB nội bộ riêng tư không tự thực thi SigV4 ở cấp listener. Tính toàn vẹn yêu cầu được thực thi ở cấp AI Request Lambda/container. Probe 2, 3 và 4 kiểm tra rằng AI Lambda từ chối đúng các yêu cầu không hợp lệ. Nếu image AI Engine không thể vượt qua các probe này, hãy chặn thăng cấp và ghi lại runtime là không tuân thủ.

### 11.4 Xử Lý Không Tuân Thủ

Nếu bất kỳ probe nào thất bại, script thoát với mã 1 và ghi kết quả JSON vào `docs/progress/request_integrity_gate_results_{environment}.json`.

**Không tuyên bố tuân thủ section-3 cho đến khi tất cả bốn probe pass.**

Khi image AI Engine không thể vượt qua các probe âm tính (vì container không thực thi xác thực replay/auth/hash), hãy ghi lại khoảng cách trong `docs/progress/request_integrity_progress.md` và thêm ghi chú ngoại lệ capstone rõ ràng. Không bỏ qua hoặc tắt cổng.

### 11.5 Tài Liệu Tham Khảo Kết Quả Cổng

Kết quả được ghi vào `docs/progress/request_integrity_gate_results_{environment}.json` sau mỗi lần chạy. File này bị git-ignore và chỉ dùng cho tham khảo vận hành cục bộ. Bước CI `terraform-apply.yml` nên gọi script này và thất bại job nếu mã thoát khác không.

---

## 12. Hướng dẫn Xuất bản Image Wrapper bằng CodeBuild

Repository này bao gồm một dự án CodeBuild để xây dựng và xuất bản container image wrapper cho AI Engine. Wrapper này sao chép AWS Lambda Web Adapter vào trong container FastAPI thượng nguồn của AIOps, cho phép nó chạy chính xác trên nền tảng AWS Lambda.

### 12.1 Quy trình Kích hoạt Thủ công

Build này phải được kích hoạt thủ công bởi vận hành viên. Vận hành viên phải cung cấp URI của image thượng nguồn được ghim bằng digest của nó. Các tag thay đổi (như `:latest`) sẽ bị từ chối để đảm bảo tính bất biến của image.

Để kích hoạt build bằng AWS CLI, chạy lệnh sau:

```bash
aws codebuild start-build \
  --project-name tf2-finops-ai-wrapper-build \
  --environment-variables-override name=UPSTREAM_IMAGE_URI,value=200000000012.dkr.ecr.ap-southeast-1.amazonaws.com/tf2/finops-ai-engine@sha256:456c2438cb20d88047915518b209d88047915518b209d88047915518b209d880,type=PLAINTEXT
```

*(Thay thế `sandbox` bằng `staging` hoặc `prod` tương ứng, và thay thế tên dự án cũng như digest thượng nguồn bằng các giá trị chính xác).*

### 12.2 Cơ chế Bỏ qua Xây dựng lại (Skip Rebuild)

Nếu tag image wrapper được tạo ra (`wrapped-<upstream-digest-short>`) đã tồn tại sẵn trong ECR repository đích, phiên chạy CodeBuild sẽ bỏ qua bước docker build và push, trả về digest hiện tại và cập nhật URI vào SSM Parameter Store.

### 12.3 Ghi nhận trên SSM Parameter Store

Sau khi chạy thành công, CodeBuild sẽ ghi các giá trị sau vào SSM Parameter Store:
- `/tf2-finops/<env>/ai-wrapper/latest-image-uri`: URI của image wrapper được ghim bằng digest.
- `/tf2-finops/<env>/ai-wrapper/latest-upstream-image-uri`: URI của image thượng nguồn gốc.

Các tham số này được sử dụng bởi vận hành viên trong quy trình triển khai Terraform được phê duyệt (Reviewed Terraform Deployment) để cập nhật biến `request_image_uri`.

---

## 13. Hướng dẫn Triển khai CodeDeploy Rollout cho AI Lambda trong Sandbox

Kho lưu trữ cấu hình việc chuyển dịch lưu lượng (traffic shifting) tuyến tính do CodeDeploy kiểm soát cho AI Engine Request Lambda trong `modules/ai-runtime-lambda`, ban đầu được cấu hình cho môi trường `sandbox`.

### 13.1 Cấu hình Rollout
- **Chiến lược Triển khai**: CodeDeploy chuyển dịch lưu lượng bằng cấu hình `CodeDeployDefault.LambdaLinear10PercentEvery1Minute`.
- **Vai trò Dịch vụ (Service Role)**: AWS CodeDeploy được gán một vai trò IAM được liên kết với policy quản lý `AWSCodeDeployRoleForLambda`.
- **Alias Đích**: Sử dụng Lambda alias `live`. Terraform được cấu hình để bỏ qua các thay đổi về phiên bản và cấu hình định tuyến trên alias này (`lifecycle { ignore_changes = [function_version, routing_config] }`), giao quyền kiểm soát hoàn toàn việc chuyển dịch lưu lượng cho CodeDeploy.

### 13.2 Các Cảnh báo Tự động Hoàn tác (Automated Rollback Alarms)
Nhóm triển khai (deployment group) được liên kết với bốn cảnh báo CloudWatch tự động để kích hoạt hoàn tác tự động nếu chúng phát cảnh báo trong quá trình triển khai:
1. **Lỗi Lambda (Lambda Errors)**: Báo động nếu chỉ số `Errors` > 0.
2. **Nghẽn Lambda (Lambda Throttles)**: Báo động nếu chỉ số `Throttles` > 0.
3. **Độ trễ P99 (P99 Duration)**: Báo động nếu thời gian thực thi P99 vượt quá 800 ms.
4. **Lỗi ALB Target 5xx**: Báo động nếu nhóm mục tiêu của ALB nội bộ gặp bất kỳ lỗi `HTTPCode_Target_5XX_Count` > 0.

Nếu bất kỳ cảnh báo nào trong số này được kích hoạt trong giai đoạn chuyển dịch lưu lượng, CodeDeploy sẽ tự động hoàn tác lưu lượng của alias `live` về phiên bản trước đó và đánh dấu đợt triển khai là thất bại.

### 13.3 Triển khai Thủ công hoặc qua Script CI
Để triển khai phiên bản image wrapper mới qua CodeDeploy:
1. Xây dựng và xuất bản image bằng CodeBuild để ghi digest vào SSM.
2. Chạy Terraform plan/apply với digest mới. Terraform sẽ xuất bản phiên bản Lambda mới nhưng vẫn giữ alias `live` trỏ tới phiên bản cũ.
3. Chạy script triển khai để kích hoạt và giám sát CodeDeploy:
   ```powershell
   ./scripts/start-ai-lambda-codedeploy.ps1 `
     -ApplicationName "finops-watch-sandbox-ai-request" `
     -DeploymentGroupName "finops-watch-sandbox-ai-request-dg" `
     -FunctionName "finops-watch-sandbox-ai-request" `
     -AliasName "live" `
     -TargetVersion "<new-published-version>"
   ```
4. Script sẽ thực hiện thăm dò cứ sau 15 giây, xuất ra trạng thái triển khai. Nếu CodeDeploy hoàn tác hoặc thất bại, script sẽ thoát với mã lỗi `1`, làm cho pipeline CI/CD thất bại.



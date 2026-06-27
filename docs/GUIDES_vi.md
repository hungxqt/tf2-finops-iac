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

#### Lá»±a chá»n B: DÃ nh cho cÃ¡c thÃ nh viÃªn khÃ¡c tiáº¿p tá»¥c lÃ m viá»‡c (Subsequent Developers)
Náº¿u bootstrap Ä‘Ã£ Ä‘Æ°á»£c cháº¡y trÆ°á»›c Ä‘Ã³ vÃ  cáº¥u hÃ¬nh S3 backend Ä‘Ã£ Ä‘Æ°á»£c kÃ­ch hoáº¡t trong kho lÆ°u trá»¯:
1. **Khá»Ÿi táº¡o Backend**:
   Khá»Ÿi táº¡o trá»±c tiáº¿p Terraform. Terraform sáº½ tá»± Ä‘á»™ng nháº­n diá»‡n khá»‘i cáº¥u hÃ¬nh S3 backend Ä‘ang hoáº¡t Ä‘á»™ng trong [bootstrap/backend.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/backend.tf) vÃ  káº¿t ná»‘i tá»›i remote state hiá»‡n cÃ³:
   ```powershell
   cd bootstrap
   terraform init
   ```
   *LÆ°u Ã½: CÃ¡c thÃ nh viÃªn khÃ¡c khÃ´ng cáº§n cháº¡y `apply` hoáº·c `migrate-state` trong thÆ° má»¥c bootstrap trá»« khi cáº§n thá»±c hiá»‡n thay Ä‘á»•i Ä‘á»‘i vá»›i chÃ­nh háº¡ táº§ng bootstrap.*

### BÆ°á»›c 2.3: ÄÃ³ng gÃ³i cÃ¡c hÃ m Lambda dÆ°á»›i dáº¡ng tá»‡p Zip
ÄÃ³ng gÃ³i 7 hÃ m adapter Python vÃ o thÆ° má»¥c `.build/lambda/`:
```powershell
cd ..
.\scripts\package-lambdas.ps1
```

### BÆ°á»›c 2.4: Triá»ƒn khai cÃ¡c MÃ´i trÆ°á»ng (Environment Compositions)
Triá»ƒn khai cÃ¡c mÃ´i trÆ°á»ng theo tuáº§n tá»± (Sandbox trÆ°á»›c, sau Ä‘Ã³ lÃ  Staging vÃ  Prod).

#### Thiáº¿t láº­p Backend vÃ  Biáº¿n cho MÃ´i trÆ°á»ng:
* **Káº¿t ná»‘i Remote State**: Khá»‘i cáº¥u hÃ¬nh remote state backend Ä‘Ã£ Ä‘Æ°á»£c thiáº¿t láº­p sáºµn trong tá»‡p `backend.tf` cá»§a má»—i mÃ´i trÆ°á»ng (`sandbox/terraform.tfstate`, `staging/terraform.tfstate`, `prod/terraform.tfstate`). Báº¡n chá»‰ cáº§n cháº¡y lá»‡nh `terraform init` Ä‘á»ƒ tá»± Ä‘á»™ng káº¿t ná»‘i vá»›i S3 remote state chung.
* **Cáº¥u hÃ¬nh Biáº¿n (Variables)**: TrÆ°á»›c khi láº­p káº¿ hoáº¡ch (plan) hoáº·c Ã¡p dá»¥ng (apply), báº¡n pháº£i sao chÃ©p tá»‡p `terraform.tfvars.example` trong thÆ° má»¥c mÃ´i trÆ°á»ng thÃ nh tá»‡p `terraform.tfvars` cá»¥c bá»™ (tá»‡p nÃ y Ä‘Æ°á»£c bá» qua bá»Ÿi git) vÃ  cáº­p nháº­t cÃ¡c giÃ¡ trá»‹ (cháº³ng háº¡n nhÆ° ECR Image URIs vÃ  ACM Certificate ARNs) cho phÃ¹ há»£p vá»›i triá»ƒn khai cá»§a báº¡n.

1. **Triá»ƒn khai Sandbox**:
   ```powershell
   cd environments/sandbox
   # Sao chÃ©p tá»‡p biáº¿n máº«u vÃ  cáº­p nháº­t giÃ¡ trá»‹
   cp terraform.tfvars.example terraform.tfvars
   # Khá»Ÿi táº¡o vÃ  káº¿t ná»‘i tá»›i remote state
   terraform init
   # Cung cáº¥p biáº¿n alb_certificate_arn báº¯t buá»™c (qua tfvars hoáº·c dÃ²ng lá»‡nh)
   terraform plan -out=sandbox.tfplan
   terraform apply sandbox.tfplan
   ```
2. **Triá»ƒn khai Staging**:
   ```powershell
   cd ../staging
   cp terraform.tfvars.example terraform.tfvars
   terraform init
   terraform plan -out=staging.tfplan
   terraform apply staging.tfplan
   ```
3. **Triá»ƒn khai Production** (YÃªu cáº§u xem xÃ©t vÃ  phÃª duyá»‡t káº¿ hoáº¡ch trÆ°á»›c):
   ```powershell
   cd ../prod
   cp terraform.tfvars.example terraform.tfvars
   terraform init
   terraform plan -out=prod.tfplan
   # Ãp dá»¥ng cho mÃ´i trÆ°á»ng Production cáº§n Ä‘Æ°á»£c phÃª duyá»‡t vÃ  kÃ­ch hoáº¡t qua GitHub Environments
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

* `private_alb_endpoint`: URL HTTPS cÆ¡ sá»Ÿ Ä‘á»ƒ truy cáº­p private ALB (qua Route 53 private DNS alias hoáº·c DNS name cá»§a internal ALB).
* `private_alb_dns_name`: TÃªn miá»n DNS thÃ´ cá»§a internal ALB.
* `private_alb_security_group_id`: ID security group cá»§a internal ALB.
* `request_lambda_function_name`: TÃªn cá»§a hÃ m AI Engine Request Lambda (cháº¡y báº±ng container image, Ä‘Æ°á»£c gá»i qua target group cá»§a internal ALB trÃªn cá»•ng 443).
* `worker_lambda_function_name`: TÃªn cá»§a hÃ m AI Engine Worker Lambda (cháº¡y báº±ng container image, xá»­ lÃ½ viá»‡c nháº­p báº¥t thÆ°á»ng báº¥t Ä‘á»“ng bá»™).
* `ecr_repository_url`: URL cá»§a kho lÆ°u trá»¯ ECR Ä‘á»ƒ push container image cho Lambda.
* `state_machine_arn`: ARN cá»§a Orchestrator State Machine.
* `dynamodb_table_names`: CÃ¡c tÃªn báº£ng DynamoDB phá»¥c vá»¥ cho viá»‡c lÆ°u trá»¯ tráº¡ng thÃ¡i cháº¡y, káº¿t quáº£, audit, vÃ  rollback cache.

### BÆ°á»›c 3.1: Triá»ƒn khai Dashboard & BÃ n giao TÃ i nguyÃªn (Asset Handoff)
Sau khi mÃ£ nguá»“n Terraform Ä‘Æ°á»£c Ã¡p dá»¥ng (apply), háº¡ táº§ng Dashboard Ä‘Ã£ sáºµn sÃ ng. Quy trÃ¬nh bÃ n giao tuÃ¢n theo cÃ¡c quy táº¯c sau:
1. **Vai trÃ² cá»§a Terraform**: Terraform khá»Ÿi táº¡o cÃ¡c tÃ i nguyÃªn AWS ná»n táº£ng (S3 buckets, CloudFront distribution vá»›i VPC Origin vÃ  liÃªn káº¿t Lambda@Edge, Cognito Identity & User Pools, cÃ¡c Athena named queries vÃ  vai trÃ² IAM).
2. **Cá»•ng XÃ¡c thá»±c (Authenticated Front Door)**: Táº¥t cáº£ tÃ i nguyÃªn tÄ©nh vÃ  tá»‡p tÃ³m táº¯t JSON (dÆ°á»›i `/${dashboard_data_prefix}*`) Ä‘Æ°á»£c phá»¥c vá»¥ qua CloudFront vÃ  báº£o vá»‡ bá»Ÿi hÃ m Lambda@Edge viewer-request sá»­ dá»¥ng xÃ¡c thá»±c Cognito PKCE.
3. **Äá»‹nh tuyáº¿n API qua VPC Origin**: CÃ¡c yÃªu cáº§u gá»­i tá»›i `/v1/*` Ä‘Æ°á»£c kÃ½ báº±ng AWS SigV4 thÃ´ng qua Lambda@Edge origin-request trÆ°á»›c khi chuyá»ƒn tiáº¿p tá»›i private internal ALB, Ä‘á»“ng thá»i loáº¡i bá» cÃ¡c cookie Cognito.
4. **Asset Upload**: Các static frontend assets của UI shell phải được build và upload độc lập/thủ công lên S3 bucket chứa static assets (được cấu hình trong output `dashboard_asset_bucket_name`). Terraform chỉ provision private bucket, CloudFront front door, Cognito access control, và object không chứa secret `dashboard_runtime_config.json`; Terraform không tự động publish file UI.
5. **NhÃ³m Cognito (Cognito Groups)**: NgÆ°á»i dÃ¹ng cáº§n Ä‘Æ°á»£c thÃªm vÃ o cÃ¡c nhÃ³m Cognito tÆ°Æ¡ng á»©ng (`finops-finance-readonly`, `finops-engineering-operator`, `finops-cdo-admin`) Ä‘á»ƒ kiá»ƒm soÃ¡t quyá»n háº¡n.
6. **Data Generation**: Cost-data writers phải publish các JSON summaries vào prefix đã cấu hình (ví dụ: `summaries/`) bên trong dashboard data S3 bucket (được cấu hình trong output `dashboard_data_bucket_name`).


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
checkov -d modules/orchestration --framework terraform
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

### BÆ°á»›c 7.1: CÃ¡c tham sá»‘ cáº¥u hÃ¬nh
HÃ nh vi thu tháº­p dá»¯ liá»‡u Ä‘Æ°á»£c kiá»ƒm soÃ¡t bá»Ÿi cÃ¡c biáº¿n Terraform Ä‘Æ°á»£c truyá»n vÃ o module `compute_lambda`:
* `cur_source_bucket`: Bucket S3 nÆ¡i AWS CUR Ä‘Æ°á»£c lÆ°u trá»¯.
* `cur_source_prefix`: ÄÆ°á»ng dáº«n prefix trong source bucket cho cÃ¡c tá»‡p CUR.
* `cur_delay_threshold_hours`: NgÆ°á»¡ng thá»i gian trá»… (tÃ­nh báº±ng giá») trÆ°á»›c khi chuyá»ƒn sang cháº¿ Ä‘á»™ dá»± phÃ²ng CE (máº·c Ä‘á»‹nh: `36`).
* `ce_lookback_window_days`: Sá»‘ ngÃ y lá»‹ch sá»­ CE cáº§n láº¥y khi cháº¡y dá»± phÃ²ng (máº·c Ä‘á»‹nh: `30`).
* `traffic_metric_identifiers`: Äá»‹nh danh dÃ¹ng Ä‘á»ƒ truy váº¥n dá»¯ liá»‡u traffic váº­t lÃ½ (vÃ­ dá»¥: tÃªn ALB).
* `synthetic_fallback_enabled`: Báº­t/táº¯t cháº¿ Ä‘á»™ tá»± Ä‘á»™ng táº¡o dá»¯ liá»‡u giáº£ láº­p cho local tests/simulations (máº·c Ä‘á»‹nh: `true`).

### BÆ°á»›c 7.2: XÃ¡c minh vÃ  Giáº£ láº­p
NgÆ°á»i váº­n hÃ nh cÃ³ thá»ƒ xÃ¡c minh luá»“ng retry/wait vÃ  xá»­ lÃ½ lá»—i cá»§a State Machine thÃ´ng qua cÃ¡c hÃ nh Ä‘á»™ng giáº£ láº­p (simulation actions) trong event thá»±c thi:
* **Giáº£ láº­p CUR bá»‹ trá»…**: Gá»­i `"action": "simulate-cur-delay"` Ä‘á»ƒ Ã©p tráº¡ng thÃ¡i trá»… CUR vÃ  kÃ­ch hoáº¡t luá»“ng dá»± phÃ²ng Cost Explorer.
* **Giáº£ láº­p CE bá»‹ throttling**: Gá»­i `"action": "simulate-ce-throttled"` Ä‘á»ƒ kÃ­ch hoáº¡t lá»—i rate limit cho CE. Náº¿u cÃ³ dá»¯ liá»‡u cache trong destination bucket, há»‡ thá»‘ng sáº½ khÃ´i phá»¥c dá»¯ liá»‡u tá»« cache vÃ  Ä‘áº·t cá» cháº¥t lÆ°á»£ng `stale_cost_explorer = true`; náº¿u khÃ´ng sáº½ tráº£ vá» lá»—i `CE_THROTTLED`.

XÃ¡c minh cÃ¡c tá»‡p JSON gzipped Ä‘Æ°á»£c táº¡o ra báº±ng cÃ¡ch kiá»ƒm tra cÃ¡c Ä‘Æ°á»ng dáº«n prefix S3:
* Cost Telemetry chÃ­nh: `s3://<lakehouse-bucket>/cur/account_id=<id>/year=YYYY/month=MM/day=DD/<run-id>_raw.json.gz`
* Utilization Features: `s3://<lakehouse-bucket>/features/account_id=<id>/year=YYYY/month=MM/day=DD/<run-id>_features.json.gz`

---

## 8. Báº£o trÃ¬ tÃ i liá»‡u hÆ°á»›ng dáº«n
TÃ i liá»‡u hÆ°á»›ng dáº«n dÃ nh cho nhÃ  phÃ¡t triá»ƒn nÃ y pháº£i luÃ´n Ä‘Æ°á»£c cáº­p nháº­t. CÃ¡c agent vÃ  ngÆ°á»i Ä‘Ã³ng gÃ³p trong tÆ°Æ¡ng lai pháº£i cáº­p nháº­t cáº£ `docs/GUIDES.md` vÃ  `docs/GUIDES_vi.md` trong cÃ¹ng má»™t thay Ä‘á»•i báº¥t ká»³ khi nÃ o cÃ³ quy trÃ¬nh lÃ m viá»‡c cá»§a developer/operator, chuá»—i lá»‡nh, quy trÃ¬nh xÃ¡c thá»±c (validation path), script, CI job, bÆ°á»›c triá»ƒn khai (deployment step) hoáº·c thá»§ tá»¥c bÃ n giao (handoff procedure) má»›i Ä‘Æ°á»£c thÃªm vÃ o hoáº·c thay Ä‘á»•i.


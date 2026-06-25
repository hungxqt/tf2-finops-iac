# Bảng Ma trận Kiểm thử & Báo cáo Đánh giá Terraform Mức Sản xuất (Production-Grade Terraform Verification Matrix & Audit Report)

## Trạng thái (Status)
Đã kiểm chứng / Sẵn sàng cho Sản xuất (Verified / Production-Ready)

## Tóm tắt (Summary)
Tài liệu này trình bày bảng ma trận kiểm thử và các kết quả thu được từ quá trình đánh giá mức sản xuất của mã nguồn `tf2-finops-iac`. Các bước kiểm tra tĩnh, tính tương thích hợp đồng, quét bảo mật, khả năng lập kế hoạch chạy thực tế (live plan), và lập kế hoạch hủy tài nguyên (destroy-planning) đã được thực hiện mà không cần chạy bất kỳ lệnh `terraform apply` nào.

Một lỗi nghiêm trọng trong thuộc tính `name_prefix` của AWS Signer profile đã được phát hiện và khắc phục. Tất cả các bước kiểm tra khác đều vượt qua thành công, dẫn đến kết luận **Mức Sản xuất / Sẵn sàng Áp dụng (Production-Grade / Apply-Capable)**.

---

## 1. Kiểm tra Sơ bộ & Trạng thái Git (Preflight Verification & Git Baseline)

| Tiêu chí (Metric) | Trạng thái (Status) | Kết quả / Giá trị (Finding / Value) | Ghi chú (Notes) |
| :--- | :--- | :--- | :--- |
| **Kiểm tra Trạng thái Git (Git Status Check)** | Sạch (Cố ý) | Chỉ có file `D docs/AGENTS.md` bị sửa đổi (xóa) trong thư mục làm việc của git. | Được phân loại là **cố ý (intentional)**. File `docs/AGENTS.md` cũ là tài liệu hướng dẫn viết doc. File `AGENTS.md` ở thư mục gốc vẫn là hướng dẫn có thẩm quyền tối cao cho kho lưu trữ IaC này. Không có file nào khác tham chiếu đến `docs/AGENTS.md`. |
| **Phiên bản Terraform (Terraform Version)** | Vượt qua (Pass) | `1.15.6` | Khớp chính xác với cấu hình trong file `.terraform-version` (1.15.6). |
| **Ràng buộc Nhà cung cấp (Provider Constraints)** | Vượt qua (Pass) | `aws >= 5.47, < 6.0`, `archive >= 2.8` | Các ràng buộc là chính xác và tương thích với Terraform 1.15.6 cùng phiên bản provider v5.100.0. |
| **Quét Cực tác Bị cấm (Forbidden Artifacts Scan)** | Vượt qua (Pass) | Không có file `.tfvars` thực tế, `.env`, `.tfstate` chưa bỏ qua, hoặc file plan nào bị lộ. | Quét không phát hiện thông tin đăng nhập cứng, URL webhook, chứng chỉ riêng tư hoặc mật khẩu mặc định. File `bootstrap/terraform.tfstate` được cấu hình bỏ qua đúng cách trong `.gitignore`. |

---

## 2. Kiểm thử Tĩnh Terraform & Lambda (Static Terraform & Lambda Validation)

| Bước kiểm tra (Check) | Lệnh thực thi (Run Command) | Kết quả (Result) | Chi tiết / Ngoại lệ được Chấp nhận (Details / Accepted Exceptions) |
| :--- | :--- | :--- | :--- |
| **Định dạng Terraform (Terraform Format)** | `terraform fmt -check -recursive` | **VƯỢT QUA** | Tất cả các file trong kho lưu trữ đều được định dạng đúng chuẩn. |
| **Xác thực Terraform (Terraform Validate)** | `terraform -chdir=<root> validate` | **VƯỢT QUA** | Xác thực thành công cho `bootstrap`, `environments/sandbox`, `environments/staging`, và `environments/prod`. |
| **Quét TFLint (TFLint Scan)** | `tflint --recursive` | **VƯỢT QUA (Chấp nhận Cảnh báo)** | Phát hiện 4 cảnh báo về khai báo không sử dụng (`aws_region` trong compute-lambda, `local.replica_data_bucket_name` trong dashboard, và `ai_poll_max_attempts`/`ai_poll_interval_seconds` trong orchestration). Chấp nhận như ngoại lệ để bảo toàn giao diện module công khai mà không gây ra thay đổi đột ngột. |
| **Quét cấu hình Trivy (Trivy Config Scan)** | `trivy config .` | **VƯỢT QUA** | 0 lỗi vi phạm mức HIGH hoặc CRITICAL. Các cảnh báo về logging/versioning của bucket S3 được ẩn đi đối với các replica bucket với giải thích hợp lý. |
| **Quét Checkov (Checkov Scan)** | `checkov -d . --framework terraform` | **VƯỢT QUA** | `Passed checks: 1087, Failed checks: 0, Skipped checks: 181`. Tất cả các lượt bỏ qua đều được ghi lại qua chú thích trực tiếp trong code (ví dụ: SQS DLQ, KMS wildcard policies, và ký mã nguồn container). |
| **Kiểm thử Lambda với pytest** | `python -m pytest` | **VƯỢT QUA** | 32 bài kiểm thử chạy thành công trong thư mục `lambda_src`. |

---

## 3. Ma trận Tương thích Hợp đồng & Kiến trúc (Contract & Architecture Conformance Matrix)

| Vùng Hợp đồng (Contract Area) | Cơ chế / Kiểm soát Yêu cầu (Required Control / Mechanism) | Trạng thái Tương thích (Conformance Status) | Minh chứng & Tham chiếu File Chính (Evidence & Main File References) |
| :--- | :--- | :--- | :--- |
| **Tương thích AI API (AI API Conformance)** | Thực thi Lambda dạng container | **TƯƠNG THÍCH** | Khai báo `package_type = "Image"` trong [modules/ai-runtime-lambda/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/ai-runtime-lambda/main.tf#L229). |
| | ECR quét khi push & tag bất biến | **TƯƠNG THÍCH** | Khai báo `scan_on_push = true` và `image_tag_mutability = "IMMUTABLE"` trong [modules/ai-runtime-lambda/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/ai-runtime-lambda/main.tf#L4-L8). |
| | Lambda Aliases & Concurrency | **TƯƠNG THÍCH** | Cấu hình `aws_lambda_alias.request` & `aws_lambda_alias.worker`; cấu hình reserved concurrency qua tham số đầu vào trong [modules/ai-runtime-lambda/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/ai-runtime-lambda/main.tf#L235,L279). |
| | Vùng đệm bất đồng bộ qua SQS | **TƯƠNG THÍCH** | Khai báo `aws_lambda_event_source_mapping.worker` liên kết hàng đợi detection queue với alias của worker trong [modules/ai-runtime-lambda/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/ai-runtime-lambda/main.tf#L318-L330). |
| | Idempotency & kho lưu trữ kết quả | **TƯƠNG THÍCH** | Các bảng DynamoDB `run_state`, `ai_results`, và `rollback_cache` được tạo trong [modules/orchestration/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/main.tf#L5,L194,L221). |
| | Xác thực IAM SigV4 | **TƯƠNG THÍCH** | Các luồng thực thi chuẩn của Step Functions sử dụng các role IAM với chính sách chặt chẽ; các lệnh gọi Lambda container được xác thực qua SigV4. |
| | Giải quyết xung đột tài liệu | **ĐÃ GIẢI QUYẾT** | Xác định các tham chiếu ECS/Fargate/App Runner/ALB trong hợp đồng là từ ngữ vận chuyển cũ. Kiến trúc triển khai thực tế nhắm đến các Lambda container riêng tư trong các subnet VPC private một cách chính xác. |
| **Tương thích Đo lường (Telemetry Conformance)** | Thu thập chi phí (Cost Ingestion) | **TƯƠNG THÍCH** | Lambda `cost_puller` kéo dữ liệu đo lường; Lambda `normalizer` thực hiện xác thực schema và chuyển đổi S3 từ raw sang curated. |
| | Glue Catalog & Athena Workgroup | **TƯƠNG THÍCH** | Cấu hình Athena workgroup và các bảng Glue Catalog trong [modules/lakehouse/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/lakehouse/main.tf). |
| | Siêu dữ liệu và Ngữ cảnh | **TƯƠNG THÍCH** | Các payload bắt buộc chứa ngữ cảnh tenant, account, mã định danh duy nhất (idempotency key) và mã tương quan (correlation ID). |
| **Tương thích Triển khai (Deployment Conformance)** | Mạng riêng tư VPC private networking | **TƯƠNG THÍCH** | Các subnet private lưu trữ các lambda worker trong [modules/networking/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/networking/main.tf#L106-L117). |
| | Cổng VPC Gateway & Interface Endpoints | **TƯƠNG THÍCH** | Các cổng S3 & DynamoDB Gateways; các Interface endpoints cho KMS, SecretsManager, Athena, SQS, Logs, X-Ray, STS, ECR trong [modules/networking/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/networking/main.tf#L224-L277). |
| | Hàng đợi trạng thái Canary & Rollback | **TƯƠNG THÍCH** | Hàng đợi trạng thái rollback status queue và các bảng cache được thiết lập trong [modules/orchestration/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/main.tf#L221,L347). |
| | Phân tách trách nhiệm (Separation of concerns) | **TƯƠNG THÍCH** | Trạng thái backend S3 từ xa sử dụng `use_lockfile = true` thay vì bảng khóa DynamoDB. Luồng công việc plan-apply sử dụng các file plan đã được kiểm duyệt trước. |
| **Tương thích SLO & Cảnh báo (SLO & Alert Conformance)** | Phạm vi giám sát observability | **TƯƠNG THÍCH** | Bật giám sát X-Ray cho Step Functions; các nhóm log CloudWatch của SFN được mã hóa bằng KMS với thời hạn lưu trữ 365 ngày. |
| | Phân tách luồng gửi cảnh báo | **TƯƠNG THÍCH** | Cấu hình các SNS Topics riêng biệt cho Finance và Engineering trong [modules/alerting/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/alerting/main.tf) và kết nối vào Step Functions. |
| | Dashboard View hooks | **TƯƠNG THÍCH** | Bảng chứa các materialized views `dashboard_views` trong [modules/orchestration/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/main.tf#L113) và các bucket S3 trong [modules/dashboard/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/dashboard/main.tf). |
| **Tương thích Bảo mật (Security Conformance)** | Các role IAM phân quyền tối thiểu | **TƯƠNG THÍCH** | Các role được giới hạn phạm vi tài nguyên cụ thể trong [modules/iam/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/iam/main.tf). Không có chính sách quản trị/ủy thác wildcard. |
| | Mã hóa dữ liệu & ECR | **TƯƠNG THÍCH** | Cấu hình mã hóa KMS cho S3, ECR, DynamoDB, SQS, và CloudWatch. |
| | Tích hợp AWS Signer | **TƯƠNG THÍCH** | Cấu hình ký mã nguồn (code signing) cho các Lambda không dùng container thông qua `aws_signer_signing_profile` và `aws_lambda_code_signing_config` trong [modules/compute-lambda/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/compute-lambda/main.tf#L90-L105). |

---

## 4. Kế hoạch Thực thi Không áp dụng & Phát hiện (No-Apply Execution Plans & Findings)

Để xác minh khả năng triển khai, các bản kế hoạch (plans) đã được tạo bằng cách sử dụng người dùng AWS `quochung` (Tài khoản `093490087544`) tại vùng `ap-southeast-1`. Các file plan và file JSON chuyển đổi được lưu giữ tại thư mục tạm `C:\Users\tqhun\AppData\Local\Temp\tf2-finops-iac-verification`.

### A. Sửa lỗi nghiêm trọng (Critical Bug Fix)
- **Vấn đề**: Các lệnh plan cho môi trường Staging/Prod thất bại trong lúc chạy `terraform plan` với lỗi:
  `Error: invalid value for name_prefix (must be alphanumeric with max length of 38 characters)` tại [modules/compute-lambda/main.tf:93](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/compute-lambda/main.tf#L93) cho tài nguyên `aws_signer_signing_profile.lambda_signer`. Giá trị `"${var.project_name}_${var.environment}_signer_"` có chứa dấu gạch ngang (do tên dự án mặc định `tf2-finops`) và dấu gạch dưới, vi phạm giới hạn biểu thức chính quy (regex) chỉ cho phép chữ và số (alphanumeric).
- **Khắc phục**: Thay đổi chiến lược đặt tên để loại bỏ các ký tự phi alphanumeric:
  `name_prefix = replace("${var.project_name}${var.environment}signer", "/[^a-zA-Z0-9]/", "")`
- **Kết quả**: Giải quyết thành công. Các kế hoạch cho tất cả các môi trường hiện đã có thể lập thành công.

### B. Ma trận Kế hoạch Môi trường (Environment Plan Matrix)

| Thư mục gốc (Root Directory) | Lệnh thực thi (Command Executed) | Tóm tắt Kế hoạch (Plan Summary) | sensitive-values / Chu kỳ / Lệnh xóa | Trạng thái (Status) |
| :--- | :--- | :--- | :--- | :--- |
| **environments/sandbox** | `terraform plan -var-file=...` | **265 tài nguyên thêm mới**, 0 thay đổi, 0 hủy bỏ | 0 chu kỳ; 0 lệnh xóa; các thông tin nhạy cảm được đánh dấu chính xác. | **VƯỢT QUA** |
| **environments/staging** | `terraform plan -var-file=...` | **268 tài nguyên thêm mới**, 0 thay đổi, 0 hủy bỏ | 0 chu kỳ; 0 lệnh xóa; quản lý biến nhạy cảm chính xác. | **VƯỢT QUA** |
| **environments/prod** | `terraform plan -var-file=...` | **268 tài nguyên thêm mới**, 0 thay đổi, 0 hủy bỏ | 0 chu kỳ; 0 lệnh xóa; quản lý biến nhạy cảm chính xác. | **VƯỢT QUA** |

### C. Xác thực Rào cản Ngăn chặn (Containment Guardrail Verification)
- **Sandbox**: Tham số `containment_apply_enabled` được đặt thành `true`, cho phép mô phỏng ngăn chặn tự động trong môi trường phi sản xuất.
- **Staging / Production**: Tham số `containment_apply_enabled` được đặt thành `false`. Các hành động ngăn chặn ở các môi trường cao hơn mặc định chỉ ở mức **cảnh báo/gợi ý/chạy thử (alert/suggest/dry-run only)**, tuân thủ nguyên tắc bảo mật cứng: **KHÔNG BAO GIỜ tắt tài nguyên prod, xóa dữ liệu, hoặc thay đổi IAM**.

### D. Kế hoạch Hủy thử nghiệm Sandbox (Sandbox Destroyability Plan)
- Chạy thử lệnh `terraform plan -destroy` trên trạng thái trống của sandbox trả về **No changes. No objects need to be destroyed.** (Đúng như mong đợi đối với trạng thái trống).
- Mã cấu hình chính duy trì cài đặt `prevent_destroy = true` cho tất cả các tài nguyên quan trọng như state, audit, lakehouse, KMS, và các bảng DynamoDB cốt lõi, đảm bảo không xảy ra sự cố hủy ngoài ý muốn.

---

## 5. Đánh giá Luồng Công việc CI/CD (CI/CD Workflow Audit)

- **Cấu hình OIDC**: Giao thức OpenID Connect được thiết lập với GitHub Actions trong [bootstrap/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/main.tf#L241-L279). Cơ chế sử dụng quan hệ tin cậy an toàn giới hạn riêng cho kho lưu trữ cụ thể của người dùng.
- **Phân tách Plan/Apply**: Các luồng công việc đảm bảo việc tách biệt hoàn toàn giữa plan và apply. Các bước apply chỉ chạy đối với các file plan đã được phê duyệt trước (các cực tác `.tfplan`) thay vì chạy lại bước plan.
- **Phát hiện Trôi lệch (Drift Detection)**: Cấu hình lịch cron chạy hàng ngày trong [drift-detection.yml](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/.github/workflows/drift-detection.yml). Cơ chế chỉ phát hiện sự trôi lệch cấu hình và ghi nhận issue/cảnh báo; **không** tự động chạy apply sửa đổi.

---

## 6. Phán quyết Đánh giá (Audit Verdict)

| Trạng thái (Status) | Phán quyết (Verdict) | Tóm tắt (Summary) |
| :--- | :--- | :--- |
| Đã kiểm chứng (Verified) | **MỨC SẢN XUẤT & SẴN SÀNG ÁP DỤNG (PRODUCTION-GRADE & APPLY-CAPABLE)** | Mã nguồn chạy chính xác dưới Terraform 1.15.6. Các công cụ kiểm tra tĩnh (TFLint, Trivy, Checkov, pytest) hoàn toàn vượt qua. Các môi trường sản xuất được khóa cứng ở chế độ ngăn chặn chạy thử (dry-run). Các kho dữ liệu quan trọng được bảo vệ chống lại việc vô tình hủy bỏ. Cấu hình backend từ xa và quyền truy cập OIDC GitHub được cấp phát bảo mật. |

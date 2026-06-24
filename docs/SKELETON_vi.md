# Kiến trúc & Cấu trúc Repository TF2 FinOps IaC

Tài liệu này cung cấp cái nhìn chi tiết và chuyên sâu về cấu trúc, các design pattern và các thành phần của repository Infrastructure-as-Code (IaC) dành cho dự án **Task Force 2 - FinOps Watch**.

---

## 1. Tổng quan cấu trúc thư mục (Directory Structure Overview)

Repository được tổ chức tuân theo các standard best practice của Terraform nhằm phân tách rõ ràng giữa các phần logic có thể tái sử dụng (modules), cấu hình môi trường cụ thể (roots), tài nguyên khởi tạo (bootstrap), mã nguồn chạy thực thi Lambda và các pipeline CI/CD.

```text
tf2-finops-iac/
├── .github/
│   └── workflows/              # GitHub Actions CI/CD workflows
│       ├── terraform-ci.yml    # Linting, formatting, kiểm tra và lập kế hoạch (planning)
│       ├── terraform-apply.yml # Triển khai hạ tầng lên các môi trường đích
│       └── drift-detection.yml # Quét phát hiện cấu hình sai lệch (drift scanning) định kỳ
├── bootstrap/                  # Khởi tạo remote state và các cấu hình định danh OIDC ban đầu
│   ├── README.md
│   ├── backend.tf              # Cấu hình backend (chuyển sang S3 sau khi khởi tạo thành công)
│   ├── locals.tf
│   ├── main.tf                 # KMS, S3 bucket, OIDC provider, và các execution roles
│   ├── outputs.tf
│   ├── providers.tf
│   ├── variables.tf
│   └── versions.tf
├── docs/                       # Tài liệu kiến trúc và tiến độ dự án
│   ├── progress/               # Các file theo dõi tiến độ (theo cặp EN & VI)
│   ├── SKELETON.md             # Tài liệu chi tiết cấu trúc repo bằng tiếng Anh
│   └── SKELETON_vi.md          # Tài liệu chi tiết cấu trúc repo bằng tiếng Việt
├── environments/               # Thư mục gốc chứa các composition của từng môi trường
│   ├── sandbox/                # Môi trường chạy thử nghiệm nhanh (fast iteration)
│   ├── staging/                # Môi trường tích hợp và chạy thử nghiệm hệ thống (pre-production)
│   └── prod/                   # Môi trường vận hành thực tế (chốt chặn phê duyệt thủ công)
├── lambda_src/                 # Mã nguồn Serverless Go Lambda worker
│   ├── finops_common/          # Các struct dùng chung, validation và phản hồi
│   ├── ai_client/              # Nhận đầu ra của normalizer và giao tiếp với AI engine
│   ├── audit_writer/           # Ghi logs workflow và lịch sử containment audit
│   ├── containment_worker/     # Thực thi các hành động remediation/safe actions
│   ├── cost_puller/            # Worker thu thập dữ liệu chi phí (cost data ingestion)
│   ├── normalizer/             # Chuẩn hóa schema dữ liệu chi phí thô sang dạng parquet
│   ├── router/                 # Điều hướng các cảnh báo phát hiện sang các alert topics
│   ├── go.mod
│   └── go.sum
├── modules/                    # Các module Terraform độc lập và có tính tái sử dụng cao
│   ├── alerting/               # Các tuyến SNS riêng biệt cho Finance và Engineering
│   ├── compute-lambda/         # Cấu hình triển khai cho các Go worker stubs
│   ├── dashboard/              # Các Athena named queries và QuickSight hooks
│   ├── iam/                    # Phân quyền least-privilege và permissions boundary
│   ├── lakehouse/              # S3 buckets, Object Lock, Glue Catalog, và KMS keys
│   ├── networking/             # Mạng VPC bảo mật và các VPC Interface endpoints
│   ├── observability/          # Hệ thống CW Dashboards và CloudWatch alarms
│   └── orchestration/          # Các bảng DynamoDB và Step Functions state machine
├── scripts/                    # Các công cụ tự động hóa trợ giúp phát triển
│   ├── validate.ps1            # Công cụ xác thực định dạng, lints và chạy unit tests
│   └── package-lambdas.ps1     # Công cụ biên dịch mã nguồn Go và đóng gói zip
├── .gitignore                  # Cấu hình bỏ qua tệp tin trong Git
├── .pre-commit-config.yaml     # Hooks ngăn chặn commit mã nguồn sai định dạng
├── .terraform-version          # Chỉ định phiên bản Terraform bắt buộc chạy
├── .tflint.hcl                 # Cấu hình bổ sung cho công cụ linting tflint
├── Makefile                    # Các câu lệnh alias nhanh cho build, test và validate
└── README.md                   # Tài liệu hướng dẫn bắt đầu nhanh của dự án
```

---

## 2. Các Design Pattern Kiến trúc Cốt lõi (Core Architectural Design Patterns)

### A. Reusable Modules vs. Compositions
- **Modules (`modules/`)**: Quản lý các logic hạ tầng độc lập, có thể tái sử dụng. Chúng chỉ chứa mã nguồn tổng quát, nhận tham số đầu vào qua variables mà không chứa các cấu hình cứng hay các secret thông tin nhạy cảm.
- **Compositions (`environments/`)**: Các composition này gọi các module và gán giá trị cụ thể cho từng tham số đầu vào tương ứng với môi trường đó. Việc này đảm bảo các môi trường staging và production sử dụng chính xác mã nguồn hạ tầng giống nhau nhưng với cấu hình được tùy biến riêng.

### B. Remote State Security
- Một lớp khởi tạo (`bootstrap/`) được chạy cục bộ ban đầu để tạo ra S3 state bucket và KMS customer managed key (CMK).
- Các môi trường composition sau đó được cấu hình S3 remote backend trỏ đến bucket này.
- **Locking**: Sử dụng tính năng khóa trạng thái tự nhiên của S3 (từ phiên bản Terraform 1.10 trở lên, tham số `use_lockfile = true` được kích hoạt). Không cần cấu hình thêm bảng DynamoDB khóa phụ.
- **Encryption**: Mọi giao thức giao tiếp với bucket bắt buộc dùng TLS. Dữ liệu được mã hóa ở chế độ rest thông qua KMS key chỉ định.

### C. OIDC Authentication
- Quá trình triển khai không cần dùng đến AWS IAM access keys tĩnh và lâu dài.
- Thư mục `bootstrap/` khởi tạo GitHub OIDC identity provider liên kết với repo này.
- Các workflow runner của GitHub Actions sẽ giả lập (assume) một phiên IAM role ngắn hạn, giới hạn phân quyền theo nhánh để lập kế hoạch (planning) và triển khai (applying) hạ tầng một cách an toàn.

---

## 3. Chi tiết Thành phần Kiến trúc (Component Breakdown)

### A. Các Terraform Modules (`modules/`)
1. **`networking`**: Tạo VPC private với 2 public subnets (để host NAT Gateways) và 2 private subnets (để host Lambda workers). Chặn hoàn toàn mọi truy cập ingress trực tiếp từ ngoài vào các private subnets. Cấu hình các gateway/interface VPC endpoints cho các dịch vụ AWS (S3, DynamoDB, KMS, Secrets Manager, Athena, CloudWatch Logs, X-Ray, STS) để lưu lượng mạng nội bộ không đi qua internet.
2. **`lakehouse`**: Khởi tạo hạ tầng S3 cost-lake với Object Lock được kích hoạt ở chế độ compliance mode đối với Audit bucket (thời gian giữ tối thiểu 90 ngày). Thiết lập bucket versioning, lifecycle transitions, TLS-only bucket policies, KMS keys (cho dữ liệu, audit logs và DynamoDB), một Glue Catalog database, và một Athena workgroup tích hợp tính năng bảo vệ giới hạn quét dữ liệu.
3. **`iam`**: Thiết lập các execution roles theo mô hình least-privilege. Một permissions boundary được đính kèm để cấm tuyệt đối: thay đổi IAM, thay đổi AWS Organizations, xóa dữ liệu RDS, hủy (terminate) EC2, và xóa bucket S3. Các hành động containment ở môi trường production tuyệt đối không được tắt máy hay thay đổi quyền hạn/dữ liệu.
4. **`compute-lambda`**: Triển khai sáu worker Go dạng file nén nhị phân lên các Lambda function trong VPC chạy trên custom runtime (`provided.al2023`). Cấu hình timeout, RAM, reserved concurrency, active X-Ray tracing, và các alias stable/canary phù hợp.
5. **`orchestration`**: Khởi tạo các bảng DynamoDB mã hóa dùng chung để quản lý trạng thái (run state, danh sách anomalies, định tuyến alert, lịch sử containment audit, materialized views). Tạo Step Functions Standard state machine điều phối luồng xử lý dữ liệu.
6. **`alerting`**: Tạo các SNS alert topic được mã hóa riêng biệt cho Finance (báo cáo spent, digest) và Engineering (lỗi hệ thống, drift hạ tầng) để giữ ranh giới rõ ràng.
7. **`observability`**: Tạo CloudWatch dashboard tổng quan và đăng ký các metric filters, metric alarms giám sát lỗi chạy workflow, AI engine timeout, runs bị treo quá 26 giờ và cảnh báo cấu hình drift phát hiện từ CI.
8. **`dashboard`**: Tạo các Athena named queries hỗ trợ tài chính truy vấn dữ liệu chi tiêu trực quan mà không yêu cầu người dùng phải có kỹ năng viết SQL.

### B. Các Môi trường Gốc Composition (`environments/`)
Mỗi thư mục composition gọi tuần tự tám module lõi. Các tham số cấu hình riêng biệt được thiết lập cho từng môi trường:

| Tham số / Guardrail | Sandbox | Staging | Production |
| :--- | :--- | :--- | :--- |
| **State Key** | `sandbox/terraform.tfstate` | `staging/terraform.tfstate` | `prod/terraform.tfstate` |
| **NAT Gateways** | `1` (Tối ưu chi phí) | `2` (Độ tin cậy cao) | `2` (Độ tin cậy cao) |
| **Remediation Action** | `apply` (Kích hoạt xử lý) | `dry-run` | `dry-run` (Không phá hủy) |
| **Log Retention** | `14 ngày` | `30 ngày` | `30 ngày` |
| **Cổng kiểm duyệt CI** | Apply tự động | Merge vào main tự động | Cổng phê duyệt thủ công |
| **Bảo vệ tài nguyên lõi** | Bình thường | Bình thường | `prevent_destroy = true` |

---

## 4. Subsystem Lambda (`lambda_src/`)

Toàn bộ worker được lập trình bằng ngôn ngữ **Go (1.21+)** nhằm tối ưu hóa hiệu năng và tính an toàn kiểu dữ liệu (type safety):
- **`finops_common`**: Chứa các struct dùng chung cho việc phân tích cú pháp sự kiện đầu vào và phản hồi đầu ra, cùng hàm kiểm tra tính hợp lệ của hợp đồng dữ liệu.
- **Đóng gói và Triển khai**: Các hàm Go Lambda được biên dịch cho hệ điều hành Linux kiến trúc `amd64` tạo ra file thực thi duy nhất tên là `bootstrap`. Công cụ `package-lambdas.ps1` tự động hóa quá trình biên dịch này và đóng gói zip thành phẩm cho Terraform triển khai.
- **Unit Testing**: Các kiểm tra nằm trực tiếp bên trong từng package tương ứng (ví dụ: `cost_puller/main_test.go` và `containment_worker/main_test.go`) và có thể chạy đồng thời qua lệnh `go test ./...` tại thư mục `lambda_src`.

---

## 5. Xác thực Mã nguồn & Giữ gìn Quy chuẩn (Repository Validation & Hygiene)

Các công cụ được cấu hình chạy tự động ở máy cục bộ và trên các pipeline CI/CD để đảm bảo quy chuẩn bảo mật:
- **Terraform Linter**: Sử dụng các rule mở rộng trong file cấu hình `.tflint.hcl` để phát hiện lỗi viết code sớm.
- **Terraform Formatting**: Đảm bảo quy chuẩn định dạng code đồng bộ qua lệnh `terraform fmt -check -recursive`.
- **Security Checkers (Công cụ quét bảo mật)**: 
  - **Trivy**: Phát hiện các lỗi cấu hình hạ tầng và các module workflow bên thứ ba.
  - **Checkov**: Quét lỗi cấu hình bảo mật Terraform (đảm bảo không phân quyền wildcard principal trust, không tạo bucket S3 public, và đầy đủ ghi log/mã hóa dữ liệu rest).
  - **Công cụ kiểm tra gộp**: Tập tin kịch bản `validate.ps1` gộp chung toàn bộ việc kiểm tra cú pháp, chạy tests và quét bảo mật chỉ bằng một câu lệnh duy nhất.

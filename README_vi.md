# TF2 FinOps IaC (Bản tiếng Việt)

Kho lưu trữ này chứa mã nguồn Infrastructure as Code (IaC) dành cho dự án **Task Force 2 - FinOps Watch**. Mục tiêu của nó là định nghĩa và thiết lập nền tảng AWS để chạy hệ thống thu thập chi phí FinOps, tích hợp quy trình phát hiện bất thường, nền tảng lưu trữ EKS cho AI Engine, cảnh báo, bảng điều khiển (dashboards), các chốt chặn ngăn chặn (containment guardrails) và nhật ký kiểm toán (audit trail).

---

## 1. Mục tiêu & Phạm vi

Kho lưu trữ này khởi tạo toàn bộ hạ tầng AWS nền tảng cần thiết trước khi các dịch vụ chạy tác vụ FinOps Watch và AI Engine do nhóm AIOps phát triển có thể vận hành.

### Nằm trong phạm vi (Hạ tầng do repo này quản lý)
* **VPC Networking**: Các subnet riêng tư (private subnets), NAT Gateways và định tuyến bảo mật.
* **Lakehouse Storage**: Các phân vùng S3 raw/curated/audit, Glue Data Catalog và Athena views.
* **EKS Hosting Platform**: Cụm EKS control plane riêng tư, các nhóm node on-demand được quản lý (cho API, explainer và dịch vụ CDO), các nhóm node spot (cho retraining, feature engineering và batch workers), kho lưu trữ hình ảnh ECR và IAM Roles cho Service Accounts (IRSA/OIDC).
* **Serverless Orchestration**: Quy trình Step Functions Standard, EventBridge Scheduler, các Python 3.13 Lambda workers và bảng DynamoDB lưu trạng thái chạy.
* **Bảo mật & IAM**: Các khóa KMS, vai trò IAM đặc quyền tối thiểu cho thu thập/chặn chi phí và xác thực GitHub OIDC không dùng khóa.
* **Observability & Dashboards**: CloudWatch Container Insights, các điểm móc thu thập metric, hệ thống cảnh báo và cấu hình dashboard dựa trên Athena.

### Ngoài phạm vi (Không thuộc quyền quản lý của repo này)
* **Mã nguồn & Cấu trúc của AI Model**: Lựa chọn model, logic huấn luyện/huấn luyện lại (training/retraining), nội dung giải thích và thuật toán phân loại (do AIOps sở hữu).
* **Tài liệu cấu hình Kubernetes và Ứng dụng**: Các cấu hình Kubernetes Deployment, Service, Helm values và cấu hình Argo CD (do `tf2-finops-gitops` sở hữu).
* **Tài liệu nghiệp vụ ngoại vi**: Các thiết kế nghiệp vụ hoặc tài liệu kiến trúc tổng quan (do `tf2-finops-docs` sở hữu).

---

## 2. Cấu trúc thư mục

Tóm tắt bố cục của kho lưu trữ này (xem [SKELETON.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/SKELETON.md) để biết chi tiết):
* `bootstrap/`: Triển khai hạ tầng remote state ban đầu và cấu hình GitHub OIDC.
* `environments/`: Cấu hình môi trường sandbox, staging và production.
* `modules/`: Các module Terraform tái sử dụng (networking, EKS, lakehouse, IAM, v.v.).
* `lambda_src/`: Mã nguồn Python 3.13 và mã kiểm thử cho các Lambda adapter.
* `docs/`: Thiết kế kiến trúc, cấu trúc chi tiết và tài liệu hướng dẫn nhà phát triển.
* `scripts/`: Công cụ đóng gói Lambda và xác thực mã nguồn.

---

## 3. Hướng dẫn dành cho Nhà phát triển & Vận hành

Chi tiết quy trình làm việc, triển khai hạ tầng, kiểm tra xác thực mã nguồn và quy trình vận hành được duy trì tại:
* **Tiếng Anh**: [GUIDES.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES.md)
* **Tiếng Việt**: [GUIDES_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES_vi.md)

Vui lòng đọc kỹ các tài liệu hướng dẫn này trước khi bắt đầu phát triển hoặc chạy các lệnh Terraform plan/apply.

---

## 4. Chốt chặn bảo vệ FinOps (Guardrails)

Toàn bộ tài nguyên hạ tầng và quy trình triển khai từ repo này phải tuân thủ nghiêm ngặt các chốt chặn an toàn sau:
* **Chỉ sử dụng AWS**: Toàn bộ hệ thống chạy hoàn toàn trên các dịch vụ đám mây AWS native.
* **Mặc định dùng dữ liệu giả lập (Synthetic)**: Trừ khi được cung cấp quyền truy cập dữ liệu hóa đơn thật, dữ liệu chi phí giả lập sẽ được sử dụng.
* **Chế độ chạy thử trước (Dry-Run First)**: Các hành động ngăn chặn tự động phải được thực thi ở chế độ dry-run trước tiên.
* **Không thực hiện hành động phá hủy**: Các hành động tự động chặn chi phí vượt mức **KHÔNG BAO GIỜ** được phép dừng các tài nguyên production, xóa dữ liệu hoặc sửa đổi chính sách bảo mật IAM.
* **Thiết kế Fail-Closed**: Khi AI Engine không khả dụng hoặc xác thực dữ liệu thất bại, hệ thống orchestrator sẽ đóng luồng an toàn (fail closed), lưu lại trạng thái, cảnh báo quản trị viên và ghi lại audit trail.
* **Thời gian lưu trữ Audit**: Nhật ký kiểm toán toàn diện phải được lưu tại phân vùng S3/DynamoDB audit tối thiểu 90 ngày.
* **Triển khai EKS riêng tư**: Cụm EKS control plane và các kết nối tích hợp AI Engine đều phải ở chế độ riêng tư (private-only); toàn bộ giao tiếp giới hạn trong các kết nối VPC Endpoint nội bộ.

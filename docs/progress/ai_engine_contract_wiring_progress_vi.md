# Tiến độ Đầu nối Biến môi trường AI Engine theo Hợp đồng

## Trạng thái
Hoàn thành (tất cả các biến, tài nguyên bảng, phân quyền IAM và cấu hình môi trường đã được cập nhật và kiểm tra thành công).

## Phạm vi công việc
Liên kết (wire) Lambda AI Engine với các biến môi trường được định nghĩa trong `deployment-contract.md` và tạo bảng DynamoDB feature-store dựa trên lược đồ của `feature-store-schema.md`.
- Tạo tài nguyên `aws_dynamodb_table.feature_store` trong `modules/orchestration` với khóa phân vùng `resource_id` (S), khóa sắp xếp `date` (S), TTL `ttl_expiry`, mã hóa KMS CMK, và bật tính năng Phục hồi Điểm thời gian (PITR).
- Đầu nối các biến môi trường runtime của AI: `AWS_REGION`, `S3_TELEMETRY_BUCKET`, `S3_CDO_NAMESPACE`, `DYNAMODB_IDEMPOTENCY_TABLE`, `DYNAMODB_FEATURE_STORE_TABLE`, và `BEDROCK_API_KEY` (được sử dụng như một tham chiếu an toàn thông qua Secrets Manager cho Bedrock).
- Thêm biến `DYNAMODB_TABLE` dưới dạng bí danh tương thích trỏ đến `DYNAMODB_IDEMPOTENCY_TABLE` cho container image hiện tại.
- Mở rộng chính sách của vai trò IAM Execution Role cho Lambda AI Request để cho phép:
  - `dynamodb:GetItem`, `dynamodb:PutItem`, và `dynamodb:UpdateItem` trên bảng idempotency.
  - `dynamodb:GetItem` và `dynamodb:Query` trên bảng feature store.
  - `secretsmanager:GetSecretValue` trên ARN hoặc tên của Bedrock secret khi được cấu hình.
- Truyền các tham số từ các thư mục môi trường (`sandbox`, `staging`, `prod`) vào module AI runtime, lấy tên bảng và ARN từ dữ liệu đầu ra của `module.orchestration` và bucket từ `module.lakehouse.lakehouse_bucket_name`.
- Thêm ARN của bảng feature-store vào danh sách bảng của module IAM ở tất cả các môi trường để đảm bảo các CDO worker có quyền truy cập phù hợp.
- Tài liệu hóa việc ánh xạ tên bảng feature store trong các tài liệu hướng dẫn nhà phát triển song ngữ.

## Quyết định đặt tên bảng (Table Naming Decision)
Theo quyết định của người dùng và để đảm bảo tính nhất quán về tiền tố trong toàn bộ kho lưu trữ, bảng feature store được cấu hình với tên `tf2-finops-{env}-feature-store` (ví dụ: `tf2-finops-sandbox-feature-store`). Tên này khác biệt có chủ đích so với tên nguyên bản `finops-feature-store-{env}` trong tài liệu `feature-store-schema.md` nhưng vẫn đảm bảo giữ nguyên cấu trúc khóa PK/SK, thuộc tính TTL và các chính sách phân quyền IAM tương tự.

## Các tệp đã thay đổi
- `modules/orchestration/main.tf` (Thêm tài nguyên bảng DynamoDB feature store)
- `modules/orchestration/outputs.tf` (Thêm outputs cho tên/ARN của bảng feature store và ARN của bảng idempotency)
- `modules/ai-runtime-lambda/variables.tf` (Thêm các biến đầu vào cho tên/ARN của bảng, S3 telemetry bucket, CDO namespace, và Bedrock secret)
- `modules/ai-runtime-lambda/main.tf` (Đầu nối biến môi trường và cập nhật chính sách thực thi IAM của Lambda)
- `environments/sandbox/variables.tf` (Thêm biến bedrock_secret_arn)
- `environments/sandbox/main.tf` (Cập nhật các khối tham số cho module.iam và module.ai_runtime_lambda)
- `environments/staging/variables.tf` (Thêm biến bedrock_secret_arn)
- `environments/staging/main.tf` (Cập nhật các khối tham số cho module.iam và module.ai_runtime_lambda)
- `environments/prod/variables.tf` (Thêm biến bedrock_secret_arn)
- `environments/prod/main.tf` (Cập nhật các khối tham số cho module.iam và module.ai_runtime_lambda)
- `docs/GUIDES.md` (Cập nhật tài liệu hướng dẫn sau triển khai)
- `docs/GUIDES_vi.md` (Cập nhật tài liệu tiếng Việt sau triển khai)

## Câu lệnh kiểm thử & Xác thực
```powershell
# Kiểm tra định dạng code
terraform fmt -check -recursive

# Xác thực cấu hình ở từng thư mục môi trường
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate

terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate

terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate

# Kiểm tra tạo plan (chạy thử chế độ destroy của sandbox)
terraform -chdir=environments/sandbox plan -destroy -out=sandbox-destroy.tfplan
```

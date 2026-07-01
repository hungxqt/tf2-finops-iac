# Tiến độ Đầu nối Biến môi trường AI Engine theo Hợp đồng

## Trạng thái
Hoàn thành. Đã áp dụng hotfix để bỏ `AWS_REGION` do Terraform tự cấu hình khỏi môi trường AI Request Lambda vì Lambda tự inject khóa reserved này lúc runtime.

## Phạm vi công việc
Liên kết (wire) Lambda AI Engine với các biến môi trường được định nghĩa trong `deployment-contract.md` và tạo bảng DynamoDB feature-store dựa trên lược đồ của `feature-store-schema.md`.
- Tạo tài nguyên `aws_dynamodb_table.feature_store` trong `modules/orchestration` với khóa phân vùng `resource_id` (S), khóa sắp xếp `date` (S), TTL `ttl_expiry`, mã hóa KMS CMK, và bật tính năng Phục hồi Điểm thời gian (PITR).
- Dựa vào `AWS_REGION` do Lambda quản lý và chỉ đầu nối các biến môi trường runtime không reserved của AI: `S3_TELEMETRY_BUCKET`, `S3_CDO_NAMESPACE`, `DYNAMODB_IDEMPOTENCY_TABLE`, `DYNAMODB_FEATURE_STORE_TABLE`, và `BEDROCK_API_KEY` (được sử dụng như một tham chiếu an toàn thông qua Secrets Manager cho Bedrock).
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
- `modules/ai-runtime-lambda/main.tf` (Đầu nối biến môi trường và cập nhật chính sách thực thi IAM của Lambda; bỏ `AWS_REGION` reserved do Terraform tự cấu hình)
- `modules/ai-runtime-lambda/variables.tf` (Làm rõ `aws_region` dùng cho ARN theo vùng, không dùng để cấu hình biến môi trường Lambda)
- `environments/sandbox/variables.tf` (Thêm biến bedrock_secret_arn)
- `environments/sandbox/main.tf` (Cập nhật các khối tham số cho module.iam và module.ai_runtime_lambda)
- `environments/staging/variables.tf` (Thêm biến bedrock_secret_arn)
- `environments/staging/main.tf` (Cập nhật các khối tham số cho module.iam và module.ai_runtime_lambda)
- `environments/prod/variables.tf` (Thêm biến bedrock_secret_arn)
- `environments/prod/main.tf` (Cập nhật các khối tham số cho module.iam và module.ai_runtime_lambda)
- `docs/GUIDES.md` (Cập nhật tài liệu hướng dẫn sau triển khai)
- `docs/GUIDES_vi.md` (Cập nhật tài liệu tiếng Việt sau triển khai)
- `docs/progress/ai_engine_contract_wiring_progress.md` và `docs/progress/ai_engine_contract_wiring_progress_vi.md` (Ghi nhận hotfix khóa reserved và kết quả kiểm tra)

## Câu lệnh kiểm thử & Xác thực
```powershell
# Kiểm tra hotfix
rg -n "AWS_REGION\s*=" modules environments .github docs/GUIDES.md docs/GUIDES_vi.md README.md
terraform fmt -check -recursive modules\ai-runtime-lambda
terraform fmt -check -recursive modules\ai-runtime-lambda modules\compute-lambda modules\orchestration modules\iam modules\networking
terraform fmt -check -recursive
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate
trivy config .
checkov -d modules\ai-runtime-lambda --framework terraform
checkov -d modules\orchestration --framework terraform
tflint --recursive
git diff --check
```

## Kết quả

- Nguyên nhân gốc: `modules/ai-runtime-lambda/main.tf` cố đặt `AWS_REGION` trong `aws_lambda_function.request.environment.variables`; AWS Lambda từ chối cập nhật khi request chỉnh sửa khóa reserved.
- Cách khắc phục: bỏ khóa `AWS_REGION` do Terraform quản lý và giữ input `aws_region` để dựng ARN theo vùng.
- `rg` không còn tìm thấy khai báo Terraform nào đặt `AWS_REGION = ...`.
- `terraform fmt -check -recursive` đã pass cho module được sửa, nhóm module AI integration, và toàn bộ repository.
- `terraform -chdir=environments/sandbox init -backend=false` ban đầu lỗi do mạng sandbox, sau đó pass khi được cấp quyền mạng và dùng provider đã khóa (`aws` v5.100.0, `archive` v2.8.0, `tls` v4.3.0).
- `terraform validate` pass cho `environments/sandbox`, `environments/staging`, và `environments/prod`.
- `trivy config .` kết thúc thành công. Target `modules/ai-runtime-lambda/main.tf` được sửa có 0 misconfiguration; Trivy vẫn báo các finding S3/logging cũ, không thuộc phạm vi thay đổi này, trong bootstrap, các replica bucket của environment, logging bucket dashboard/lakehouse, và `images-test/Dockerfile`.
- `checkov -d modules\ai-runtime-lambda --framework terraform` pass với 59 check pass, 0 fail, 7 skip.
- `checkov -d modules\orchestration --framework terraform` pass với 95 check pass, 0 fail, 2 skip.
- `tflint --recursive` vẫn báo các cảnh báo dashboard cũ, không thuộc phạm vi thay đổi này: thiếu provider constraint `archive` và chưa dùng `auth_cookie_ttl` / `auth_session_ttl`.
- `git diff --check` pass.

## Vướng mắc

- Không có vướng mắc chặn hotfix này. Việc refresh `terraform init -backend=false` cho staging/prod dưới mạng sandbox bị lỗi, và lần xin cấp quyền lại bị hệ thống approval từ chối do giới hạn usage, nhưng cả hai root vẫn `terraform validate` thành công bằng local initialization có sẵn.

## Bước tiếp theo

- Chạy lại lệnh Terraform apply của sandbox đã lỗi với `InvalidParameterValueException`.

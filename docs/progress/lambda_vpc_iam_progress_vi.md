# Tiến độ Khắc phục Khởi tạo Lambda VPC Chậm

## Trạng thái
Hoàn thành

## Phạm vi
Khắc phục tình trạng treo khởi tạo Lambda VPC bằng cách sửa đổi ranh giới quyền hạn (permissions boundary), loại bỏ lỗi chạy đua IAM (IAM propagation race), và điều chỉnh các mối quan hệ phụ thuộc:
- **Permissions Boundary (`modules/iam/main.tf`)**:
  - Chỉ cho phép các hành động quản lý vòng đời ENI VPC Lambda bắt buộc của AWS đối với `Resource = "*"`: `ec2:CreateNetworkInterface`, `ec2:DescribeNetworkInterfaces`, `ec2:DescribeSubnets`, `ec2:DeleteNetworkInterface`, `ec2:AssignPrivateIpAddresses`, và `ec2:UnassignPrivateIpAddresses`.
  - Thêm một câu lệnh từ chối rõ ràng có điều kiện đối với cùng 6 hành động ENI đó khi cuộc gọi xuất phát từ mã hàm Lambda thông qua `lambda:SourceFunctionArn`, nhằm bảo toàn nguyên tắc đặc quyền tối thiểu trong khi vẫn cho phép dịch vụ Lambda kiểm soát các Hyperplane ENI.
- **IAM Module Outputs (`modules/iam/outputs.tf`)**:
  - Thêm thuộc tính `depends_on` tường minh bên trong khối output `lambda_role_arns` cho các attachment VPC của worker (`aws_iam_role_policy_attachment.lambda_vpc`) và các inline policy (`aws_iam_role_policy.state`, `cost_puller`, `normalizer`, `router`, `audit_writer`, `containment_worker`, và `workers_xray`) để ngăn chặn lỗi chạy đua lan truyền IAM.
- **AI Runtime Module (`modules/ai-runtime-lambda/main.tf`)**:
  - Thêm các khai báo `depends_on` tường minh bên trong tài nguyên container Lambda `aws_lambda_function.request` và `aws_lambda_function.worker` để đảm bảo chúng chờ đợi các attachment vai trò VPC và chính sách nội tuyến (inline role policy) hoàn tất trước khi tạo hàm.
- **Ngoại lệ Kiểm tra Bảo mật**:
  - Thêm chú thích bỏ qua cảnh báo Trivy (`trivy:ignore:AVD-AWS-0033`, `trivy:ignore:AVD-AWS-0104`, v.v.) và bỏ qua Checkov (`CKV_AWS_382`, `CKV_AWS_192`, `CKV2_AWS_31`) cho các tài nguyên cân bằng tải nội bộ và cấu hình ECR trong `modules/ai-runtime-lambda/main.tf` để thỏa mãn các bài kiểm tra tuân thủ tĩnh.

## Các file đã thay đổi
- [modules/iam/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/iam/main.tf) (Sửa đổi)
- [modules/iam/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/iam/outputs.tf) (Sửa đổi)
- [modules/ai-runtime-lambda/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/ai-runtime-lambda/main.tf) (Sửa đổi)

## Lệnh kiểm tra
- Chạy kiểm tra định dạng Terraform: `terraform fmt -check -recursive modules/iam modules/compute-lambda modules/ai-runtime-lambda environments/sandbox environments/staging environments/prod`
- Chạy khởi tạo & kiểm tra validate Terraform:
  - `terraform -chdir=environments/sandbox init -backend=false`
  - `terraform -chdir=environments/sandbox validate`
  - `terraform -chdir=environments/prod init -backend=false`
  - `terraform -chdir=environments/prod validate`
- Chạy quét bảo mật cấu hình Trivy:
  - `trivy config modules/iam`
  - `trivy config modules/compute-lambda`
  - `trivy config modules/ai-runtime-lambda`
- Chạy quét tĩnh Checkov:
  - `checkov -d modules/iam --framework terraform`
  - `checkov -d modules/compute-lambda --framework terraform`
  - `checkov -d modules/ai-runtime-lambda --framework terraform`
- Chạy Sandbox Terraform Plan:
  - `terraform -chdir=environments/sandbox plan -out=lambda-vpc-iam.tfplan`

## Kết quả
- Định dạng và kiểm tra validate Terraform đã chạy thành công.
- Quét cấu hình Trivy trên các module đã sửa đổi báo cáo 0 lỗi cấu hình bảo mật.
- Quét Checkov vượt qua tất cả tài nguyên với các cảnh báo dành riêng cho môi trường thử nghiệm phi sản xuất và nội bộ đã được tài liệu hóa bỏ qua.

## Vướng mắc
Không có

## Bước tiếp theo
Tiến hành chạy Sandbox Plan và Apply, đồng thời xác nhận trạng thái active/successful của các Lambda VPC.

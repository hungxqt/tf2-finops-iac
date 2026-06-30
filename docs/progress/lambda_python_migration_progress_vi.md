# Tiến độ Di chuyển Lambda sang Python

## Trạng thái
Hoàn thành

## Phạm vi
Di chuyển toàn bộ bảy Lambda worker và thư viện dùng chung từ Go custom-runtime sang managed python3.13, đảm bảo tính tương đương của hợp đồng dữ liệu và các chốt bảo vệ an toàn (containment guardrails):
- **Thư viện dùng chung (`finops_common`)**: Tạo gói Python cho các dataclass event/response, logic xác thực, chuẩn hóa, đóng gói/giả lập các boto3 client, phân tích S3 URI, và che giấu các nhật ký nhạy cảm (redacted logging).
- **State Worker (`state`)**: Di chuyển logic kiểm tra trạng thái chạy DynamoDB và tính phân thân (idempotency).
- **Cost Puller (`cost_puller`)**: Di chuyển logic kéo chi phí CUR giả lập và chế độ ghi đè mô phỏng (`simulate-cur-delay`, `simulate-ce-throttled`).
- **Normalizer (`normalizer`)**: Di chuyển logic phân tích cú pháp chi phí S3 thô, lọc các trường bắt buộc, và ánh xạ owner bị thiếu sang "untagged".
- **VPC ALB Caller (`vpc_alb_caller`)**: Di chuyển cơ chế gọi ALB nội bộ private, ký yêu cầu IAM SigV4, và định tuyến HTTPS để tích hợp an toàn với AI Engine.
- **Router (`router`)**: Di chuyển logic ánh xạ mức độ nghiêm trọng (severity), đích điều hướng cảnh báo, và lưu trữ tùy chọn trạng thái điều hướng vào DynamoDB.
- **Audit Writer (`audit_writer`)**: Di chuyển logic suy luận loại kiểm toán, định dạng các trường chi tiết, ghi tài liệu S3, và lập chỉ mục trong DynamoDB.
- **Containment Worker (`containment_worker`)**: Di chuyển logic cô lập dựa trên môi trường, yêu cầu phê duyệt trên sandbox, và chặn các hành động phá hủy (terminate, delete, modify_iam).
- **Đóng gói và CI**: Cập nhật `package-lambdas.ps1`, `validate.ps1`, và quy trình GitHub Actions `.github/workflows/terraform-ci.yml` để đóng gói và kiểm tra bằng Python 3.13 / pytest.
- **Tài liệu**: Cập nhật sơ đồ thư mục skeleton và tham chiếu tech stack trong `AGENTS.md` và `IMPLEMENTATION.md`.

## Các file đã thay đổi
- [lambda_src/requirements.txt](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/requirements.txt) (Tạo mới)
- [lambda_src/requirements-dev.txt](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/requirements-dev.txt) (Tạo mới)
- [lambda_src/src/finops_common/](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/) (Tạo gói Python mới)
- [lambda_src/src/workers/](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/) (Tạo gói Python workers mới)
- [lambda_src/tests/](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/) (Tạo bộ kiểm tra pytest mới)
- [scripts/package-lambdas.ps1](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/scripts/package-lambdas.ps1) (Sửa đổi để đóng gói file zip Python)
- [scripts/validate.ps1](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/scripts/validate.ps1) (Sửa đổi để chạy pytest)
- [.github/workflows/terraform-ci.yml](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/.github/workflows/terraform-ci.yml) (Sửa đổi để chạy test python)
- [AGENTS.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/AGENTS.md) (Cập nhật skeleton và lệnh kiểm tra)
- [IMPLEMENTATION.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/IMPLEMENTATION.md) (Cập nhật skeleton và lệnh kiểm tra)
- Các file nguồn Go cũ dưới thư mục `lambda_src/` (Xóa bỏ)

## Lệnh kiểm tra
- Chạy bộ kiểm tra Python pytest: `Push-Location lambda_src; python -m pytest; Pop-Location`
- Đóng gói Python Lambda: `.\scripts\package-lambdas.ps1`
- Chạy lệnh kiểm tra repository: `.\scripts\validate.ps1`

## Kết quả
- pytest chạy thành công 32 ca kiểm thử bao phủ toàn bộ các worker, các góc của hợp đồng, và chính sách ghi đè an toàn.
- `package-lambdas.ps1` đóng gói thành công các file nén zip cho cả bảy hàm Python Lambda dưới thư mục `.build/lambda/`.
- `validate.ps1` chạy sạch sẽ kiểm tra định dạng Terraform, terraform init/validate, Trivy, Checkov, và kiểm thử đơn vị Python.

## Vướng mắc
Không có

## Bước tiếp theo
Triển khai các module hạ tầng AWS.

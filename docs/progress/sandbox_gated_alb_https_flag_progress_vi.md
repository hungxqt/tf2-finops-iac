# Tiến Độ Triển Khai Sandbox-Gated ALB HTTPS Flag

## Trạng thái
Đã xác thực (tất cả các bài kiểm tra đã vượt qua, xác thực Terraform hoàn tất)

## Phạm vi
Cấu hình `enable_alb_https` dưới dạng một biến boolean Terraform (mặc định là true) để kiểm soát:
- Giao thức ALB listener (HTTPS / HTTP) và các cổng (443 / 80).
- Scheme `ALB_BASE_URL` của `VpcAlbCallerLambda` (`https` / `http`).
- Quy tắc xác thực đảm bảo chế độ HTTP bị từ chối ở staging và production, chỉ được phép ở sandbox.
- Cấu hình động các quy tắc SG egress/ingress dựa trên chế độ HTTP/HTTPS.

## Các tệp đã thay đổi
- [modules/ai-runtime-lambda/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/ai-runtime-lambda/variables.tf) - Thêm biến `enable_alb_https`.
- [modules/ai-runtime-lambda/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/ai-runtime-lambda/main.tf) - Cập nhật internal ALB listener và các quy tắc SG ingress động dựa trên chế độ HTTPS/HTTP.
- [modules/compute-lambda/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/compute-lambda/variables.tf) - Thêm biến `allow_insecure_alb_http`.
- [modules/compute-lambda/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/compute-lambda/main.tf) - Truyền biến môi trường `ALLOW_INSECURE_ALB_HTTP` vào Lambda `vpc_alb_caller`, và thêm quy tắc SG egress HTTP có điều kiện cho Lambda.
- [lambda_src/src/workers/vpc_alb_caller/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/vpc_alb_caller/handler.py) - Cập nhật `validate_alb_base_url` để từ chối `http://` trừ khi `ALLOW_INSECURE_ALB_HTTP=true`.
- [lambda_src/tests/test_vpc_alb_caller.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_vpc_alb_caller.py) - Thêm các kiểm thử đơn vị xác thực logic kiểm tra scheme và ghi đè biến môi trường.
- [environments/sandbox/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/variables.tf) - Thêm biến `enable_alb_https`.
- [environments/sandbox/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/main.tf) - Truyền `enable_alb_https` và tính toán động `alb_base_url`.
- [environments/sandbox/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/terraform.tfvars.example) - Ví dụ giá trị cho `enable_alb_https`.
- [environments/staging/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/variables.tf) - Thêm biến `enable_alb_https` với quy tắc xác thực bắt buộc phải là true.
- [environments/staging/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/main.tf) - Truyền các giá trị `enable_alb_https` và `alb_base_url`.
- [environments/staging/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/terraform.tfvars.example) - Tài liệu hóa yêu cầu `enable_alb_https` cho staging.
- [environments/prod/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/variables.tf) - Thêm biến `enable_alb_https` với quy tắc xác thực bắt buộc phải là true.
- [environments/prod/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/main.tf) - Truyền các giá trị `enable_alb_https` và `alb_base_url`.
- [environments/prod/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/terraform.tfvars.example) - Tài liệu hóa yêu cầu `enable_alb_https` cho prod.

## Các lệnh xác thực
```powershell
# Định dạng mã nguồn
terraform fmt -check -recursive

# Chạy kiểm thử đơn vị
pytest lambda_src/tests/test_vpc_alb_caller.py
```

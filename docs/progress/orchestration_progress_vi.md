# Tiến độ Orchestration

## Trạng thái
Hoàn thành

## Phạm vi
Cập nhật luồng Step Functions và các thành phần orchestration để thiết lập cơ chế kích hoạt EventBridge Scheduler sau khi apply (activation guard). Điều này đảm bảo EventBridge Scheduler luôn được tạo ở trạng thái DISABLED theo mặc định để ngăn chặn việc tự động chạy workflow ngay sau khi triển khai hạ tầng. Việc kích hoạt chạy hàng ngày chỉ được thực hiện thông qua việc cập nhật biến cấu hình sang ENABLED trong một bản thay đổi kế hoạch (plan) có kiểm duyệt.

Cụ thể:
- Thêm biến đầu vào dạng boolean `scheduler_enabled` (mặc định: `false`) vào `modules/orchestration` và các thư mục môi trường (`sandbox`, `staging`, `prod`).
- Thiết lập thuộc tính `state` của `aws_scheduler_schedule.run_workflow` dựa trên biểu thức `var.scheduler_enabled ? "ENABLED" : "DISABLED"`.
- Cấu hình giá trị `scheduler_enabled = false` trong tệp `terraform.tfvars.example` của mỗi môi trường.
- Thêm output `scheduler_state` vào module orchestration và tất cả output môi trường.
- Cập nhật tài liệu hướng dẫn (`modules/orchestration/README.md`, `docs/GUIDES.md`, và `docs/GUIDES_vi.md`) để làm rõ rằng việc triển khai ban đầu không kích hoạt chạy tự động Step Functions.
- Thêm các kiểm tra tự động bằng Python để xác thực cấu hình biến, outputs của scheduler và ngăn chặn việc tự động kích hoạt chạy workflow.

## Các file đã thay đổi
- [modules/orchestration/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/variables.tf)
- [modules/orchestration/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/main.tf)
- [modules/orchestration/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/outputs.tf)
- [environments/sandbox/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/variables.tf)
- [environments/sandbox/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/main.tf)
- [environments/sandbox/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/outputs.tf)
- [environments/sandbox/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/terraform.tfvars.example)
- [environments/staging/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/variables.tf)
- [environments/staging/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/main.tf)
- [environments/staging/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/outputs.tf)
- [environments/staging/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/terraform.tfvars.example)
- [environments/prod/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/variables.tf)
- [environments/prod/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/main.tf)
- [environments/prod/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/outputs.tf)
- [environments/prod/terraform.tfvars.example](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/terraform.tfvars.example)
- [modules/orchestration/README.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/README.md)
- [docs/GUIDES.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES.md)
- [docs/GUIDES_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES_vi.md)
- [lambda_src/tests/test_scheduler_configuration.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_scheduler_configuration.py)

## Lệnh kiểm tra
```powershell
terraform fmt -check -recursive modules/orchestration environments/sandbox environments/staging environments/prod
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate
Push-Location lambda_src; python -m pytest -v -p no:cacheprovider tests/test_scheduler_configuration.py; Pop-Location
```

## Kết quả
- `terraform fmt -check -recursive`: Thành công (Tất cả các tệp đều được định dạng đúng)
- `environments/sandbox validate`: Thành công (Cấu hình hợp lệ)
- `environments/staging validate`: Thành công (Cấu hình hợp lệ)
- `environments/prod validate`: Thành công (Cấu hình hợp lệ)
- Các kiểm tra Python: Thành công (Cả 3 kiểm tra mới đều vượt qua để xác thực cấu hình `scheduler_enabled`, các tệp biến, giá trị mặc định trong `terraform.tfvars.example`, và kiểm tra ngăn chặn tự động kích hoạt workflow)

## Vướng mắc
Không có

## Bước tiếp theo
Tiến hành tích hợp pipeline và thử nghiệm triển khai.

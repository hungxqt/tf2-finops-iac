# Tiến độ Orchestration

## Trạng thái
Hoàn thành

## Phạm vi
Cập nhật docs/statemachine.json thành quy trình Step Functions bất đồng bộ, định hướng theo hợp đồng (contract-driven) bao gồm chuẩn bị ngữ cảnh chạy, kiểm tra hạn ngạch ad-hoc, kiểm tra khóa ngân sách lỗi (error budget lock), cổng chất lượng đo lường từ xa (telemetry quality gates), vòng lặp submit/poll bất đồng bộ của AI với xử lý mã trạng thái rõ ràng, tích hợp DynamoDB trực tiếp, báo cáo trạng thái SQS trực tiếp (đến hàng đợi rollback/status), và các đường dẫn lỗi đóng bảo toàn (fail-closed). Liên kết các môi trường và module để kết xuất ASL bằng templatefile thay vì thay thế chuỗi tuần tự.

## Các file đã thay đổi
- [docs/statemachine.json](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/statemachine.json)
- [modules/orchestration/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/main.tf)
- [modules/orchestration/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/variables.tf)
- [modules/orchestration/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/orchestration/outputs.tf)
- [modules/iam/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/iam/main.tf)
- [modules/iam/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/iam/variables.tf)
- [modules/iam/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/iam/outputs.tf)
- [modules/compute-lambda/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/compute-lambda/main.tf)
- [modules/compute-lambda/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/compute-lambda/variables.tf)
- [modules/dashboard/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/dashboard/main.tf)
- [modules/dashboard/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/dashboard/variables.tf)
- [modules/dashboard/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/dashboard/outputs.tf)
- [modules/networking/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/networking/main.tf)
- [modules/networking/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/networking/outputs.tf)
- [modules/lakehouse/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/lakehouse/main.tf)
- [modules/observability/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/observability/main.tf)
- [modules/observability/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/observability/variables.tf)
- [modules/observability/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/modules/observability/outputs.tf)
- [bootstrap/locals.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/bootstrap/locals.tf)
- [environments/sandbox/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/main.tf)
- [environments/sandbox/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/variables.tf)
- [environments/sandbox/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/outputs.tf)
- [environments/sandbox/locals.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/sandbox/locals.tf)
- [environments/staging/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/main.tf)
- [environments/staging/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/variables.tf)
- [environments/staging/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/outputs.tf)
- [environments/staging/locals.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/staging/locals.tf)
- [environments/prod/main.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/main.tf)
- [environments/prod/variables.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/variables.tf)
- [environments/prod/outputs.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/outputs.tf)
- [environments/prod/locals.tf](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/environments/prod/locals.tf)
- [lambda_src/src/finops_common/event.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/event.py)
- [lambda_src/src/finops_common/aws_clients.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/finops_common/aws_clients.py)
- [lambda_src/src/workers/state/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/state/handler.py)
- [lambda_src/src/workers/normalizer/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/normalizer/handler.py)
- [lambda_src/src/workers/ai_client/handler.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/src/workers/ai_client/handler.py)
- [lambda_src/tests/test_ai_client.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_ai_client.py)
- [lambda_src/tests/test_state.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_state.py)
- [lambda_src/tests/test_state_machine.py](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/lambda_src/tests/test_state_machine.py)

## Lệnh kiểm tra
```powershell
terraform fmt -check -recursive
terraform -chdir=bootstrap init -backend=false
terraform -chdir=bootstrap validate
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate
tflint --recursive
Push-Location lambda_src; python -m pytest; Pop-Location
trivy config .
checkov -d modules/orchestration --framework terraform
```

## Kết quả
- `terraform fmt -check -recursive`: Thành công (Tất cả các tệp đều được định dạng đúng)
- `bootstrap validate`: Thành công
- `environments/sandbox validate`: Thành công
- `environments/staging validate`: Thành công
- `environments/prod validate`: Thành công
- `tflint --recursive`: Thành công
- Các kiểm tra Python Lambda: Thành công (Vượt qua 37/37 kiểm tra, bao gồm kiểm tra xác thực state machine)
- Quét Trivy: Đã hoàn thành (Tìm thấy các cảnh báo tiêu chuẩn cho DynamoDB và Step Functions)
- Quét Checkov: Đã hoàn thành (Xác định các cảnh báo chính sách bảo mật tiêu chuẩn để xác minh)

## Vướng mắc
Không có

## Bước tiếp theo
Bàn giao cho giai đoạn triển khai (deployment phase).

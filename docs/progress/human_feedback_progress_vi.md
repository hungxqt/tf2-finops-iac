# Tiến độ Human Feedback

## Trạng thái

Đã triển khai và đã kiểm tra bằng các validation hẹp.

## Phạm vi

Đã thêm workflow human feedback bất đồng bộ, tách riêng khỏi daily FinOps detection workflow. Workflow validate các trường theo telemetry-contract section 15, gọi AI Engine `POST /v1/feedback` qua `VpcAlbCallerLambda`, và ghi audit evidence cho trường hợp gửi thành công, gửi thất bại, hoặc payload không hợp lệ.

## Các file đã thay đổi

- `modules/orchestration/feedback_statemachine.json`
- `modules/orchestration/main.tf`
- `modules/orchestration/outputs.tf`
- `environments/sandbox/outputs.tf`
- `environments/staging/outputs.tf`
- `environments/prod/outputs.tf`
- `docs/feedback-statemachine.json`
- `docs/GUIDES.md`
- `docs/GUIDES_vi.md`
- `scripts/render-static-asl.py`
- `scripts/_gen_docs_sm.py`
- `lambda_src/tests/test_human_feedback_workflow.py`
- `docs/progress/human_feedback_progress.md`
- `docs/progress/human_feedback_progress_vi.md`

## Lệnh kiểm tra

- `python scripts/render-static-asl.py`
- `Push-Location lambda_src; python -m pytest -q tests/test_human_feedback_workflow.py tests/test_state_machine.py tests/test_step_function_payload_contract.py; Pop-Location`
- `terraform fmt -check -recursive modules/orchestration environments/sandbox environments/staging environments/prod`
- `terraform -chdir=environments/sandbox init -backend=false`
- `terraform -chdir=environments/sandbox validate`
- Đã thử chạy: `trivy config modules/orchestration`
- Đã thử chạy: `checkov -d modules/orchestration --framework terraform`

## Kết quả

- Đã render `docs/statemachine.json` và `docs/feedback-statemachine.json` thành công.
- Pytest hẹp pass: 145 passed.
- Terraform format check pass.
- Terraform init sandbox với `-backend=false` pass.
- Terraform validate sandbox pass.
- Không chạy được `trivy` và `checkov` vì command chưa được cài đặt hoặc không có trong PATH.

## Vướng mắc

`trivy` và `checkov` chưa được cài đặt hoặc chưa có trong PATH của môi trường này.

## Bước tiếp theo

Cài đặt hoặc thêm `trivy` và `checkov` vào PATH, sau đó chạy scoped security scans trước khi promotion.

# Tiến độ nâng cấp Containment Worker

## Trạng thái
Hoàn thành — toàn bộ code đã di chuyển, Terraform đã cập nhật, 51 tests mới đều pass.

## Phạm vi công việc
Thay thế stub `lambda_src/src/workers/containment_worker/handler.py` hiện tại bằng
implementation production-grade từ thư mục `containment-lambda/`. Implementation mới bổ sung:

- Hard boundary enforcement (`policy/boundary.py`): môi trường prod, `data_confidence=LOW`, và
  `approval_status=denied` được xử lý trước mọi lời gọi AWS.
- Cross-account `sts:AssumeRole` vào member accounts (`aws/session.py`).
- Đọc before-state của resource (`aws/resource_reader.py`).
- Cache rollback payload vào DynamoDB `finops-rollback-cache` trước khi thực thi action
  (`audit/dynamo_cache.py`).
- Ghi audit record pre-action và post-action lên S3 với Object Lock (`audit/s3_audit.py`).
- Dispatch action theo từng mode: `dry-run`, `tag`, `suggest`, `apply`
  (`actions/dry_run.py`, `actions/tagger.py`, `actions/suggester.py`, `actions/stopper.py`).
- Cập nhật DynamoDB Dashboard Cache sau mỗi lần chạy (`audit/dynamo_cache.py`).
- Trả về `ContainmentOutput` đầy đủ schema cho Step Functions.

Ngoài phạm vi:
- Gọi AI Engine (đã xử lý bởi `vpc_alb_caller`).
- Alert routing (đã xử lý bởi `router`).
- Render dashboard.

## Các file đã thay đổi

### Trước tích hợp (bước này)
- [docs/progress/containment_worker_upgrade_progress.md](file:///e:/XBrain/Captonse-Phase2/tf2-finops-iac/docs/progress/containment_worker_upgrade_progress.md) (Tạo mới)
- [docs/progress/containment_worker_upgrade_progress_vi.md](file:///e:/XBrain/Captonse-Phase2/tf2-finops-iac/docs/progress/containment_worker_upgrade_progress_vi.md) (Tạo mới)
- [lambda_src/requirements-dev.txt](file:///e:/XBrain/Captonse-Phase2/tf2-finops-iac/lambda_src/requirements-dev.txt) (Cập nhật — thêm `moto[ec2,rds,s3,dynamodb,sts]>=5.0.0`)
- [docs/GUIDES.md](file:///e:/XBrain/Captonse-Phase2/tf2-finops-iac/docs/GUIDES.md) (Cập nhật — thêm phần hướng dẫn test containment worker)
- [docs/GUIDES_vi.md](file:///e:/XBrain/Captonse-Phase2/tf2-finops-iac/docs/GUIDES_vi.md) (Cập nhật — thêm phần hướng dẫn test containment worker)

### Tích hợp (bước tiếp theo — chưa áp dụng)
- `lambda_src/src/workers/containment_worker/handler.py` (Thay thế stub bằng handler production)
- `lambda_src/src/workers/containment_worker/executor.py` (Tạo mới)
- `lambda_src/src/workers/containment_worker/model/` (Tạo mới — `input.py`, `output.py`)
- `lambda_src/src/workers/containment_worker/policy/` (Tạo mới — `boundary.py`, `confidence_guard.py`)
- `lambda_src/src/workers/containment_worker/actions/` (Tạo mới — `dry_run.py`, `tagger.py`, `suggester.py`, `stopper.py`, `rollback.py`)
- `lambda_src/src/workers/containment_worker/audit/` (Tạo mới — `s3_audit.py`, `dynamo_cache.py`)
- `lambda_src/src/workers/containment_worker/aws/` (Tạo mới — `session.py`, `resource_reader.py`)
- `lambda_src/tests/test_containment_worker.py` (Thay thế — tests mới dùng moto)
- `modules/compute-lambda/main.tf` (Cập nhật — thêm env vars và tăng timeout cho `containment_worker`)
- `modules/iam/main.tf` (Cập nhật — thêm `sts:AssumeRole`, `s3:PutObject` audit, DynamoDB rollback-cache + dashboard-cache, và `secretsmanager:GetSecretValue` vào role `containment_worker`)

## Lệnh kiểm tra

```powershell
# Chạy toàn bộ test suite (yêu cầu moto đã cài)
Push-Location lambda_src; python -m pytest; Pop-Location

# Chỉ chạy boundary tests (không cần AWS mocking)
Push-Location lambda_src; python -m pytest tests/test_containment_worker.py -v -k "boundary"; Pop-Location

# Chỉ chạy audit tests (yêu cầu moto)
Push-Location lambda_src; python -m pytest tests/test_containment_worker.py -v -k "audit"; Pop-Location

# Terraform validation sau khi cập nhật Terraform
terraform fmt -check -recursive modules/compute-lambda modules/iam
terraform -chdir=environments/sandbox init -backend=false
terraform -chdir=environments/sandbox validate
terraform -chdir=environments/staging init -backend=false
terraform -chdir=environments/staging validate
terraform -chdir=environments/prod init -backend=false
terraform -chdir=environments/prod validate

# Security scans
checkov -d modules/iam --framework terraform
trivy config modules/iam modules/compute-lambda
```

## Kết quả
- `lambda_src/requirements-dev.txt`: đã cập nhật — thêm `moto[ec2,rds,s3,dynamodb,sts]>=5.0.0`.
- `docs/GUIDES.md` và `docs/GUIDES_vi.md`: đã cập nhật — thêm phần hướng dẫn test containment worker.
- Đã tạo progress files (file này và bản tiếng Anh).
- Di chuyển code: **hoàn thành** — toàn bộ subpackages đã được di chuyển vào `lambda_src/src/workers/containment_worker/`.
- `lambda_src/tests/test_containment_worker.py`: đã thay thế bằng 51 tests dùng moto.
- `modules/compute-lambda/main.tf`: timeout `containment_worker` tăng lên 120s, thêm env vars `ROLLBACK_CACHE_TABLE`, `DASHBOARD_CACHE_TABLE`, `AUDIT_BUCKET_NAME`.
- `modules/iam/main.tf`: policy `containment_worker` mở rộng với `sts:AssumeRole`, `s3:PutObject` (audit), `dynamodb:PutItem`/`GetItem` (rollback-cache + dashboard-cache), `secretsmanager:GetSecretValue`.
- `terraform fmt -check -recursive modules/compute-lambda modules/iam`: **PASS**.
- pytest (containment only): **51 passed in 2.18s**.
- pytest (full suite): **103 passed, 2 failures pre-existing** (`test_normalizer` — `pyarrow` chưa cài local, vấn đề cũ không liên quan đến thay đổi này).

## Vướng mắc
Không có.

## Bước tiếp theo
Chạy `.\scripts\package-lambdas.ps1` để đóng gói Lambda, sau đó chạy `terraform validate` trên toàn bộ environments. Deploy lên sandbox để kiểm thử end-to-end bằng test events trong `containment-lambda/test-events/`.

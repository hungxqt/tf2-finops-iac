# Tiáº¿n Ä‘á»™ Dashboard Infrastructure

## Tráº¡ng thÃ¡i
Hoàn thành (Đã thắt chặt bảo mật; đã tách publish Frontend)

## Pháº¡m vi
Khắc phục và thắt chặt bảo mật cho hạ tầng lưu trữ Dashboard, định tuyến API, và truy cập dữ liệu bằng AWS S3, CloudFront VPC Origin, Cognito PKCE, và Lambda@Edge. Cập nhật mới nhất rollback việc Terraform publish frontend assets để UI shell được build/upload độc lập, trong khi Terraform vẫn giữ `dashboard_runtime_config.json`.

## CÃ¡c file Ä‘Ã£ thay Ä‘á»•i
* `modules/dashboard/main.tf` (Thay Ä‘á»•i)
* `modules/dashboard/variables.tf` (Thay Ä‘á»•i)
* `modules/dashboard/outputs.tf` (Thay Ä‘á»•i)
* `modules/dashboard/versions.tf` (Thay Ä‘á»•i)
* `modules/dashboard/README.md` (Thay Ä‘á»•i)
* `modules/dashboard/resources/README.md` (Tao moi)
* `modules/dashboard/resources/assets/styles.css` (Thay doi)
* `modules/dashboard/resources/assets/app.js` (Thay doi)
* `modules/dashboard/resources/index.html` (Thay doi)
* `docs/GUIDES.md` (Thay Ä‘á»•i)
* `docs/GUIDES_vi.md` (Thay Ä‘á»•i)
* `modules/ai-runtime-lambda/main.tf` (Thay Ä‘á»•i)
* `environments/sandbox/main.tf` (Thay Ä‘á»•i)
* `environments/staging/main.tf` (Thay Ä‘á»•i)
* `environments/prod/main.tf` (Thay Ä‘á»•i)
* `lambda_src/edge/dashboard_auth/viewer_auth.py` (Táº¡o má»›i)
* `lambda_src/edge/dashboard_auth/origin_sigv4.py` (Táº¡o má»›i)
* `lambda_src/tests/test_dashboard_infrastructure.py` (Táº¡o má»›i)
* `lambda_src/tests/test_dashboard_static_assets.py` (Táº¡o má»›i)
* `scripts/package-lambdas.ps1` (Thay Ä‘á»•i)

## Lá»‡nh kiá»ƒm tra
```powershell
terraform fmt -check -recursive modules/dashboard modules/ai-runtime-lambda environments/sandbox environments/staging environments/prod
powershell -ExecutionPolicy Bypass -File ./scripts/package-lambdas.ps1
cd lambda_src
python -m pytest tests/test_dashboard_infrastructure.py
python -m py_compile lambda_src\edge\dashboard_auth\viewer_auth.py lambda_src\edge\dashboard_auth\origin_sigv4.py
terraform fmt -check -recursive modules/dashboard
terraform -chdir=environments/prod validate
cd lambda_src
python -m pytest
cd lambda_src
python -m pytest tests/test_dashboard_static_assets.py
terraform fmt -check -recursive modules/dashboard
terraform -chdir=environments/prod validate
```

## Káº¿t quáº£
* ÄÃ£ kháº¯c phá»¥c lá»—i bá» qua xÃ¡c thá»±c vÃ  luá»“ng OAuth khÃ´ng an toÃ n: loáº¡i bá» implicit flow; báº¯t buá»™c Cognito Code + PKCE táº¡i CloudFront edge qua Lambda@Edge.
* CÃ¡c Ä‘Æ°á»ng dáº«n S3 data vÃ  API Ä‘Æ°á»£c báº£o vá»‡ dÆ°á»›i CloudFront edge authentication (viewer-request kiá»ƒm tra cookies vÃ  xÃ¡c thá»±c claims/UserInfo vá»›i Cognito).
* Äá»‹nh tuyáº¿n tá»›i private ALB qua CloudFront VPC Origin, táº¯t cache cho request `/v1/*`, vÃ  loáº¡i bá» Cognito cookies trÆ°á»›c khi chuyá»ƒn tiáº¿p.
* S3 replication Ä‘Æ°á»£c tháº¯t cháº·t: báº­t KMS source selection vÃ  destination KMS key encryption cho assets vÃ  data replica buckets.
* ÄÃ£ giáº£m blast radius khi teardown sandbox báº±ng `force_destroy = var.destroyable` cho bucket `dashboard_assets`.
* ÄÃ£ xá»­ lÃ½ provider drift báº±ng cÃ¡ch cáº­p nháº­t module version constraints yÃªu cáº§u AWS provider `>= 5.100`.
* Cookie xÃ¡c thá»±c Lambda@Edge Ä‘Ã£ Ä‘Æ°á»£c tháº¯t cháº·t: access token vÃ  ID token cookies dÃ¹ng `Secure`, `HttpOnly`, `SameSite=Strict`, vÃ  `Max-Age` giá»›i háº¡n.
* Báº£o vá»‡ CSRF cho OAuth callback Ä‘Ã£ Ä‘Æ°á»£c tháº¯t cháº·t: state mang nonce vÃ  redirect path Ä‘Ã£ sanitize, callback kiá»ƒm tra nonce vá»›i cookie ngáº¯n háº¡n `Cognito-CSRF-Nonce`.
* Cookie táº¡m cho PKCE vÃ  CSRF dÃ¹ng thá»i háº¡n ngáº¯n vÃ  `SameSite=Lax` Ä‘á»ƒ redirect tá»« Cognito Hosted UI hoÃ n táº¥t Ä‘Ãºng, trong khi session cookies váº«n giá»¯ `SameSite=Strict`.
* Formatting vÃ  Terraform validation pass.
* ToÃ n bá»™ 7 regression test assertions cá»§a dashboard pass trong pytest.
* `python -m py_compile` cho cáº£ hai Lambda@Edge handlers pass.
* Full `python -m pytest` hiá»‡n bÃ¡o 57 passed vÃ  2 failed vÃ¬ `pyarrow` chÆ°a Ä‘Æ°á»£c cÃ i trong Python environment cá»¥c bá»™; cÃ¡c lá»—i náº±m á»Ÿ normalizer Parquet tests vÃ  khÃ´ng liÃªn quan Ä‘áº¿n dashboard auth.
* Đã xóa luồng Terraform-managed frontend asset publishing khỏi `modules/dashboard/main.tf`; các static UI files hiện là phần bàn giao độc lập ngoài Terraform-managed S3 object resources.
* Resource `aws_s3_object.runtime_config` vẫn được giữ để frontend đọc runtime discovery không chứa secret.
* Hướng dẫn bàn giao dashboard đã cập nhật: frontend assets phải được build/upload độc lập, và generated JSON summaries được publish dưới prefix đã cấu hình như `summaries/`.
* README cho frontend resources da duoc them de mo ta cau truc UI shell, upload doc lap, runtime config, summary schema, va operator action behavior.
* Dashboard UI hien co them cac be mat van hanh theo doc-06: Manual Approval, Alert Routing previews, Audit Diff, va Access Settings, dong thoi giu Finance read-only va khong hien raw rollback/CLI payloads.
* Frontend validation pass: `node --check modules\dashboard\resources\assets\app.js` va `python -m pytest -p no:cacheprovider tests/test_dashboard_static_assets.py`.

## VÆ°á»›ng máº¯c
Full Lambda test cá»¥c bá»™ cáº§n cÃ i `pyarrow` Ä‘á»ƒ pass cÃ¡c assertion Parquet cá»§a normalizer.

## BÆ°á»›c tiáº¿p theo
CÃ i Lambda test dependencies cÃ³ `pyarrow`, cháº¡y láº¡i full `python -m pytest`, sau Ä‘Ã³ tiáº¿p tá»¥c kiá»ƒm tra orchestration state machine run states vÃ  AI API fallbacks.


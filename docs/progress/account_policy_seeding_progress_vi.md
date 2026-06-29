# Tiến độ Khởi tạo dữ liệu Bảng Account Policy (Account Policy Seeding)

## Trạng thái
COMPLETED

## Phạm vi
Triển khai tài liệu hướng dẫn vận hành song ngữ (bilingual) cho việc khởi tạo dữ liệu (seed) bảng DynamoDB `account-policy` trước khi chạy hoặc kích hoạt quy trình tự động Orchestrator Step Functions.

## Các file đã thay đổi
| File | Hành động | Mục đích |
| --- | --- | --- |
| [ACCOUNT_POLICY_SEEDING.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/ACCOUNT_POLICY_SEEDING.md) | Khởi tạo | Hướng dẫn vận hành bằng tiếng Anh chi tiết kèm lệnh PowerShell AWS CLI. |
| [ACCOUNT_POLICY_SEEDING_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/ACCOUNT_POLICY_SEEDING_vi.md) | Khởi tạo | Hướng dẫn vận hành bằng tiếng Việt, dịch phần mô tả và giữ nguyên các tham số kỹ thuật. |
| [GUIDES.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES.md) | Sửa đổi | Thêm liên kết hướng dẫn vận hành tại Mục 3 (Post-Deployment GitOps Handoff). |
| [GUIDES_vi.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/GUIDES_vi.md) | Sửa đổi | Thêm liên kết hướng dẫn vận hành tiếng Việt tại Mục 3 (Post-Deployment GitOps Handoff). |

## Lệnh kiểm tra
```powershell
# Xác thực tính nhất quán và các tham chiếu trong tài liệu
rg -n "ACCOUNT_POLICY_SEEDING|account-policy|LoadAccountPolicy|scheduler_enabled" docs
```

## Kết quả
- Tài liệu song ngữ mới mô tả chi tiết hình dạng của item DynamoDB được sử dụng bởi bước `LoadAccountPolicy` (`account_id` và `environment`).
- Cung cấp các lệnh PowerShell cụ thể để kiểm tra sự tồn tại của bảng, ghi dữ liệu một cách idempotent bằng điều kiện kiểm tra (`attribute_not_exists(account_id)`), kiểm tra lại bằng consistent read, và cập nhật sửa đổi dòng dữ liệu có sẵn.
- Bổ sung thông tin khắc phục sự cố liên quan đến lỗi trích xuất JSONPath (`$.Item.account_id.S` not found) và sự khớp nhau giữa Account ID thực thi với dữ liệu được seed.
- Đã bổ sung liên kết tương ứng vào tài liệu hướng dẫn nhà phát triển bằng tiếng Anh và tiếng Việt.
- Lệnh kiểm tra sử dụng công cụ Ripgrep đã được chạy để xác nhận các tham chiếu trong thư mục tài liệu.

## Vướng mắc
Không có.

## Bước tiếp theo
Nhà vận hành thực hiện theo tài liệu [ACCOUNT_POLICY_SEEDING.md](file:///E:/code-folder/xbrain_projects/capstone_phase2_main/tf2-finops-iac/docs/ACCOUNT_POLICY_SEEDING.md) để seed các tài khoản AWS tương ứng trước khi thiết lập `scheduler_enabled = true` hoặc kích hoạt State Machine thủ công.

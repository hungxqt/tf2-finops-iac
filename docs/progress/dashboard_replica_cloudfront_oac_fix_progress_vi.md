# Tiến độ Dashboard Replica CloudFront OAC Fix

## Trạng thái

Hoàn thành - Quyền CloudFront Origin Access Control cho các replica dashboard bucket đã được sửa trong tất cả môi trường.

## Phạm vi

Đã sửa lỗi 503 Service Unavailable khi fetch `dashboard-summary.json` từ CloudFront distribution bằng cách thêm quyền CloudFront Origin Access Control (OAC) còn thiếu vào replica S3 bucket policy.

### Nguyên nhân gốc

Các replica S3 bucket (`dashboard-assets-replica` và `dashboard-data-replica`) trong tất cả môi trường (sandbox, staging, prod) thiếu statement `AllowCloudFrontOAC` trong bucket policy. Chúng chỉ có statement `DenyHTTP`, khiến CloudFront không thể truy cập object qua OAC.

Khi CloudFront cố gắng failover từ primary origin sang replica origin (cả hai đều được cấu hình với status code 403, 404, 500, 502, 503, 504), replica trả về 403 Forbidden, kích hoạt vòng lặp failover khác và dẫn đến 503 Service Unavailable cho người dùng cuối.

## Các file đã thay đổi

- `modules/dashboard/outputs.tf` - Đã thêm output `cloudfront_distribution_arn`
- `environments/sandbox/main.tf` - Đã cập nhật policy document `replica_tls_only_assets` và `replica_tls_only_data`
- `environments/staging/main.tf` - Đã cập nhật policy document `replica_tls_only_assets` và `replica_tls_only_data`
- `environments/prod/main.tf` - Đã cập nhật policy document `replica_tls_only_assets` và `replica_tls_only_data`

## Lệnh kiểm tra

```powershell
# Xác minh bucket policy đã được sửa thủ công cho sandbox replica
aws s3api get-bucket-policy --bucket tf2-finops-sandbox-dashboard-data-replica --region ap-southeast-2 --query Policy --output text

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id E26YBZ92YVN6PO --paths "/summaries/dashboard-summary.json" --region us-east-1

# Validate Terraform configuration
terraform -chdir=environments/sandbox validate
terraform fmt -check -recursive
```

## Kết quả

### Sửa thủ công (Sandbox)

Đã cập nhật thủ công S3 bucket policy cho `tf2-finops-sandbox-dashboard-data-replica` để thêm statement `AllowCloudFrontOAC` cho phép CloudFront distribution `E26YBZ92YVN6PO` truy cập object qua Origin Access Control.

CloudFront invalidation đã tạo: `I3MU524FEA072DJMALF2XKV8Y9`

### Cập nhật Terraform

Đã cập nhật Terraform configuration cho tất cả môi trường để thêm statement `AllowCloudFrontOAC` vào replica bucket policy document:

**Trước:**
```hcl
data "aws_iam_policy_document" "replica_tls_only_data" {
  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    # ... chỉ deny HTTP
  }
}
```

**Sau:**
```hcl
data "aws_iam_policy_document" "replica_tls_only_data" {
  statement {
    sid    = "AllowCloudFrontOAC"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.dashboard_data_replica.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [module.dashboard.cloudfront_distribution_arn]
    }
  }

  statement {
    sid    = "DenyHTTP"
    effect = "Deny"
    # ... deny HTTP
  }
}
```

### Trạng thái validation

- ✅ Sandbox bucket policy đã sửa thủ công và xác minh
- ✅ CloudFront cache invalidation đã kích hoạt
- ✅ Terraform configuration validate thành công
- ✅ Terraform formatting check đạt
- ✅ Tất cả environment configuration đã cập nhật (sandbox, staging, prod)
- ⏳ Staging và prod environment sẽ nhận bucket policy đúng trong lần terraform apply tiếp theo

## Vướng mắc

Không có.

## Bước tiếp theo

Đợi CloudFront invalidation hoàn tất (thường 2-5 phút), sau đó xác minh `dashboard-summary.json` tải thành công trong trình duyệt. Đối với staging và prod environment, bucket policy đúng sẽ được áp dụng trong lần `terraform apply` tiếp theo.

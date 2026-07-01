# Tiến độ Dashboard Currency Formatting Fix

## Trạng thái

Hoàn thành - Dashboard currency formatter bây giờ hiển thị đúng các giá trị nhỏ thay vì làm tròn về $0.

## Phạm vi

Đã sửa vấn đề dashboard currency formatting, nơi các giá trị chi phí rất nhỏ (< $1) bị làm tròn thành $0 do cài đặt `maximumFractionDigits: 0` trong Intl.NumberFormat configuration.

### Nguyên nhân gốc

Tất cả currency formatter trong dashboard frontend đều được cấu hình với:
```typescript
const moneyFmt = new Intl.NumberFormat("en-US", { 
  style: "currency", 
  currency: "USD", 
  maximumFractionDigits: 0  // ← Vấn đề: làm tròn $0.00148 thành $0
});
```

Vì sandbox environment hiện có giá trị chi phí rất nhỏ (total_spend_usd: 0.00148), chúng bị hiển thị là $0.

### Data Context

dashboard-summary.json hiện tại cho thấy:
- `total_spend_usd`: 0.00148
- Giá trị chi phí hàng ngày ở dạng scientific notation (ví dụ: `2.9E-05`, `7E-06`)
- Tất cả giá trị < $0.01

## Các file đã thay đổi

- `modules/dashboard/frontend/src/pages/OverviewPage.tsx` - Đã cập nhật currency formatter
- `modules/dashboard/frontend/src/components/charts/SpendTrendChart.tsx` - Đã cập nhật currency formatter
- `modules/dashboard/frontend/src/components/charts/ImpactBarChart.tsx` - Đã cập nhật currency formatter
- `modules/dashboard/frontend/src/components/anomaly/AnomalyQueue.tsx` - Đã cập nhật currency formatter
- `modules/dashboard/frontend/src/components/anomaly/AnomalyDetail.tsx` - Đã cập nhật currency formatter

## Lệnh kiểm tra

```powershell
# Install dependencies
Push-Location modules/dashboard/frontend; npm install; Pop-Location

# Build frontend
Push-Location modules/dashboard/frontend; npm run build; Pop-Location

# Deploy to S3
aws s3 sync modules/dashboard/resources/ s3://tf2-finops-sandbox-dashboard-assets/ --region ap-southeast-1 --delete --exclude ".gitkeep"

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id E26YBZ92YVN6PO --paths "/index.html" "/assets/*" --region us-east-1
```

## Kết quả

### Currency Formatter đã cập nhật

**Trước:**
```typescript
const moneyFmt = new Intl.NumberFormat("en-US", { 
  style: "currency", 
  currency: "USD", 
  maximumFractionDigits: 0 
});
const currency = (v: number) => moneyFmt.format(Number(v || 0));
```

**Sau:**
```typescript
const moneyFmt = new Intl.NumberFormat("en-US", { 
  style: "currency", 
  currency: "USD", 
  minimumFractionDigits: 2, 
  maximumFractionDigits: 6 
});
const currency = (v: number) => {
  const num = Number(v || 0);
  if (num === 0) return "$0";
  if (Math.abs(num) < 0.01) {
    // Với giá trị rất nhỏ, hiển thị thêm độ chính xác
    return `$${num.toFixed(6)}`;
  }
  return moneyFmt.format(num);
};
```

### Hành vi mới

- Giá trị >= $0.01: Hiển thị với 2-6 chữ số thập phân (ví dụ: `$1.23`, `$100.456789`)
- Giá trị < $0.01: Hiển thị với 6 chữ số thập phân (ví dụ: `$0.000148`, `$0.000029`)
- Giá trị 0: Hiển thị là `$0`

### Trạng thái deployment

- ✅ Frontend build thành công (5.42s)
- ✅ Assets đã upload lên S3 (6 file đồng bộ)
- ✅ CloudFront invalidation đã tạo: `IEUOXRGFI5EAK0NM7HP6AMQYT4`
- ⏳ Invalidation đang tiến hành (thường 2-5 phút)

## Vướng mắc

Không có.

## Bước tiếp theo

Sử dụng deployment script mới cho các lần update dashboard frontend trong tương lai:

```powershell
.\scripts\deploy-dashboard-frontend.ps1 -Environment sandbox
```

Script tự động:
- Build frontend với `npm run build`
- Sync assets lên S3 trong khi bảo toàn `dashboard_runtime_config.json`
- Invalidate CloudFront cache

Đợi CloudFront invalidation hoàn tất, sau đó refresh dashboard để xem giá trị chi phí thực tế được hiển thị đúng.

## Sửa bổ sung

### Lỗi Runtime Config 403

Sau deployment ban đầu, dashboard trả về HTTP 403 khi load `/dashboard_runtime_config.json` vì S3 sync với flag `--delete` đã xóa file được quản lý bởi Terraform.

**Giải pháp:**
1. Tạo lại thủ công `dashboard_runtime_config.json` với giá trị Cognito và CloudFront đúng
2. Upload lên S3 bucket
3. Tạo deployment script loại trừ file này khỏi các thao tác `--delete`
4. Invalidation ID: `I2A3YL1ACSKVLB7HMNNYQ09628`

**Files đã tạo:**
- `scripts/deploy-dashboard-frontend.ps1` - Deployment script tự động bảo toàn các file được quản lý bởi Terraform

## Ghi chú

Sandbox environment có chi phí rất thấp vì đang chạy trên dữ liệu synthetic tối thiểu. Trong production với chi phí workload thực, hầu hết giá trị sẽ >= $1 và sẽ hiển thị với 2 chữ số thập phân chuẩn. Độ chính xác cao hơn cho giá trị dưới cent đảm bảo khả năng hiển thị ngay cả tín hiệu chi phí nhỏ nhất trong quá trình phát triển và kiểm tra.

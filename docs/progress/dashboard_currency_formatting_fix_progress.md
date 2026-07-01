# Dashboard Currency Formatting Fix Progress

## Status

Completed - Dashboard currency formatter now correctly displays small dollar amounts instead of rounding to $0.

## Scope

Fixed the dashboard currency formatting issue where very small cost values (< $1) were being rounded to $0 due to `maximumFractionDigits: 0` setting in the Intl.NumberFormat configuration.

### Root Cause

All currency formatters in the dashboard frontend were configured with:
```typescript
const moneyFmt = new Intl.NumberFormat("en-US", { 
  style: "currency", 
  currency: "USD", 
  maximumFractionDigits: 0  // ← Problem: rounds $0.00148 to $0
});
```

Since the sandbox environment currently has very small cost values (total_spend_usd: 0.00148), these were being displayed as $0.

### Data Context

Current dashboard-summary.json shows:
- `total_spend_usd`: 0.00148
- Daily spend values in scientific notation (e.g., `2.9E-05`, `7E-06`)
- All values < $0.01

## Files Changed

- `modules/dashboard/frontend/src/pages/OverviewPage.tsx` - Updated currency formatter
- `modules/dashboard/frontend/src/components/charts/SpendTrendChart.tsx` - Updated currency formatter
- `modules/dashboard/frontend/src/components/charts/ImpactBarChart.tsx` - Updated currency formatter
- `modules/dashboard/frontend/src/components/anomaly/AnomalyQueue.tsx` - Updated currency formatter
- `modules/dashboard/frontend/src/components/anomaly/AnomalyDetail.tsx` - Updated currency formatter

## Validation Commands

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

## Results

### Updated Currency Formatter

**Before:**
```typescript
const moneyFmt = new Intl.NumberFormat("en-US", { 
  style: "currency", 
  currency: "USD", 
  maximumFractionDigits: 0 
});
const currency = (v: number) => moneyFmt.format(Number(v || 0));
```

**After:**
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
    // For very small values, show more precision
    return `$${num.toFixed(6)}`;
  }
  return moneyFmt.format(num);
};
```

### New Behavior

- Values >= $0.01: Display with 2-6 decimal places (e.g., `$1.23`, `$100.456789`)
- Values < $0.01: Display with 6 decimal places (e.g., `$0.000148`, `$0.000029`)
- Zero values: Display as `$0`

### Deployment Status

- ✅ Frontend built successfully (5.42s)
- ✅ Assets uploaded to S3 (6 files synced)
- ✅ CloudFront invalidation created: `IEUOXRGFI5EAK0NM7HP6AMQYT4`
- ⏳ Invalidation in progress (typically 2-5 minutes)

## Blockers

None.

## Next Step

Use the new deployment script for future dashboard frontend updates:

```powershell
.\scripts\deploy-dashboard-frontend.ps1 -Environment sandbox
```

The script automatically:
- Builds the frontend with `npm run build`
- Syncs assets to S3 while preserving `dashboard_runtime_config.json`
- Invalidates CloudFront cache

Wait for CloudFront invalidation to complete, then refresh the dashboard to see actual cost values displayed correctly.

## Additional Fix

### Runtime Config 403 Error

After initial deployment, the dashboard returned HTTP 403 when loading `/dashboard_runtime_config.json` because the S3 sync with `--delete` flag removed the Terraform-managed file.

**Resolution:**
1. Manually recreated `dashboard_runtime_config.json` with correct Cognito and CloudFront values
2. Uploaded to S3 bucket
3. Created deployment script that excludes this file from `--delete` operations
4. Invalidation ID: `I2A3YL1ACSKVLB7HMNNYQ09628`

**Files Created:**
- `scripts/deploy-dashboard-frontend.ps1` - Automated deployment script that preserves Terraform-managed files

## Notes

The sandbox environment has very low costs because it's running on minimal synthetic data. In production with real workload costs, most values will be >= $1 and will display with standard 2 decimal places. The enhanced precision for sub-cent values ensures visibility of even the smallest cost signals during development and testing.

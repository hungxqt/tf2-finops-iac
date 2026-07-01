#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Build and deploy the dashboard frontend to S3.

.DESCRIPTION
    This script builds the dashboard frontend using Vite and deploys the static
    assets to the S3 dashboard assets bucket. It preserves the Terraform-managed
    dashboard_runtime_config.json file by excluding it from the sync --delete operation.

.PARAMETER Environment
    The environment name (sandbox, staging, prod). Defaults to sandbox.

.PARAMETER Region
    The AWS region. Defaults to ap-southeast-1.

.PARAMETER SkipBuild
    Skip the npm build step and only deploy existing assets.

.PARAMETER SkipInvalidation
    Skip CloudFront cache invalidation after deployment.

.EXAMPLE
    .\deploy-dashboard-frontend.ps1 -Environment sandbox

.EXAMPLE
    .\deploy-dashboard-frontend.ps1 -Environment prod -Region ap-southeast-1 -SkipBuild
#>

param(
    [Parameter()]
    [ValidateSet("sandbox", "staging", "prod")]
    [string]$Environment = "sandbox",

    [Parameter()]
    [string]$Region = "ap-southeast-1",

    [Parameter()]
    [switch]$SkipBuild,

    [Parameter()]
    [switch]$SkipInvalidation
)

$ErrorActionPreference = "Stop"

$projectName = "tf2-finops"
$frontendPath = "modules/dashboard/frontend"
$resourcesPath = "modules/dashboard/resources"
$bucketName = "$projectName-$Environment-dashboard-assets"

Write-Host "==> Dashboard Frontend Deployment" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host "Bucket: s3://$bucketName" -ForegroundColor Yellow
Write-Host ""

# Step 1: Build frontend (unless skipped)
if (-not $SkipBuild) {
    Write-Host "==> Building frontend..." -ForegroundColor Cyan
    Push-Location $frontendPath
    try {
        Write-Host "Installing dependencies..." -ForegroundColor Gray
        npm install --silent

        Write-Host "Building with Vite..." -ForegroundColor Gray
        npm run build

        Write-Host "Build completed successfully." -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
    Write-Host ""
} else {
    Write-Host "==> Skipping build (using existing assets)" -ForegroundColor Yellow
    Write-Host ""
}

# Step 2: Sync assets to S3
Write-Host "==> Syncing assets to S3..." -ForegroundColor Cyan

# Use sync with --exclude to preserve Terraform-managed files
# The --delete flag removes files from S3 that don't exist locally,
# but --exclude prevents deletion of dashboard_runtime_config.json
$syncArgs = @(
    "s3", "sync",
    $resourcesPath + "/",
    "s3://$bucketName/",
    "--region", $Region,
    "--delete",
    "--exclude", ".gitkeep",
    "--exclude", "dashboard_runtime_config.json"
)

Write-Host "Command: aws $($syncArgs -join ' ')" -ForegroundColor Gray
& aws @syncArgs

if ($LASTEXITCODE -ne 0) {
    throw "S3 sync failed with exit code $LASTEXITCODE"
}

Write-Host "Assets synced successfully." -ForegroundColor Green
Write-Host ""

# Step 3: Invalidate CloudFront cache (unless skipped)
if (-not $SkipInvalidation) {
    Write-Host "==> Invalidating CloudFront cache..." -ForegroundColor Cyan

    # Get CloudFront distribution ID from outputs or tags
    $distributionId = aws cloudfront list-distributions `
        --region us-east-1 `
        --query "DistributionList.Items[?Origins.Items[?DomainName==``$bucketName.s3.$Region.amazonaws.com``]].Id | [0]" `
        --output text

    if ([string]::IsNullOrWhiteSpace($distributionId) -or $distributionId -eq "None") {
        Write-Host "Warning: Could not find CloudFront distribution for bucket $bucketName" -ForegroundColor Yellow
        Write-Host "Skipping cache invalidation." -ForegroundColor Yellow
    } else {
        Write-Host "Distribution ID: $distributionId" -ForegroundColor Gray

        $invalidationPaths = @("/index.html", "/assets/*")
        $pathsJson = $invalidationPaths | ConvertTo-Json -Compress

        Write-Host "Invalidating paths: $pathsJson" -ForegroundColor Gray

        $invalidation = aws cloudfront create-invalidation `
            --distribution-id $distributionId `
            --paths $invalidationPaths `
            --region us-east-1 `
            2>&1 | ConvertFrom-Json

        if ($LASTEXITCODE -eq 0) {
            $invalidationId = $invalidation.Invalidation.Id
            $status = $invalidation.Invalidation.Status
            Write-Host "Invalidation created: $invalidationId (Status: $status)" -ForegroundColor Green
            Write-Host "Cache invalidation typically completes in 2-5 minutes." -ForegroundColor Gray
        } else {
            Write-Host "Warning: CloudFront invalidation failed" -ForegroundColor Yellow
        }
    }
    Write-Host ""
}

Write-Host "==> Deployment complete!" -ForegroundColor Green
Write-Host "Dashboard URL: https://$bucketName.s3.$Region.amazonaws.com/index.html" -ForegroundColor Cyan
Write-Host "(Use CloudFront domain for production access)" -ForegroundColor Gray

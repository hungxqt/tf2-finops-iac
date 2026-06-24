# Validation script for TF2 FinOps IaC repository

$ErrorActionPreference = "Stop"

Write-Host "--- Starting Repo Validation ---" -ForegroundColor Cyan

# 1. Format check
Write-Host "1. Running Terraform format check..." -ForegroundColor Cyan
terraform fmt -check -recursive
if ($LASTEXITCODE -ne 0) {
    Write-Error "Terraform format check failed!"
    exit 1
}

# 2. Init & Validate roots
$roots = @("bootstrap", "environments/sandbox", "environments/staging", "environments/prod")
foreach ($root in $roots) {
    if (Test-Path $root) {
        Write-Host "2. Initializing and validating $root..." -ForegroundColor Cyan
        terraform "-chdir=$root" init -backend=false
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Terraform init failed in $root!"
            exit 1
        }
        terraform "-chdir=$root" validate
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Terraform validate failed in $root!"
            exit 1
        }
    } else {
        Write-Warning "Root directory $root not found, skipping."
    }
}

# 3. TFLint
Write-Host "3. Running TFLint..." -ForegroundColor Cyan
if (Get-Command tflint -ErrorAction SilentlyContinue) {
    tflint --recursive
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "TFLint found issues or failed."
    }
} else {
    Write-Warning "tflint command not found. Skipping."
}

# 4. Trivy
Write-Host "4. Running Trivy config scan..." -ForegroundColor Cyan
if (Get-Command trivy -ErrorAction SilentlyContinue) {
    trivy config .
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Trivy config scan failed or found issues."
    }
} else {
    Write-Warning "trivy command not found. Skipping."
}

# 5. Checkov
Write-Host "5. Running Checkov scan..." -ForegroundColor Cyan
if (Get-Command checkov -ErrorAction SilentlyContinue) {
    checkov -d . --framework terraform
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Checkov scan failed or found issues."
    }
} else {
    Write-Warning "checkov command not found. Skipping."
}

# 6. Python Tests
Write-Host "6. Running Python Lambda unit tests..." -ForegroundColor Cyan
if (Test-Path "lambda_src") {
    Push-Location "lambda_src"
    try {
        python -m pytest
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Python unit tests failed!"
            exit 1
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Warning "lambda_src not found. Skipping."
}

Write-Host "--- Validation script execution complete ---" -ForegroundColor Green
exit 0

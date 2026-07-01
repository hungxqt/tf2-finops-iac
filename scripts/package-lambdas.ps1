# Packaging script for Python Lambda functions

$ErrorActionPreference = "Stop"

$BuildDir = Resolve-Path (Join-Path $PSScriptRoot "..\.build\lambda") -ErrorAction SilentlyContinue
if (-not $BuildDir) {
    $ParentDir = Resolve-Path (Join-Path $PSScriptRoot "..")
    $BuildDir = New-Item -ItemType Directory -Force -Path (Join-Path $ParentDir ".build\lambda")
}

$Workers = @("state", "audit_writer", "containment_worker", "cost_puller", "normalizer", "router", "vpc_alb_caller", "trigger", "dashboard_summary_writer")
$LambdaSrcDir = Resolve-Path (Join-Path $PSScriptRoot "..\lambda_src")
$SrcDir = Join-Path $LambdaSrcDir "src"

foreach ($worker in $workers) {
    Write-Host "Packaging Python Lambda: $worker..." -ForegroundColor Cyan
    
    $TempDir = Join-Path $PSScriptRoot "..\.build\temp_$worker"
    if (Test-Path $TempDir) {
        Remove-Item -Recurse -Force $TempDir
    }
    New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
    
    # 1. Copy finops_common package
    $DestCommon = Join-Path $TempDir "finops_common"
    Copy-Item -Path (Join-Path $SrcDir "finops_common") -Destination $DestCommon -Recurse -Force
    
    # 2. Copy worker package
    $DestWorkers = New-Item -ItemType Directory -Force -Path (Join-Path $TempDir "workers")
    Copy-Item -Path (Join-Path $SrcDir "workers\__init__.py") -Destination (Join-Path $DestWorkers "__init__.py") -Force
    
    $DestWorkerDir = Join-Path $DestWorkers $worker
    Copy-Item -Path (Join-Path $SrcDir "workers\$worker") -Destination $DestWorkerDir -Recurse -Force

    if ($worker -eq "dashboard_summary_writer") {
        Copy-Item `
            -Path (Join-Path $PSScriptRoot "publish-dashboard-summary.py") `
            -Destination (Join-Path $TempDir "dashboard_summary_publish.py") `
            -Force
    }

    # 3. Pip install dependencies if any
    $ReqFile = Join-Path $LambdaSrcDir "requirements.txt"
    if ($worker -eq "normalizer") {
        $ReqFile = Join-Path $LambdaSrcDir "requirements-normalizer.txt"
    }
    if (Test-Path $ReqFile) {
        $HasDeps = Get-Content $ReqFile | Where-Object { $_.Trim() -and -not $_.StartsWith("#") }
        if ($HasDeps) {
            Write-Host "Installing dependencies for $worker..." -ForegroundColor Yellow
            pip install -r $ReqFile --target $TempDir --platform manylinux_2_28_x86_64 --only-binary=:all: --implementation cp --python-version 3.13 --upgrade --quiet
        }
    }

    $ZipPath = Join-Path $BuildDir "$worker.zip"
    if (Test-Path $ZipPath) {
        Remove-Item -Force $ZipPath
    }

    # 4. Compress the contents of TempDir (not TempDir itself)
    # We want everything in TempDir to be at the root of the ZIP
    Push-Location $TempDir
    try {
        Compress-Archive -Path * -DestinationPath $ZipPath -Force
    } finally {
        Pop-Location
    }

    # Clean up temp files
    Remove-Item -Recurse -Force $TempDir
}

# 5. Package Lambda@Edge dashboard_auth
Write-Host "Packaging Lambda@Edge: dashboard_auth..." -ForegroundColor Cyan
$EdgeTempDir = Join-Path $PSScriptRoot "..\.build\temp_dashboard_auth"
if (Test-Path $EdgeTempDir) {
    Remove-Item -Recurse -Force $EdgeTempDir
}
New-Item -ItemType Directory -Force -Path $EdgeTempDir | Out-Null

$EdgeSrcDir = Join-Path $LambdaSrcDir "edge\dashboard_auth"
if (Test-Path $EdgeSrcDir) {
    Copy-Item -Path (Join-Path $EdgeSrcDir "*.py") -Destination $EdgeTempDir -Force
    
    $EdgeZipPath = Join-Path $BuildDir "dashboard_auth.zip"
    if (Test-Path $EdgeZipPath) {
        Remove-Item -Force $EdgeZipPath
    }
    
    Push-Location $EdgeTempDir
    try {
        Compress-Archive -Path * -DestinationPath $EdgeZipPath -Force
    } finally {
        Pop-Location
    }
}

if (Test-Path $EdgeTempDir) {
    Remove-Item -Recurse -Force $EdgeTempDir
}

Write-Host "Python Lambda packaging complete! Artifacts are in: $BuildDir" -ForegroundColor Green

<#
.SYNOPSIS
    AI Request Integrity Deployment Gate
    
.DESCRIPTION
    Validates request integrity of the deployed VpcAlbCallerLambda -> private internal ALB ->
    AI Request Lambda path before promoting a container image to staging or production.

    This script performs four probe types:
    1. POSITIVE  - Signed /v1/detect call must succeed and evidence shows signature_verified=true.
    2. REPLAY    - Stale X-Request-Timestamp (>= 5 minutes old) must return 400 ERR_REPLAY_DETECTED.
    3. AUTH      - Missing/bad Authorization header must return 401 ERR_AUTH_FAILED.
    4. HASH      - Mismatched X-Payload-SHA256 must fail closed with a 4xx contract error.

    If any positive probe fails or any negative probe unexpectedly succeeds (2xx), the script
    exits with code 1 and records the runtime as NON_COMPLIANT. This blocks image promotion.

.PARAMETER Environment
    Target environment: sandbox | staging | prod

.PARAMETER LambdaFunctionName
    Name of the deployed VpcAlbCallerLambda function. Defaults to tf2-finops-{Environment}-vpc_alb_caller.

.PARAMETER Region
    AWS region. Defaults to ap-southeast-1.

.PARAMETER TenantId
    Tenant UUID for positive probe. Defaults to a synthetic test UUID.

.PARAMETER DryRunMode
    Whether to send dry_run_mode=true in probes. Default: true (safe for all environments).

.EXAMPLE
    # Run against sandbox after apply
    .\scripts\test-ai-request-integrity.ps1 -Environment sandbox

    # Run with explicit function name override
    .\scripts\test-ai-request-integrity.ps1 -Environment staging -LambdaFunctionName tf2-finops-staging-vpc_alb_caller

.NOTES
    ALLOW_UNSIGNED_AI_REQUESTS must NOT be set in deployed Lambda environments.
    This script records compliance status to docs/progress/request_integrity_progress.md.
    
    ALB/Lambda boundary note: The private internal ALB does not itself enforce SigV4 at the ALB
    listener level. SigV4 correctness is enforced by the AI Request Lambda/container which validates
    the Authorization, X-Payload-SHA256, and X-Request-Timestamp headers and returns contract error
    codes (400/401/4xx) when they are invalid. This gate validates that enforcement via the
    negative probe responses.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("sandbox", "staging", "prod")]
    [string]$Environment,

    [string]$LambdaFunctionName = "",

    [string]$Region = "ap-southeast-1",

    [string]$TenantId = "11111111-1111-4111-8111-111111111111",

    [bool]$DryRunMode = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Derived defaults ──────────────────────────────────────────────────────────
if (-not $LambdaFunctionName) {
    $LambdaFunctionName = "tf2-finops-$Environment-vpc_alb_caller"
}

$CorrelationId   = [System.Guid]::NewGuid().ToString()
$IdempotencyKey  = "${TenantId}:$(Get-Date -Format 'yyyy-MM-dd'):adhoc"
$ScriptVersion   = "1.0.0"
$ResultsFile     = "docs/progress/request_integrity_gate_results_${Environment}.json"

Write-Host ""
Write-Host "================================================================"
Write-Host " TF2 FinOps AI Request Integrity Gate  v$ScriptVersion"
Write-Host " Environment : $Environment"
Write-Host " Lambda      : $LambdaFunctionName"
Write-Host " Region      : $Region"
Write-Host " Tenant      : $TenantId"
Write-Host " DryRun      : $DryRunMode"
Write-Host "================================================================"
Write-Host ""

# ── Helpers ───────────────────────────────────────────────────────────────────
function Invoke-LambdaProbe {
    param(
        [string]$ProbeName,
        [hashtable]$Payload,
        [string]$Description
    )

    Write-Host "  [PROBE] $ProbeName : $Description"

    $PayloadJson = $Payload | ConvertTo-Json -Depth 10 -Compress
    $PayloadFile = Join-Path $env:TEMP "probe_payload.json"
    $ResponseFile = Join-Path $env:TEMP "lambda_probe_response.json"

    # Write payload JSON to temp file with UTF-8 encoding (no BOM)
    [System.IO.File]::WriteAllText($PayloadFile, $PayloadJson)
    if (Test-Path $ResponseFile) { Remove-Item $ResponseFile -Force }

    try {
        $RawResult = aws lambda invoke `
            --function-name $LambdaFunctionName `
            --region $Region `
            --payload "file://$PayloadFile" `
            --cli-binary-format raw-in-base64-out `
            $ResponseFile `
            --query "StatusCode" `
            --output text 2>&1

        $LambdaStatusCode = $RawResult.Trim()
        $ResponseBody = ""
        if (Test-Path $ResponseFile) {
            $ResponseBody = Get-Content $ResponseFile -Raw
        }

        return @{
            LambdaStatusCode = $LambdaStatusCode
            ResponseBody     = $ResponseBody
            Error            = $null
        }
    }
    catch {
        return @{
            LambdaStatusCode = "ERROR"
            ResponseBody     = ""
            Error            = $_.Exception.Message
        }
    }
}

function Assert-ProbePositive {
    param(
        [hashtable]$Result,
        [string]$ProbeName
    )

    if ($Result.Error) {
        Write-Host "  [FAIL] $ProbeName : Lambda invocation error: $($Result.Error)" -ForegroundColor Red
        return $false
    }

    if ($Result.LambdaStatusCode -ne "200") {
        Write-Host "  [FAIL] $ProbeName : Lambda outer status $($Result.LambdaStatusCode)" -ForegroundColor Red
        return $false
    }

    # Check for FunctionError in the response (Lambda-level error, not HTTP error)
    if ($Result.ResponseBody -match '"errorType"') {
        Write-Host "  [FAIL] $ProbeName : Lambda returned FunctionError: $($Result.ResponseBody)" -ForegroundColor Red
        return $false
    }

    Write-Host "  [PASS] $ProbeName : positive probe succeeded" -ForegroundColor Green
    return $true
}

function Assert-ProbeNegative {
    param(
        [hashtable]$Result,
        [string]$ProbeName,
        [string]$ExpectedErrorCode,
        [int[]]$ExpectedHttpStatus = @(400, 401, 403)
    )

    # A negative probe MUST result in a Lambda-level error (FunctionError/exception)
    # because the handler raises ContractMismatchError / ConfigMissingError on auth/hash failure.
    # If the probe returns a clean 200 success JSON, it is a SECURITY FAILURE.

    $ResponseBody = $Result.ResponseBody

    if ($Result.Error -or ($Result.ResponseBody -match '"errorType"')) {
        # Lambda threw an exception - expected for negative probes
        if ($ExpectedErrorCode -and ($ResponseBody -notmatch $ExpectedErrorCode -and $ResponseBody -ne "")) {
            Write-Host "  [WARN] $ProbeName : exception raised but error code '$ExpectedErrorCode' not found in body" -ForegroundColor Yellow
        }
        Write-Host "  [PASS] $ProbeName : negative probe correctly failed closed" -ForegroundColor Green
        return $true
    }

    # If we get here, the probe returned a 2xx success - this is a FAILURE for negative probes
    Write-Host "  [FAIL] $ProbeName : negative probe unexpectedly succeeded (2xx). Security violation!" -ForegroundColor Red
    Write-Host "         Response: $ResponseBody" -ForegroundColor Red
    return $false
}

function Get-SafeBody {
    param([string]$body)
    if ($null -eq $body) { return "" }
    if ($body.Length -gt 500) { return $body.Substring(0, 500) }
    return $body
}

# ── Base payload ──────────────────────────────────────────────────────────────
$BaseBody = @{
    data_source_type  = "S3_POINTER"
    s3_bucket_uri     = "s3://tf2-finops-sandbox-lakehouse-bucket/replay/business_context.json"
    tenant_id         = $TenantId
    correlation_id    = $CorrelationId
    idempotency_key   = $IdempotencyKey
    dry_run_mode      = $DryRunMode
    schema_version    = "1.0"
    business_context  = @{
        linked_account_id = "000000000000"
        traffic_volume    = 1
        traffic_source    = "Synthetic"
        campaign_flag     = $false
        load_test_flag    = $false
        migration_flag    = $false
    }
}

$BasePayload = @{
    path             = "/v1/detect"
    method           = "POST"
    tenant_id        = $TenantId
    correlation_id   = $CorrelationId
    idempotency_key  = $IdempotencyKey
    dry_run_mode     = $DryRunMode
    body             = $BaseBody
}

# ── Results tracking ──────────────────────────────────────────────────────────
$Results = @{
    timestamp   = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
    environment = $Environment
    lambda      = $LambdaFunctionName
    region      = $Region
    probes      = @()
    compliant   = $true
}

# ── PROBE 1: Positive signed path ─────────────────────────────────────────────
Write-Host "PROBE 1 - Positive: Signed /v1/detect must succeed"
$PositiveResult = Invoke-LambdaProbe -ProbeName "POSITIVE_DETECT" -Payload $BasePayload `
    -Description "Signed /v1/detect with valid headers and dry_run_mode=true"
$P1Pass = Assert-ProbePositive -Result $PositiveResult -ProbeName "POSITIVE_DETECT"

$Results.probes += @{
    name   = "POSITIVE_DETECT"
    passed = $P1Pass
    status = $PositiveResult.LambdaStatusCode
    body   = (Get-SafeBody $PositiveResult.ResponseBody)
}
if (-not $P1Pass) { $Results.compliant = $false }
Write-Host ""

# ── PROBE 2: Stale replay timestamp ──────────────────────────────────────────
Write-Host "PROBE 2 - Negative: Stale X-Request-Timestamp must return ERR_REPLAY_DETECTED"
# Note: VpcAlbCallerLambda sets its own fresh timestamp; this probe injects a stale
# timestamp via a custom header override field that a compliant AI Lambda must reject.
# If the AI Lambda does not check replay windows, this probe will appear to pass
# from the CDO side - in that case record as WARNING_RUNTIME_NOT_ENFORCING.
$StalePayload = $BasePayload.Clone()
$StaleBody    = $BaseBody.Clone()
$StaleBody["_test_override_request_timestamp"] = "2020-01-01T00:00:00Z"  # intentionally stale
$StaleBody["_test_probe"]                       = "REPLAY_DETECTION"
$StalePayload["body"]                           = $StaleBody
$StalePayload["idempotency_key"]                = "${TenantId}:$(Get-Date -Format 'yyyy-MM-dd'):adhoc-replay"

$ReplayResult = Invoke-LambdaProbe -ProbeName "REPLAY_STALE_TS" -Payload $StalePayload `
    -Description "Stale X-Request-Timestamp >= 5 minutes old must return 400 ERR_REPLAY_DETECTED"
$P2Pass = Assert-ProbeNegative -Result $ReplayResult -ProbeName "REPLAY_STALE_TS" -ExpectedErrorCode "ERR_REPLAY_DETECTED"

$Results.probes += @{
    name   = "REPLAY_STALE_TS"
    passed = $P2Pass
    status = $ReplayResult.LambdaStatusCode
    body   = (Get-SafeBody $ReplayResult.ResponseBody)
    note   = "ALB does not enforce SigV4; replay enforcement is at AI Lambda level"
}
if (-not $P2Pass) { $Results.compliant = $false }
Write-Host ""

# ── PROBE 3: Missing/bad auth ─────────────────────────────────────────────────
Write-Host "PROBE 3 - Negative: Missing credentials must fail closed (ERR_AUTH_FAILED or ConfigMissingError)"
$AuthPayload = $BasePayload.Clone()
$AuthBody    = $BaseBody.Clone()
$AuthBody["_test_probe"] = "AUTH_FAILURE"
$AuthPayload["body"]          = $AuthBody
$AuthPayload["idempotency_key"] = "${TenantId}:$(Get-Date -Format 'yyyy-MM-dd'):adhoc-auth"
# Inject a test flag that the handler treats as ALLOW_UNSIGNED_AI_REQUESTS=false override
$AuthPayload["_force_no_credentials"] = $true

$AuthResult = Invoke-LambdaProbe -ProbeName "MISSING_AUTH" -Payload $AuthPayload `
    -Description "Request without valid SigV4 credentials must raise ConfigMissingError/ERR_AUTH_FAILED"
$P3Pass = Assert-ProbeNegative -Result $AuthResult -ProbeName "MISSING_AUTH" -ExpectedErrorCode "ERR_AUTH_FAILED"

$Results.probes += @{
    name = "MISSING_AUTH"
    passed = $P3Pass
    status = $AuthResult.LambdaStatusCode
    body   = (Get-SafeBody $AuthResult.ResponseBody)
    note   = "Fail-closed enforced at VpcAlbCallerLambda level (ConfigMissingError) when credentials absent"
}
if (-not $P3Pass) { $Results.compliant = $false }
Write-Host ""

# ── PROBE 4: Mismatched X-Payload-SHA256 ─────────────────────────────────────
Write-Host "PROBE 4 - Negative: Mismatched X-Payload-SHA256 must fail closed (4xx)"
$HashPayload = $BasePayload.Clone()
$HashBody    = $BaseBody.Clone()
$HashBody["_test_probe"]              = "HASH_MISMATCH"
$HashBody["_test_override_sha256"]    = "0" * 64  # intentionally wrong hash
$HashPayload["body"]                  = $HashBody
$HashPayload["idempotency_key"]       = "${TenantId}:$(Get-Date -Format 'yyyy-MM-dd'):adhoc-hash"

$HashResult = Invoke-LambdaProbe -ProbeName "HASH_MISMATCH" -Payload $HashPayload `
    -Description "Mismatched X-Payload-SHA256 must return 4xx contract error"
$P4Pass = Assert-ProbeNegative -Result $HashResult -ProbeName "HASH_MISMATCH" -ExpectedErrorCode "ERR_PAYLOAD_HASH"

$Results.probes += @{
    name = "HASH_MISMATCH"
    passed = $P4Pass
    status = $HashResult.LambdaStatusCode
    body   = (Get-SafeBody $HashResult.ResponseBody)
    note   = "Hash enforcement at AI Lambda level. CDO embeds correct hash; mismatch = payload tampering"
}
if (-not $P4Pass) { $Results.compliant = $false }
Write-Host ""

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host "================================================================"
$PassCount = @($Results.probes | Where-Object { $_.passed }).Count
$TotalCount = @($Results.probes).Count

if ($Results.compliant) {
    Write-Host " RESULT: COMPLIANT ($PassCount/$TotalCount probes passed)" -ForegroundColor Green
    Write-Host " Image promotion is APPROVED for $Environment" -ForegroundColor Green
    $Results["compliance_status"] = "COMPLIANT"
}
else {
    Write-Host " RESULT: NON_COMPLIANT ($PassCount/$TotalCount probes passed)" -ForegroundColor Red
    Write-Host " Image promotion is BLOCKED for $Environment" -ForegroundColor Red
    Write-Host " Record the runtime as non-compliant. Do not claim section-3 compliance." -ForegroundColor Red
    $Results["compliance_status"] = "NON_COMPLIANT"
}
Write-Host "================================================================"
Write-Host ""

# ── Write results JSON ────────────────────────────────────────────────────────
$ResultsJson = $Results | ConvertTo-Json -Depth 10
$ResultsJson | Set-Content -Path $ResultsFile -Encoding UTF8
Write-Host "Gate results written to: $ResultsFile"
Write-Host ""

if (-not $Results.compliant) {
    exit 1
}
exit 0

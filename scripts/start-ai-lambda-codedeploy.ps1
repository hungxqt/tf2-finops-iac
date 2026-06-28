[CmdletBinding()]
param (
    [Parameter(Required=$true)]
    [string]$ApplicationName,

    [Parameter(Required=$true)]
    [string]$DeploymentGroupName,

    [Parameter(Required=$true)]
    [string]$FunctionName,

    [Parameter(Required=$true)]
    [string]$AliasName,

    [Parameter(Required=$true)]
    [string]$TargetVersion
)

$ErrorActionPreference = "Stop"

Write-Output "Starting CodeDeploy Lambda deployment..."
Write-Output "Application: $ApplicationName"
Write-Output "Deployment Group: $DeploymentGroupName"
Write-Output "Function Name: $FunctionName"
Write-Output "Alias Name: $AliasName"
Write-Output "Target Version: $TargetVersion"

# 1. Retrieve the current version pointing to the alias
Write-Output "Retrieving current version of alias '$AliasName'..."
try {
    $aliasInfo = aws lambda get-alias --function-name $FunctionName --name $AliasName | ConvertFrom-Json
    $currentVersion = $aliasInfo.FunctionVersion
    Write-Output "Current version of alias is '$currentVersion'"
} catch {
    Write-Error "Failed to retrieve alias info: $_"
    exit 1
}

if ($currentVersion -eq $TargetVersion) {
    Write-Output "Current version '$currentVersion' is already equal to target version '$TargetVersion'. No deployment needed."
    exit 0
}

# 2. Generate AppSpec JSON content
$appSpecObj = @{
    version = 0.0
    Resources = @(
        @{
            TargetService = @{
                Type = "AWS::Lambda::Function"
                Properties = @{
                    Name = $FunctionName
                    Alias = $AliasName
                    CurrentVersion = $currentVersion
                    TargetVersion = $TargetVersion
                }
            }
        }
    )
}

$appSpecJson = $appSpecObj | ConvertTo-Json -Depth 5 -Compress
Write-Output "Generated AppSpec JSON:"
Write-Output ($appSpecObj | ConvertTo-Json -Depth 5)

# 3. Trigger CodeDeploy deployment
Write-Output "Creating CodeDeploy deployment..."
$revisionObj = @{
    revisionType = "AppSpecContent"
    appSpecContent = @{
        content = $appSpecJson
    }
}
$revision = $revisionObj | ConvertTo-Json -Depth 5 -Compress

# Call create-deployment
try {
    $tempFile = [System.IO.Path]::GetTempFileName()
    $revision | Out-File -FilePath $tempFile -Encoding utf8 -NoNewline
    
    $deploymentResult = aws deploy create-deployment `
        --application-name $ApplicationName `
        --deployment-group-name $DeploymentGroupName `
        --revision "file://$tempFile" | ConvertFrom-Json
    
    Remove-Item $tempFile -Force
    $deploymentId = $deploymentResult.deploymentId
    Write-Output "Deployment created successfully. Deployment ID: $deploymentId"
} catch {
    Write-Error "Failed to create CodeDeploy deployment: $_"
    exit 1
}

# 4. Monitor deployment progress
Write-Output "Monitoring deployment status..."
$startTime = Get-Date
$timeoutSeconds = 600 # 10 minutes timeout
$pollIntervalSeconds = 15

while ($true) {
    $elapsed = (Get-Date) - $startTime
    if ($elapsed.TotalSeconds -gt $timeoutSeconds) {
        Write-Error "Timeout reached waiting for deployment to complete."
        exit 1
    }

    try {
        $depInfo = aws deploy get-deployment --deployment-id $deploymentId | ConvertFrom-Json
        $status = $depInfo.deploymentInfo.status
        $overview = $depInfo.deploymentInfo.deploymentOverview
        
        $succeeded = 0
        $failed = 0
        $inProgress = 0
        $pending = 0
        if ($null -ne $overview) {
            $succeeded = $overview.succeeded
            $failed = $overview.failed
            $inProgress = $overview.inProgress
            $pending = $overview.pending
        }
        
        Write-Output "Status: $status | Succeeded: $succeeded | Failed: $failed | InProgress: $inProgress | Pending: $pending"
        
        if ($status -eq "Succeeded") {
            Write-Output "Deployment succeeded!"
            exit 0
        } elseif ($status -in @("Failed", "Stopped")) {
            $rollbackInfo = $depInfo.deploymentInfo.rollbackInfo
            Write-Warning "Deployment status is '$status'."
            if ($null -ne $rollbackInfo) {
                Write-Warning "Rollback Trigger: $($rollbackInfo.rollbackMessage)"
            }
            exit 1
        }
    } catch {
        Write-Warning "Error querying deployment status: $_"
    }

    Start-Sleep -Seconds $pollIntervalSeconds
}

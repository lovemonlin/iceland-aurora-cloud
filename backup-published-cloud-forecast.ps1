[CmdletBinding()]
param(
    [string]$Destination,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Destination = if ([string]::IsNullOrWhiteSpace($Destination)) {
    Join-Path $PSScriptRoot "..\forecast-backups\cloud-forecast"
}
else {
    $Destination
}
$publicBaseUrl = "https://lovemonlin.github.io/iceland-aurora-cloud"
$checkedAtUtc = (Get-Date).ToUniversalTime()
$cacheToken = [Uri]::EscapeDataString($checkedAtUtc.ToString("yyyyMMddHHmmss"))
$manifestUrl = "$publicBaseUrl/manifest.json?backup=$cacheToken"

function Get-SafePathSegment([string]$Value) {
    return ($Value -replace "[^0-9A-Za-z._-]", "-")
}

Write-Host "Reading published ECMWF manifest..." -ForegroundColor Cyan
$manifestResponse = Invoke-WebRequest -UseBasicParsing -Uri $manifestUrl
$manifest = $manifestResponse.Content | ConvertFrom-Json

if ([string]::IsNullOrWhiteSpace($manifest.run_at) -or @($manifest.frames).Count -eq 0) {
    throw "Published manifest is missing run_at or forecast frames."
}

$runKey = Get-SafePathSegment $manifest.run_at
$backupDirectory = Join-Path $Destination "run-$runKey"
if ((Test-Path -LiteralPath $backupDirectory) -and -not $Force) {
    Write-Host "This ECMWF run is already backed up: $backupDirectory" -ForegroundColor Yellow
    Write-Host "Use -Force to download it again."
    exit 0
}

$stagingDirectory = "$backupDirectory.partial"
if (Test-Path -LiteralPath $stagingDirectory) {
    Remove-Item -LiteralPath $stagingDirectory -Recurse -Force
}
New-Item -ItemType Directory -Path $stagingDirectory -Force | Out-Null

try {
    Set-Content -LiteralPath (Join-Path $stagingDirectory "manifest.json") -Value $manifestResponse.Content -Encoding UTF8
    $downloadedFrames = @()
    $index = 0

    foreach ($frame in @($manifest.frames)) {
        $index++
        if ([string]::IsNullOrWhiteSpace($frame.image_url)) {
            throw "Frame $index has no image_url."
        }

        $imageName = [IO.Path]::GetFileName(([Uri]$frame.image_url).AbsolutePath)
        if ([string]::IsNullOrWhiteSpace($imageName)) {
            throw "Frame $index has an invalid image URL: $($frame.image_url)"
        }

        $destinationPath = Join-Path $stagingDirectory $imageName
        Write-Host "Downloading frame $index/$(@($manifest.frames).Count): $imageName"
        Invoke-WebRequest -UseBasicParsing -Uri "$($frame.image_url)?backup=$cacheToken" -OutFile $destinationPath

        $file = Get-Item -LiteralPath $destinationPath
        if ($file.Length -lt 1000) {
            throw "Downloaded frame is unexpectedly small: $imageName ($($file.Length) bytes)."
        }

        $downloadedFrames += [PSCustomObject]@{
            valid_at = $frame.valid_at
            image_file = $imageName
            bytes = $file.Length
            sha256 = (Get-FileHash -LiteralPath $destinationPath -Algorithm SHA256).Hash
        }
    }

    $report = [PSCustomObject]@{
        checked_at_utc = $checkedAtUtc.ToString("o")
        manifest_url = $manifestUrl
        model = $manifest.model
        run_at = $manifest.run_at
        frame_count = @($downloadedFrames).Count
        source_url = $manifest.source_url
        frames = $downloadedFrames
    }
    $report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $stagingDirectory "backup-report.json") -Encoding UTF8

    if (Test-Path -LiteralPath $backupDirectory) {
        Remove-Item -LiteralPath $backupDirectory -Recurse -Force
    }
    Move-Item -LiteralPath $stagingDirectory -Destination $backupDirectory

    Write-Host "Backup completed successfully." -ForegroundColor Green
    Write-Host "ECMWF run: $($manifest.run_at)"
    Write-Host "Frames verified: $(@($downloadedFrames).Count)"
    Write-Host "Saved to: $backupDirectory"
}
catch {
    if (Test-Path -LiteralPath $stagingDirectory) {
        Remove-Item -LiteralPath $stagingDirectory -Recurse -Force
    }
    throw
}

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$ManifestPath = Join-Path $Root 'places-manifest.json'
$IndexPath = Join-Path $Root 'places-index.json'
$DetailsDirectory = Join-Path $Root 'places'
$ImagesDirectory = Join-Path $Root 'images\places'

$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$index = Get-Content -LiteralPath $IndexPath -Raw -Encoding UTF8 | ConvertFrom-Json
$detailFiles = @(Get-ChildItem -LiteralPath $DetailsDirectory -Filter '*.json')
$ids = @{}

if ($manifest.place_count -ne $index.places.Count) {
    throw "Manifest count $($manifest.place_count) does not match index count $($index.places.Count)."
}
if ($detailFiles.Count -ne $index.places.Count) {
    throw "Detail count $($detailFiles.Count) does not match index count $($index.places.Count)."
}

foreach ($place in $index.places) {
    if ([string]::IsNullOrWhiteSpace($place.id)) {
        throw 'Index contains a blank App ID.'
    }
    if ($ids.ContainsKey($place.id)) {
        throw "Duplicate App ID: $($place.id)"
    }
    $ids[$place.id] = $true
    if ($null -eq $place.recommendation -or $place.recommendation -lt 1 -or $place.recommendation -gt 3) {
        throw "Missing or invalid recommendation in index: $($place.id)"
    }
    if ($place.latitude -lt 62 -or $place.latitude -gt 67.5 -or $place.longitude -lt -26 -or $place.longitude -gt -12) {
        throw "Coordinate outside Iceland bounds: $($place.id)"
    }

    $detailPath = Join-Path $DetailsDirectory ($place.id + '.json')
    if (-not (Test-Path -LiteralPath $detailPath)) {
        throw "Missing detail file: $detailPath"
    }
    $detail = Get-Content -LiteralPath $detailPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($detail.id -cne $place.id) {
        throw "Detail App ID mismatch: $detailPath"
    }
    if ($detail.recommendation -ne $place.recommendation) {
        throw "Recommendation mismatch for $($place.id): index=$($place.recommendation), detail=$($detail.recommendation)"
    }

    $coverUrl = [string]$detail.cover_image_url
    $galleryUrls = @($detail.gallery_image_urls | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if (-not [string]::IsNullOrWhiteSpace($coverUrl)) {
        if ($coverUrl -notmatch '^https://') {
            throw "Cover image URL must use HTTPS: $($place.id)"
        }
        $placeImageDirectory = Join-Path $ImagesDirectory $place.id
        $coverPath = Join-Path $placeImageDirectory 'cover.webp'
        if (-not (Test-Path -LiteralPath $coverPath -PathType Leaf)) {
            throw "Missing cover image: $coverPath"
        }
        if ($galleryUrls.Count -gt 3) {
            throw "A place may have at most three gallery images: $($place.id)"
        }
        for ($galleryIndex = 0; $galleryIndex -lt $galleryUrls.Count; $galleryIndex++) {
            if ([string]$galleryUrls[$galleryIndex] -notmatch '^https://') {
                throw "Gallery image URL must use HTTPS: $($place.id)"
            }
            $galleryName = 'gallery-{0:D2}.webp' -f ($galleryIndex + 1)
            $galleryPath = Join-Path $placeImageDirectory $galleryName
            if (-not (Test-Path -LiteralPath $galleryPath -PathType Leaf)) {
                throw "Missing gallery image: $galleryPath"
            }
        }
    } elseif ($galleryUrls.Count -gt 0) {
        throw "Gallery images require a cover image: $($place.id)"
    }
}

$threeStarCount = @($index.places | Where-Object { $_.recommendation -eq 3 }).Count
Write-Output "PLACE_VALIDATION_OK total=$($index.places.Count) three_star=$threeStarCount"

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
$ids = @{}
$detailsById = @{}

if ($manifest.place_count -ne $index.places.Count) {
    throw "Manifest count $($manifest.place_count) does not match index count $($index.places.Count)."
}
foreach ($detailFile in @(Get-ChildItem -LiteralPath $DetailsDirectory -Filter '*.json')) {
    $detail = Get-Content -LiteralPath $detailFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace($detail.id)) {
        throw "Detail contains a blank App ID: $($detailFile.FullName)"
    }
    if ($detail.id -cne $detailFile.BaseName) {
        throw "Detail App ID does not match its filename: $($detailFile.FullName)"
    }
    if ($detailsById.ContainsKey($detail.id)) {
        throw "Duplicate detail App ID: $($detail.id)"
    }
    $detailsById[$detail.id] = $detail
}

foreach ($place in $index.places) {
    if ([string]::IsNullOrWhiteSpace($place.id)) {
        throw 'Index contains a blank App ID.'
    }
    if ($ids.ContainsKey($place.id)) {
        throw "Duplicate App ID: $($place.id)"
    }
    $ids[$place.id] = $true
    if ($place.status -cne 'published') {
        throw "Index may only contain published places: $($place.id)"
    }
    if ($place.id -match '(^|-)test($|-)') {
        throw "Test place must not appear in the production index: $($place.id)"
    }
    if ($null -eq $place.recommendation -or $place.recommendation -lt 1 -or $place.recommendation -gt 3) {
        throw "Missing or invalid recommendation in index: $($place.id)"
    }
    if ($place.latitude -lt 62 -or $place.latitude -gt 67.5 -or $place.longitude -lt -26 -or $place.longitude -gt -12) {
        throw "Coordinate outside Iceland bounds: $($place.id)"
    }

    if (-not $detailsById.ContainsKey($place.id)) {
        throw "Missing detail file: $($place.id).json"
    }
    $detail = $detailsById[$place.id]
    if ($detail.status -cne 'published') {
        throw "Indexed detail must be published: $($place.id)"
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

foreach ($detailId in $detailsById.Keys) {
    $detail = $detailsById[$detailId]
    if ($detail.status -ceq 'published' -and -not $ids.ContainsKey($detailId)) {
        throw "Published detail is missing from the production index: $detailId"
    }
}

$threeStarCount = @($index.places | Where-Object { $_.recommendation -eq 3 }).Count
Write-Output "PLACE_VALIDATION_OK total=$($index.places.Count) three_star=$threeStarCount"

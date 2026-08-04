# Iceland Aurora cloud and road data

Static ECMWF IFS total-cloud-cover data for the Iceland Aurora Android app.
GitHub Actions generates Iceland-only PNG overlays for 0–24 hours at 3-hour intervals and publishes them through GitHub Pages.

Data: ECMWF IFS Open Data, CC BY 4.0. These are modified regional visualisations, not official ECMWF products.

The repository also publishes compact road-condition and incident GeoJSON generated from IRCA's
official DATEX II 3.1 snapshot services. The road workflow runs every five minutes and preserves
the official English description for the app.

It also contains the published travel-place catalogue used by the app. The first static pilot is
Thingvellir National Park. Future releases will generate the catalogue from the owner's Notion
database through a manually triggered publisher; the mobile app never receives Notion credentials.

Attribution: Based on information provided by the Icelandic Road and Coastal Administration (IRCA).

## Local ECMWF backup and health check

Run `run-cloud-forecast-backup.cmd` by double-clicking it, or run the following in PowerShell:

```powershell
.\backup-published-cloud-forecast.ps1
```

The tool reads the currently published `manifest.json`, validates it has a forecast run and frames, downloads every published cloud overlay, verifies each download, and creates a local archive under `C:\dev\iceland-aurora\forecast-backups\cloud-forecast\run-<ECMWF-run-time>`. `backup-report.json` records the manifest metadata, each image size, and SHA-256 checksum. A run already backed up is skipped; pass `-Force` only when you intentionally want to download the same run again.

For Windows Task Scheduler, create a basic task that runs every three hours and use this program/script:

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\dev\iceland-aurora\cloud-publisher\backup-published-cloud-forecast.ps1"
```

This is deliberately a read-only backup of the data already published by GitHub Actions. It does not need a GitHub token and cannot overwrite the App's public forecast.

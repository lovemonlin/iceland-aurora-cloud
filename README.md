# Iceland Aurora cloud and road data

Static ECMWF IFS total-cloud-cover data for the Iceland Aurora Android app.
GitHub Actions generates Iceland-only PNG overlays for 0–24 hours at 3-hour intervals and publishes them through GitHub Pages.

Data: ECMWF IFS Open Data, CC BY 4.0. These are modified regional visualisations, not official ECMWF products.

The repository also publishes compact road-condition and incident GeoJSON generated from IRCA's
official DATEX II 3.1 snapshot services. The road workflow runs every five minutes and preserves
the official English description for the app.

Attribution: Based on information provided by the Icelandic Road and Coastal Administration (IRCA).

"""Generate Iceland ECMWF total-cloud-cover overlays for the Android app."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, timedelta
from pathlib import Path

import numpy as np
import xarray as xr
from ecmwf.opendata import Client
from PIL import Image

LAT_MIN, LAT_MAX = 63.40, 66.54
LON_MIN, LON_MAX = -24.54, -13.50
STEPS = range(0, 25, 3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--public-base-url", required=True)
    return parser.parse_args()


def retrieve_latest_run(target: Path):
    """Fetch the newest complete IFS run selected by the official client."""
    client = Client(source="ecmwf")
    result = client.retrieve(
        type="fc",
        param="tcc",
        step=list(STEPS),
        target=str(target),
    )
    run_at = result.datetime
    return run_at if run_at.tzinfo is not None else run_at.replace(tzinfo=UTC)


def cloud_rgba(cloud_fraction: np.ndarray) -> Image.Image:
    cloud = np.nan_to_num(cloud_fraction, nan=1.0).clip(0.0, 1.0)
    rgba = np.empty((*cloud.shape, 4), dtype=np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = 210, 230, 255
    rgba[..., 3] = (cloud * 185).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    grib = args.output / "ifs-tcc.grib2"
    run_at = retrieve_latest_run(grib)
    dataset = xr.open_dataset(str(grib), engine="cfgrib", backend_kwargs={"indexpath": ""})
    dataset = dataset.assign_coords(longitude=dataset.longitude % 360).sortby("longitude")
    iceland = dataset.sel(latitude=slice(LAT_MAX, LAT_MIN), longitude=slice(360 + LON_MIN, 360 + LON_MAX))
    base_url = args.public_base_url.rstrip("/")
    frames = []
    for step in STEPS:
        image_name = f"tcc-{step:02d}h.png"
        field = iceland.tcc.sel(step=np.timedelta64(step, "h")).values
        cloud_rgba(field).resize((1024, 768), Image.Resampling.BILINEAR).save(args.output / image_name)
        valid_at = run_at + timedelta(hours=step)
        frames.append({"valid_at": valid_at.isoformat().replace("+00:00", "Z"), "image_url": f"{base_url}/{image_name}"})
    manifest = {
        "model": "ECMWF IFS Open Data (0.25 degree)",
        "run_at": run_at.isoformat().replace("+00:00", "Z"),
        "source_url": "https://www.ecmwf.int/en/forecasts/datasets/open-data",
        "attribution": "European Centre for Medium-Range Weather Forecasts (ECMWF), CC BY 4.0. Modified by Iceland Aurora.",
        "frames": frames,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    grib.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

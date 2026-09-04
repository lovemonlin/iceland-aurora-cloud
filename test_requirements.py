"""Regression guard for the ecmwf-opendata pin.

`ecmwf-opendata` below 0.3.29 silently publishes the wrong forecast cycle.

Its `patch_stream()` rewrote the 06 and 18 UTC IFS runs from `stream=oper` to the retired
`stream=scda`. Since IFS Cycle 50r1 went operational on 2026-05-12 those runs live directly under
`oper`, so the rewritten URL 404s, the client silently falls back to the previous 00/12 UTC cycle,
and the publish *succeeds* carrying stale data. Nothing fails; `run_at` simply never advances to a
06 or 18 UTC cycle.

Measured on 2026-09-04 at 16:17 UTC with the exact request `generate_cloud_frames.py` makes:

    0.3.24  ->  latest() = 2026-09-04T00:00:00   (.../20260904/00z/ifs/0p25/oper/...)
    0.3.29  ->  latest() = 2026-09-04T06:00:00   (.../20260904/06z/ifs/0p25/oper/...)

0.3.29 is the earliest release that carries the `IFS_50R1_DATE = 2026-05-12` boundary, so the pin
must never go below it again.

Run directly (`python test_requirements.py`) or under pytest. It reads the pin as text and needs no
network access.
"""

from __future__ import annotations

import re
from pathlib import Path

MINIMUM_ECMWF_OPENDATA = (0, 3, 29)
REQUIREMENTS = Path(__file__).with_name("requirements.txt")


def _parse(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def read_pin(name: str) -> str:
    """The exact pinned version of one requirement."""
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        match = re.match(rf"^{re.escape(name)}==([0-9.]+)\s*$", line.strip())
        if match:
            return match.group(1)
    raise AssertionError(f"{name} is not pinned in requirements.txt")


def test_ecmwf_opendata_is_not_pinned_below_the_cycle_50r1_fix() -> None:
    pinned = read_pin("ecmwf-opendata")
    assert _parse(pinned) >= MINIMUM_ECMWF_OPENDATA, (
        f"ecmwf-opendata is pinned to {pinned}, below "
        f"{'.'.join(str(part) for part in MINIMUM_ECMWF_OPENDATA)}. Versions below that rewrite the "
        "06/18 UTC IFS runs to the retired stream=scda, so the publisher silently falls back to the "
        "previous 00/12 UTC cycle and republishes stale data without failing."
    )


def test_the_pin_is_exact_so_a_publish_is_reproducible() -> None:
    # A range would let a future release change the resolved cycle without anyone noticing.
    assert re.search(r"^ecmwf-opendata==", REQUIREMENTS.read_text(encoding="utf-8"), re.M)


if __name__ == "__main__":
    test_ecmwf_opendata_is_not_pinned_below_the_cycle_50r1_fix()
    test_the_pin_is_exact_so_a_publish_is_reproducible()
    print(f"OK: ecmwf-opendata=={read_pin('ecmwf-opendata')}")

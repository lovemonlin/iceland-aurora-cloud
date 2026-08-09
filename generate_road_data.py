"""Convert IRCA DATEX II road data into compact GeoJSON for the Android app."""

from __future__ import annotations

import argparse
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from pyproj import Transformer


SOURCES = {
    "locations": "https://datex.vegagerdin.is/predefinedlocationspublication3_1/PredefinedLocationsPublicationService/pullsnapshotdata",
    "conditions": "https://datex.vegagerdin.is/situationpublication3_1/RoadConditionService/pullsnapshotdata",
    "incidents": "https://datex.vegagerdin.is/situationpublication3_1/SituationService/pullsnapshotdata",
    "sites": "https://datex.vegagerdin.is/measurementsitetablepublication3_1/MeasurementSiteTablePublicationService/pullsnapshotdata",
    "measurements": "https://datex.vegagerdin.is/measureddatapublication3_1/MeasureDataService/pullsnapshotdata",
}
ATTRIBUTION = "Based on information provided by the Icelandic Road and Coastal Administration (IRCA)."
TRANSFORM = Transformer.from_crs("EPSG:3057", "EPSG:4326", always_xy=True)


def local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def descendants(element: ET.Element, name: str) -> Iterable[ET.Element]:
    return (child for child in element.iter() if local_name(child) == name)


def first_text(element: ET.Element, name: str) -> str:
    for child in descendants(element, name):
        value = (child.text or "").strip()
        if value:
            return value
    return ""


def translated_values(element: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in descendants(element, "value"):
        text = (value.text or "").strip()
        if text:
            result[value.attrib.get("lang", "unknown")] = text
    return result


def publication_time(root: ET.Element) -> str:
    return first_text(root, "publicationTime")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--public-base-url", required=True)
    parser.add_argument("--source-dir", type=Path, help="Use local DATEX XML snapshot files for repeatable publishing")
    return parser.parse_args()


def load_sources(source_dir: Path | None) -> dict[str, ET.Element]:
    roots: dict[str, ET.Element] = {}
    for name, url in SOURCES.items():
        if source_dir:
            path = source_dir / f"{name}.xml"
            # The first captured IRCA sample was named measured.xml. Keep that
            # spelling accepted so local verification remains straightforward.
            if name == "measurements" and not path.exists():
                path = source_dir / "measured.xml"
            roots[name] = ET.parse(path).getroot()
            continue
        request = urllib.request.Request(url, headers={"User-Agent": "IcelandAuroraRoadPublisher/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            roots[name] = ET.fromstring(response.read())
    return roots


def location_records(root: ET.Element) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for element in descendants(root, "predefinedLocationReference"):
        location_id = element.attrib.get("id")
        line_strings = list(descendants(element, "gmlLineString"))
        if not location_id or not line_strings:
            continue
        names = translated_values(next(descendants(element, "predefinedLocationName"), element))
        road_numbers = [text for item in descendants(element, "roadNumber") if (text := (item.text or "").strip())]
        geometries: list[list[list[float]]] = []
        for line in line_strings:
            pos_list = first_text(line, "posList")
            if not pos_list:
                continue
            values = [float(value) for value in pos_list.split()]
            coordinates = []
            for index in range(0, len(values) - 1, 2):
                lon, lat = TRANSFORM.transform(values[index], values[index + 1])
                coordinates.append([round(lon, 6), round(lat, 6)])
            if len(coordinates) >= 2:
                geometries.append(coordinates)
        if geometries:
            records[location_id] = {
                "name": names.get("en") or names.get("is") or next(iter(names.values()), ""),
                "road_number": ", ".join(dict.fromkeys(road_numbers)),
                "coordinates": geometries,
            }
    return records


def status_code(english_comments: list[str], type_values: list[str]) -> str:
    text = " ".join(english_comments).lower()
    if "impassable" in text or "no passage" in text:
        return "closed"
    if "mountain vehicles" in text:
        return "mountain_vehicles"
    if "extremely slippery" in text:
        return "extremely_slippery"
    if "slippery" in text:
        return "slippery"
    if "wet snow" in text:
        return "wet_snow"
    if "snow" in text:
        return "snow"
    if "difficult" in text:
        return "difficult"
    if "spots of ice" in text:
        return "spots_of_ice"
    if "flying gravel" in text or "loosechippings" in " ".join(type_values).lower():
        return "loose_gravel"
    if "fog" in text:
        return "fog"
    if "weight" in text:
        return "weight_restriction"
    if "easily passable" in text:
        return "easily_passable"
    if "not known" in text or "unknown" in " ".join(type_values).lower():
        return "unknown"
    return "restriction"


def condition_records(root: ET.Element) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for situation in descendants(root, "situation"):
        record = next(descendants(situation, "situationRecord"), None)
        if record is None:
            continue
        reference = next(descendants(record, "predefinedLocationReference"), None)
        location_id = reference.attrib.get("id") if reference is not None else None
        if not location_id:
            continue
        comments_en: list[str] = []
        comments_is: list[str] = []
        for comment in descendants(record, "comment"):
            values = translated_values(comment)
            if values.get("en"):
                comments_en.append(values["en"])
            if values.get("is"):
                comments_is.append(values["is"])
        types = [
            (item.text or "").strip()
            for item in record.iter()
            if local_name(item).endswith("Type") and (item.text or "").strip()
        ]
        result[location_id] = {
            "status": status_code(comments_en, types),
            "description_en": " · ".join(comments_en),
            "description_is": " · ".join(comments_is),
            "updated_at": first_text(record, "situationRecordVersionTime"),
        }
    return result


def road_geojson(locations: dict[str, dict], conditions: dict[str, dict]) -> dict:
    features = []
    for location_id, location in locations.items():
        condition = conditions.get(location_id, {})
        properties = {
            "id": location_id,
            "name": location["name"],
            "road_number": location["road_number"],
            "status": condition.get("status", "no_reported_restriction"),
            "description_en": condition.get("description_en", "No reported restriction"),
            "description_is": condition.get("description_is", ""),
            "updated_at": condition.get("updated_at", ""),
        }
        geometry_type = "LineString" if len(location["coordinates"]) == 1 else "MultiLineString"
        coordinates = location["coordinates"][0] if geometry_type == "LineString" else location["coordinates"]
        features.append({"type": "Feature", "properties": properties, "geometry": {"type": geometry_type, "coordinates": coordinates}})
    return {"type": "FeatureCollection", "features": features}


def incident_kind(record: ET.Element) -> str:
    xsi_type = next((value for key, value in record.attrib.items() if key.endswith("}type")), "").split(":")[-1]
    explicit = next(
        (
            (item.text or "").strip()
            for item in record.iter()
            if local_name(item).endswith("Type") and local_name(item) != "commentType" and (item.text or "").strip()
        ),
        "",
    )
    raw = (explicit or xsi_type or "incident").lower()
    if "maintenance" in raw or "roadwork" in raw:
        return "roadworks"
    if "accident" in raw:
        return "accident"
    if "animal" in raw:
        return "animals"
    if "closed" in raw or "passage" in raw:
        return "closure"
    if "poorcondition" in raw or "loosechipping" in raw:
        return "road_surface"
    return "warning"


def incident_geojson(root: ET.Element) -> dict:
    features = []
    for situation in descendants(root, "situation"):
        record = next(descendants(situation, "situationRecord"), None)
        if record is None:
            continue
        display = next(descendants(record, "coordinatesForDisplay"), None)
        if display is None:
            continue
        try:
            lat = float(first_text(display, "latitude"))
            lon = float(first_text(display, "longitude"))
        except ValueError:
            continue
        values = translated_values(next(descendants(record, "comment"), record))
        kind = incident_kind(record)
        features.append({
            "type": "Feature",
            "properties": {
                "id": situation.attrib.get("id", record.attrib.get("id", "")),
                "kind": kind,
                "title_en": {"roadworks": "Road works", "accident": "Traffic accident", "animals": "Animals on road", "closure": "Road closed", "road_surface": "Road surface warning"}.get(kind, "Road warning"),
                "description_en": values.get("en", ""),
                "description_is": values.get("is", ""),
                "started_at": first_text(record, "overallStartTime"),
                "ends_at": first_text(record, "overallEndTime"),
                "updated_at": first_text(record, "situationRecordVersionTime"),
            },
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
        })
    return {"type": "FeatureCollection", "features": features}


def number_text(element: ET.Element, name: str) -> str:
    """Return a compact numeric DATEX value, or an empty string when absent."""
    value = first_text(element, name)
    if not value:
        return ""
    try:
        return f"{float(value):.1f}".rstrip("0").rstrip(".")
    except ValueError:
        return value


def has_descendant(element: ET.Element, name: str) -> bool:
    return next(descendants(element, name), None) is not None


def station_records(root: ET.Element) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for site in descendants(root, "measurementSite"):
        site_id = site.attrib.get("id", "")
        display = next(descendants(site, "coordinatesForDisplay"), None)
        if not site_id or display is None:
            continue
        try:
            latitude = float(first_text(display, "latitude"))
            longitude = float(first_text(display, "longitude"))
        except ValueError:
            continue
        names = translated_values(next(descendants(site, "measurementSiteName"), site))
        records[site_id] = {
            "name": names.get("en") or names.get("is") or next(iter(names.values()), site_id),
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
        }
    return records


def station_records_from_geojson(path: Path) -> dict[str, dict]:
    """Reuse stable station names and coordinates when IRCA omits its site table.

    IRCA's measured-data feed can remain current while the separate measurement
    site table temporarily contains no ``measurementSite`` entries. Coordinates
    change rarely, so the last successfully published GeoJSON is a safer source
    of station metadata than replacing the live layer with an empty collection.
    """
    if not path.is_file():
        return {}
    try:
        collection = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    records: dict[str, dict] = {}
    for feature in collection.get("features", []):
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        site_id = str(properties.get("id") or "")
        if geometry.get("type") != "Point" or not site_id or len(coordinates) < 2:
            continue
        try:
            longitude = float(coordinates[0])
            latitude = float(coordinates[1])
        except (TypeError, ValueError):
            continue
        records[site_id] = {
            "name": str(properties.get("name") or site_id),
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
        }
    return records


def measurement_records(root: ET.Element) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for measurement in descendants(root, "siteMeasurements"):
        reference = next(descendants(measurement, "measurementSiteReference"), None)
        site_id = reference.attrib.get("id", "") if reference is not None else ""
        if not site_id:
            continue
        values: dict[str, str] = {"updated_at": first_text(measurement, "timeValue")}
        for quantity in descendants(measurement, "physicalQuantity"):
            # Each physicalQuantity has one value type. The tests are based on
            # element names rather than index values, which IRCA can change.
            if has_descendant(quantity, "airTemperature"):
                values["temperature"] = number_text(quantity, "temperature")
            elif has_descendant(quantity, "roadSurfaceTemperature"):
                values["road_temperature"] = number_text(quantity, "temperature")
            elif has_descendant(quantity, "windDirectionBearing"):
                values["wind_direction"] = number_text(quantity, "directionBearing")
            elif has_descendant(quantity, "maximumWindSpeed"):
                values["wind_gust"] = number_text(quantity, "windSpeed")
            elif has_descendant(quantity, "windSpeed"):
                values["wind_speed"] = number_text(quantity, "windSpeed")
            elif has_descendant(quantity, "relativeHumidity"):
                values["humidity"] = number_text(quantity, "percentage")
            elif has_descendant(quantity, "vehicleFlowPer10Minute"):
                values["traffic_recent"] = number_text(next(descendants(quantity, "vehicleFlowPer10Minute")), "vehicleFlowRate")
            elif has_descendant(quantity, "vehicleFlowPerDay"):
                values["traffic_today"] = number_text(next(descendants(quantity, "vehicleFlowPerDay")), "vehicleFlowRate")
        records[site_id] = values
    return records


def wind_arrow(direction: str) -> str:
    try:
        value = (float(direction) + 180) % 360  # show where the wind is blowing to
    except ValueError:
        return ""
    arrows = ["↓", "↙", "←", "↖", "↑", "↗", "→", "↘"]
    return arrows[int((value + 22.5) // 45) % 8]


def station_geojson(sites: dict[str, dict], measurements: dict[str, dict]) -> dict:
    features = []
    for site_id, site in sites.items():
        measured = measurements.get(site_id)
        if not measured:
            continue
        temperature = measured.get("temperature", "")
        wind_speed = measured.get("wind_speed", "")
        recent = measured.get("traffic_recent", "")
        today = measured.get("traffic_today", "")
        label_lines = []
        if temperature:
            label_lines.append(f"{temperature}°")
        if wind_speed:
            label_lines.append(f"{wind_arrow(measured.get('wind_direction', ''))} {wind_speed} m/s".strip())
        if recent or today:
            label_lines.append(f"🚗 {recent or '—'} / {today or '—'}")
        features.append({
            "type": "Feature",
            "properties": {
                "id": site_id,
                "name": site["name"],
                "temperature": temperature,
                "road_temperature": measured.get("road_temperature", ""),
                "wind_speed": wind_speed,
                "wind_gust": measured.get("wind_gust", ""),
                "wind_direction": measured.get("wind_direction", ""),
                "humidity": measured.get("humidity", ""),
                "traffic_recent": recent,
                "traffic_today": today,
                "updated_at": measured.get("updated_at", ""),
                "map_label": "\n".join(label_lines),
                "has_traffic": bool(recent or today),
            },
            "geometry": {"type": "Point", "coordinates": [site["longitude"], site["latitude"]]},
        })
    return {"type": "FeatureCollection", "features": features}


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    roots = load_sources(args.source_dir)
    locations = location_records(roots["locations"])
    conditions = condition_records(roots["conditions"])
    roads = road_geojson(locations, conditions)
    incidents = incident_geojson(roots["incidents"])
    sites = station_records(roots["sites"])
    if not sites:
        sites = station_records_from_geojson(args.output / "road-stations.geojson")
    measurements = measurement_records(roots["measurements"])
    if not sites:
        raise RuntimeError("IRCA returned no measurement-site metadata and no previous station GeoJSON is available")
    if not measurements:
        raise RuntimeError("IRCA returned no road weather or traffic measurements")
    stations = station_geojson(sites, measurements)
    if not stations["features"]:
        raise RuntimeError("IRCA measurement IDs do not match the available station metadata")
    write_json(args.output / "road-conditions.geojson", roads)
    write_json(args.output / "road-incidents.geojson", incidents)
    write_json(args.output / "road-stations.geojson", stations)
    base_url = args.public_base_url.rstrip("/")
    write_json(args.output / "road-manifest.json", {
        "schema_version": 2,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "road_data_at": publication_time(roots["conditions"]),
        "incident_data_at": publication_time(roots["incidents"]),
        "measurement_data_at": publication_time(roots["measurements"]),
        "road_count": len(roads["features"]),
        "incident_count": len(incidents["features"]),
        "station_count": len(stations["features"]),
        "traffic_station_count": sum(item["properties"]["has_traffic"] for item in stations["features"]),
        "roads_url": f"{base_url}/road-conditions.geojson",
        "incidents_url": f"{base_url}/road-incidents.geojson",
        "stations_url": f"{base_url}/road-stations.geojson",
        "attribution": ATTRIBUTION,
        "source_url": "https://umferdin.is/en",
    })
    print(f"Published {len(roads['features'])} roads, {len(incidents['features'])} incidents and {len(stations['features'])} measurement stations")


if __name__ == "__main__":
    main()

import json
import tempfile
import unittest
from pathlib import Path

from generate_road_data import station_geojson, station_records_from_geojson


class StationMetadataFallbackTest(unittest.TestCase):
    def test_reuses_previous_station_coordinates_and_refreshes_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "road-stations.geojson"
            path.write_text(
                json.dumps({
                    "type": "FeatureCollection",
                    "features": [{
                        "type": "Feature",
                        "properties": {"id": "IRCA_MP_1", "name": "Test station"},
                        "geometry": {"type": "Point", "coordinates": [-20.5, 64.1]},
                    }],
                }),
                encoding="utf-8",
            )

            sites = station_records_from_geojson(path)
            result = station_geojson(sites, {
                "IRCA_MP_1": {
                    "temperature": "4.5",
                    "wind_speed": "7",
                    "wind_direction": "90",
                    "traffic_recent": "12",
                    "traffic_today": "340",
                    "updated_at": "2026-08-09T15:00:00Z",
                },
            })

            self.assertEqual({"IRCA_MP_1"}, set(sites))
            self.assertEqual([-20.5, 64.1], result["features"][0]["geometry"]["coordinates"])
            self.assertEqual("4.5", result["features"][0]["properties"]["temperature"])
            self.assertEqual("12", result["features"][0]["properties"]["traffic_recent"])
            self.assertTrue(result["features"][0]["properties"]["has_traffic"])

    def test_missing_or_invalid_previous_file_is_not_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "road-stations.geojson"
            self.assertEqual({}, station_records_from_geojson(path))
            path.write_text("not json", encoding="utf-8")
            self.assertEqual({}, station_records_from_geojson(path))


if __name__ == "__main__":
    unittest.main()

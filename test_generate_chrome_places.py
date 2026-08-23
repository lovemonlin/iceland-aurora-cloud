import json
import tempfile
import unittest
from pathlib import Path

from generate_chrome_places import generate


class ChromePlaceGeneratorTest(unittest.TestCase):
    def test_generates_free_cards_and_filters_shared_keywords(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "places").mkdir()
            (root / "places-manifest.json").write_text(
                json.dumps({"place_count": 2, "generated_at": "2026-08-23T00:00:00Z"}), encoding="utf-8"
            )
            places = [
                self.place("one", "蓋錫爾間歇泉", "Geysir", ["Geysir", "Strokkur", "Waterfall"]),
                self.place("two", "測試瀑布", "Test Waterfall", ["Test", "Waterfall"]),
            ]
            (root / "places-index.json").write_text(json.dumps({"places": places}), encoding="utf-8")
            for place in places:
                (root / "places" / f"{place['id']}.json").write_text(json.dumps(place), encoding="utf-8")

            result = generate(root)

            self.assertEqual(2, len(result["places"]))
            self.assertIn("Strokkur", result["places"][0]["aliases"])
            self.assertIn("蓋錫爾", result["places"][0]["aliases"])
            self.assertNotIn("Waterfall", result["places"][0]["aliases"])
            self.assertEqual(["付費停車", "免費廁所", "觀景台"], result["places"][0]["facilities"])
            self.assertLessEqual(len(result["places"][0]["shortSummary"]), 110)

    @staticmethod
    def place(place_id, name_zh, name_en, keywords):
        return {
            "id": place_id,
            "status": "published",
            "name_zh": name_zh,
            "name_en": name_en,
            "summary_zh": "這是一段很長的測試摘要。" * 20,
            "google_maps_url": "https://maps.example/place",
            "cover_image_url": None,
            "facilities": ["parking", "toilet", "viewpoint"],
            "parking": "paid",
            "toilet": "free",
            "recommendation": 3,
            "latitude": 64.3,
            "longitude": -20.3,
            "search_keywords": keywords,
        }


if __name__ == "__main__":
    unittest.main()

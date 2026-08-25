#!/usr/bin/env python3
import argparse
import json
import re
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path


GENERIC_ALIASES = {
    "area", "attraction", "beach", "cave", "church", "circle", "city", "falls",
    "golden", "hot", "lake", "landmark", "mountain", "national", "park", "river",
    "route", "spring", "the", "viewpoint", "waterfall", "冰島", "公園", "地標", "景點",
    "瀑布", "溫泉", "黃金圈",
}
ZH_SUFFIXES = ("國家公園", "間歇泉", "冰河湖", "瀑布", "教堂", "燈塔", "溫泉", "海灘", "峽谷", "洞穴")
EN_SUFFIXES = (" national park", " waterfall", " church", " lighthouse", " hot spring", " beach", " canyon", " cave")
FACILITY_LABELS = {
    "viewpoint": "觀景台",
    "food": "餐飲",
    "fuel": "加油",
    "convenience_store": "超商",
}
FACILITY_LABELS_EN = {
    "viewpoint": "Viewpoint",
    "food": "Food",
    "fuel": "Fuel",
    "convenience_store": "Convenience store",
}
REGION_LABELS = {
    "southwest": "西南冰島",
    "southeast": "東南冰島",
    "eastfjords": "東峽灣",
    "northeast": "東北冰島",
    "northwest": "西北冰島",
    "westfjords": "西峽灣",
    "snaefellsnes": "斯奈山半島",
}
REGION_LABELS_EN = {
    "southwest": "Southwest Iceland",
    "southeast": "Southeast Iceland",
    "eastfjords": "Eastfjords",
    "northeast": "Northeast Iceland",
    "northwest": "Northwest Iceland",
    "westfjords": "Westfjords",
    "snaefellsnes": "Snæfellsnes Peninsula",
}
GOOGLE_MAPS_ALIASES = {
    "attraction-skogafoss": ["史可加瀑布", "斯科加爾瀑布"],
}


def load_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def normalize(value):
    value = unicodedata.normalize("NFKD", str(value).strip().lower())
    return "".join(character for character in value if character.isalnum())


def keyword_values(place):
    values = place.get("search_keywords") or []
    if isinstance(values, str):
        values = [values]
    if len(values) == 1 and len(values[0]) > 80:
        values = re.split(r"\s+", values[0])
    return [value.strip() for value in values if isinstance(value, str) and value.strip()]


def derived_name_aliases(place):
    aliases = []
    name_zh = place["name_zh"].strip()
    for suffix in ZH_SUFFIXES:
        if name_zh.endswith(suffix) and len(name_zh.removesuffix(suffix)) >= 3:
            aliases.append(name_zh.removesuffix(suffix))
            break
    name_en = place["name_en"].strip()
    lowered = name_en.lower()
    for suffix in EN_SUFFIXES:
        if lowered.endswith(suffix) and len(name_en[:-len(suffix)].strip()) >= 4:
            aliases.append(name_en[:-len(suffix)].strip())
            break
    return aliases


def short_summary(value):
    return " ".join(str(value).split())


def facility_labels(place, english=False):
    facilities = set(place.get("facilities") or [])
    labels = []
    parking_labels = {"free": "Free parking", "paid": "Paid parking"} if english else {"free": "免費停車", "paid": "付費停車"}
    toilet_labels = {"free": "Free restroom", "paid": "Paid restroom", "none": "No restroom"} if english else {"free": "免費廁所", "paid": "付費廁所", "none": "無廁所"}
    if "parking" in facilities or place.get("parking"):
        labels.append(parking_labels.get(place.get("parking"), "Parking" if english else "停車"))
    if "toilet" in facilities or place.get("toilet"):
        labels.append(toilet_labels.get(place.get("toilet"), "Restroom" if english else "廁所"))
    facility_labels_by_type = FACILITY_LABELS_EN if english else FACILITY_LABELS
    labels.extend(facility_labels_by_type[item] for item in facility_labels_by_type if item in facilities)
    return labels


def generate(root):
    manifest = load_json(root / "places-manifest.json")
    index = load_json(root / "places-index.json")
    indexed_places = [place for place in index["places"] if place.get("status") == "published"]
    if manifest["place_count"] != len(indexed_places):
        raise ValueError("places-manifest.json 與已發布景點數量不一致")

    details = []
    for indexed_place in indexed_places:
        detail = load_json(root / "places" / f"{indexed_place['id']}.json")
        if detail.get("id") != indexed_place["id"]:
            raise ValueError(f"景點 ID 不一致：{indexed_place['id']}")
        details.append(detail)

    keyword_sets = [{normalize(value) for value in keyword_values(place)} for place in details]
    frequency = Counter(value for values in keyword_sets for value in values if value)
    output_places = []
    for place in details:
        latitude = place.get("latitude")
        longitude = place.get("longitude")
        rating = place.get("recommendation")
        last_verified = place.get("last_verified")
        region = place.get("region")
        stay_minutes = place.get("recommended_stay_minutes")
        if not (isinstance(latitude, (int, float)) and isinstance(longitude, (int, float))):
            raise ValueError(f"缺少座標：{place['id']}")
        if not (1 <= rating <= 3):
            raise ValueError(f"推薦星等不正確：{place['id']}")
        if region not in REGION_LABELS:
            raise ValueError(f"地區不正確：{place['id']}")
        if stay_minutes is not None and (not isinstance(stay_minutes, int) or stay_minutes <= 0):
            raise ValueError(f"建議停留時間不正確：{place['id']}")
        try:
            date.fromisoformat(last_verified)
        except (TypeError, ValueError) as error:
            raise ValueError(f"最後確認日期不正確：{place['id']}") from error
        if not str(place.get("google_maps_url", "")).startswith("https://"):
            raise ValueError(f"Google Maps 網址不正確：{place['id']}")

        aliases = []
        candidates = keyword_values(place) + derived_name_aliases(place) + GOOGLE_MAPS_ALIASES.get(place["id"], [])
        for candidate in candidates:
            key = normalize(candidate)
            has_non_ascii = any(ord(character) > 127 for character in candidate)
            if not key or key in {normalize(place["name_zh"]), normalize(place["name_en"])}:
                continue
            if key in {normalize(value) for value in GENERIC_ALIASES}:
                continue
            if frequency.get(key, 1) > 1:
                continue
            if len(key) < (2 if has_non_ascii else 4):
                continue
            if key not in {normalize(value) for value in aliases}:
                aliases.append(candidate)

        cover = place.get("cover_image_url") or None
        if cover and not cover.startswith("https://"):
            raise ValueError(f"封面網址不正確：{place['id']}")
        output_places.append({
            "id": place["id"],
            "nameZh": place["name_zh"],
            "nameEn": place["name_en"],
            "aliases": aliases,
            "latitude": latitude,
            "longitude": longitude,
            "matchRadiusMeters": 800,
            "coverImageUrl": cover,
            "shortSummary": short_summary(place["summary_zh"]),
            "shortSummaryEn": short_summary(place["summary_en"]),
            "rating": rating,
            "lastVerified": last_verified,
            "regionLabel": REGION_LABELS[region],
            "regionLabelEn": REGION_LABELS_EN[region],
            "recommendedStayMinutes": stay_minutes,
            "facilities": facility_labels(place),
            "facilitiesEn": facility_labels(place, english=True),
            "googleMapsUrl": place["google_maps_url"],
            "appUrl": None,
        })

    return {
        "schemaVersion": 2,
        "generatedAt": manifest["generated_at"],
        "places": output_places,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate the free Chrome place index from published App data.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, default=Path("chrome-places.json"))
    args = parser.parse_args()
    result = generate(args.root)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"CHROME_PLACES_OK count={len(result['places'])} output={args.output}")


if __name__ == "__main__":
    main()

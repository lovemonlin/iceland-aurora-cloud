#!/usr/bin/env python3
"""Generate the public Chrome announcement config from Notion."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any


DATA_SOURCE_ID = "3c536b38-6fd9-80e3-99d9-000b960b86a8"
NOTION_API_VERSION = "2026-03-11"
TAIPEI = timezone(timedelta(hours=8))
PUBLISHABLE_STATUSES = {"啟用中", "排程中"}


class AnnouncementError(ValueError):
    """Raised when Notion announcement data is unsafe to publish."""


def _plain_text(items: list[dict[str, Any]]) -> str:
    return "".join(item.get("plain_text", "") for item in items).strip()


def _property_text(properties: dict[str, Any], name: str) -> str:
    prop = properties.get(name, {})
    return _plain_text(prop.get("title", prop.get("rich_text", [])))


def _parse_notion_date(value: str | None, *, is_end: bool) -> datetime | None:
    if not value:
        return None
    if len(value) == 10:
        day = datetime.fromisoformat(value).date()
        return datetime.combine(day, time.max if is_end else time.min, TAIPEI)

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=TAIPEI) if parsed.tzinfo is None else parsed


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def build_config(pages: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    if now.tzinfo is None:
        raise AnnouncementError("目前時間必須包含時區。")

    active: list[dict[str, Any]] = []
    for page in pages:
        properties = page.get("properties", {})
        status = properties.get("狀態", {}).get("status", {}).get("name", "")
        if status not in PUBLISHABLE_STATUSES:
            continue

        start_date = properties.get("開始時間", {}).get("date") or {}
        end_date = properties.get("結束時間", {}).get("date") or {}
        starts_at = _parse_notion_date(start_date.get("start"), is_end=False)
        ends_at = _parse_notion_date(end_date.get("start"), is_end=True)

        if status == "排程中" and starts_at is None:
            raise AnnouncementError("排程中的公告必須填寫開始時間。")
        if starts_at and ends_at and ends_at < starts_at:
            raise AnnouncementError("公告的結束時間不可早於開始時間。")
        if starts_at and now < starts_at:
            continue
        if ends_at and now > ends_at:
            continue

        title = _property_text(properties, "公告標題")
        message = _property_text(properties, "公告內容")
        button_text = _property_text(properties, "按鈕文字")
        url = (properties.get("按鈕網址", {}).get("url") or "").strip()

        if not title or not message:
            raise AnnouncementError("啟用中的公告必須填寫公告標題與公告內容。")
        if bool(button_text) != bool(url):
            raise AnnouncementError("按鈕文字與按鈕網址必須同時填寫，或同時留空。")
        if url and not url.startswith("https://"):
            raise AnnouncementError("公告按鈕只允許 HTTPS 網址。")

        active.append(
            {
                "enabled": True,
                "title": title,
                "message": message,
                "buttonText": button_text or None,
                "url": url or None,
                "startsAt": _iso(starts_at),
                "endsAt": _iso(ends_at),
            }
        )

    if len(active) > 1:
        raise AnnouncementError("同一時間只能有一筆啟用中的公告。")

    return {
        "schemaVersion": 1,
        "announcement": active[0] if active else {"enabled": False},
    }


def query_notion(token: str) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        body: dict[str, Any] = {
            "filter": {
                "or": [
                    {"property": "狀態", "status": {"equals": "啟用中"}},
                    {"property": "狀態", "status": {"equals": "排程中"}},
                ]
            },
            "page_size": 100,
        }
        if cursor:
            body["start_cursor"] = cursor

        request = urllib.request.Request(
            f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Notion-Version": NOTION_API_VERSION,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Notion API 回傳 HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"無法連線 Notion API: {error.reason}") from error

        pages.extend(payload.get("results", []))
        if not payload.get("has_more"):
            return pages
        cursor = payload.get("next_cursor")
        if not cursor:
            raise RuntimeError("Notion API 表示仍有資料，卻沒有回傳下一頁游標。")


def write_if_changed(path: Path, config: dict[str, Any]) -> bool:
    rendered = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8", newline="\n")
    temporary.replace(path)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("chrome-config.json"))
    args = parser.parse_args()

    token = os.environ.get("NOTION_API_KEY") or os.environ.get("NOTION_TOKEN")
    if not token:
        print("缺少 NOTION_API_KEY（本機亦可使用 NOTION_TOKEN）。", file=sys.stderr)
        return 2

    try:
        config = build_config(query_notion(token), datetime.now(timezone.utc))
        changed = write_if_changed(args.output, config)
    except (AnnouncementError, RuntimeError) as error:
        print(f"公告發布失敗：{error}", file=sys.stderr)
        return 1

    print(f"Chrome 公告設定：{'已更新' if changed else '沒有變更'} ({args.output})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

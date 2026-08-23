import unittest
from datetime import datetime

from generate_chrome_announcement import AnnouncementError, TAIPEI, build_config


def page(
    *, status="啟用中", title="Notion 公告測試",
    message="這是測試 Notion 資料庫公告系統",
    button_text="點我去看公告", url="https://example.com/announcement",
    starts_at="2026-08-23", ends_at="2026-08-24",
):
    def rich_text(value):
        return [{"plain_text": value}] if value else []

    return {
        "properties": {
            "公告標題": {"title": rich_text(title)},
            "狀態": {"status": {"name": status}},
            "公告內容": {"rich_text": rich_text(message)},
            "按鈕文字": {"rich_text": rich_text(button_text)},
            "按鈕網址": {"url": url},
            "開始時間": {"date": {"start": starts_at} if starts_at else None},
            "結束時間": {"date": {"start": ends_at} if ends_at else None},
        }
    }


class BuildConfigTest(unittest.TestCase):
    def test_date_only_uses_full_taipei_days(self):
        config = build_config([page()], datetime(2026, 8, 24, 12, tzinfo=TAIPEI))
        announcement = config["announcement"]
        self.assertTrue(announcement["enabled"])
        self.assertEqual(announcement["startsAt"], "2026-08-23T00:00:00+08:00")
        self.assertEqual(announcement["endsAt"], "2026-08-24T23:59:59+08:00")

    def test_ended_announcement_is_not_published(self):
        config = build_config(
            [page(status="已結束")],
            datetime(2026, 8, 24, 12, tzinfo=TAIPEI),
        )
        self.assertEqual(config["announcement"], {"enabled": False})

    def test_more_than_one_active_announcement_fails_safely(self):
        with self.assertRaisesRegex(AnnouncementError, "只能有一筆"):
            build_config([page(), page()], datetime(2026, 8, 24, 12, tzinfo=TAIPEI))

    def test_button_text_and_url_must_be_a_pair(self):
        with self.assertRaisesRegex(AnnouncementError, "必須同時填寫"):
            build_config([page(url="")], datetime(2026, 8, 24, 12, tzinfo=TAIPEI))

    def test_button_url_must_use_https(self):
        with self.assertRaisesRegex(AnnouncementError, "HTTPS"):
            build_config(
                [page(url="http://example.com")],
                datetime(2026, 8, 24, 12, tzinfo=TAIPEI),
            )


if __name__ == "__main__":
    unittest.main()

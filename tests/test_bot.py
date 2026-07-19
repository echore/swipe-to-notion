import bot


def test_detect_platform_known():
    assert bot.detect_platform("https://www.xiaohongshu.com/abc") == ["小红书"]
    assert bot.detect_platform("https://b23.tv/xyz") == ["B站"]
    assert bot.detect_platform("https://x.com/user/status/1") == ["Twitter/X"]


def test_detect_platform_unknown():
    assert bot.detect_platform("https://example.com/foo") == ["其他"]


def test_extract_urls_multiple():
    text = "看这个 https://a.com/1 和 https://b.com/2 备注"
    assert bot.extract_urls(text) == ["https://a.com/1", "https://b.com/2"]


def test_extract_note_strips_urls():
    assert bot.extract_note("好帖 https://a.com/1 值得学") == "好帖  值得学"


def test_save_to_notion_builds_payload(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(bot.requests, "post", fake_post)
    monkeypatch.setattr(bot, "NOTION_DATABASE_ID", "db123")

    ok = bot.save_to_notion("https://x.com/p/1", ["Twitter/X"], "好帖")

    assert ok is True
    props = captured["json"]["properties"]
    assert props[bot.TITLE_PROPERTY]["title"][0]["text"]["content"] == "好帖"
    assert props[bot.URL_PROPERTY]["url"] == "https://x.com/p/1"
    assert props[bot.STATUS_PROPERTY]["select"]["name"] == bot.DEFAULT_STATUS
    assert props[bot.PLATFORM_PROPERTY]["multi_select"] == [{"name": "Twitter/X"}]


def test_save_to_notion_title_falls_back_to_url(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200

    monkeypatch.setattr(bot.requests, "post",
                        lambda url, headers=None, json=None, timeout=None: captured.update(json=json) or FakeResp())
    bot.save_to_notion("https://x.com/p/1", ["其他"], "")
    assert captured["json"]["properties"][bot.TITLE_PROPERTY]["title"][0]["text"]["content"] == "https://x.com/p/1"

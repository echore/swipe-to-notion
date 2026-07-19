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


def test_handle_text_no_url():
    assert "没有检测到链接" in bot.handle_text("纯文字没有链接")


def test_handle_text_saves_each_url(monkeypatch):
    saved = []
    monkeypatch.setattr(bot, "save_to_notion", lambda url, platform, note: saved.append((url, platform, note)) or True)
    reply = bot.handle_text("https://b23.tv/x 好视频")
    assert saved == [("https://b23.tv/x", ["B站"], "好视频")]
    assert "已存入" in reply


def test_handle_text_reports_failure_when_save_returns_false(monkeypatch):
    monkeypatch.setattr(bot, "save_to_notion", lambda url, platform, note: False)
    reply = bot.handle_text("https://b23.tv/x 好视频")
    assert "存入失败" in reply


def test_handle_text_reports_failure_when_save_raises(monkeypatch):
    def boom(url, platform, note):
        raise RuntimeError("network down")

    monkeypatch.setattr(bot, "save_to_notion", boom)
    reply = bot.handle_text("https://b23.tv/x 好视频")
    assert "存入失败" in reply


def test_run_once_processes_and_confirms_offset(monkeypatch):
    monkeypatch.setattr(bot, "save_to_notion", lambda *a, **k: True)
    calls = {"offsets": [], "sent": []}
    fake_updates = [
        {"update_id": 301, "message": {"chat": {"id": 9}, "text": "https://x.com/p/1"}},
    ]

    def fake_get_updates(token, offset=None, timeout=0):
        calls["offsets"].append(offset)
        return fake_updates if offset is None else []

    def fake_send(token, chat_id, text):
        calls["sent"].append((chat_id, text))
        return {}

    count = bot.run_once("T", fake_get_updates, fake_send, bot.handle_text)
    assert count == 1
    assert calls["offsets"] == [None, 302]
    assert calls["sent"][0][0] == 9


def test_run_once_advances_offset_even_when_notion_save_fails(monkeypatch):
    monkeypatch.setattr(bot, "save_to_notion", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    calls = {"offsets": [], "sent": []}
    fake_updates = [
        {"update_id": 301, "message": {"chat": {"id": 9}, "text": "https://x.com/p/1"}},
    ]

    def fake_get_updates(token, offset=None, timeout=0):
        calls["offsets"].append(offset)
        return fake_updates if offset is None else []

    def fake_send(token, chat_id, text):
        calls["sent"].append((chat_id, text))
        return {}

    count = bot.run_once("T", fake_get_updates, fake_send, bot.handle_text)
    assert count == 1
    assert calls["offsets"] == [None, 302]
    assert "存入失败" in calls["sent"][0][1]


def test_run_once_empty_no_confirm():
    assert bot.run_once("T", lambda *a, **k: [], lambda *a: {}, lambda t: "") == 0

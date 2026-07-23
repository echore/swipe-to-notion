import bot


# ---------- 平台识别：英文 slug ----------
def test_detect_platform_english_slugs():
    assert bot.detect_platform("https://www.xiaohongshu.com/abc") == ["Xiaohongshu"]
    assert bot.detect_platform("https://b23.tv/xyz") == ["Bilibili"]
    assert bot.detect_platform("https://x.com/user/status/1") == ["Twitter/X"]
    assert bot.detect_platform("https://youtu.be/x") == ["YouTube"]
    assert bot.detect_platform("https://weibo.com/x") == ["Weibo"]
    assert bot.detect_platform("https://www.douyin.com/x") == ["Douyin"]


def test_detect_platform_unknown_is_other():
    assert bot.detect_platform("https://example.com/foo") == ["Other"]


def test_extract_urls_multiple():
    text = "看这个 https://a.com/1 和 https://b.com/2 备注"
    assert bot.extract_urls(text) == ["https://a.com/1", "https://b.com/2"]


def test_extract_note_strips_urls():
    assert bot.extract_note("好帖 https://a.com/1 值得学") == "好帖  值得学"


# ---------- schema fixtures ----------
def _sel(*names):
    return {"type": "select", "select": {"options": [{"name": n} for n in names]}}


def _status(*names):
    return {"type": "status", "status": {"options": [{"name": n} for n in names]}}


def _ms(*names):
    return {"type": "multi_select", "multi_select": {"options": [{"name": n} for n in names]}}


CN_SCHEMA = {
    "素材名称": {"type": "title", "title": {}},
    "素材链接": {"type": "url", "url": {}},
    "状态": _sel("待分析", "分析中", "已应用"),
    "平台来源": _ms("Xiaohongshu", "YouTube"),
}
EN_SCHEMA = {
    "Name": {"type": "title", "title": {}},
    "Link": {"type": "url", "url": {}},
    "Status": _sel("To Review", "Analyzing", "Applied"),
    "Platform": _ms("YouTube"),
}


# ---------- 类型推断：唯一类型 ----------
def test_resolves_chinese_schema_by_type():
    r = bot.resolve_roles(CN_SCHEMA, {})
    assert r["title"]["name"] == "素材名称"
    assert r["link"]["name"] == "素材链接"
    assert r["status"]["name"] == "状态"
    assert r["status"]["default"] == "待分析"
    assert r["platform"]["name"] == "平台来源"


def test_resolves_english_schema_by_type():
    r = bot.resolve_roles(EN_SCHEMA, {})
    assert r["status"]["default"] == "To Review"
    assert r["link"]["name"] == "Link"


# ---------- 认 Notion 的 status 类型 ----------
def test_status_property_type_recognized():
    schema = {"名字": {"type": "title", "title": {}}, "进度": _status("待办", "进行中")}
    r = bot.resolve_roles(schema, {})
    assert r["status"]["name"] == "进度"
    assert r["status"]["type"] == "status"
    assert r["status"]["default"] == "待办"


# ---------- 方法5：撞车按名字兜底 ----------
def test_two_selects_pick_status_by_hint():
    schema = {"名字": {"type": "title", "title": {}},
              "状态": _sel("待分析"), "优先级": _sel("高", "低")}
    r = bot.resolve_roles(schema, {})
    assert r["status"]["name"] == "状态"


def test_two_multiselects_pick_platform_by_hint():
    schema = {"名字": {"type": "title", "title": {}},
              "平台来源": _ms("YouTube"), "主题标签": _ms("口播", "测评")}
    r = bot.resolve_roles(schema, {})
    assert r["platform"]["name"] == "平台来源"


def test_two_urls_pick_link_by_hint():
    schema = {"名字": {"type": "title", "title": {}},
              "素材链接": {"type": "url", "url": {}}, "封面": {"type": "url", "url": {}}}
    r = bot.resolve_roles(schema, {})
    assert r["link"]["name"] == "素材链接"


def test_ambiguous_without_hint_is_skipped():
    schema = {"名字": {"type": "title", "title": {}}, "甲": _sel("a"), "乙": _sel("b")}
    r = bot.resolve_roles(schema, {})
    assert r["status"] is None


def test_env_override_wins_over_ambiguity():
    schema = {"名字": {"type": "title", "title": {}}, "甲": _sel("a"), "乙": _sel("b")}
    r = bot.resolve_roles(schema, {"status": "乙"})
    assert r["status"]["name"] == "乙"


# ---------- 边角：空选项 / 文本链接 ----------
def test_empty_select_options_skipped():
    schema = {"名字": {"type": "title", "title": {}}, "状态": _sel()}
    assert bot.resolve_roles(schema, {})["status"] is None


def test_link_as_rich_text_fallback():
    schema = {"名字": {"type": "title", "title": {}},
              "链接": {"type": "rich_text", "rich_text": {}}}
    r = bot.resolve_roles(schema, {})
    assert r["link"]["name"] == "链接"
    assert r["link"]["type"] == "rich_text"


# ---------- build_properties ----------
def test_build_url_link_and_select_status():
    r = bot.resolve_roles(CN_SCHEMA, {})
    props = bot.build_properties(r, "https://x", ["YouTube"], "好钩子")
    assert props["素材名称"]["title"][0]["text"]["content"] == "好钩子"
    assert props["素材链接"] == {"url": "https://x"}
    assert props["状态"] == {"select": {"name": "待分析"}}
    assert props["平台来源"] == {"multi_select": [{"name": "YouTube"}]}


def test_build_status_type_shape():
    schema = {"名字": {"type": "title", "title": {}}, "进度": _status("待办")}
    r = bot.resolve_roles(schema, {})
    props = bot.build_properties(r, "https://x", [], "")
    assert props["进度"] == {"status": {"name": "待办"}}


def test_build_rich_text_link_shape():
    schema = {"名字": {"type": "title", "title": {}},
              "链接": {"type": "rich_text", "rich_text": {}}}
    r = bot.resolve_roles(schema, {})
    props = bot.build_properties(r, "https://x", [], "")
    assert props["链接"]["rich_text"][0]["text"]["content"] == "https://x"


def test_build_appends_url_to_title_when_no_link_column():
    schema = {"名字": {"type": "title", "title": {}}}
    r = bot.resolve_roles(schema, {})
    props = bot.build_properties(r, "https://x", [], "只有备注")
    assert "https://x" in props["名字"]["title"][0]["text"]["content"]


def test_build_title_falls_back_to_url_when_no_note():
    r = bot.resolve_roles(CN_SCHEMA, {})
    props = bot.build_properties(r, "https://x", ["YouTube"], "")
    assert props["素材名称"]["title"][0]["text"]["content"] == "https://x"


def test_build_skips_platform_when_no_column():
    schema = {"名字": {"type": "title", "title": {}}}
    r = bot.resolve_roles(schema, {})
    props = bot.build_properties(r, "https://x", ["YouTube"], "")
    assert all("multi_select" not in v for v in props.values())


def test_build_raises_without_title():
    import pytest
    with pytest.raises(ValueError):
        bot.build_properties({"title": None}, "https://x", [], "")


# ---------- save_to_notion ----------
def test_save_fetches_schema_and_posts_resolved_payload(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(bot.requests, "post", fake_post)
    monkeypatch.setattr(bot, "NOTION_DATABASE_ID", "db123")
    ok = bot.save_to_notion("https://youtu.be/x", ["YouTube"], "笔记",
                            schema_fetcher=lambda: CN_SCHEMA)
    assert ok is True
    props = captured["json"]["properties"]
    assert props["状态"] == {"select": {"name": "待分析"}}
    assert props["平台来源"] == {"multi_select": [{"name": "YouTube"}]}
    assert props["素材链接"] == {"url": "https://youtu.be/x"}


def test_save_returns_false_on_non_200(monkeypatch):
    class FakeResp:
        status_code = 400

    monkeypatch.setattr(bot.requests, "post", lambda *a, **k: FakeResp())
    ok = bot.save_to_notion("https://x", ["YouTube"], "", schema_fetcher=lambda: CN_SCHEMA)
    assert ok is False


# ---------- handle_text / run_once（沿用旧逻辑，仅平台改英文） ----------
def test_handle_text_no_url():
    assert "没有检测到链接" in bot.handle_text("纯文字没有链接")


def test_handle_text_saves_each_url(monkeypatch):
    saved = []
    monkeypatch.setattr(bot, "save_to_notion",
                        lambda url, platform, note: saved.append((url, platform, note)) or True)
    reply = bot.handle_text("https://b23.tv/x 好视频")
    assert saved == [("https://b23.tv/x", ["Bilibili"], "好视频")]
    assert "已存入" in reply


def test_handle_text_reports_failure_when_save_returns_false(monkeypatch):
    monkeypatch.setattr(bot, "save_to_notion", lambda url, platform, note: False)
    assert "存入失败" in bot.handle_text("https://b23.tv/x 好视频")


def test_handle_text_reports_failure_when_save_raises(monkeypatch):
    def boom(url, platform, note):
        raise RuntimeError("network down")

    monkeypatch.setattr(bot, "save_to_notion", boom)
    assert "存入失败" in bot.handle_text("https://b23.tv/x 好视频")


def test_run_once_processes_and_confirms_offset(monkeypatch):
    monkeypatch.setattr(bot, "save_to_notion", lambda *a, **k: True)
    calls = {"offsets": [], "sent": []}
    fake_updates = [{"update_id": 301, "message": {"chat": {"id": 9}, "text": "https://x.com/p/1"}}]

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
    monkeypatch.setattr(bot, "save_to_notion",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    calls = {"offsets": [], "sent": []}
    fake_updates = [{"update_id": 301, "message": {"chat": {"id": 9}, "text": "https://x.com/p/1"}}]

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

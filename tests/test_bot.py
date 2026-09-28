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
        text = ""

    monkeypatch.setattr(bot.requests, "post", lambda *a, **k: FakeResp())
    ok = bot.save_to_notion("https://x", ["YouTube"], "", schema_fetcher=lambda: CN_SCHEMA)
    assert ok is False


# ---------- handle_text / run_once（沿用旧逻辑，仅平台改英文） ----------
def test_handle_text_no_url():
    assert "没有检测到链接" in bot.handle_text("纯文字没有链接")


def test_handle_text_saves_each_url(monkeypatch):
    saved = []
    monkeypatch.setattr(bot, "save_to_notion",
                        lambda url, platform, note, **kw: saved.append((url, platform, note)) or True)
    reply = bot.handle_text("https://b23.tv/x 好视频")
    assert saved == [("https://b23.tv/x", ["Bilibili"], "好视频")]
    assert "已存入" in reply


def test_handle_text_reports_failure_when_save_returns_false(monkeypatch):
    monkeypatch.setattr(bot, "save_to_notion", lambda url, platform, note, **kw: False)
    assert "存入失败" in bot.handle_text("https://b23.tv/x 好视频")


def test_handle_text_reports_failure_when_save_raises(monkeypatch):
    def boom(url, platform, note, **kw):
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


# ---------- 学习库：抓取到的详情写进对应列 ----------
from meta import Meta  # noqa: E402

STUDY_SCHEMA = {
    "Name": {"type": "title", "title": {}},
    "备注": {"type": "rich_text", "rich_text": {}},
    "平台": _sel("ins", "小红书"),
    "类型": _sel("账号", "帖子"),
    "链接": {"type": "url", "url": {}},
    "数据": {"type": "rich_text", "rich_text": {}},
    "封面": {"type": "files", "files": {}},
    "Created time": {"type": "created_time", "created_time": {}},
}

REEL = Meta(kind="post", title="craighillcompany：The word is out.", stats="26K 赞 · 336 评论",
            author="craighillcompany", body="The word is out.", image_urls=["https://img"])


def _text(prop):
    return prop["rich_text"][0]["text"]["content"]


def test_study_schema_roles_do_not_steal_platform_select_as_status():
    r = bot.resolve_roles(STUDY_SCHEMA, {})
    assert r["status"] is None
    assert r["platform"]["name"] == "平台"
    assert r["kind"]["name"] == "类型"
    assert r["stats"]["name"] == "数据"
    assert r["cover"]["name"] == "封面"
    assert r["note"]["name"] == "备注"


def test_build_post_with_meta_fills_study_columns():
    r = bot.resolve_roles(STUDY_SCHEMA, {})
    props = bot.build_properties(r, "https://www.instagram.com/reel/DZx/", ["Instagram"], "打火机好酷",
                                 meta=REEL, kind="post", cover_ids=["up1"])
    assert props["Name"]["title"][0]["text"]["content"] == "craighillcompany：The word is out."
    assert props["平台"] == {"select": {"name": "ins"}}          # 沿用库里已有的 ins，不另建 Instagram
    assert props["类型"] == {"select": {"name": "帖子"}}
    assert _text(props["数据"]) == "26K 赞 · 336 评论"
    assert props["链接"] == {"url": "https://www.instagram.com/reel/DZx/"}
    assert _text(props["备注"]) == "打火机好酷"
    assert props["封面"] == {"files": [{"type": "file_upload", "file_upload": {"id": "up1"}, "name": "cover"}]}


def test_build_xhs_platform_maps_to_existing_chinese_option():
    r = bot.resolve_roles(STUDY_SCHEMA, {})
    props = bot.build_properties(r, "https://xhslink.cn/o/x", ["Xiaohongshu"], "", kind="post")
    assert props["平台"] == {"select": {"name": "小红书"}}


def test_build_without_meta_still_sets_kind_and_link():
    r = bot.resolve_roles(STUDY_SCHEMA, {})
    props = bot.build_properties(r, "https://www.instagram.com/craighillcompany/", ["Instagram"], "",
                                 kind="account")
    assert props["Name"]["title"][0]["text"]["content"] == "https://www.instagram.com/craighillcompany/"
    assert props["类型"] == {"select": {"name": "账号"}}
    assert "数据" not in props and "封面" not in props


def test_build_platform_without_matching_option_uses_slug():
    r = bot.resolve_roles(STUDY_SCHEMA, {})
    props = bot.build_properties(r, "https://youtu.be/x", ["YouTube"], "")
    assert props["平台"] == {"select": {"name": "YouTube"}}
    assert "类型" not in props


# ---------- 处理一条消息：抓详情 → 存 → 回复 ----------
def _capture_save(monkeypatch):
    saved = []

    def fake_save(url, platform, note, **kw):
        saved.append({"url": url, "platform": platform, "note": note, **kw})
        return True

    monkeypatch.setattr(bot, "save_to_notion", fake_save)
    return saved


def test_handle_instagram_link_saves_fetched_details(monkeypatch):
    saved = _capture_save(monkeypatch)
    monkeypatch.setattr(bot, "fetch_meta", lambda url: REEL)
    reply = bot.handle_text("https://www.instagram.com/reel/DZx/ 打火机好酷")
    assert saved[0]["meta"] is REEL
    assert saved[0]["kind"] == "post"
    assert saved[0]["note"] == "打火机好酷"
    assert "✅ 已存入 Notion" in reply
    assert "帖子 · Instagram · craighillcompany" in reply


def test_handle_link_when_fetch_fails_saves_link_only_and_warns(monkeypatch):
    saved = _capture_save(monkeypatch)
    monkeypatch.setattr(bot, "fetch_meta", lambda url: None)
    reply = bot.handle_text("https://www.instagram.com/craighillcompany/")
    assert saved[0]["meta"] is None
    assert saved[0]["kind"] == "account"   # 抓不到也能从链接看出是账号
    assert "⚠️ 已存链接，但没抓到详情" in reply


def test_handle_other_platform_does_not_fetch(monkeypatch):
    saved = _capture_save(monkeypatch)

    def must_not_fetch(url):
        raise AssertionError("不该去抓 B 站")

    monkeypatch.setattr(bot, "fetch_meta", must_not_fetch)
    reply = bot.handle_text("https://b23.tv/x 好视频")
    assert saved[0]["meta"] is None
    assert "✅ 已存入 Notion" in reply


def test_save_with_meta_uploads_images_into_cover_and_body(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(bot.requests, "post", fake_post)
    xhs = Meta(kind="post", title="SOUL BREW", stats="38 赞", author="猫头鹰酱",
               body="文创品牌", image_urls=["https://a", "https://b", "https://broken"])
    uploads = {"https://a": "up-a", "https://b": "up-b", "https://broken": None}
    ok = bot.save_to_notion("https://xhslink.cn/o/x", ["Xiaohongshu"], "中草药", schema_fetcher=lambda: STUDY_SCHEMA,
                            meta=xhs, kind="post", uploader=uploads.get)
    assert ok is True
    payload = captured["json"]
    assert payload["properties"]["封面"]["files"][0]["file_upload"]["id"] == "up-a"
    images = [b["image"]["file_upload"]["id"] for b in payload["children"] if b["type"] == "image"]
    assert images == ["up-a", "up-b"]      # 上传失败的图跳过，不影响整条
    texts = [b["paragraph"]["rich_text"][0]["text"]["content"] for b in payload["children"] if b["type"] == "paragraph"]
    assert "文创品牌" in texts


# ---------- 小红书分享文案 ----------
XHS_SHARE = ("混进a16z的屋顶派对，我先研究下谁请客 旧金山科技周T... https://xhslink.cn/o/5ydxGyBYJg5 "
             "先复制这段，再进【小红书】就能浏览笔记。")


def test_detect_platform_xhslink_cn():
    assert bot.detect_platform("https://xhslink.cn/o/5ydxGyBYJg5") == ["Xiaohongshu"]


def test_extract_note_drops_xhs_share_boilerplate():
    assert "先复制这段" not in bot.extract_note(XHS_SHARE)
    assert bot.extract_note("SOUL BREW 🟥... https://xhslink.cn/o/x Copy and open rednote to view the note") \
        == "SOUL BREW 🟥..."


def test_xhs_share_text_is_not_kept_as_note_when_details_fetched(monkeypatch):
    saved = _capture_save(monkeypatch)
    xhs = Meta(kind="post", title="混进a16z的屋顶派对，我先研究下谁请客", author="某人", image_urls=[])
    monkeypatch.setattr(bot, "fetch_meta", lambda url: xhs)
    bot.handle_text(XHS_SHARE)
    assert saved[0]["platform"] == ["Xiaohongshu"]
    assert saved[0]["note"] == ""          # 分享文案只是标题的重复，不当备注


def test_own_note_is_kept_next_to_xhs_link(monkeypatch):
    saved = _capture_save(monkeypatch)
    xhs = Meta(kind="post", title="混进a16z的屋顶派对", author="某人", image_urls=[])
    monkeypatch.setattr(bot, "fetch_meta", lambda url: xhs)
    bot.handle_text("https://xhslink.cn/o/x 排版可以学")
    assert saved[0]["note"] == "排版可以学"

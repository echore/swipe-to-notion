from pathlib import Path

import meta

FIXTURES = Path(__file__).parent / "fixtures"


def serve(fixture, final_url=None):
    """假的 http_get：不联网，返回 (最终 URL, 页面 HTML)。"""
    def http_get(url):
        return (final_url or url, (FIXTURES / fixture).read_text(encoding="utf-8"))
    return http_get


# ---------- Instagram ----------
def test_instagram_profile_is_account_with_follower_stats():
    m = meta.fetch_meta("https://www.instagram.com/craighillcompany/", http_get=serve("ig_profile.html"))
    assert m.kind == "account"
    assert m.title == "Craighill (@craighillcompany)"
    assert m.stats == "776K 粉丝 · 1,446 关注 · 231 帖子"
    assert len(m.image_urls) == 1
    assert m.image_urls[0].startswith("https://scontent.cdninstagram.com/")
    assert "&amp;" not in m.image_urls[0]


def test_instagram_reel_is_post_with_caption_and_likes():
    m = meta.fetch_meta("https://www.instagram.com/reel/DZxU9z0Axjh/", http_get=serve("ig_reel.html"))
    assert m.kind == "post"
    assert m.author == "craighillcompany"
    assert m.stats == "26K 赞 · 336 评论"
    assert m.body == ("The word is out, spark is lit, and the top has swung wide open. "
                      "Pre-order the Swingtop Lighter now.")
    assert m.title == "craighillcompany：The word is out, spark is lit, and the top has swung wide open."
    assert len(m.image_urls) == 1


# ---------- 小红书 ----------
XHS_NOTE_URL = "https://www.xiaohongshu.com/discovery/item/6a6328ac000000000100c18d?xsec_source=app_share"


def test_xhs_short_link_resolves_to_note_with_all_images():
    m = meta.fetch_meta("https://xhslink.cn/o/4R9vwjfHAzd", http_get=serve("xhs_note.html", final_url=XHS_NOTE_URL))
    assert m.kind == "post"
    assert m.title == "SOUL BREW 精神补给中心"
    assert m.author == "这里是猫头鹰酱"
    assert m.stats == "38 赞 · 29 收藏 · 2 评论"
    assert m.body.startswith("🟥SOUL BREW 精神补给中心，是一个以中草药意象为原型")
    assert len(m.image_urls) == 2
    assert all(u.startswith("http://sns-webpic-qc.xhscdn.com/") for u in m.image_urls)


# ---------- 抓取失败：返回 None，调用方退回只存链接 ----------
def test_network_error_returns_none():
    def boom(url):
        raise ConnectionError("blocked")
    assert meta.fetch_meta("https://www.instagram.com/craighillcompany/", http_get=boom) is None


def test_login_wall_without_data_returns_none():
    def login_wall(url):
        return ("https://www.instagram.com/accounts/login/", "<html><head><title>Login</title></head></html>")
    assert meta.fetch_meta("https://www.instagram.com/reel/DZxU9z0Axjh/", http_get=login_wall) is None


# ---------- 不联网也能从链接看出是账号还是帖子 ----------
def test_kind_from_url():
    assert meta.kind_from_url("https://www.instagram.com/craighillcompany/") == "account"
    assert meta.kind_from_url("https://www.instagram.com/craighillcompany?igsh=abc") == "account"
    assert meta.kind_from_url("https://www.instagram.com/reel/DZxU9z0Axjh/") == "post"
    assert meta.kind_from_url("https://www.instagram.com/p/ABC123/?img_index=1") == "post"
    assert meta.kind_from_url("https://www.xiaohongshu.com/discovery/item/6a63") == "post"
    assert meta.kind_from_url("https://www.xiaohongshu.com/explore/6a63") == "post"
    assert meta.kind_from_url("https://www.xiaohongshu.com/user/profile/62e5") == "account"
    assert meta.kind_from_url("https://xhslink.cn/o/4R9vwjfHAzd") is None
    assert meta.kind_from_url("https://www.youtube.com/watch?v=x") is None

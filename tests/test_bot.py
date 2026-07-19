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

"""抓取社媒链接的公开信息（匿名请求，不登录、不带 cookie）。

对外只有一个入口 fetch_meta(url)：返回 Meta，抓不到就返回 None，
调用方据此退回「只存链接」。
"""
from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import dataclass, field

import requests

USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


@dataclass
class Meta:
    kind: str                      # "account" | "post"
    title: str
    stats: str = ""                # 例："776K 粉丝 · 231 帖子"
    author: str = ""
    body: str = ""                 # 帖子文案
    image_urls: list[str] = field(default_factory=list)


def http_get(url: str) -> tuple[str, str]:
    """真实请求：跟随跳转，返回 (最终 URL, HTML)。"""
    resp = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.url, resp.text


def _og(page: str, name: str) -> str:
    m = re.search(r'<meta property="og:%s" content="([^"]*)"' % name, page)
    return html_lib.unescape(m.group(1)).strip() if m else ""


# ---------- Instagram ----------
def _parse_instagram(page: str) -> Meta | None:
    title = _og(page, "title")
    desc = _og(page, "description")
    image = _og(page, "image")
    if not title:
        return None
    m = re.match(r"([\d.,]+[KMB]?) Followers, ([\d.,]+[KMB]?) Following, ([\d.,]+[KMB]?) Posts", desc)
    if m:
        name = re.sub(r"\s*•\s*Instagram.*$", "", title)
        stats = f"{m.group(1)} 粉丝 · {m.group(2)} 关注 · {m.group(3)} 帖子"
        return Meta(kind="account", title=name, stats=stats, image_urls=[image] if image else [])
    m = re.match(r'([\d.,]+[KMB]?) likes?, ([\d.,]+[KMB]?) comments? - (\S+) on [^:]+: "(.*)"', desc, re.S)
    if m:
        author, caption = m.group(3), m.group(4).strip()
        return Meta(
            kind="post",
            title=f"{author}：{_headline(caption)}" if caption else author,
            stats=f"{m.group(1)} 赞 · {m.group(2)} 评论",
            author=author,
            body=caption,
            image_urls=[image] if image else [],
        )
    return None


def _headline(text: str, limit: int = 80) -> str:
    """取第一句（或第一行）当标题，超长截断。"""
    first = text.strip().splitlines()[0]
    m = re.match(r"(.+?[.!?。！？])(\s|$)", first)
    if m:
        first = m.group(1)
    return first if len(first) <= limit else first[:limit].rstrip() + "…"


# ---------- 小红书 ----------
MAX_IMAGES = 9


def _xhs_state(page: str) -> dict | None:
    m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*</script>", page, re.S)
    if not m:
        return None
    try:
        return json.loads(re.sub(r"\bundefined\b", "null", m.group(1)))
    except ValueError:
        return None


def _parse_xhs_note(page: str) -> Meta | None:
    state = _xhs_state(page)
    try:
        note = state["noteData"]["data"]["noteData"]
    except (TypeError, KeyError):
        return None
    desc = (note.get("desc") or "").strip()
    title = (note.get("title") or "").strip() or (_headline(desc) if desc else "")
    if not title:
        return None
    info = note.get("interactInfo") or {}
    images = []
    for img in (note.get("imageList") or [])[:MAX_IMAGES]:
        detail = [i["url"] for i in img.get("infoList") or [] if i.get("imageScene") == "H5_DTL"]
        url = detail[0] if detail else img.get("url")
        if url:
            images.append(url)
    return Meta(
        kind="post",
        title=title,
        stats=f"{info.get('likedCount', '0')} 赞 · {info.get('collectedCount', '0')} 收藏 · {info.get('commentCount', '0')} 评论",
        author=(note.get("user") or {}).get("nickName", ""),
        body=desc,
        image_urls=images,
    )


IG_POST_PATHS = ("p", "reel", "reels", "tv")


def kind_from_url(url: str) -> str | None:
    """只看链接格式判断账号/帖子；短链等看不出来的返回 None。"""
    m = re.match(r"https?://(?:www\.)?instagram\.com/([^/?#]+)", url)
    if m:
        return "post" if m.group(1) in IG_POST_PATHS else "account"
    if re.search(r"xiaohongshu\.com/(discovery/item|explore)/", url):
        return "post"
    if re.search(r"xiaohongshu\.com/user/profile/", url):
        return "account"
    return None


def fetch_meta(url: str, http_get=http_get) -> Meta | None:
    try:
        final_url, page = http_get(url)
    except Exception:
        return None
    if "instagram.com" in final_url:
        return _parse_instagram(page)
    if "xiaohongshu.com" in final_url:
        return _parse_xhs_note(page)
    return None

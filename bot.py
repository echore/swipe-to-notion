"""Telegram → Notion 社媒收藏 bot（无状态定时轮询版）。

写入策略：先读一次库结构，按属性类型自动认列（认类型不认名字），撞车时
按名字关键词兜底，SOCIAL_* 环境变量作为歧义时的手动 override。平台标签
统一英文 slug。
"""
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# 可选 override（只在歧义时才需要）；默认 None，靠类型推断
ENV_OVERRIDES = {
    "title": os.getenv("SOCIAL_TITLE_PROPERTY"),
    "link": os.getenv("SOCIAL_URL_PROPERTY"),
    "status": os.getenv("SOCIAL_STATUS_PROPERTY"),
    "platform": os.getenv("SOCIAL_PLATFORM_PROPERTY"),
    "default_status": os.getenv("SOCIAL_DEFAULT_STATUS"),
}

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}
NOTION_PAGES_URL = "https://api.notion.com/v1/pages"
NOTION_DB_URL = "https://api.notion.com/v1/databases/{db}"

# 撞车时的名字兜底关键词（全小写匹配）
LINK_HINTS = ("链接", "link", "url", "网址")
STATUS_HINTS = ("状态", "status", "进度", "state", "阶段")
PLATFORM_HINTS = ("平台", "platform", "来源", "source", "渠道")
KIND_HINTS = ("类型", "type", "kind", "种类")
STATS_HINTS = ("数据", "stats", "metrics", "互动")
NOTE_HINTS = ("备注", "note", "memo", "笔记")
COVER_HINTS = ("封面", "cover", "图片", "image")

# 平台 slug → 库里可能已有的选项名（全小写）。命中就沿用库里的叫法，不另建选项。
PLATFORM_ALIASES = {
    "Instagram": {"instagram", "ins", "ig"},
    "Xiaohongshu": {"xiaohongshu", "小红书", "红书", "xhs", "rednote"},
    "Bilibili": {"bilibili", "b站", "哔哩哔哩"},
    "YouTube": {"youtube", "油管"},
    "Twitter/X": {"twitter/x", "twitter", "x", "推特"},
    "Weibo": {"weibo", "微博"},
    "Douyin": {"douyin", "抖音"},
}
KIND_ALIASES = {
    "account": {"账号", "account", "profile", "博主"},
    "post": {"帖子", "post", "笔记"},
}
KIND_LABELS = {"account": "账号", "post": "帖子"}


# ---------- 纯函数：平台识别（英文 slug） ----------
def detect_platform(url: str) -> list[str]:
    u = url.lower()
    if "xiaohongshu.com" in u or "xhslink.com" in u:
        return ["Xiaohongshu"]
    if "bilibili.com" in u or "b23.tv" in u:
        return ["Bilibili"]
    if "youtube.com" in u or "youtu.be" in u:
        return ["YouTube"]
    if "twitter.com" in u or "x.com" in u:
        return ["Twitter/X"]
    if "instagram.com" in u:
        return ["Instagram"]
    if "weibo.com" in u:
        return ["Weibo"]
    if "douyin.com" in u or "iesdouyin.com" in u:
        return ["Douyin"]
    return ["Other"]


def extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s]+", text)


def extract_note(text: str) -> str:
    return re.sub(r"https?://[^\s]+", "", text).strip()


# ---------- 纯函数：库结构解析（类型推断 + 名字兜底 + override） ----------
def _pick(candidates, hints, override_name):
    """candidates: list[(name, prop)]。返回唯一命中或 None。"""
    if override_name:
        for name, prop in candidates:
            if name == override_name:
                return (name, prop)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        hinted = [(n, p) for (n, p) in candidates
                  if any(h in n.lower() for h in hints)]
        if len(hinted) == 1:
            return hinted[0]
    return None


def _pick_hinted(candidates, hints):
    """只认名字带关键词的列（不接受「唯一一列就是它」的推断）。"""
    hinted = [(n, p) for (n, p) in candidates if any(h in n.lower() for h in hints)]
    return hinted[0] if len(hinted) == 1 else None


def _option_names(prop):
    return [o["name"] for o in prop.get(prop["type"], {}).get("options", [])]


def _match_option(options, aliases, fallback):
    """库里已有同义选项就用库里的名字，否则用 fallback（写入时 Notion 会自动建新选项）。"""
    for name in options:
        if name.lower() in aliases:
            return name
    return fallback


def _status_default(prop, override_default):
    t = prop["type"]  # "select" 或 "status"
    names = [o["name"] for o in prop.get(t, {}).get("options", [])]
    if not names:
        return None
    if override_default and override_default in names:
        return override_default
    return names[0]  # 取第一个已有选项 → 母语


def resolve_roles(schema: dict, overrides: dict) -> dict:
    """schema: Notion retrieve-database 的 properties map（name -> prop）。"""
    def by_type(*types):
        return [(n, p) for n, p in schema.items() if p["type"] in types]

    titles = by_type("title")
    title = titles[0] if titles else None

    # link：优先 url 类型；一个都没有时，才找带关键词的文本列
    link = _pick(by_type("url"), LINK_HINTS, overrides.get("link"))
    if link is None and not by_type("url"):
        texts = [(n, p) for n, p in by_type("rich_text")
                 if any(h in n.lower() for h in LINK_HINTS)]
        link = texts[0] if len(texts) == 1 else None

    # 平台：优先多选列；没有时退到名字带「平台」的单选列
    platform = _pick(by_type("multi_select"), PLATFORM_HINTS, overrides.get("platform"))
    if platform is None and not by_type("multi_select"):
        platform = _pick_hinted(by_type("select"), PLATFORM_HINTS)
    kind = _pick_hinted(by_type("select"), KIND_HINTS)
    # 状态只从没被平台/类型占用的单选列里找
    taken = {c[0] for c in (platform, kind) if c}
    status = _pick([c for c in by_type("select", "status") if c[0] not in taken],
                   STATUS_HINTS, overrides.get("status"))
    stats = _pick_hinted(by_type("rich_text"), STATS_HINTS)
    note = _pick_hinted([c for c in by_type("rich_text") if not link or c[0] != link[0]], NOTE_HINTS)
    cover = _pick(by_type("files"), COVER_HINTS, None)

    res = {"title": None, "link": None, "status": None, "platform": None,
           "kind": None, "stats": None, "note": None, "cover": None}
    if title:
        res["title"] = {"name": title[0], "type": "title"}
    if link:
        res["link"] = {"name": link[0], "type": link[1]["type"]}
    if status:
        default = _status_default(status[1], overrides.get("default_status"))
        if default is not None:
            res["status"] = {"name": status[0], "type": status[1]["type"], "default": default}
    if platform:
        res["platform"] = {"name": platform[0], "type": platform[1]["type"],
                           "options": _option_names(platform[1])}
    if kind:
        res["kind"] = {"name": kind[0], "options": _option_names(kind[1])}
    if stats:
        res["stats"] = {"name": stats[0]}
    if note:
        res["note"] = {"name": note[0]}
    if cover:
        res["cover"] = {"name": cover[0]}
    return res


# ---------- 纯函数：构造 Notion properties ----------
def _rich(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text[:2000]}}]}


def build_properties(resolution: dict, url: str, platform: list[str], note: str,
                     meta=None, kind=None, cover_ids=()) -> dict:
    if not resolution.get("title"):
        raise ValueError("数据库缺少标题属性，无法写入")
    link = resolution.get("link")
    # 抓到详情 → 标题用帖子标题/账号名；否则沿用旧逻辑：备注或 URL
    headline = meta.title if meta and meta.title else note
    # 有链接列 → 标题用 headline 或 URL；无链接列 → 把 URL 并进标题，别丢
    if link:
        title_text = headline if headline else url
    else:
        title_text = f"{headline} {url}".strip() if headline else url

    props = {resolution["title"]["name"]: {"title": [{"text": {"content": title_text}}]}}
    if link:
        if link["type"] == "url":
            props[link["name"]] = {"url": url}
        else:  # rich_text 兜底
            props[link["name"]] = {"rich_text": [{"text": {"content": url}}]}
    status = resolution.get("status")
    if status:
        props[status["name"]] = {status["type"]: {"name": status["default"]}}
    plat = resolution.get("platform")
    if plat and platform:
        names = [_match_option(plat.get("options", []), PLATFORM_ALIASES.get(p, {p.lower()}), p)
                 for p in platform]
        if plat["type"] == "select":
            props[plat["name"]] = {"select": {"name": names[0]}}
        else:
            props[plat["name"]] = {"multi_select": [{"name": n} for n in names]}
    kind_col = resolution.get("kind")
    if kind_col and kind in KIND_LABELS:
        label = _match_option(kind_col["options"], KIND_ALIASES[kind], KIND_LABELS[kind])
        props[kind_col["name"]] = {"select": {"name": label}}
    stats_col = resolution.get("stats")
    if stats_col and meta and meta.stats:
        props[stats_col["name"]] = _rich(meta.stats)
    note_col = resolution.get("note")
    if note_col and note:
        props[note_col["name"]] = _rich(note)
    cover_col = resolution.get("cover")
    if cover_col and cover_ids:
        props[cover_col["name"]] = {"files": [
            {"type": "file_upload", "file_upload": {"id": cover_ids[0]}, "name": "cover"}]}
    return props


# ---------- IO：读结构 + 写页面 ----------
def get_database_schema(database_id=None):
    db = database_id or NOTION_DATABASE_ID
    resp = requests.get(NOTION_DB_URL.format(db=db), headers=NOTION_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()["properties"]


def save_to_notion(url: str, platform: list[str], note: str,
                   schema_fetcher=get_database_schema) -> bool:
    schema = schema_fetcher()
    resolution = resolve_roles(schema, ENV_OVERRIDES)
    props = build_properties(resolution, url, platform, note)
    payload = {"parent": {"database_id": NOTION_DATABASE_ID}, "properties": props}
    resp = requests.post(NOTION_PAGES_URL, headers=NOTION_HEADERS, json=payload, timeout=30)
    return resp.status_code == 200


TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def get_updates(token, offset=None, timeout=0):
    params = {"timeout": timeout, "allowed_updates": '["message"]'}
    if offset is not None:
        params["offset"] = offset
    resp = requests.get(TELEGRAM_API.format(token=token, method="getUpdates"), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()["result"]


def send_message(token, chat_id, text):
    resp = requests.post(
        TELEGRAM_API.format(token=token, method="sendMessage"),
        json={"chat_id": chat_id, "text": text},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def handle_text(text: str) -> str:
    urls = extract_urls(text)
    if not urls:
        return "没有检测到链接，请直接发送链接（可以附带备注）。"
    note = extract_note(text)
    results = []
    for url in urls:
        platform = detect_platform(url)
        platform_str = "、".join(platform)
        try:
            ok = save_to_notion(url, platform, note)
        except Exception as exc:
            results.append(f"❌ 存入失败：{exc}\n📎 {url}")
            continue
        if ok:
            results.append(f"✅ 已存入 Notion\n📎 {url}\n🏷 {platform_str}")
        else:
            results.append(f"❌ 存入失败\n📎 {url}")
    return "\n\n".join(results)


def run_once(token, get_updates_fn=get_updates, send_message_fn=send_message, handle_text_fn=handle_text) -> int:
    updates = get_updates_fn(token, offset=None)
    if not updates:
        return 0
    last_update_id = None
    for update in updates:
        last_update_id = update["update_id"]
        message = update.get("message")
        if not message:
            continue
        chat_id = message["chat"]["id"]
        text = (message.get("text") or "").strip()
        if not text:
            send_message_fn(token, chat_id, "发一条带链接的消息给我，我会存进 Notion。")
            continue
        send_message_fn(token, chat_id, handle_text_fn(text))
    if last_update_id is not None:
        get_updates_fn(token, offset=last_update_id + 1)
    return len(updates)


def main():
    missing = [
        name
        for name, value in [
            ("TELEGRAM_BOT_TOKEN", TELEGRAM_TOKEN),
            ("NOTION_TOKEN", NOTION_TOKEN),
            ("NOTION_DATABASE_ID", NOTION_DATABASE_ID),
        ]
        if not value
    ]
    if missing:
        raise SystemExit(f"ERROR: 缺少环境变量: {', '.join(missing)}")
    count = run_once(TELEGRAM_TOKEN)
    print(f"processed {count} update(s)")


if __name__ == "__main__":
    main()

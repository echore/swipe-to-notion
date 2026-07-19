"""Telegram → Notion 社媒收藏 bot（无状态定时轮询版）。"""
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

TITLE_PROPERTY = os.getenv("SOCIAL_TITLE_PROPERTY", "素材名称")
URL_PROPERTY = os.getenv("SOCIAL_URL_PROPERTY", "素材链接")
STATUS_PROPERTY = os.getenv("SOCIAL_STATUS_PROPERTY", "状态")
PLATFORM_PROPERTY = os.getenv("SOCIAL_PLATFORM_PROPERTY", "平台来源")
DEFAULT_STATUS = os.getenv("SOCIAL_DEFAULT_STATUS", "待分析")

NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def detect_platform(url: str) -> list[str]:
    url = url.lower()
    if "xiaohongshu.com" in url or "xhslink.com" in url:
        return ["小红书"]
    elif "bilibili.com" in url or "b23.tv" in url:
        return ["B站"]
    elif "youtube.com" in url or "youtu.be" in url:
        return ["YouTube"]
    elif "twitter.com" in url or "x.com" in url:
        return ["Twitter/X"]
    elif "instagram.com" in url:
        return ["Instagram"]
    elif "weibo.com" in url:
        return ["微博"]
    elif "douyin.com" in url or "iesdouyin.com" in url:
        return ["抖音"]
    else:
        return ["其他"]


def extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s]+", text)


def extract_note(text: str) -> str:
    return re.sub(r"https?://[^\s]+", "", text).strip()


def save_to_notion(url: str, platform: list[str], note: str) -> bool:
    title = note if note else url
    properties = {
        TITLE_PROPERTY: {"title": [{"text": {"content": title}}]},
        URL_PROPERTY: {"url": url},
        STATUS_PROPERTY: {"select": {"name": DEFAULT_STATUS}},
    }
    if platform:
        properties[PLATFORM_PROPERTY] = {"multi_select": [{"name": p} for p in platform]}
    payload = {"parent": {"database_id": NOTION_DATABASE_ID}, "properties": properties}
    response = requests.post(NOTION_API_URL, headers=NOTION_HEADERS, json=payload, timeout=30)
    return response.status_code == 200


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

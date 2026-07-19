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

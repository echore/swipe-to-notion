# Telegram → Notion 社媒收藏 bot

在各 app 看到好帖子，直接把链接（可附备注）发给 Telegram bot，
几分钟内自动存进你的 Notion 社媒库，并识别平台来源——不用再点收藏
（点了也会忘）。跑在 GitHub Actions 上，永久免费，无需服务器。

面向内容创作者 / 需要系统性收集参考素材的人。

## 它怎么工作
GitHub Actions 每 15 分钟触发一次，拉取这段时间你发的消息，提取链接、
识别平台、写进 Notion，然后退出。不是实时的——通常几分钟到二十几分钟。

支持识别：小红书、B站、YouTube、Twitter/X、Instagram、微博、抖音，
其余归为"其他"。

## 自助部署（约 10 分钟）

1. **建 Telegram bot**：Telegram 里找 @BotFather，发 `/newbot`，拿 token。
2. **建 Notion integration**：https://www.notion.so/my-integrations
   新建并复制 secret。建一个数据库，字段建议：素材名称（标题）、
   素材链接（URL）、状态（Select）、平台来源（Multi-select）。在数据库
   ··· → Connections 连上 integration，复制数据库 ID。
3. **Fork 本仓库**。
4. **填 Secrets**：Settings → Secrets and variables → Actions，新建
   `TELEGRAM_BOT_TOKEN`、`NOTION_TOKEN`、`NOTION_DATABASE_ID`。
5. **启用 Actions**：Actions 页点启用。
6. **测试**：给 bot 发一条带链接的消息，最多 15 分钟看 Notion；也可在
   Actions 页手动 "Run workflow" 立即触发。

## 自定义字段名
若你的字段名不同，可在 Secrets 里额外设 `SOCIAL_TITLE_PROPERTY` 等
（见 `.env.example`）。

## 已知限制
- cron 高峰期可能延迟 5–20 分钟。
- 仓库 60 天无提交会被 GitHub 自动暂停定时任务，点一下即可恢复。
- 极少数情况下（写入 Notion 成功后、确认 offset 前发生网络错误），该批消息会在下次运行时被重复处理，可能产生重复的 Notion 记录；这是无状态设计的固有取舍。

## 本地开发
复制 `.env.example` 为 `.env` 填真实值，`pip install -r requirements.txt
&& python bot.py`。`.env` 已被 `.gitignore` 忽略。

# Telegram → Notion 社媒收藏 bot 设计文档

日期：2026-07-18
状态：已确认，待实现

## 目标
在 Telegram 发社媒帖子链接（可附备注）→ 几小时内（实际约 5–25 分钟）
自动存进 Notion 社媒库，识别平台来源。无需在各 app 里点收藏（点了也会忘）。
定位：**面向内容创作者**，公开发布，别人可自助免费部署自己的版本。

## 非目标
- 不做秒回 / 实时响应
- 不做多轮对话、编辑、删除
- 不做多用户托管服务（每个人部署自己的实例）
- 不抓取帖子正文/元数据（只存链接、平台、备注）

## 架构：无状态定时轮询
运行在 GitHub Actions cron 上，每 15 分钟触发一次性脚本：

    定时触发 (cron */15)
      → getUpdates 拉取积压消息
      → 逐条: 提取链接+备注 → 识别平台 → 写 Notion → 回确认/报错给用户
      → getUpdates(offset=最后update_id+1) 标记该批已消费
      → 退出

无需外部数据库存 offset——Telegram 服务器负责保留未确认的消息。

## 关键设计决策
- **无状态 offset**：靠 Telegram 的 getUpdates offset 机制去重，
  不自己存状态。
- **失败也推进 offset**：某条写 Notion 失败 → 回一条错误提示给用户，
  但仍推进 offset，避免"毒消息"反复重试堵死后续消息。用户看到提示
  可手动补发。
- **崩溃容忍**：整批处理完才确认 offset；中途崩溃最坏是下次重复处理
  （低概率，可接受）。
- **并发保护**：workflow 设 concurrency group，防两次运行同时抢
  getUpdates。

## 🔀 本仓库处理逻辑（社媒库）
- 从消息中提取所有链接（正则），剩余文字作为备注
- 识别平台来源：小红书 / B站 / YouTube / Twitter·X / Instagram /
  微博 / 抖音 / 其他（复用现有 detect_platform）
- 每条链接建一条 Notion 记录：素材名称（备注或链接）、素材链接、
  平台来源（multi_select）、状态默认"待分析"
- 属性名可通过环境变量配置，适配别人不同的表头

## 密钥安全
- 真实 token 绝不进代码、绝不进仓库
- 本地 .env（被 .gitignore 忽略），线上 GitHub Secrets
- workflow 通过 ${{ secrets.* }} 注入环境变量
- **⚠️ 发布前必做**：现有 bot.py 里明文硬编码的 Telegram token 和
  Notion token 必须作废重建——BotFather `/revoke` 换新 bot token，
  Notion 后台重新生成 integration secret。旧值一旦进过文件即视为泄露。

## 环境变量
- TELEGRAM_BOT_TOKEN
- NOTION_TOKEN
- NOTION_DATABASE_ID
- 可选：属性名配置（素材名称 / 素材链接 / 状态 / 平台来源 对应字段）

## 仓库结构
    .github/workflows/poll.yml   # cron 每15分钟
    bot.py                       # 一次性 getUpdates → 写 Notion
    requirements.txt
    .env.example
    .gitignore                   # 忽略 .env
    README.md                    # 部署教程 + Notion 建表说明

## 已知限制
- cron 高峰期延迟 5–20 分钟（对本需求可接受）
- 仓库 60 天无提交，GitHub 自动停用定时 workflow，需手动点一下恢复
  （README 说明）

## 别人部署步骤（写进 README）
1. BotFather 建 bot 拿 token
2. 建 Notion integration 拿 secret，建库（含平台来源等字段）、邀请
   integration、复制 database ID
3. Fork 本仓库
4. Settings → Secrets 填 3 个值
5. Actions 页点 Enable
6. 发一条带链接的消息测试，最多 15 分钟看结果

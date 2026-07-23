# swipe-to-notion

**给 Telegram bot 发一个链接，15 分钟内它自动进你的 Notion 数据库，并打好平台标签。**

[English](README.md) · **简体中文**

给需要研究别人作品的内容创作者做的。跑在 GitHub Actions 上，不用买服务器，也没有需要一直开着的进程。

<!-- 截图：把 Telegram 对话和 Notion 里生成的那行放在一起。
     存成 docs/images/hero.png，然后取消下面这行的注释。
![发链接给 Telegram，Notion 里就多一行](docs/images/hero.png)
-->

## 为什么要做这个

你刷到一条做得很好的帖子。钩子抓人，结构干净，评论区证明它确实有效。于是你点了收藏，然后这辈子再也没打开过它。

收藏夹是好素材去世的地方。它们躺在你当时所在的那个 app 里，散在小红书、Instagram、YouTube 和另外四个信息流中间，没有笔记，也没法互相对照。

我想要的是一个 Notion 数据库：所有我觉得值得拆解的帖子，汇总在一张表里，按平台打好标签，等我坐下来规划自己内容的时候可以直接翻。

难的是"存"这个动作。复制链接、切到 Notion、在侧边栏点好几下找到那个数据库、新建页面、粘贴 URL、选平台标签。每一次都是六步，我坚持了不到一周就放弃了。

现在整件事就是发一条消息。我把链接转给 Telegram bot，然后继续刷，那一行会自己出现在 Notion 里。

## 它怎么工作

```
你                 GitHub Actions          Telegram             Notion
 |                  （每 15 分钟）             |                    |
 |---- 发链接 --------------------------------->|                   |
 |                       |---- 拉取新消息 ----->|                    |
 |                       |<---- 你的消息 -------|                    |
 |                       |---- 提取链接、识别平台 ---------------->  |
 |                       |                      |    创建页面 ----->|
 |<---- "✅ 已存入 Notion" -----------------------|                  |
```

GitHub Actions 的定时任务每 15 分钟醒一次，向 Telegram 要走你上次之后发的消息，把里面的链接提出来，按平台打标签，往你的 Notion 数据库写一行，在对话里回复你，然后退出。两次唤醒之间什么都不跑。

链接旁边附带的文字会成为这一行的标题，所以发 `https://example.com/post 钩子不错，结尾拉胯` 存进去就带着你自己的备注。只发链接不写字，标题就是 URL。

能识别七个平台：小红书、B站、YouTube、Twitter/X、Instagram、微博、抖音。其余归为"其他"。

配置之前有两件事得知道。存入不是实时的，一条链接从几秒到二十几分钟才出现，取决于你发的时候正处在周期的哪一段。另外 bot 只回应跟它说话的人，所以 token 别外泄，这个 bot 就一直是你自己的。

## 自助部署（约 10 分钟）

需要一个 Telegram 账号、一个 Notion 账号、一个 GitHub 账号。不用信用卡，不用服务器。

### 1. 建一个 Telegram bot

打开 Telegram，搜 **@BotFather**，发 `/newbot`。取个名字和用户名，BotFather 会回一个形如 `1234567890:AAE...` 的 token。留着，第 4 步要用。

<!-- ![BotFather 发放 token](docs/images/botfather.png) -->

### 2. 建 Notion 数据库和 integration

在 Notion 里建一个数据库，四个字段：

| 字段 | 类型 | 作用 |
|---|---|---|
| `素材名称` | 标题 | 你写的备注；没写就是 URL |
| `素材链接` | URL | 存下来的链接 |
| `状态` | 单选 | 处理状态，存入时写 `待分析` |
| `平台来源` | 多选 | 链接来自哪个平台 |

字段名不一样也没关系，用第 4 步的环境变量覆盖即可，见[改字段名](#改字段名)。

然后去 [notion.so/my-integrations](https://www.notion.so/my-integrations) 建一个 internal integration，复制它的 secret。

把 integration 连到数据库上：打开数据库，点右上角 `···`，选 **Connections**，加上你的 integration。这一步是最常见的失败原因，漏了的话每次写入都返回 404。

最后从数据库 URL 里复制数据库 ID。在 `notion.so/myworkspace/a8aec43384f447ed84390e8e42c2e089?v=...` 里，ID 就是那串 32 位的 `a8aec43384f447ed84390e8e42c2e089`。

<!-- ![把 integration 连到数据库](docs/images/notion-connection.png) -->

### 3. Fork 本仓库

点页面顶部的 **Fork**。你的 fork 有自己的 Actions 运行器和自己的 secrets，你的凭据我看不到，别人也看不到。

### 4. 填三个 Secret

在你的 fork 里进 **Settings → Secrets and variables → Actions**，新建三个 repository secret：

| Secret | 值 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | 第 1 步的 token |
| `NOTION_TOKEN` | 第 2 步的 integration secret |
| `NOTION_DATABASE_ID` | 第 2 步那串 32 位数据库 ID |

GitHub 会加密存储并在日志里屏蔽它们。别人 fork 你的仓库只拿得到代码，拿不到 secret。

<!-- ![填 repository secrets](docs/images/github-secrets.png) -->

### 5. 启用 Actions

进 fork 的 **Actions** 标签页，点启用 workflow 的按钮。GitHub 默认会关掉新 fork 上的定时任务，所以这一步必须做。

### 6. 发条测试链接

给你的 bot 发任意一个链接，然后进 **Actions → poll-telegram → Run workflow** 立即触发一次，不用等定时。bot 会在 Telegram 里回复你，Notion 里也会出现新的一行。

如果没反应，去 Actions 标签页打开那次失败的运行。Notion 返回 404 说明 integration 没连上数据库（第 2 步）；401 说明 token 填错了；字段名报错说明你的 Notion 字段名和默认值不一致，看下一节。

## 改字段名

把下面这些当作 repository secret 加进去，就能匹配你自己的数据库：

| 变量 | 默认值 |
|---|---|
| `SOCIAL_TITLE_PROPERTY` | `素材名称` |
| `SOCIAL_URL_PROPERTY` | `素材链接` |
| `SOCIAL_STATUS_PROPERTY` | `状态` |
| `SOCIAL_PLATFORM_PROPERTY` | `平台来源` |
| `SOCIAL_DEFAULT_STATUS` | `待分析` |

比如字段叫 `Name` / `Link` / `Status` / `Platform` 的英文数据库，就加四个 secret：`SOCIAL_TITLE_PROPERTY=Name`、`SOCIAL_URL_PROPERTY=Link`、`SOCIAL_STATUS_PROPERTY=Status`、`SOCIAL_PLATFORM_PROPERTY=Platform`。

平台标签本身的文字写在 [bot.py](bot.py) 的 `detect_platform` 里（`小红书`、`B站`、`YouTube`、`Twitter/X`、`Instagram`、`微博`、`抖音`、`其他`）。想换标签直接改那个函数，Notion 的多选项会在第一次用到时自动创建，不需要提前建。

## 已知限制

定时靠 GitHub 的 cron，高峰期会排队，所以一条链接可能比标称的 15 分钟再晚 5 到 20 分钟。

仓库连续 60 天没有提交，GitHub 会暂停定时任务。在 Actions 页点一下就能恢复。

这套设计自己不存任何状态：队列在 Telegram 那边，bot 处理完一批才去确认。如果在"Notion 写入成功"和"确认"之间断网，下次运行会重跑这一批，于是多出一条重复记录。概率很低，而这正是"不需要我们自己的数据库"所付出的代价。

## 本地开发

```bash
cp .env.example .env    # 填上真实的值
pip install -r requirements.txt
python bot.py           # 跑一个轮询周期然后退出
```

`.env` 已被 gitignore。跑测试用 `python -m pytest tests/ -v`，13 个测试全部离线跑在假对象上，不需要任何凭据。

## License

MIT。随便用，随便 fork，随便改。所有凭据都走环境变量，这个仓库里不含我的、也不会含你的任何 token。

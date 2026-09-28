# swipe-to-notion

**Send a link to a Telegram bot. It lands in your Notion database, tagged by platform, within 15 minutes.**

**English** · [简体中文](README.zh-CN.md)

Built for content creators who study other people's work. Runs on GitHub Actions, so there is no server to rent and nothing to keep online.

<!-- Screenshot: put a side-by-side of the Telegram chat and the resulting Notion row here.
     Save it as docs/images/hero.png, then uncomment the line below.
![Send a link in Telegram, get a row in Notion](docs/images/hero.png)
-->

## Why This Exists

You scroll past a post that does something right. The hook lands, the structure is clean, the comments prove it worked. So you tap the bookmark icon, and that is the last time you ever see it.

Bookmarks are where good references go to be forgotten. They sit inside whichever app you were in, split across Xiaohongshu, Instagram, YouTube and four other feeds, with no notes and no way to compare one against another.

What I wanted instead was a single Notion database: every post I thought was worth taking apart, in one table, tagged by platform, ready to review when I sit down to plan my own content.

The problem was the saving. Copy the link, switch to Notion, click through the sidebar to find the database, create a page, paste the URL, pick the platform tag. Six steps, every time, and I gave up on it within a week.

Now the whole thing is one message. I forward the link to a Telegram bot and go back to scrolling. The row shows up in Notion on its own.

## How It Works

```
You                GitHub Actions            Telegram             Notion
 |                 (every 15 min)               |                    |
 |-- send link --------------------------------->|                   |
 |                       |-- fetch new msgs ---->|                   |
 |                       |<-- your messages -----|                   |
 |                       |-- extract URL, detect platform -------->  |
 |                       |                       |    create page -->|
 |<-- "✅ Saved to Notion" ----------------------|                   |
```

A scheduled GitHub Actions job wakes up every 15 minutes, asks Telegram for messages you sent since the last run, pulls the URLs out of them, tags each one by platform, writes a row to your Notion database, replies to you in the chat, and exits. Nothing runs between those wake-ups.

Any text you send alongside the link becomes the row title, so `https://example.com/post great hook, weak ending` saves with your own note attached. Send a link on its own and the URL becomes the title.

The bot recognizes seven platforms: Xiaohongshu, Bilibili, YouTube, Twitter/X, Instagram, Weibo, and Douyin. Anything else is tagged as "other".

Two consequences worth knowing before you set this up. Saves are not instant; a link takes anywhere from a few seconds to twenty-odd minutes to appear, depending on where in the cycle you send it. And the bot only listens to whoever talks to it, so keep the bot token private and the bot stays yours.

## Deploy Your Own (About 10 Minutes)

You need a Telegram account, a Notion account, and a GitHub account. No credit card, no server.

### 1. Create a Telegram Bot

Open Telegram, search for **@BotFather**, and send `/newbot`. Pick a name and a username. BotFather replies with a token that looks like `1234567890:AAE...`. Keep it somewhere safe for step 4.

<!-- ![BotFather issuing a token](docs/images/botfather.png) -->

### 2. Create the Notion Database and Integration

**Fastest path — duplicate a ready-made template**, then click **Duplicate** at the top right to copy it into your workspace:

- [English template](https://fifree.notion.site/3a6942e6a592807f9dc3e2370bb527e9?v=3a6942e6a5928094af3a000ce0bdd2c4)
- [中文模板](https://fifree.notion.site/3a6942e6a59280d9b165c05de688db66?v=3a6942e6a59280108d9f000c35330a2c)

Each ships with example rows and a study-breakdown layout; delete the examples once you start. Skip to the integration step below after duplicating.

Or build your own database with four properties:

| Property | Type | Purpose |
|---|---|---|
| `Name` | Title | Your note, or the URL if you sent no note |
| `Link` | URL | The saved link |
| `Status` | Select or Status | Review status, set to the first option on save |
| `Platform` | Multi-select | Which platform the link came from |

The names above are only examples. The bot finds each property **by type, not by name**, so call them whatever you like in whatever language you like: it writes the title to the one title property, the link to a URL property, the status to a select-or-status property, and the platform tags to a multi-select property. See [Customizing Your Database](#customizing-your-database) for what it does and does not touch.

Then go to [notion.so/my-integrations](https://www.notion.so/my-integrations), create an internal integration, and copy its secret.

Connect the integration to your database: open the database, click `···` in the top right, choose **Connections**, and add your integration. Skipping this step is the single most common failure; without it every write returns a 404.

Finally, copy the database ID out of the database URL. In `notion.so/myworkspace/a8aec43384f447ed84390e8e42c2e089?v=...`, the ID is the 32-character string `a8aec43384f447ed84390e8e42c2e089`.

<!-- ![Connecting the integration to the database](docs/images/notion-connection.png) -->

### 3. Fork This Repository

Click **Fork** at the top of this page. Your fork gets its own Actions runner and its own secrets, and none of your credentials are visible to me or to anyone else.

### 4. Add Your Three Secrets

In your fork, go to **Settings → Secrets and variables → Actions**, and add three repository secrets:

| Secret | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | The token from step 1 |
| `NOTION_TOKEN` | The integration secret from step 2 |
| `NOTION_DATABASE_ID` | The 32-character database ID from step 2 |

GitHub encrypts these and hides them from logs. Anyone who forks your fork gets the code and none of the secrets.

<!-- ![Adding repository secrets](docs/images/github-secrets.png) -->

### 5. Enable Actions

Open the **Actions** tab in your fork and click the button to enable workflows. GitHub disables scheduled workflows on new forks by default, so this step is required.

### 6. Send a Test Link

Message your bot with any link. Then open **Actions → poll-telegram → Run workflow** to trigger a run immediately instead of waiting for the schedule. The bot replies in Telegram, and the row appears in Notion.

If nothing happens, open the failed run in the Actions tab. A 404 from Notion means the integration is not connected to the database (step 2). A 401 means the token is wrong.

## Customizing Your Database

The bot reads your database structure on each run and matches four roles by property type, so you can rename columns, reorder them, or run the whole thing in another language without touching any config.

- **Title** → the single title property. Always written.
- **Link** → a URL property (or a text property named like a link if you have no URL column). If there is no such column, the link is kept inside the title so it is never lost.
- **Status** → a Select or Status property. The bot writes that column's **first option**, so whatever you named it (`待分析`, `To Review`, …) is what gets set.
- **Platform** → a Multi-select property. Values are written as English slugs: `Xiaohongshu`, `Bilibili`, `YouTube`, `Twitter/X`, `Instagram`, `Weibo`, `Douyin`, `Other`.

Add any other columns you want (priority, due date, rating, notes, tags): the bot only writes the four roles above and leaves everything else blank for you to fill.

The **one** case to watch is adding a second column of a role's type, for example a Status column plus a Priority column that are both Select. The bot then disambiguates by name — a column whose name contains `status` / `状态` / `进度` wins for status, `platform` / `平台` / `来源` for platform, `link` / `链接` / `url` for the link — and skips the rest. If the names give no hint, it skips that role rather than guess wrong. To force a specific column, set a repository secret: `SOCIAL_STATUS_PROPERTY`, `SOCIAL_PLATFORM_PROPERTY`, `SOCIAL_URL_PROPERTY`, or `SOCIAL_TITLE_PROPERTY`. `SOCIAL_DEFAULT_STATUS` overrides which status option is written.

### Instagram and Xiaohongshu: Fetched Details

For Instagram and Xiaohongshu links, the bot opens the public page anonymously. It sends no login and no cookies, so the platform cannot tie the request to your account. It then saves the details alongside the link:

| Link | What the bot fetches |
|---|---|
| Instagram post or Reel | Caption, author, like and comment counts, cover image |
| Instagram profile | Account name, follower / following / post counts, profile picture |
| Xiaohongshu note (including `xhslink` short links) | Title, text, author, like / save / comment counts, all images (up to 9) |

The bot downloads each image and uploads it to Notion, because the platforms sign their image URLs and those URLs expire within days. The download stays in the memory of the machine that runs the bot and never touches disk. For videos the bot saves the cover frame, not the video file.

To store these details, add any of the columns below. Each one is optional, and the bot skips any role it cannot find.

| Name contains | Type | What the bot writes |
|---|---|---|
| `type` / `类型` | Select | `账号` (account) or `帖子` (post); taken from the URL when the fetch fails |
| `stats` / `数据` | Text | For example `776K 粉丝 · 231 帖子` or `26K 赞 · 336 评论` |
| `cover` / `封面` | Files | The first image. Pair it with a Gallery view that uses this column as the card preview |
| `note` / `备注` | Text | The note you typed next to the link in Telegram |

With details available, the title becomes the post title or account name instead of the raw URL. The page body holds the images, then the full caption, then your note. The platform column may also be a Select: if it already has an option such as `ins` or `小红书`, the bot reuses your label instead of adding `Instagram`.

When a platform blocks the fetch (for example by demanding a login from the server's IP address), the bot still saves the link without details and replies `⚠️ 已存链接，但没抓到详情`.

To change the platform slugs themselves (or add a platform), edit `detect_platform` in [bot.py](bot.py).

## Known Limits

Delivery runs on GitHub's cron, which queues jobs at busy times, so a link can take 5 to 20 minutes longer than the nominal 15.

GitHub pauses scheduled workflows on repositories with no commits for 60 days. One click in the Actions tab brings them back.

The design keeps no state of its own: Telegram holds the queue, and the bot confirms a batch only after processing it. If the network fails between a successful Notion write and that confirmation, the next run reprocesses the batch and you get a duplicate row. Rare, and the tradeoff that removes the need for any database of our own.

## Local Development

```bash
cp .env.example .env    # fill in your real values
pip install -r requirements.txt
python bot.py           # runs one poll cycle and exits
```

`.env` is gitignored. Run the tests with `python -m pytest tests/ -v`; all of them pass offline against fakes and saved sample pages, so no credentials are needed.

## License

MIT. Use it, fork it, change it. Every credential lives in an environment variable, so this repository never contains a token of mine or of yours.

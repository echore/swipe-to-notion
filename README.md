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

Create a database in Notion with four properties:

| Property | Type | Purpose |
|---|---|---|
| `素材名称` | Title | Your note, or the URL if you sent no note |
| `素材链接` | URL | The saved link |
| `状态` | Select | Review status, set to `待分析` on save |
| `平台来源` | Multi-select | Which platform the link came from |

Those default names are Chinese because I built this for my own database. To use English names, create the properties with whatever names you prefer and override them in step 4 (see [Renaming the Notion Properties](#renaming-the-notion-properties)).

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

If nothing happens, open the failed run in the Actions tab. A 404 from Notion means the integration is not connected to the database (step 2). A 401 means the token is wrong. A property-name error means your Notion property names differ from the defaults, which the next section covers.

## Renaming the Notion Properties

Add any of these as repository secrets to match your own database:

| Variable | Default |
|---|---|
| `SOCIAL_TITLE_PROPERTY` | `素材名称` |
| `SOCIAL_URL_PROPERTY` | `素材链接` |
| `SOCIAL_STATUS_PROPERTY` | `状态` |
| `SOCIAL_PLATFORM_PROPERTY` | `平台来源` |
| `SOCIAL_DEFAULT_STATUS` | `待分析` |

So an English database with `Name`, `Link`, `Status` and `Platform` needs four secrets: `SOCIAL_TITLE_PROPERTY=Name`, `SOCIAL_URL_PROPERTY=Link`, `SOCIAL_STATUS_PROPERTY=Status`, `SOCIAL_PLATFORM_PROPERTY=Platform`.

The platform tag values themselves are written by `detect_platform` in [bot.py](bot.py) and are a mix of Chinese and English (`小红书`, `B站`, `YouTube`, `Twitter/X`, `Instagram`, `微博`, `抖音`, `其他`). Edit that function if you want different labels; Notion creates multi-select options on first use, so no setup is needed on the Notion side.

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

`.env` is gitignored. Run the tests with `python -m pytest tests/ -v`; all 13 pass offline against fakes, so no credentials are needed.

## License

MIT. Use it, fork it, change it. Every credential lives in an environment variable, so this repository never contains a token of mine or of yours.

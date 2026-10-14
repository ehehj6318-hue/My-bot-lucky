# SMS Bot — Render Free Web Service

## Deploy

1. Revoke the bot token that was placed in the uploaded source. Create a replacement with BotFather; keep it private.
2. Stop the old polling/background-worker service. Telegram cannot deliver updates to polling and a webhook at the same time.
3. Deploy this folder as a Render **Web Service** from your GitHub `main` branch.
4. In Render → Environment, set `BOT_TOKEN` to the replacement token. Do not put it in source code or commit it.
5. Render supplies `RENDER_EXTERNAL_URL`; the app registers its webhook automatically at startup. For a custom domain, set `PUBLIC_BASE_URL` to its public HTTPS URL.
6. Keep Python at `3.11.9`, use the included build/start commands, and deploy the latest commit.

`WEBHOOK_SECRET` is optional. If omitted, the app derives a stable webhook secret from `BOT_TOKEN`.

## Free plan storage note

Render Free Web Services can spin down when idle and use an ephemeral filesystem. The bot's `bot_data.json` and in-memory FSM state can be lost on restart or redeploy. Use a persistent database or paid persistent disk if the data must survive those events.

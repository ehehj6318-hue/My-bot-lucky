# Lucky Auto Token Bot

## Render deployment

This version uses a Telegram webhook so it can run as a Render Free Web Service.

1. Stop the old polling/background-worker service before starting this version. Telegram cannot deliver updates to polling and a webhook at the same time.
2. Deploy this folder as a Render **Web Service** from the `main` branch. The included `render.yaml` configures the web service, health check, and Python version.
3. Set `BOT_TOKEN` in the Render service's Environment settings. Do not put the token in source code or commit it.
4. Render supplies `RENDER_EXTERNAL_URL`; the app registers its webhook automatically at startup. If using a custom domain, set `PUBLIC_BASE_URL` to its public HTTPS URL.
5. Keep the Build Command as defined in `render.yaml`, then deploy the latest commit.

`WEBHOOK_SECRET` is optional. If omitted, the app derives a stable Telegram webhook secret from `BOT_TOKEN`.

## Free-instance storage limitation

Render Free Web Services can spin down when idle and have an ephemeral filesystem. A sleeping service can add delay to the first webhook update, and the bot's `bot_data.json` file and in-memory FSM state can be lost on restart or redeploy. Use a persistent database or a paid persistent disk if this data must survive restarts.

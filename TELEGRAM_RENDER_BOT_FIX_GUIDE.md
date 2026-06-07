# Telegram bot fix for Render

## What was fixed

The bot could become completely silent on Render because the previous code deleted the Telegram webhook during backend shutdown. During a Render redeploy, the old instance can shut down after the new instance has configured the webhook, so the old instance could remove the active webhook.

This patch changes the behavior:

- webhook is **not deleted on shutdown** by default;
- webhook update parsing uses `types.Update.model_validate(..., context={"bot": bot})`;
- added safe diagnostics: `/api/webhook/telegram/status`;
- added manual webhook reset endpoint: `/api/webhook/telegram/reconfigure`;
- bot status no longer exposes the Telegram token.

## Correct Render environment variables

In `it-school-backend -> Environment`, set:

```env
ENABLE_BOT=true
BOT_MODE=webhook
TELEGRAM_BOT_TOKEN=<token from BotFather>
TELEGRAM_WEBHOOK_URL=https://it-school-backend.onrender.com/api/webhook/telegram
TELEGRAM_WEBHOOK_SECRET=<any long random secret>
TELEGRAM_DELETE_WEBHOOK_ON_SHUTDOWN=false
```

Keep:

```env
DATABASE_URL=<Render Internal Database URL>
AUTO_CREATE_DB=true
```

If your backend URL is not `https://it-school-backend.onrender.com`, use the real backend URL in `TELEGRAM_WEBHOOK_URL`.

## Do not run two modes at once

For the same Telegram bot token, use only one active mode:

- Render production: `BOT_MODE=webhook`;
- local development: `BOT_MODE=polling`.

If Render webhook is enabled, stop your local polling backend. Otherwise Telegram updates can be stolen by the wrong process.

## How to deploy

```bash
git add backend/app/config.py backend/app/bot/__init__.py backend/app/api/endpoints/webhook.py backend/.env.example RENDER_ENV_TEMPLATE.txt render.yaml TELEGRAM_RENDER_BOT_FIX_GUIDE.md
git commit -m "Fix Telegram bot webhook lifecycle on Render"
git push
```

Then in Render:

1. `it-school-backend -> Environment` — set the variables above.
2. `it-school-backend -> Manual Deploy -> Clear build cache & deploy`.
3. Wait until deploy is live.

## How to check

Open this in browser:

```text
https://it-school-backend.onrender.com/api/webhook/telegram/status
```

Expected important fields:

```json
{
  "status": {
    "enabled_setting": true,
    "token_configured": true,
    "normalized_mode": "webhook",
    "transport": "webhook",
    "bot_initialized": true
  },
  "webhook_info": {
    "url": "https://it-school-backend.onrender.com/api/webhook/telegram",
    "last_error_message": null
  }
}
```

If `last_error_message` is not null, it tells the real reason why Telegram cannot reach your backend.

## Manual webhook reconfigure

If the status shows an empty or wrong webhook URL, you can re-set it without another deploy:

```powershell
$headers = @{ "X-Admin-Secret" = "<your TELEGRAM_WEBHOOK_SECRET>" }
Invoke-RestMethod -Method Post -Uri "https://it-school-backend.onrender.com/api/webhook/telegram/reconfigure" -Headers $headers
```

Then open `/api/webhook/telegram/status` again.

## Local development

For local polling mode in `backend/.env`:

```env
ENABLE_BOT=true
BOT_MODE=polling
TELEGRAM_BOT_TOKEN=<token from BotFather>
TELEGRAM_WEBHOOK_URL=
TELEGRAM_WEBHOOK_SECRET=
```

If you use local polling, Render webhook should be disabled or you should use a separate bot token for local tests.

#!/usr/bin/env python3
"""Telegram bot diagnostic.

Reads the token from the TELEGRAM_BOT_TOKEN environment variable (NEVER hardcode
it here) and prints the two checks that explain ~95% of "dead bot" cases:

  * getMe          -> is the token valid / not revoked?
  * getWebhookInfo -> is a webhook set, to which URL, and what is last_error_message?

Usage (PowerShell):
    $env:TELEGRAM_BOT_TOKEN="<your-new-token>"; python diagnose_bot.py

Usage (bash):
    TELEGRAM_BOT_TOKEN="<your-new-token>" python diagnose_bot.py

Optional: pass --delete-webhook to clear a stale webhook and pending queue,
or --set-webhook https://host/api/webhook/telegram to (re)point it.
"""
import os
import sys
import json
import urllib.request
import urllib.parse

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
API = "https://api.telegram.org/bot{token}/{method}"


def call(method: str, **params):
    url = API.format(token=TOKEN, method=method)
    data = urllib.parse.urlencode(params).encode() if params else None
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as r:
        return json.loads(r.read().decode())


def main() -> int:
    if not TOKEN:
        print("ERROR: set TELEGRAM_BOT_TOKEN in the environment first.")
        return 2

    args = sys.argv[1:]

    if "--delete-webhook" in args:
        print("deleteWebhook ->", json.dumps(call("deleteWebhook", drop_pending_updates="true"), ensure_ascii=False))

    if "--set-webhook" in args:
        i = args.index("--set-webhook")
        try:
            target = args[i + 1]
        except IndexError:
            print("ERROR: --set-webhook needs a URL")
            return 2
        print("setWebhook ->", json.dumps(call("setWebhook", url=target), ensure_ascii=False))

    try:
        me = call("getMe")
    except Exception as e:
        print("getMe FAILED:", e)
        print(">>> Token is likely invalid/revoked. Generate a new one in @BotFather.")
        return 1
    print("getMe        ->", json.dumps(me, ensure_ascii=False))

    info = call("getWebhookInfo")
    print("getWebhookInfo ->", json.dumps(info, ensure_ascii=False, indent=2))

    r = info.get("result", {})
    url = r.get("url") or ""
    print("\n--- interpretation ---")
    if not me.get("ok"):
        print("* Token invalid -> 401. Regenerate in @BotFather.")
    if not url:
        print("* No webhook set. You are (or should be) in POLLING mode.")
        print("  On Render free tier polling dies when the service sleeps -> use webhook.")
    else:
        print(f"* Webhook URL: {url}")
        print("  It MUST be your live backend host + /api/webhook/telegram")
    if r.get("last_error_message"):
        print(f"* last_error_message: {r['last_error_message']}  <-- the real reason")
    if r.get("pending_update_count"):
        print(f"* pending_update_count: {r['pending_update_count']} (updates queued, not delivered)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

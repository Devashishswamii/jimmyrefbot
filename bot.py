"""
Jimmy Refunds Captcha Bot — Bulletproof Edition
- python-telegram-bot v20 (synchronous entry, manages its own loop)
- Health server uses stdlib http.server (no asyncio conflict)
- Auto-pinger runs in a daemon thread
"""

import os
import random
import asyncio
import io
import datetime
import threading
import requests as rq
from http.server import HTTPServer, BaseHTTPRequestHandler

from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PORT      = int(os.environ.get("PORT", "10000"))

CHAT_IDS = {
    "cashback":     os.environ.get("CHAT_CASHBACK", ""),
    "announcement": os.environ.get("CHAT_ANNOUNCEMENT", ""),
    "storelist":    os.environ.get("CHAT_STORELIST", ""),
    "vouches":      os.environ.get("CHAT_VOUCHES", ""),
    "cashout":      os.environ.get("CHAT_CASHOUT", ""),
    "billpay":      os.environ.get("CHAT_BILLPAY", ""),
}

# ── Promo template ────────────────────────────────────────────────────────────
PROMO_TEMPLATE = (
    "\U0001F4E8 Your exclusive links \u2014 valid for \u23F3 {time_left}s:\n\n"
    "\u26A1\uFE0F JIMMY R\u00A3FUNDS \u26A1\uFE0F\n"
    "Reship Like a Pro. Control Like a Boss.\n\n"
    "\u2E3B\n\n"
    "\U0001F31F Warm Greetings from the Jimmy Team!\n"
    "Welcome to the most trusted reship & R\u20ACfund network.\n\n"
    "\u2E3B\n\n"
    "\U0001F4E6 Official Jimmy Network Links:\n\n"
    "\U0001F539 Cashback Lounge:\n\U0001F449 {link_cashback}\n\n"
    "\U0001F539 Announcement:\n\U0001F449 {link_announcement}\n\n"
    "\U0001F539 StoreList:\n\U0001F449 {link_storelist}\n\n"
    "\U0001F539 Vouches:\n\U0001F449 {link_vouches}\n\n"
    "\U0001F539 Cashout:\n\U0001F449 {link_cashout}\n\n"
    "\U0001F539 BillPay/Discounts/Bookings:\n\U0001F449 {link_billpay}\n\n"
    "\U0001F451 Founder & Refunder:\n"
    "\U0001F449 @JimmyRefund / @JimmyRefs \U0001F48E https://t.me/JimmyRefund\n\n"
    "1. Click each link and join\n"
    "2. Join ALL groups listed above\n"
    "3. Missed one? Send /start again"
)

# ── Captcha image ─────────────────────────────────────────────────────────────
def make_captcha_image(text: str) -> io.BytesIO:
    img  = Image.new("RGB", (400, 160), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=58)
    except Exception:
        font = ImageFont.load_default()
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        tw, th = 200, 58
    draw.text(((400 - tw) / 2, (160 - th) / 2), text, fill=(255, 255, 255), font=font)
    buf = io.BytesIO()
    buf.name = "captcha.png"
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

# ── Health check server (pure stdlib — zero asyncio) ──────────────────────────
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"Jimmy Bot is alive!"
        self.send_response(200)
        self.send_header("Content-Type",   "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, *args):
        pass   # silence access logs

def _start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), _HealthHandler)
    print(f"[WEB]  Health server on port {PORT}")
    server.serve_forever()

# ── Auto-pinger thread (keeps Render free tier awake) ─────────────────────────
def _auto_ping():
    import time
    url = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
    if not url:
        print("[PING] RENDER_EXTERNAL_URL not set — skipping")
        return
    if not url.startswith("http"):
        url = "https://" + url
    while True:
        time.sleep(240)   # every 4 minutes
        try:
            r = rq.get(url, timeout=10)
            print(f"[PING] {url} → {r.status_code}")
        except Exception as e:
            print(f"[PING] error: {e}")

# ── /id ───────────────────────────────────────────────────────────────────────
async def cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"\U0001F4CB Chat ID: `{update.effective_chat.id}`\n\nPaste into Render env vars.",
        parse_mode="Markdown",
    )

# ── /ping ─────────────────────────────────────────────────────────────────────
async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\u2705 Bot is alive and running 24/7!")

# ── /start ────────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    print(f"[START] user={uid}")

    op = random.choice(["+", "-"])
    if op == "+":
        a, b = random.randint(10, 50), random.randint(10, 50)
    else:
        a = random.randint(20, 60)
        b = random.randint(5, a - 1)
    ans = a + b if op == "+" else a - b

    choices = [ans]
    while len(choices) < 4:
        w = ans + random.choice([-1, 1]) * random.randint(1, 15)
        if w >= 0 and w not in choices:
            choices.append(w)
    random.shuffle(choices)

    # Correct answer embedded in callback_data — no session store needed
    rows = [
        [
            InlineKeyboardButton(str(choices[0]), callback_data=f"ans_{choices[0]}_{ans}"),
            InlineKeyboardButton(str(choices[1]), callback_data=f"ans_{choices[1]}_{ans}"),
        ],
        [
            InlineKeyboardButton(str(choices[2]), callback_data=f"ans_{choices[2]}_{ans}"),
            InlineKeyboardButton(str(choices[3]), callback_data=f"ans_{choices[3]}_{ans}"),
        ],
    ]

    await update.message.reply_photo(
        photo=make_captcha_image(f"{a} {op} {b} = ?"),
        caption=(
            "\U0001F916 HUMAN VERIFICATION\n\n"
            "Solve the math problem to get your private group links:"
        ),
        reply_markup=InlineKeyboardMarkup(rows),
    )
    print(f"[START] captcha sent to {uid}")

# ── Callback: verify answer ───────────────────────────────────────────────────
async def cb_verify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cq       = update.callback_query
    uid      = cq.from_user.id
    parts    = cq.data.split("_")   # ans_<selected>_<correct>
    selected = int(parts[1])
    correct  = int(parts[2])
    print(f"[VERIFY] user={uid} sel={selected} correct={correct}")

    if selected != correct:
        await cq.answer("\u274C Wrong! Try again or send /start.", show_alert=True)
        return

    await cq.answer("\u2705 Correct! Generating your links...", show_alert=True)
    try:
        await cq.message.delete()
    except Exception:
        pass

    expire_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=65)
    links, invites = {}, []

    for name, cid in CHAT_IDS.items():
        key = f"link_{name}"
        if cid.strip():
            try:
                inv = await ctx.bot.create_chat_invite_link(
                    chat_id=int(cid.strip()),
                    member_limit=1,
                    expire_date=expire_dt,
                )
                links[key] = inv.invite_link
                invites.append((int(cid.strip()), inv.invite_link))
            except Exception as e:
                print(f"[LINK] {name}: {e}")
                links[key] = "\u274C Bot not admin here"
        else:
            links[key] = "\u274C Not configured in Render"

    msg = await ctx.bot.send_message(
        chat_id=uid,
        text=PROMO_TEMPLATE.format(time_left=60, **links),
        disable_web_page_preview=True,
    )
    print(f"[PROMO] sent msg_id={msg.message_id} to {uid}")
    asyncio.create_task(expire_message(ctx.bot, uid, msg.message_id, links, invites))

# ── Countdown + revoke + delete ───────────────────────────────────────────────
async def expire_message(bot, chat_id, msg_id, links, invites, total=60, step=5):
    remaining = total
    while remaining > 0:
        await asyncio.sleep(step)
        remaining -= step
        if remaining > 0:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=PROMO_TEMPLATE.format(time_left=remaining, **links),
                    disable_web_page_preview=True,
                )
            except Exception:
                pass

    for cid, link in invites:
        try:
            await bot.revoke_chat_invite_link(chat_id=cid, invite_link=link)
            print(f"[REVOKE] {link}")
        except Exception as e:
            print(f"[REVOKE] error: {e}")

    try:
        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception as e:
        print(f"[DELETE] error: {e}")

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise SystemExit("ERROR: BOT_TOKEN environment variable is not set!")

    # Threads (no asyncio conflicts — fully isolated)
    threading.Thread(target=_start_health_server, daemon=True).start()
    threading.Thread(target=_auto_ping,           daemon=True).start()

    # Build PTB application
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("ping",  cmd_ping))
    application.add_handler(CommandHandler("id",    cmd_id))
    application.add_handler(CallbackQueryHandler(cb_verify, pattern=r"^ans_-?\d+_-?\d+$"))

    print("[BOT] \U0001F7E2 Starting — bot is live 24/7!")

    # run_polling() called DIRECTLY (not inside async) — it manages its OWN loop
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )

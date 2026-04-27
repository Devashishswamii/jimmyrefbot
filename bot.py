"""
Jimmy Refunds Captcha Bot
Framework: python-telegram-bot v20 (asyncio-native, no loop conflicts)
"""

import os
import random
import asyncio
import io
import datetime
import threading
import requests as req

from aiohttp import web
from PIL import Image, ImageDraw, ImageFont

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
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

# ── Promo message template ────────────────────────────────────────────────────
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

# ── /id command ───────────────────────────────────────────────────────────────
async def cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"\U0001F4CB Chat ID: `{update.effective_chat.id}`\n\nCopy this into Render env vars.",
        parse_mode="Markdown",
    )

# ── /ping command ─────────────────────────────────────────────────────────────
async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\u2705 Bot is alive and running 24/7!")

# ── /start command ────────────────────────────────────────────────────────────
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

    # Embed correct answer directly in callback_data → no DB needed
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
            "Solve the math problem above to receive your private group links:"
        ),
        reply_markup=InlineKeyboardMarkup(rows),
    )
    print(f"[START] captcha sent to {uid}")

# ── Button callback ───────────────────────────────────────────────────────────
async def cb_verify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cq  = update.callback_query
    uid = cq.from_user.id
    await cq.answer()   # dismiss the loading spinner immediately

    parts    = cq.data.split("_")         # ans_<selected>_<correct>
    selected = int(parts[1])
    correct  = int(parts[2])
    print(f"[VERIFY] user={uid} selected={selected} correct={correct}")

    if selected != correct:
        await cq.answer("\u274C Wrong! Try again or send /start.", show_alert=True)
        return

    await cq.answer("\u2705 Correct! Sending your links...", show_alert=True)

    # Clean up captcha message
    try:
        await cq.message.delete()
    except Exception:
        pass

    # Generate one-time invite links (expire in 65 s, single-use)
    expire_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=65)
    links   = {}
    invites = []
    bot     = ctx.bot

    for name, cid in CHAT_IDS.items():
        key = f"link_{name}"
        if cid.strip():
            try:
                inv = await bot.create_chat_invite_link(
                    chat_id=int(cid.strip()),
                    member_limit=1,
                    expire_date=expire_dt,
                )
                links[key]  = inv.invite_link
                invites.append((int(cid.strip()), inv.invite_link))
            except Exception as e:
                print(f"[LINK] {name} error: {e}")
                links[key] = "\u274C Bot not admin here"
        else:
            links[key] = "\u274C Not configured (add in Render env)"

    msg = await bot.send_message(
        chat_id=uid,
        text=PROMO_TEMPLATE.format(time_left=60, **links),
        disable_web_page_preview=True,
    )
    print(f"[PROMO] sent to {uid}, msg_id={msg.message_id}")

    # Schedule countdown + auto-delete
    asyncio.create_task(expire_message(bot, uid, msg.message_id, links, invites))

# ── Countdown timer → revoke links → delete message ──────────────────────────
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

    # Revoke all one-time links
    for cid, link in invites:
        try:
            await bot.revoke_chat_invite_link(chat_id=cid, invite_link=link)
            print(f"[REVOKE] {link}")
        except Exception as e:
            print(f"[REVOKE] error: {e}")

    # Delete the message
    try:
        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception as e:
        print(f"[DELETE] error: {e}")

# ── Health check web server (aiohttp) ─────────────────────────────────────────
async def run_health_server():
    async def handle(request):
        return web.Response(text="Jimmy Bot is alive!", status=200)
    app_web = web.Application()
    app_web.router.add_route("*", "/{tail:.*}", handle)
    runner = web.AppRunner(app_web)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    print(f"[WEB] Health server on port {PORT}")

# ── Auto-pinger thread (keeps Render free tier awake) ─────────────────────────
def auto_ping_thread():
    url = os.environ.get("RENDER_EXTERNAL_URL", "")
    if not url:
        print("[PING] RENDER_EXTERNAL_URL not set — skipping auto-ping")
        return
    if not url.startswith("http"):
        url = "https://" + url
    import time
    while True:
        time.sleep(240)  # every 4 minutes
        try:
            r = req.get(url, timeout=10)
            print(f"[PING] {url} → {r.status_code}")
        except Exception as e:
            print(f"[PING] error: {e}")

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set!")

    # Start health server
    await run_health_server()

    # Start pinger in background thread (avoids asyncio loop conflicts entirely)
    t = threading.Thread(target=auto_ping_thread, daemon=True)
    t.start()

    # Build and start the bot (drop_pending_updates clears stuck queue)
    bot_app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    bot_app.add_handler(CommandHandler("start", cmd_start))
    bot_app.add_handler(CommandHandler("ping",  cmd_ping))
    bot_app.add_handler(CommandHandler("id",    cmd_id))
    bot_app.add_handler(CallbackQueryHandler(cb_verify, pattern=r"^ans_-?\d+_-?\d+$"))

    print("[BOT] \U0001F7E2 Starting polling — bot is live 24/7!")
    await bot_app.run_polling(
        drop_pending_updates=True,   # clears the 15 stuck updates immediately
        allowed_updates=Update.ALL_TYPES,
    )

if __name__ == "__main__":
    asyncio.run(main())

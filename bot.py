import os
import random
import asyncio
import io
import datetime
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageDeleteForbidden, FloodWait
from PIL import Image, ImageDraw, ImageFont

# ── Config ───────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
API_ID    = int(os.environ.get("API_ID", "2040"))
API_HASH  = os.environ.get("API_HASH", "b18441a1ff607e10a989891a5462e627")
PORT      = int(os.environ.get("PORT", "10000"))

CHAT_IDS = {
    "cashback":     os.environ.get("CHAT_CASHBACK", ""),
    "announcement": os.environ.get("CHAT_ANNOUNCEMENT", ""),
    "storelist":    os.environ.get("CHAT_STORELIST", ""),
    "vouches":      os.environ.get("CHAT_VOUCHES", ""),
    "cashout":      os.environ.get("CHAT_CASHOUT", ""),
    "billpay":      os.environ.get("CHAT_BILLPAY", ""),
}

# ── Pyrogram Client ───────────────────────────────────────────────────────────
app = Client(
    name="captcha_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)

# ── In-memory captcha store ───────────────────────────────────────────────────
ACTIVE_CAPTCHAS: dict = {}

# ── Promo Template ────────────────────────────────────────────────────────────
PROMO_TEMPLATE = (
    "\U0001F4E8 Your links (valid for \u23F3 {time_left} seconds):\n\n"
    "\u26A1\uFE0F JIMMY R\u00A3FUNDS \u26A1\uFE0F\n"
    "Reship Like a Pro. Control Like a Boss.\n\n"
    "\u2E3B\n\n"
    "\U0001F31F Warm Greetings from the Jimmy Team! \U0001F31F\n"
    "Welcome to the most trusted and efficient reship & R\u20ACfund network \u2014 "
    "where precision, privacy, and professionalism meet speed and reliability.\n\n"
    "\u2E3B\n\n"
    "\U0001F4E6 Official Jimmy Network Links:\n\n"
    "\U0001F539 Cashback Lounge:\n\U0001F449 {link_cashback}\n\n"
    "\U0001F539 Announcement:\n\U0001F449 {link_announcement}\n\n"
    "\U0001F539 StoreList:\n\U0001F449 {link_storelist}\n\n"
    "\U0001F539 Vouches:\n\U0001F449 {link_vouches}\n\n"
    "\U0001F539 Cashout:\n\U0001F449 {link_cashout}\n\n"
    "\U0001F539 BillPay/Discounts/bookings:\n\U0001F449 {link_billpay}\n\n"
    "\U0001F451 Founder & Refunder:\n"
    "\U0001F449 @JimmyRefund / @JimmyRefs \U0001F48E https://t.me/JimmyRefund\n\n"
    "1. Click each link and join\n"
    "2. Make sure to join ALL groups above\n"
    "3. Missed one? Send /start again"
)

# ── Captcha image ─────────────────────────────────────────────────────────────
def make_captcha_image(text: str) -> io.BytesIO:
    img = Image.new("RGB", (400, 160), color=(30, 30, 30))
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

# ── /id helper ────────────────────────────────────────────────────────────────
@app.on_message(filters.command("id"))
async def cmd_id(client, message):
    await message.reply(f"Chat ID: `{message.chat.id}`")

# ── /ping ─────────────────────────────────────────────────────────────────────
@app.on_message(filters.command("ping") & filters.private)
async def cmd_ping(client, message):
    await message.reply("\u2705 Bot is alive and working 24/7!")

# ── /start ────────────────────────────────────────────────────────────────────
@app.on_message(filters.command("start") & filters.private)
async def cmd_start(client, message):
    uid = message.from_user.id
    print(f"[START] user={uid}")
    try:
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

        # Embed correct answer in callback_data so we never need the in-memory store
        rows = []
        for i in range(0, 4, 2):
            rows.append([
                InlineKeyboardButton(str(choices[i]),     callback_data=f"ans_{choices[i]}_{ans}"),
                InlineKeyboardButton(str(choices[i + 1]), callback_data=f"ans_{choices[i+1]}_{ans}"),
            ])

        await message.reply_photo(
            photo=make_captcha_image(f"{a} {op} {b} = ?"),
            caption="\U0001F916 HUMAN VERIFICATION\n\nSolve the math problem above to get your links:",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        print(f"[START] captcha sent to {uid}")
    except Exception as e:
        print(f"[START] ERROR: {e}")

# ── Callback: verify answer ───────────────────────────────────────────────────
@app.on_callback_query(filters.regex(r"^ans_(-?\d+)_(-?\d+)$"))
async def cb_answer(client, cq):
    uid      = cq.from_user.id
    selected = int(cq.matches[0].group(1))
    correct  = int(cq.matches[0].group(2))
    print(f"[VERIFY] user={uid} selected={selected} correct={correct}")

    if selected != correct:
        await cq.answer("\u274C Wrong! Try again or send /start for a new question.", show_alert=True)
        return

    await cq.answer("\u2705 Verified! Here are your links.", show_alert=False)
    try:
        await cq.message.delete()
    except Exception:
        pass

    # Generate one-time 65-second expiry invite links
    expire_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=65)
    links   = {}
    invites = []
    for name, cid in CHAT_IDS.items():
        if cid.strip():
            try:
                inv = await client.create_chat_invite_link(
                    chat_id=int(cid.strip()),
                    member_limit=1,
                    expire_date=expire_date,
                )
                links[f"link_{name}"] = inv.invite_link
                invites.append((int(cid.strip()), inv.invite_link))
            except Exception as e:
                print(f"[LINK] {name} failed: {e}")
                links[f"link_{name}"] = "\u274C Bot not admin in this channel"
        else:
            links[f"link_{name}"] = "\u274C Not configured in Render"

    try:
        msg = await client.send_message(
            chat_id=uid,
            text=PROMO_TEMPLATE.format(time_left=60, **links),
            disable_web_page_preview=True,
        )
        asyncio.create_task(expire_message(client, uid, msg.id, links, invites))
        print(f"[PROMO] sent to {uid}")
    except Exception as e:
        print(f"[PROMO] send error: {e}")

# ── Timer: countdown + revoke + delete ────────────────────────────────────────
async def expire_message(client, chat_id, msg_id, links, invites, total=60, step=5):
    remaining = total
    while remaining > 0:
        await asyncio.sleep(step)
        remaining -= step
        if remaining > 0:
            try:
                await client.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=PROMO_TEMPLATE.format(time_left=remaining, **links),
                    disable_web_page_preview=True,
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                pass

    for cid, link in invites:
        try:
            await client.revoke_chat_invite_link(chat_id=cid, invite_link=link)
            print(f"[REVOKE] {link}")
        except Exception as e:
            print(f"[REVOKE] failed: {e}")

    try:
        await client.delete_messages(chat_id=chat_id, message_ids=msg_id)
    except Exception as e:
        print(f"[DELETE] failed: {e}")

# ── Health endpoint (Render / UptimeRobot) ────────────────────────────────────
async def start_web_server():
    async def handle(request):
        return web.Response(text="Bot is alive!", status=200)
    app_web = web.Application()
    app_web.router.add_route("*", "/{tail:.*}", handle)
    runner = web.AppRunner(app_web)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    print(f"[WEB] Health server running on port {PORT}")

# ── Auto-pinger (keeps Render free tier alive) ────────────────────────────────
async def auto_ping():
    import aiohttp
    timeout = aiohttp.ClientTimeout(total=10)
    while True:
        await asyncio.sleep(240)   # every 4 minutes
        url = os.environ.get("RENDER_EXTERNAL_URL", "")
        if url:
            if not url.startswith("http"):
                url = "https://" + url
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as r:
                        print(f"[PING] {url} -> {r.status}")
            except Exception as e:
                print(f"[PING] error: {e}")

# ── Main entry point ──────────────────────────────────────────────────────────
async def main():
    await app.start()
    print("[BOT] Connected to Telegram \u2705")
    await start_web_server()
    asyncio.create_task(auto_ping())
    print("[BOT] Ready — listening 24/7 \U0001F7E2")
    await idle()
    await app.stop()
    print("[BOT] Stopped.")

if __name__ == "__main__":
    asyncio.run(main())

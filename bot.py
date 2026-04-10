import os
import random
import asyncio
import io
import time
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageDeleteForbidden, FloodWait
from PIL import Image, ImageDraw, ImageFont

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
# Test API credentials, safe to leave as default unless user has their own
API_ID = int(os.environ.get("API_ID", "2040"))
API_HASH = os.environ.get("API_HASH", "b18441a1ff607e10a989891a5462e627")
PORT = int(os.environ.get("PORT", "8080"))

app = Client(
    "captcha_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

PROMO_MESSAGE = """📨 Your links (valid for ⏳ {time_left} seconds):

⚡️ JIMMY R£FUNDS ⚡️
Reship Like a Pro. Control Like a Boss.

⸻

🌟 Warm Greetings from the Jimmy Team! 🌟
Welcome to the most trusted and efficient reship & R€fund network — where precision, privacy, and professionalism meet speed and reliability.

⸻

📦 Official Jimmy Network Links:

🔹 Cashback Lounge:
👉 {link_cashback}

🔹 Announcement:
👉  {link_announcement}

🔹 StoreList:
👉  {link_storelist}

🔹 Vouches:
👉 {link_vouches}

🔹 Cashout:
👉 {link_cashout}

🔹 BillPay/Discounts/bookings.
👉  {link_billpay}

👑 Founder & Refunder:
👉 @JimmyRefund / @JimmyRefs 💎 https://t.me/JimmyRefund

1. Click the Link and Join
2. Make sure to join all the groups above by clicking the links
3. If you missed any, re-enter /start"""

# In-memory store: user_id -> {"answer": int}
ACTIVE_CAPTCHAS = {}

@app.on_message(filters.command("id"))
async def id_command(client, message):
    await message.reply(f"Here is the Chat ID:\n`{message.chat.id}`\n\nCopy that exact number and configure it in Render!")

def generate_captcha_image(text):
    # Native crystal clear 400x160 HD rendering
    img = Image.new('RGB', (400, 160), color=(40, 40, 40))
    d = ImageDraw.Draw(img)
    
    # Load smooth, anti-aliased native size font
    try:
        font = ImageFont.load_default(size=50)
    except Exception:
        font = ImageFont.load_default()
        
    # Beautifully center the math text
    try:
        bbox = d.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except Exception:
        text_w = 200
        text_h = 50
        
    x = (400 - text_w) / 2
    y = (160 - text_h) / 2
    
    d.text((x, y), text, fill=(255, 255, 255), font=font)
    
    bio = io.BytesIO()
    bio.name = 'captcha.jpg'
    img.save(bio, 'JPEG', quality=95)
    bio.seek(0)
    return bio

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    print(f"Received /start from {message.from_user.id}")
    try:
        # Generate random math problem
        op = random.choice(['+', '-'])
        if op == '+':
            a = random.randint(10, 50)
            b = random.randint(10, 50)
            ans = a + b
        else:
            a = random.randint(20, 50)
            b = random.randint(10, a - 1) # Keep answer positive
            ans = a - b
            
        question_text = f"{a} {op} {b} = ?"
        img_stream = generate_captcha_image(question_text)
        
        # Generate 4 choices
        choices = [ans]
        while len(choices) < 4:
            offset = random.randint(1, 15)
            # Randomly add or subtract the offset
            direction = random.choice([1, -1])
            wrong = ans + (offset * direction)
            # Keep choices positive and unique
            if wrong not in choices and wrong >= 0:
                choices.append(wrong)
                
        # Shuffle so correct answer isn't always first
        random.shuffle(choices)
        
        # Save correct answer in memory
        ACTIVE_CAPTCHAS[message.from_user.id] = {"answer": ans}
        
        # Build a 2x2 keyboard
        buttons = []
        row = []
        for c in choices:
            row.append(InlineKeyboardButton(str(c), callback_data=f"verify_{c}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
            
        await message.reply_photo(
            photo=img_stream,
            caption="🤖 HUMAN VERIFICATION\n\nSOLVE THIS CAPTCHA TO GET LINK:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        print("Sent captcha successfully.")
    except Exception as e:
        print(f"ERROR inside start_command: {e}")

@app.on_callback_query(filters.regex(r"^verify_(\d+)$"))
async def verify_callback(client, callback_query):
    user_id = callback_query.from_user.id
    selected_answer = int(callback_query.matches[0].group(1))
    print(f"Callback received: verify_{selected_answer} from {user_id}")
    
    captcha_data = ACTIVE_CAPTCHAS.get(user_id)
    if not captcha_data:
        await callback_query.answer("Verification expired or not found. Please type /start again.", show_alert=True)
        return
        
    correct_answer = captcha_data["answer"]
    
    if selected_answer == correct_answer:
        # Success
        del ACTIVE_CAPTCHAS[user_id]
        await callback_query.answer("Verification successful!", show_alert=False)
        
        # Delete captcha message to clean up chat
        try:
            await callback_query.message.delete()
        except MessageDeleteForbidden:
            pass # Ignore if we can't delete
        
        # Generate new one-time links dynamically
        import datetime
        # Expire slightly after the message deletion to ensure they can click it at second 59
        expire_date = datetime.datetime.now() + datetime.timedelta(seconds=65) 
        
        chat_ids = {
            "cashback": os.environ.get("CHAT_CASHBACK", ""),
            "announcement": os.environ.get("CHAT_ANNOUNCEMENT", ""),
            "storelist": os.environ.get("CHAT_STORELIST", ""),
            "vouches": os.environ.get("CHAT_VOUCHES", ""),
            "cashout": os.environ.get("CHAT_CASHOUT", ""),
            "billpay": os.environ.get("CHAT_BILLPAY", "")
        }
        
        generated_links = {}
        active_invites = []
        
        for name, cid in chat_ids.items():
            if cid:
                try:
                    invite = await client.create_chat_invite_link(
                        chat_id=int(cid.strip()),
                        member_limit=1,
                        expire_date=expire_date
                    )
                    generated_links[f"link_{name}"] = invite.invite_link
                    active_invites.append((int(cid.strip()), invite.invite_link))
                except Exception as e:
                    print(f"Failed generating link for {name}: {e}")
                    generated_links[f"link_{name}"] = "❌ Error: Bot not Admin"
            else:
                 generated_links[f"link_{name}"] = "❌ Not Linked in Render"

        formatted_promo = PROMO_MESSAGE.format(time_left="60", **generated_links)

        try:
            promo_msg = await client.send_message(
                chat_id=user_id,
                text=formatted_promo,
                disable_web_page_preview=True
            )
            print("Sent PROMO_MESSAGE successfully.")
            # Schedule the deletion after exactly 60 seconds with timer updates
            asyncio.create_task(delete_after_delay(client, user_id, promo_msg.id, 60, generated_links, active_invites))
        except Exception as e:
            print(f"ERROR sending PROMO_MESSAGE: {e}")
    else:
        # Failure
        await callback_query.answer("Incorrect answer! Please try again or type /start for a new question.", show_alert=True)

async def delete_after_delay(client, chat_id, message_id, delay, links_dict, active_invites):
    """Updates the message with a countdown timer, then deletes it and explicitly revokes all links."""
    time_left = delay
    step = 5  # Update the message every 5 seconds
    
    while time_left > 0:
        await asyncio.sleep(step)
        time_left -= step
        
        if time_left > 0:
            try:
                # Update the countdown text
                updated_text = PROMO_MESSAGE.format(time_left=str(time_left), **links_dict)
                await client.edit_message_text(
                    chat_id=chat_id, 
                    message_id=message_id, 
                    text=updated_text, 
                    disable_web_page_preview=True
                )
            except FloodWait as e:
                # If we hit rate limits, wait the required time
                await asyncio.sleep(e.value)
            except Exception as e:
                # Ignore message not modified or other transient errors
                pass

    # Revoke all one-time links immediately, ensuring they are dead
    for c_id, link in active_invites:
        try:
            await client.revoke_chat_invite_link(chat_id=c_id, invite_link=link)
            print(f"Successfully killed link: {link}")
        except Exception as e:
            print(f"Failed to revoke link {link}: {e}")

    # Delete the message once time is up
    try:
        await client.delete_messages(chat_id=chat_id, message_ids=message_id)
    except Exception as e:
        print(f"Failed to delete message: {e}")

# --- Web Server to satisfy Render's health checks ---
async def web_server():
    async def handle_ping(request):
        return web.Response(text="Bot is alive and running!", status=200)
        
    webapp = web.Application()
    # Catch-all route to avoid 404s
    webapp.router.add_route('*', '/{tail:.*}', handle_ping)
    
    runner = web.AppRunner(webapp)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"Web server started on port {PORT}")

async def auto_ping():
    """Pings the server externally every 5 minutes to keep it 24/7 alive."""
    import aiohttp
    while True:
        await asyncio.sleep(300) # 5 minutes
        url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("PING_URL")
        if url:
            try:
                if not url.startswith("http"):
                    url = f"https://{url}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        print(f"Auto-pinger (24/7 Alive): Pinged {url} - Status: {response.status}")
            except Exception as e:
                print(f"Auto-pinger error: {e}")

if __name__ == "__main__":
    print("Starting background web server and tasks...")
    loop = asyncio.get_event_loop()
    loop.create_task(web_server())
    loop.create_task(auto_ping())
    
    print("Initializing Pyrogram Event Loop...")
    app.run()

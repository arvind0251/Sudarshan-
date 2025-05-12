import os, json, asyncio
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import ReportSpamRequest
from telethon.errors import FloodWaitError

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

BOT_TOKEN = "8057384324:AAFiDKf4vZZdS0hsmu2hMk4GnS2Bhpiz5tY"
ACCOUNTS_FILE = "accounts.json"
SESSIONS_DIR = "sessions"
ADD_DELAY = 10
BATCH_SIZE = 30

os.makedirs(SESSIONS_DIR, exist_ok=True)

def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    with open(ACCOUNTS_FILE, "r") as f:
        return json.load(f)

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, indent=4)

# --- Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to Telegram Adder Bot!\nCommands:\n/login api_id api_hash phone\n/addmembers source target\n/report @username")

async def handle_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = update.message.text.split()
        _, api_id, api_hash, phone = args
        api_id = int(api_id)
        session_path = f"{SESSIONS_DIR}/{phone}"
        client = TelegramClient(session_path, api_id, api_hash)
        await client.start(phone)
        await client.disconnect()

        accounts = load_accounts()
        accounts.append({'api_id': api_id, 'api_hash': api_hash, 'phone': phone})
        save_accounts(accounts)
        await update.message.reply_text(f"✅ {phone} logged in.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /report @username")
        return

    username = context.args[0]
    accounts = load_accounts()

    for acc in accounts:
        try:
            client = TelegramClient(f"{SESSIONS_DIR}/{acc['phone']}", acc['api_id'], acc['api_hash'])
            await client.connect()
            user = await client.get_entity(username)
            await client(ReportSpamRequest(user))
            await update.message.reply_text(f"✅ Reported {username} from {acc['phone']}")
            await client.disconnect()
        except Exception as e:
            await update.message.reply_text(f"❌ {acc['phone']}: {e}")

async def add_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /addmembers source_group target_group")
        return

    source = context.args[0]
    target = context.args[1]
    accounts = load_accounts()

    if not accounts:
        await update.message.reply_text("No logged-in accounts.")
        return

    main_client = TelegramClient(f"{SESSIONS_DIR}/{accounts[0]['phone']}", accounts[0]['api_id'], accounts[0]['api_hash'])
    await main_client.connect()
    try:
        source_entity = await main_client.get_input_entity(source)
        users = await main_client.get_participants(source_entity)
        await update.message.reply_text(f"Fetched {len(users)} users from {source}")
    except Exception as e:
        await update.message.reply_text(f"Error fetching members: {e}")
        await main_client.disconnect()
        return

    await main_client.disconnect()

    index = 0
    for acc in accounts:
        client = TelegramClient(f"{SESSIONS_DIR}/{acc['phone']}", acc['api_id'], acc['api_hash'])
        await client.connect()
        try:
            target_entity = await client.get_input_entity(target)
            batch = users[index:index + BATCH_SIZE]
            for user in batch:
                try:
                    await client(InviteToChannelRequest(channel=target_entity, users=[user.id]))
                    await update.message.reply_text(f"Added {user.first_name} via {acc['phone']}")
                    await asyncio.sleep(ADD_DELAY)
                except FloodWaitError as f:
                    await update.message.reply_text(f"Flood wait {f.seconds}s")
                    await asyncio.sleep(f.seconds)
                except Exception as e:
                    await update.message.reply_text(f"Skip {user.id} error: {e}")
            index += BATCH_SIZE
            await client.disconnect()
            if index >= len(users):
                break
        except Exception as e:
            await update.message.reply_text(f"{acc['phone']} error: {e}")
            await client.disconnect()

# --- Start Bot ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/login "), handle_login))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("addmembers", add_members))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()

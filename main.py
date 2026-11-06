import logging
import os
import re
import time
from collections import defaultdict
from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from james_universe.db import Database
from james_universe.personality import PRESETS, build_system_prompt
from james_universe.group_intelligence import GroupContext
from james_universe.moderation import inspect_message

load_dotenv()
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                    level=logging.INFO)
log = logging.getLogger("james-universe")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
BOT_NAME = os.getenv("BOT_NAME", "James AI Universe")
AUTO_REPLY = os.getenv("AUTO_REPLY", "false").lower() == "true"
DB_PATH = os.getenv("DATABASE_PATH", "james_universe.db")
MAX_CONTEXT = max(4, min(30, int(os.getenv("MAX_CONTEXT_MESSAGES", "16"))))
XP_COOLDOWN_SECONDS = 60

if not TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN. Configure your .env file.")
if not API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY. Configure your .env file.")

ai = AsyncOpenAI(api_key=API_KEY)
db = Database(DB_PATH)
memory = GroupContext(MAX_CONTEXT)
last_xp = {}

def display_name(user):
    return user.full_name or user.username or str(user.id)

async def is_group_admin(update, context):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return True
    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in ("administrator", "creator")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == ChatType.PRIVATE:
        me = await context.bot.get_me()
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("➕ Add James to a group",
                                 url=f"https://t.me/{me.username}?startgroup=true")
        ]])
        await update.effective_message.reply_text(
            f"⚡ Welcome to {BOT_NAME}!\\n\\n"
            "I'm your AI-powered group companion. Add me to your Telegram group, "
            "then mention me or reply to one of my messages to chat.\\n\\n"
            "✨ AI conversations\\n🎭 Group personalities\\n🧠 Short-term group context\\n"
            "🛡️ Optional Guardian moderation\\n🏆 XP and leaderboards\\n\\n"
            "Use /help to explore commands.",
            reply_markup=keyboard
        )
    else:
        await update.effective_message.reply_text(
            f"⚡ {BOT_NAME} is online! Mention me or reply to my message to chat. "
            "Use /help for commands."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "⚡ James AI Universe\\n"
        "/ask <question> — ask the AI\\n/profile — your XP and level\\n"
        "/leaderboard — top members\\n/personality — show or set group personality\\n"
        "/guardian — show or toggle spam protection (admins only)\\n/help — commands\\n\\n"
        "Personal chat: use the Add me to a group button. In groups, mention me or reply to me."
    )

async def make_ai_reply(chat_id, group_title, question):
    settings = db.get_settings(chat_id)
    messages = [{"role": "system",
                 "content": build_system_prompt(group_title, settings["personality"])}]
    messages.extend(memory.prompt_messages(chat_id))
    messages.append({"role": "user", "content": question[:3000]})
    response = await ai.chat.completions.create(
        model=MODEL, messages=messages, temperature=0.8, max_tokens=350)
    answer = response.choices[0].message.content or "I couldn't think of a reply just now."
    memory.add_assistant(chat_id, answer)
    return answer[:4000]

async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = " ".join(context.args).strip()
    if not question:
        await update.effective_message.reply_text("Usage: /ask <your question>")
        return
    chat = update.effective_chat
    msg = await update.effective_message.reply_text("🧠 Thinking...")
    try:
        answer = await make_ai_reply(chat.id, chat.title or "Private chat", question)
        await msg.edit_text(answer)
    except Exception:
        log.exception("AI request failed")
        await msg.edit_text("⚠️ I couldn't reach the AI service. Please try again.")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, chat = update.effective_user, update.effective_chat
    xp = db.get_xp(chat.id, user.id)
    await update.effective_message.reply_text(
        f"👤 {display_name(user)}\\n⭐ XP: {xp}\\n🏅 Level: {1 + xp // 100}")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.leaderboard(update.effective_chat.id, 10)
    if not rows:
        await update.effective_message.reply_text("No leaderboard data yet. Start chatting!")
        return
    lines = ["🏆 Group leaderboard"]
    lines.extend(f"{i}. {name} — {xp} XP" for i, (name, xp) in enumerate(rows, 1))
    await update.effective_message.reply_text("\\n".join(lines))

async def personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    settings = db.get_settings(chat.id)
    if not context.args:
        names = ", ".join(PRESETS.keys())
        await update.effective_message.reply_text(
            f"Current personality: {settings['personality']}\\nAvailable: {names}\\n"
            "Set with /personality james (admins only).")
        return
    selected = context.args[0].lower()
    if selected not in PRESETS:
        await update.effective_message.reply_text("Unknown personality. Choose: " + ", ".join(PRESETS))
        return
    if not await is_group_admin(update, context):
        await update.effective_message.reply_text("Only group admins can change the personality.")
        return
    db.set_personality(chat.id, selected)
    await update.effective_message.reply_text(f"🎭 Personality changed to {selected}.")

async def guardian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    settings = db.get_settings(chat.id)
    if not context.args:
        status = "ON" if settings["guardian"] else "OFF"
        await update.effective_message.reply_text(
            f"🛡️ Guardian is {status}.\\nAdmins can use /guardian on or /guardian off.")
        return
    if not await is_group_admin(update, context):
        await update.effective_message.reply_text("Only group admins can change Guardian.")
        return
    value = context.args[0].lower()
    if value not in ("on", "off"):
        await update.effective_message.reply_text("Usage: /guardian on or /guardian off")
        return
    db.set_guardian(chat.id, value == "on")
    await update.effective_message.reply_text(
        "🛡️ Guardian enabled. Likely spam may be deleted when I have delete permissions."
        if value == "on" else "Guardian disabled.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if not msg or not user or user.is_bot or not msg.text:
        return

    # XP is awarded at most once per user per chat every 60 seconds.
    key, now = (chat.id, user.id), time.time()
    if now - last_xp.get(key, 0) >= XP_COOLDOWN_SECONDS:
        db.add_xp(chat.id, user.id, display_name(user), 5)
        last_xp[key] = now

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    settings = db.get_settings(chat.id)
    if settings["guardian"]:
        spam, reason = inspect_message(chat.id, user.id, msg.text)
        if spam:
            try:
                await msg.delete()
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=f"🛡️ Guardian removed a likely spam message ({reason}).")
                return
            except Exception:
                log.warning("Guardian detected spam but could not delete; check bot admin permissions.")

    me = await context.bot.get_me()
    addressed = bool(re.search(rf"@{re.escape(me.username or '')}\\b", msg.text, re.I))
    if msg.reply_to_message and msg.reply_to_message.from_user:
        addressed = addressed or msg.reply_to_message.from_user.id == me.id

    # Build short-lived group context from messages seen by the bot.
    memory.add(chat.id, display_name(user), msg.text)
    if not addressed and not AUTO_REPLY:
        return

    cleaned = re.sub(rf"@{re.escape(me.username or '')}\\b", "", msg.text, flags=re.I).strip()
    if not cleaned:
        cleaned = "Please respond to the conversation."
    try:
        answer = await make_ai_reply(chat.id, chat.title or "Telegram group",
                                     f"{display_name(user)} says: {cleaned}")
        await msg.reply_text(answer, reply_to_message_id=msg.message_id)
    except Exception:
        log.exception("AI reply failed")
        await msg.reply_text("⚠️ My AI connection is having trouble. Try again shortly.")

async def on_error(update, context):
    log.error("Unhandled Telegram error", exc_info=context.error)

def main():
    db.initialize()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ask", ask))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("personality", personality))
    app.add_handler(CommandHandler("guardian", guardian))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(on_error)
    log.info("%s starting with model %s", BOT_NAME, MODEL)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

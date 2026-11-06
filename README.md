# James AI Universe — Telegram Bot

Python Telegram bot starter with an AI chat engine, per-group personalities, short-lived group context, opt-in Guardian spam checks, and XP/leaderboards.

## Features
- `/start` in private chat shows a welcome message and **Add me to a group** button.
- AI replies when mentioned or when someone replies to its message.
- `/ask <question>`, `/help`, `/profile`, `/leaderboard`.
- `/personality` displays the current preset; admins can use `/personality james|chill|hype|professor|professional`.
- `/guardian` shows status; admins can use `/guardian on` or `/guardian off`.
- Guardian uses conservative heuristics and attempts to delete likely spam only when enabled and the bot has Telegram delete permissions.
- XP and group settings are stored in SQLite. Recent group context is held in RAM only.

## Setup
1. Create a bot with Telegram **@BotFather** using `/newbot`.
2. Copy `.env.example` to `.env`.
3. Put your Telegram bot token and OpenAI API key in `.env`.
4. Install Python 3.10+ dependencies and run:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS/Termux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Telegram setup
- Add the bot to your group. Mention it or reply to one of its messages to chat.
- To let it see all ordinary group messages, adjust BotFather privacy mode and inform members. `AUTO_REPLY=true` also opts into replying to every message the bot receives; use cautiously.
- For Guardian deletion, promote it with **Delete messages** permission. Start with Guardian OFF and test in a small group.

## Privacy and security
- Keep `.env` private. Never publish bot tokens or API keys.
- The bot is transparent that it is an AI.
- Recent group context is in-memory and is not saved to the database. Messages sent to the AI are processed by the configured AI provider.
- Guardian is heuristic and can make mistakes. Keep it disabled until you are comfortable with its behavior.
- Add consent, rate limits, logging controls, and user data deletion before production use.

## Structure
- `main.py` — Telegram handlers and app startup
- `james_universe/personality.py` — group personality presets
- `james_universe/group_intelligence.py` — short-term context
- `james_universe/moderation.py` — conservative spam detection
- `james_universe/db.py` — SQLite persistence

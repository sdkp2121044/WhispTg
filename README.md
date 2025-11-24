# 🤫 ShriBots Whisper Bot

A Telegram bot for sending anonymous secret messages that only the intended recipient can read.

## Features
- 🔒 Anonymous secret messages
- 🚀 Inline mode support  
- 🤖 Bot cloning system
- 📊 Admin statistics
- 💾 Persistent data storage

## Deployment on Render

1. Fork this repository
2. Go to [Render.com](https://render.com)
3. Create new Web Service
4. Connect your GitHub repo
5. Use these settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
6. Add environment variables in Render dashboard

## Environment Variables
- `API_ID` - Your Telegram API ID
- `API_HASH` - Your Telegram API Hash  
- `BOT_TOKEN` - Your bot token from @BotFather
- `ADMIN_ID` - Your Telegram user ID

## Commands
- `/start` - Start the bot
- `/help` - Show help guide
- `/clone` - Clone your own bot
- `/mybots` - View your cloned bots
- `/remove` - Remove your bots

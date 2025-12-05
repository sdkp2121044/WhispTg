import os
import logging
import asyncio
from datetime import datetime
from flask import Flask, jsonify
from telethon import TelegramClient, events, Button

# Configure logging for Render
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables - Render provides these
API_ID = int(os.getenv('API_ID', '25136703'))
API_HASH = os.getenv('API_HASH', 'accfaf5ecd981c67e481328515c39f89')
BOT_TOKEN = os.getenv('BOT_TOKEN', '8366493122:AAG7nl7a3BqXd8-oyTAHovAjc7UUuLeHb-4')
ADMIN_ID = int(os.getenv('ADMIN_ID', '8027090675'))
PORT = int(os.environ.get('PORT', 10000))

# Import handlers
from handlers.whisper_handler import WhisperHandler
from handlers.user_manager import UserManager
from handlers.callback_handler import CallbackHandler

# Initialize Flask app for Render web service
app = Flask(__name__)

# Initialize bot
try:
    bot = TelegramClient('whisper_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    logger.info("✅ Bot client initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize bot: {e}")
    raise

# Initialize handlers
whisper_handler = WhisperHandler(bot)
user_manager = UserManager()
callback_handler = CallbackHandler(bot, user_manager)

# Load data
user_manager.load_data()

# WELCOME TEXT
WELCOME_TEXT = """
╔══════════════════════╗
║     🎭 𝗦𝗛𝗥𝗜𝗕𝗢𝗧𝗦     ║ 𝐏𝐨𝐰𝐞𝐫𝐞𝐝 𝐛𝐲
║    𝗪𝗛𝗜𝗦𝗣𝗘𝗥 𝗕𝗢𝗧    ║      𝐀𝐫𝐭𝐢𝐬𝐭
╚══════════════════════╝

🤫 Welcome to Secret Whisper Bot!

🔒 Send anonymous secret messages
🚀 Only intended recipient can read
🎯 Easy to use inline mode

Create whispers that only specific users can unlock!

**Usage:** `@bot_username message @username`
**Example:** `@bot_username Hello! @shribots`
**OR:** `@bot_username Hello! 123456789`
"""

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        logger.info(f"🚀 Start command from user: {event.sender_id}")
        
        await event.reply(
            WELCOME_TEXT,
            buttons=[
                [Button.switch_inline("🚀 Send Whisper", query="")],
                [Button.inline("📖 Help", data="help")]
            ]
        )
    except Exception as e:
        logger.error(f"Start error: {e}")
        await event.reply("❌ An error occurred. Please try again.")

@bot.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    try:
        bot_username = (await bot.get_me()).username
        help_text = f"""
📖 **How to Use Whisper Bot**

**Usage:**
`@{bot_username} message @username`
`@{bot_username} message 123456789`

**Examples:**
• `@{bot_username} Hello! @shribots`
• `@{bot_username} I miss you 123456789`

**Features:**
• Send anonymous messages
• Only recipient can read
• Quick recent user selection
• Works with username or user ID

**Recent Users:**
Last 10 users will be shown for quick sending.

🔒 **Only the mentioned user can read your message!**
"""
        
        await event.reply(
            help_text,
            buttons=[
                [Button.switch_inline("🚀 Try Now", query="")],
                [Button.inline("🔙 Back", data="back_start")]
            ]
        )
    except Exception as e:
        logger.error(f"Help error: {e}")
        await event.reply("❌ An error occurred. Please try again.")

# Register inline handler
@bot.on(events.InlineQuery)
async def inline_handler(event):
    await whisper_handler.handle_inline_query(event)

# Register callback handler
@bot.on(events.CallbackQuery)
async def callback_handler(event):
    await callback_handler.handle_callback(event)

# Flask routes for Render health checks
@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "service": "ShriBots Whisper Bot",
        "timestamp": datetime.now().isoformat(),
        "recent_users": len(user_manager.recent_users),
        "total_messages": len(whisper_handler.messages_db)
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "bot_connected": bot.is_connected(),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/ping')
def ping():
    return "pong"

async def main():
    """Main function to start the bot"""
    try:
        me = await bot.get_me()
        logger.info(f"🎭 ShriBots Whisper Bot Started on Render!")
        logger.info(f"🤖 Bot: @{me.username}")
        logger.info(f"🆔 Bot ID: {me.id}")
        logger.info(f"👑 Admin: {ADMIN_ID}")
        logger.info(f"🌐 Port: {PORT}")
        logger.info(f"👥 Recent Users: {len(user_manager.recent_users)}")
        logger.info("✅ Bot is ready and working!")
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

def run_flask():
    """Run Flask web server for Render"""
    logger.info(f"🌐 Starting Flask server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

def run_bot():
    """Run the Telegram bot"""
    print("🚀 Starting ShriBots Whisper Bot on Render...")
    print(f"📝 Environment: API_ID={API_ID}, PORT={PORT}")
    
    try:
        # Start the bot
        bot.start()
        
        # Run main function
        bot.loop.run_until_complete(main())
        
        print("✅ Bot started successfully!")
        print("🔄 Bot is now running...")
        
        # Keep the bot running
        bot.run_until_disconnected()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        print(f"❌ Error: {e}")
    finally:
        print("💾 Saving data before exit...")
        user_manager.save_data()

if __name__ == '__main__':
    # For Render, we need to handle both web and worker
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'web':
        # Run as web service
        run_flask()
    else:
        # Run as worker (bot)
        run_bot()

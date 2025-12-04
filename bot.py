# bot.py
import os
import logging
import asyncio
from telethon import TelegramClient

# Import from other files
from config import API_ID, API_HASH, BOT_TOKEN, PORT
from database import load_data, save_data
from handlers import setup_handlers
from web_server import start_web_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot
try:
    bot = TelegramClient('whisper_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    logger.info("✅ Bot client initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize bot: {e}")
    raise

async def main():
    """Main function to start the bot"""
    try:
        # Load data
        load_data()
        
        # Setup handlers
        setup_handlers(bot)
        
        # Get bot info
        me = await bot.get_me()
        
        from database import user_whisper_history, messages_db, user_entity_cache
        total_history_entries = sum(len(v) for v in user_whisper_history.values())
        
        logger.info(f"🎭 ShriBots Whisper Bot v4.0 Started!")
        logger.info(f"🤖 Bot: @{me.username}")
        logger.info(f"🆔 Bot ID: {me.id}")
        logger.info(f"👥 Total Users: {len(user_whisper_history)}")
        logger.info(f"💬 Total Messages: {len(messages_db)}")
        logger.info(f"📚 Total History Entries: {total_history_entries}")
        logger.info(f"🌐 Web server running on port {PORT}")
        logger.info("📚 Complete History Tracking: ACTIVE")
        logger.info("✨ ALL past recipients remembered!")
        logger.info("✅ Bot is ready and working!")
        logger.info("🔗 Use /start to begin")
        
        print("\n" + "="*60)
        print("📚 COMPLETE HISTORY TRACKING FEATURES:")
        print("   • Remembers ALL past whispers")
        print("   • Stores EVERY username/userID ever used")
        print("   • Shows ALL recipients when typing @bot_username")
        print("   • Personal statistics for each user")
        print("="*60)
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Starting ShriBots Whisper Bot v4.0")
    print("📚 With COMPLETE HISTORY TRACKING")
    print("=" * 60)
    
    # Check environment variables
    required_vars = ['API_ID', 'API_HASH', 'BOT_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("⚠️  Please set these in Render environment variables")
        exit(1)
    
    print(f"📝 Environment: API_ID={API_ID}, PORT={PORT}")
    print("🔄 Starting bot...")
    
    try:
        # Start web server
        start_web_server()
        
        # Start the bot
        bot.start()
        bot.loop.run_until_complete(main())
        
        print("=" * 60)
        print("✅ Bot started successfully!")
        print("💡 Key Features:")
        print("   1. Remembers ALL your past whispers")
        print("   2. Shows ALL recipients when you type @bot_username")
        print("   3. Every username/userID is saved forever")
        print("   4. Personal stats with /stats command")
        print("=" * 60)
        print("🔄 Bot is now running...")
        print(f"🌐 Web Dashboard: http://localhost:{PORT}")
        
        # Keep the bot running
        bot.run_until_disconnected()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        print(f"❌ Error: {e}")
    finally:
        print("💾 Saving data before exit...")
        save_data()

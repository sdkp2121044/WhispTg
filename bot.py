# main.py
import os
import asyncio
import logging
import sys
import signal
from datetime import datetime

from telethon import TelegramClient

from config import API_ID, API_HASH, BOT_TOKEN, logger, BOT_NAME
from database import init_database, message_manager
from handlers import setup_handlers
from web_server import start_web_server
from utils import cooldown_manager

# ======================
# BOT INITIALIZATION
# ======================
class WhisperBot:
    def __init__(self):
        self.bot = None
        self.is_running = False
        self.start_time = None
        
    async def initialize(self):
        """Initialize the bot"""
        try:
            logger.info("🚀 Initializing Whisper Bot...")
            
            # Initialize database
            init_database()
            logger.info("✅ Database initialized")
            
            # Initialize bot client
            self.bot = TelegramClient('whisper_bot', API_ID, API_HASH)
            await self.bot.start(bot_token=BOT_TOKEN)
            logger.info("✅ Bot client started")
            
            # Setup handlers
            setup_handlers(self.bot)
            logger.info("✅ Handlers configured")
            
            # Start web server
            web_server_thread = start_web_server()
            if web_server_thread:
                logger.info("✅ Web server started")
            
            self.start_time = datetime.now()
            self.is_running = True
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            return False
    
    async def get_bot_info(self):
        """Get bot information"""
        try:
            me = await self.bot.get_me()
            return {
                'username': me.username,
                'id': me.id,
                'name': me.first_name,
                'is_bot': me.bot
            }
        except Exception as e:
            logger.error(f"Error getting bot info: {e}")
            return None
    
    async def print_startup_info(self):
        """Print startup information"""
        print("\n" + "="*60)
        print(f"🤫 {BOT_NAME}")
        print("="*60)
        
        bot_info = await self.get_bot_info()
        if bot_info:
            print(f"🔹 Bot: @{bot_info['username']}")
            print(f"🔹 ID: {bot_info['id']}")
        
        print(f"🔹 Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔹 API ID: {API_ID}")
        print("="*60)
        print("✨ Features Active:")
        print("   • Instant User Detection (ANY format)")
        print("   • Complete History Tracking")
        print("   • All Past Recipients Show")
        print("   • Smart Auto-Suggest")
        print("   • Multi-Format Support")
        print("="*60)
        print("📱 Usage: Type @bot_username in any Telegram chat")
        print("="*60)
        print("\n🔄 Bot is running... (Press Ctrl+C to stop)\n")
    
    async def cleanup(self):
        """Cleanup before shutdown"""
        try:
            logger.info("🧹 Starting cleanup...")
            
            # Cleanup expired messages
            message_manager.cleanup_expired()
            
            # Clear cooldown cache
            cooldown_manager.clear_old()
            
            # Disconnect bot
            if self.bot and self.bot.is_connected():
                await self.bot.disconnect()
                logger.info("✅ Bot disconnected")
            
            self.is_running = False
            logger.info("✅ Cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")
    
    async def run(self):
        """Main bot running loop"""
        try:
            # Initialize
            success = await self.initialize()
            if not success:
                logger.error("❌ Failed to initialize bot")
                return
            
            # Print startup info
            await self.print_startup_info()
            
            # Set up signal handlers
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(self.shutdown())
                )
            
            # Keep bot running
            await self.bot.run_until_disconnected()
            
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Bot runtime error: {e}")
        finally:
            await self.cleanup()
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🔻 Shutdown initiated...")
        await self.cleanup()
        sys.exit(0)

# ======================
# MAIN ENTRY POINT
# ======================
async def main():
    """Main entry point"""
    bot = WhisperBot()
    await bot.run()

if __name__ == '__main__':
    # Check environment variables
    required_vars = ['API_ID', 'API_HASH', 'BOT_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("💡 Set them with:")
        print("   export API_ID=your_api_id")
        print("   export API_HASH=your_api_hash")
        print("   export BOT_TOKEN=your_bot_token")
        sys.exit(1)
    
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

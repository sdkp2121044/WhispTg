# config.py
import os

# Environment variables
API_ID = int(os.getenv('API_ID', ''))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_ID = int(os.getenv('ADMIN_ID', ''))
PORT = int(os.environ.get('PORT', 10000))

# Bot configuration
BOT_NAME = "ShriBots Whisper Bot"
SUPPORT_CHANNEL = "shribots"
SUPPORT_GROUP = "idxhelp"

# Data files
DATA_DIR = "data"
WHISPER_HISTORY_FILE = os.path.join(DATA_DIR, "whisper_history.json")
RECENT_RECIPIENTS_FILE = os.path.join(DATA_DIR, "recent_recipients.json")

# Text messages
WELCOME_TEXT = """
╔══════════════════════╗
║     🎭 𝗦𝗛𝗥𝗜𝗕𝗢𝗧𝗦     ║ 𝐏𝐨𝐰𝐞𝐫𝐞𝐝 𝐛𝐲
║    𝗪𝗛𝗜𝗦𝗣𝗘𝗥 𝗕𝗢𝗧    ║      𝐀𝐫𝐭𝐢𝐬𝐭
╚══════════════════════╝

🤫 Welcome to Secret Whisper Bot!

🔒 Send anonymous secret messages
🚀 Only intended recipient can read
🎯 Easy to use inline mode

✨ **SMART FEATURES:**
• Complete whisper history tracking
• All past usernames automatic suggestions
• Real-time detection while typing
• Auto-suggest last recipient

📊 **Your Stats:** {stats}
"""

HELP_TEXT = """
📖 **How to Use Whisper Bot**

**1. Basic Usage:**
   • Type `@{}` in any chat
   • Write your message  
   • Add @username OR user ID
   • Send!

**2. Smart History:**
   • Bot remembers ALL your past whispers
   • Type `@{} ` (with space) to see ALL past recipients
   • Click any to send again quickly

**3. Auto-Detection:**
   • Type `@{} how are you 123456789`
   • Bot auto-detects the user ID
   • No special format needed!

**4. View Your History:**
   • `/history` - See all your whispers
   • `/stats` - Your personal statistics
   • `/recent` - Recent recipients only

**5. Commands:**
   • /start - Start bot
   • /help - Show help
   • /history - Complete whisper history
   • /recent - Recent recipients
   • /clear - Clear your history
   • /stats - Your statistics

🔒 **Only the mentioned user can read your message!**
📚 **Bot remembers ALL your past whispers!**
"""

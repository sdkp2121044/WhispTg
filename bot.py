import os
import logging
import re
import asyncio
import json
from datetime import datetime, timedelta
from flask import Flask, render_template_string
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables - Render पर इन्हें set करना होगा
API_ID = int(os.getenv('API_ID', ''))  # Render में जरूर set करें
API_HASH = os.getenv('API_HASH', '')   # Render में जरूर set करें
BOT_TOKEN = os.getenv('BOT_TOKEN', '') # Render में जरूर set करें
ADMIN_ID = int(os.getenv('ADMIN_ID', ''))
PORT = int(os.environ.get('PORT', 10000))

# Import Telethon
try:
    from telethon import TelegramClient, events, Button
    from telethon.errors import SessionPasswordNeededError
except ImportError as e:
    logger.error(f"Telethon import error: {e}")
    raise

# Support channels
SUPPORT_CHANNEL = "shribots"
SUPPORT_GROUP = "idxhelp"

# Initialize bot
try:
    bot = TelegramClient('whisper_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    logger.info("✅ Bot client initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize bot: {e}")
    raise

# Storage for messages
messages_db = {}
# User's last recipient history (for auto-suggest)
user_history = {}
# Cooldown for spam prevention
user_cooldown = {}

# Data files
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
USER_HISTORY_FILE = os.path.join(DATA_DIR, "user_history.json")

def load_data():
    """Load user history from file"""
    global user_history
    try:
        if os.path.exists(USER_HISTORY_FILE):
            with open(USER_HISTORY_FILE, 'r', encoding='utf-8') as f:
                user_history = json.load(f)
            logger.info(f"✅ Loaded history for {len(user_history)} users")
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        user_history = {}

def save_data():
    """Save user history to file"""
    try:
        with open(USER_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"❌ Error saving data: {e}")

# Load data on startup
load_data()

WELCOME_TEXT = """
╔══════════════════════╗
║     🎭 𝗦𝗛𝗥𝗜𝗕𝗢𝗧𝗦     ║ 𝐏𝐨𝐰𝐞𝐫𝐞𝐝 𝐛𝐲
║    𝗪𝗛𝗜𝗦𝗣𝗘𝗥 𝗕𝗢𝗧    ║      𝐀𝐫𝐭𝐢𝐬𝐭
╚══════════════════════╝

🤫 Welcome to Secret Whisper Bot!

🔒 Send anonymous secret messages
🚀 Only intended recipient can read
🎯 Easy to use inline mode

✨ **NEW**: Auto-suggest last recipient!
Send whisper to same person again without typing ID!

Create whispers that only specific users can unlock!
"""

HELP_TEXT = """
📖 **How to Use Whisper Bot**

**1. Inline Mode (Basic):**
   • Type `@{}` in any chat
   • Write your message  
   • Add @username OR user ID at end
   • Send!

**2. Inline Mode (Auto-Suggest):**
   • Type `@{}` in any chat
   • Just type your message
   • Last recipient will be auto-selected!
   • Send!

**3. Examples:**
   • `@{} Hello! @username` (First time)
   • `@{} How are you?` (Auto to last person)
   • `@{} I miss you 123456789`

**4. Commands:**
   • /start - Start bot
   • /help - Show help
   • /clear - Clear your last recipient
   • /stats - Admin statistics

🔒 **Only the mentioned user can read your message!**
✨ **Auto-suggest remembers your last recipient!**
"""

def update_user_history(user_id, target_user_id, target_username=None, target_name=None):
    """Update user's last recipient history"""
    try:
        user_id_str = str(user_id)
        if user_id_str not in user_history:
            user_history[user_id_str] = []
        
        # Check if target already in history
        for item in user_history[user_id_str]:
            if item.get('id') == target_user_id:
                # Update timestamp
                item['timestamp'] = datetime.now().isoformat()
                save_data()
                return
        
        # Add new entry
        history_entry = {
            'id': target_user_id,
            'username': target_username,
            'name': target_name,
            'timestamp': datetime.now().isoformat()
        }
        
        user_history[user_id_str].insert(0, history_entry)
        
        # Keep only last 5 recipients
        if len(user_history[user_id_str]) > 5:
            user_history[user_id_str] = user_history[user_id_str][:5]
        
        save_data()
    except Exception as e:
        logger.error(f"Error updating user history: {e}")

def get_last_recipient(user_id):
    """Get user's last recipient"""
    try:
        user_id_str = str(user_id)
        if user_id_str in user_history and user_history[user_id_str]:
            return user_history[user_id_str][0]
    except Exception as e:
        logger.error(f"Error getting last recipient: {e}")
    return None

def is_cooldown(user_id):
    """Check if user is in cooldown"""
    now = datetime.now().timestamp()
    user_id_str = str(user_id)
    
    if user_id_str in user_cooldown:
        if now - user_cooldown[user_id_str] < 3:  # 3 seconds cooldown
            return True
    
    user_cooldown[user_id_str] = now
    return False

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        logger.info(f"🚀 Start command from user: {event.sender_id}")
        
        # Check if user has history
        last_recipient = get_last_recipient(event.sender_id)
        
        if last_recipient:
            last_user_text = f"\n\n📝 **Last Recipient:** {last_recipient.get('name', 'User')}"
            if last_recipient.get('username'):
                last_user_text += f" (@{last_recipient['username']})"
        else:
            last_user_text = "\n\n📝 **No recent recipients yet**"
        
        welcome_with_history = WELCOME_TEXT + last_user_text
        
        buttons = [
            [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
            [Button.url("👥 Group", f"https://t.me/{SUPPORT_GROUP}")],
            [Button.switch_inline("🚀 Try Now", query="")],
            [Button.inline("📖 Help", data="help"), Button.inline("🗑️ Clear History", data="clear_history")]
        ]
        
        if event.sender_id == ADMIN_ID:
            buttons.append([Button.inline("📊 Statistics", data="admin_stats")])
        
        await event.reply(welcome_with_history, buttons=buttons)
        
    except Exception as e:
        logger.error(f"Start error: {e}")
        await event.reply("❌ An error occurred. Please try again.")

@bot.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    try:
        bot_username = (await bot.get_me()).username
        help_text = HELP_TEXT.format(bot_username, bot_username, bot_username)
        
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

@bot.on(events.NewMessage(pattern='/clear'))
async def clear_handler(event):
    """Clear user's recipient history"""
    try:
        user_id_str = str(event.sender_id)
        if user_id_str in user_history:
            del user_history[user_id_str]
            save_data()
            await event.reply("✅ Your recipient history has been cleared!")
        else:
            await event.reply("ℹ️ You have no history to clear.")
    except Exception as e:
        logger.error(f"Clear error: {e}")
        await event.reply("❌ Error clearing history.")

@bot.on(events.NewMessage(pattern='/stats'))
async def stats_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
        
    try:
        total_users = len(user_history)
        total_messages = len(messages_db)
        
        # Count active users (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        active_users = 0
        
        for user_data in user_history.values():
            if user_data:
                last_time = datetime.fromisoformat(user_data[0]['timestamp'])
                if last_time > week_ago:
                    active_users += 1
        
        stats_text = f"""
📊 **Admin Statistics**

👥 Total Users: {total_users}
📈 Active Users (7 days): {active_users}
💬 Total Messages: {total_messages}
🆔 Admin ID: {ADMIN_ID}
🌐 Port: {PORT}

**Bot Status:** ✅ Running
**Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
        """
        
        await event.reply(stats_text)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await event.reply("❌ Error fetching statistics.")

@bot.on(events.InlineQuery)
async def inline_handler(event):
    """Handle inline queries with auto-suggest feature"""
    try:
        if is_cooldown(event.sender_id):
            await event.answer([])
            return

        # Check if user has history
        last_recipient = get_last_recipient(event.sender_id)
        
        # If no text provided, show help
        if not event.text or not event.text.strip():
            if last_recipient:
                # Auto-suggest last recipient
                target_name = last_recipient.get('name', 'User')
                result = event.builder.article(
                    title=f"🤫 Send to {target_name} (Auto-suggest)",
                    description=f"Just type your message for {target_name}",
                    text=f"**Auto-suggest Active!**\n\nType your message below to send to **{target_name}** automatically!\n\nOr mention @username / user ID for someone else.",
                    buttons=[
                        [Button.switch_inline(f"💌 Message {target_name}", query="")],
                        [Button.inline("❌ Clear Auto-suggest", data="clear_auto")]
                    ]
                )
            else:
                result = event.builder.article(
                    title="🤫 Whisper Bot - Send Secret Messages",
                    description="Usage: message @username OR just message",
                    text="**Send Secret Messages!**\n\n**Format:** `your_message @username`\n\n**Auto-suggest:** After first use, just type message!\n\n🔒 Only they can read!",
                    buttons=[[Button.switch_inline("🚀 Try Now", query="")]]
                )
            await event.answer([result])
            return
        
        text = event.text.strip()
        sender_id = event.sender_id
        
        # Try to extract target user from message
        patterns = [
            r'@(\w+)$',      # @username at end
            r'(\d+)$',       # user ID at end
            r'to @(\w+):?\s*(.*)',  # "to @username: message"
            r'to (\d+):?\s*(.*)'    # "to userid: message"
        ]
        
        target_user = None
        message_text = text
        explicit_target = False
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if pattern in [r'@(\w+)$', r'(\d+)$']:
                    # Simple format: message @username
                    target_user = match.group(1)
                    message_text = text.replace(f"@{target_user}", "").replace(target_user, "").strip()
                    explicit_target = True
                else:
                    # "to @username: message" format
                    target_user = match.group(1)
                    message_text = match.group(2).strip() if match.group(2) else ""
                    explicit_target = True
                break
        
        # If no explicit target, try auto-suggest
        if not explicit_target and last_recipient:
            target_user = last_recipient['id']
            message_text = text  # Use entire text as message
            auto_suggested = True
        elif not explicit_target:
            # No target found and no history
            result = event.builder.article(
                title="❌ No recipient specified",
                description="Mention @username or user ID",
                text="**Please specify a recipient!**\n\n**Format:** `message @username`\n**Or:** `message 123456789`\n\nFirst time needs explicit mention, then auto-suggest works!",
                buttons=[[Button.switch_inline("🔄 Try Again", query=text)]]
            )
            await event.answer([result])
            return
        else:
            auto_suggested = False
        
        # Validate message
        if not message_text or len(message_text) > 1000:
            result = event.builder.article(
                title="❌ Invalid Message",
                description="Message empty or too long",
                text="❌ Please enter a valid message (1-1000 characters)."
            )
            await event.answer([result])
            return
        
        # Get user entity
        try:
            if isinstance(target_user, int) or (isinstance(target_user, str) and target_user.isdigit()):
                user_obj = await bot.get_entity(int(target_user))
            else:
                # Validate username format
                if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', target_user):
                    result = event.builder.article(
                        title="❌ Invalid Username",
                        description="Username format is invalid",
                        text="**Valid username format:**\n• Starts with letter\n• 4-31 characters\n• Letters, numbers, underscores only"
                    )
                    await event.answer([result])
                    return
                
                user_obj = await bot.get_entity(target_user)
            
            # Check if it's a user
            if not hasattr(user_obj, 'first_name'):
                result = event.builder.article(
                    title="❌ Not a User",
                    description="You can only send to users",
                    text="This appears to be a channel or group. Please mention a user instead."
                )
                await event.answer([result])
                return
            
        except Exception as e:
            logger.error(f"Error getting user entity: {e}")
            result = event.builder.article(
                title="❌ User Not Found",
                description="User not found or invalid",
                text="❌ User not found! Please check username or user ID."
            )
            await event.answer([result])
            return
        
        # Update user history for auto-suggest
        update_user_history(
            sender_id,
            user_obj.id,
            getattr(user_obj, 'username', None),
            getattr(user_obj, 'first_name', 'User')
        )
        
        # Create message entry
        message_id = f'msg_{sender_id}_{user_obj.id}_{int(datetime.now().timestamp())}'
        messages_db[message_id] = {
            'user_id': user_obj.id,
            'msg': message_text,
            'sender_id': sender_id,
            'timestamp': datetime.now().isoformat(),
            'target_name': getattr(user_obj, 'first_name', 'User'),
            'auto_suggested': auto_suggested
        }
        
        # Create result
        target_name = getattr(user_obj, 'first_name', 'User')
        if auto_suggested:
            description = f"Auto-sent to {target_name}"
            title = f"🔒 Auto to {target_name}"
        else:
            description = f"Click to send to {target_name}"
            title = f"🔒 For {target_name}"
        
        result_text = f"**🔐 A secret message for {target_name}!**"
        if auto_suggested:
            result_text += f"\n\n✨ **Auto-suggest was used!**\nNext time, just type your message!"
        
        result_text += f"\n\n*Only {target_name} can open this message.*"
        
        result = event.builder.article(
            title=title,
            description=description,
            text=result_text,
            buttons=[[Button.inline("🔓 Show Message", message_id)]]
        )
        
        await event.answer([result])
        
    except Exception as e:
        logger.error(f"Inline query error: {e}")
        result = event.builder.article(
            title="❌ Error",
            description="Something went wrong",
            text="❌ An error occurred. Please try again in a moment."
        )
        await event.answer([result])

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    try:
        data = event.data.decode('utf-8')
        
        if data == "help":
            bot_username = (await bot.get_me()).username
            help_text = HELP_TEXT.format(bot_username, bot_username, bot_username)
            
            await event.edit(
                help_text,
                buttons=[
                    [Button.switch_inline("🚀 Try Now", query="")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
        
        elif data == "admin_stats":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
                
            total_users = len(user_history)
            total_messages = len(messages_db)
            
            stats_text = f"📊 **Admin Statistics**\n\n"
            stats_text += f"👥 Total Users: {total_users}\n"
            stats_text += f"💬 Total Messages: {total_messages}\n"
            stats_text += f"🆔 Admin ID: {ADMIN_ID}\n"
            stats_text += f"🌐 Port: {PORT}\n"
            stats_text += f"🕒 Last Updated: {datetime.now().strftime('%H:%M:%S')}\n\n"
            stats_text += f"**Status:** ✅ Running"
            
            await event.edit(
                stats_text,
                buttons=[[Button.inline("🔙 Back", data="back_start")]]
            )
        
        elif data == "clear_history":
            user_id_str = str(event.sender_id)
            if user_id_str in user_history:
                del user_history[user_id_str]
                save_data()
                await event.answer("✅ History cleared!", alert=True)
                await event.edit(
                    "✅ Your recipient history has been cleared!\n\nNext whisper will need explicit @username or ID.",
                    buttons=[[Button.inline("🔙 Back", data="back_start")]]
                )
            else:
                await event.answer("No history to clear!", alert=True)
        
        elif data == "clear_auto":
            user_id_str = str(event.sender_id)
            if user_id_str in user_history:
                # Just remove the first (most recent) entry
                if user_history[user_id_str]:
                    user_history[user_id_str] = user_history[user_id_str][1:]
                    if not user_history[user_id_str]:
                        del user_history[user_id_str]
                    save_data()
                    await event.answer("✅ Auto-suggest cleared!", alert=True)
                    await event.edit(
                        "✅ Auto-suggest cleared!\n\nNext time, mention @username or user ID explicitly.",
                        buttons=[[Button.switch_inline("🚀 Try Now", query="")]]
                    )
                else:
                    await event.answer("No auto-suggest to clear!", alert=True)
            else:
                await event.answer("No history found!", alert=True)
        
        elif data == "back_start":
            # Get updated last recipient info
            last_recipient = get_last_recipient(event.sender_id)
            
            if last_recipient:
                last_user_text = f"\n\n📝 **Last Recipient:** {last_recipient.get('name', 'User')}"
                if last_recipient.get('username'):
                    last_user_text += f" (@{last_recipient['username']})"
            else:
                last_user_text = "\n\n📝 **No recent recipients yet**"
            
            welcome_with_history = WELCOME_TEXT + last_user_text
            
            buttons = [
                [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                [Button.url("👥 Group", f"https://t.me/{SUPPORT_GROUP}")],
                [Button.switch_inline("🚀 Try Now", query="")],
                [Button.inline("📖 Help", data="help"), Button.inline("🗑️ Clear History", data="clear_history")]
            ]
            
            if event.sender_id == ADMIN_ID:
                buttons.append([Button.inline("📊 Statistics", data="admin_stats")])
            
            await event.edit(welcome_with_history, buttons=buttons)
        
        elif data in messages_db:
            msg_data = messages_db[data]
            
            if event.sender_id == msg_data['user_id']:
                # Target user viewing the message
                sender_info = ""
                try:
                    sender = await bot.get_entity(msg_data['sender_id'])
                    sender_name = getattr(sender, 'first_name', 'Someone')
                    sender_info = f"\n\n💌 From: {sender_name}"
                    if hasattr(sender, 'username'):
                        sender_info += f" (@{sender.username})"
                except:
                    sender_info = f"\n\n💌 From: Anonymous"
                
                alert_text = f"🔓 {msg_data['msg']}{sender_info}"
                if msg_data.get('auto_suggested'):
                    alert_text += "\n\n✨ This was sent using auto-suggest!"
                
                await event.answer(alert_text, alert=True)
            
            elif event.sender_id == msg_data['sender_id']:
                # Sender viewing their own message
                alert_text = f"📝 Your message: {msg_data['msg']}\n\n👤 To: {msg_data.get('target_name', 'User')}"
                if msg_data.get('auto_suggested'):
                    alert_text += "\n\n✅ Auto-suggest was used!"
                
                await event.answer(alert_text, alert=True)
            
            else:
                # Someone else trying to view
                await event.answer("🔒 This message is not for you!", alert=True)
        
        else:
            await event.answer("❌ Invalid button!", alert=True)
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await event.answer("❌ An error occurred. Please try again.", alert=True)

# Flask web server for Render
app = Flask(__name__)

@app.route('/')
def home():
    bot_username = "whisper_bot"
    try:
        if bot.is_connected():
            bot_username = bot.loop.run_until_complete(bot.get_me()).username
    except:
        pass
    
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ShriBots Whisper Bot</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                overflow: hidden;
                width: 100%;
                max-width: 800px;
            }
            
            .header {
                background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 15px;
            }
            
            .header p {
                font-size: 1.1rem;
                opacity: 0.9;
            }
            
            .content {
                padding: 40px;
            }
            
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            
            .stat-card {
                background: #f8fafc;
                border-radius: 15px;
                padding: 25px;
                text-align: center;
                border: 2px solid #e2e8f0;
                transition: transform 0.3s, border-color 0.3s;
            }
            
            .stat-card:hover {
                transform: translateY(-5px);
                border-color: #4f46e5;
            }
            
            .stat-value {
                font-size: 2.5rem;
                font-weight: bold;
                color: #4f46e5;
                margin-bottom: 10px;
            }
            
            .stat-label {
                font-size: 1rem;
                color: #64748b;
                font-weight: 500;
            }
            
            .feature-card {
                background: #f1f5f9;
                border-radius: 15px;
                padding: 25px;
                margin-bottom: 20px;
                border-left: 5px solid #4f46e5;
            }
            
            .feature-card h3 {
                color: #334155;
                margin-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .feature-card ul {
                list-style: none;
                padding-left: 0;
            }
            
            .feature-card li {
                padding: 8px 0;
                color: #475569;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .bot-link {
                display: inline-block;
                background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
                color: white;
                text-decoration: none;
                padding: 15px 30px;
                border-radius: 50px;
                font-weight: bold;
                font-size: 1.1rem;
                margin-top: 20px;
                transition: transform 0.3s, box-shadow 0.3s;
            }
            
            .bot-link:hover {
                transform: translateY(-3px);
                box-shadow: 0 10px 25px rgba(79, 70, 229, 0.4);
            }
            
            .status-badge {
                display: inline-block;
                padding: 8px 20px;
                background: #10b981;
                color: white;
                border-radius: 50px;
                font-weight: bold;
                margin-bottom: 20px;
            }
            
            @media (max-width: 768px) {
                .header h1 {
                    font-size: 2rem;
                }
                
                .content {
                    padding: 20px;
                }
                
                .stats-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤫 ShriBots Whisper Bot</h1>
                <p>Send anonymous secret messages on Telegram</p>
            </div>
            
            <div class="content">
                <div class="status-badge">✅ Bot is Running</div>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{{ total_users }}</div>
                        <div class="stat-label">👥 Total Users</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-value">{{ total_messages }}</div>
                        <div class="stat-label">💬 Total Messages</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-value">{{ port }}</div>
                        <div class="stat-label">🌐 Server Port</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-value">{{ time }}</div>
                        <div class="stat-label">🕒 Server Time</div>
                    </div>
                </div>
                
                <div class="feature-card">
                    <h3>✨ Auto-Suggest Feature</h3>
                    <ul>
                        <li>🎯 Send to last recipient automatically</li>
                        <li>🔢 No need to type username/ID again</li>
                        <li>📝 Just type your message and send</li>
                        <li>🔄 First time needs @username, then auto!</li>
                    </ul>
                </div>
                
                <div class="feature-card">
                    <h3>🚀 How to Use</h3>
                    <ul>
                        <li>1. Type @{{ bot_username }} in any chat</li>
                        <li>2. Write your message</li>
                        <li>3. Add @username (first time only)</li>
                        <li>4. Next time: Just type message!</li>
                        <li>5. Only they can read it 🔒</li>
                    </ul>
                </div>
                
                <center>
                    <a href="https://t.me/{{ bot_username }}" class="bot-link" target="_blank">
                        🚀 Start Using Bot
                    </a>
                </center>
            </div>
        </div>
    </body>
    </html>
    """
    
    return render_template_string(
        html_template,
        total_users=len(user_history),
        total_messages=len(messages_db),
        port=PORT,
        time=datetime.now().strftime("%H:%M:%S"),
        bot_username=bot_username
    )

@app.route('/health')
def health():
    return json.dumps({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "total_users": len(user_history),
        "total_messages": len(messages_db),
        "bot_connected": bot.is_connected(),
        "version": "2.0",
        "feature": "whisper_with_auto_suggest"
    })

def run_flask():
    """Run Flask web server"""
    logger.info(f"🌐 Starting Flask server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

# Start Flask in background thread
flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

async def main():
    """Main function to start the bot"""
    try:
        me = await bot.get_me()
        logger.info(f"🎭 ShriBots Whisper Bot Started!")
        logger.info(f"🤖 Bot: @{me.username}")
        logger.info(f"🆔 Bot ID: {me.id}")
        logger.info(f"👑 Admin: {ADMIN_ID}")
        logger.info(f"👥 Total Users: {len(user_history)}")
        logger.info(f"💬 Total Messages: {len(messages_db)}")
        logger.info(f"🌐 Web server running on port {PORT}")
        logger.info("✨ Auto-suggest feature: ACTIVE")
        logger.info("✅ Bot is ready and working!")
        logger.info("🔗 Use /start to begin")
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Starting ShriBots Whisper Bot v2.0")
    print("✨ With Auto-Suggest Feature")
    print("=" * 50)
    
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
        # Start the bot
        bot.start()
        bot.loop.run_until_complete(main())
        
        print("=" * 50)
        print("✅ Bot started successfully!")
        print("✨ Features:")
        print("   • Secret whisper messages")
        print("   • Auto-suggest last recipient")
        print("   • No clone feature (simplified)")
        print("   • Render compatible")
        print("=" * 50)
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
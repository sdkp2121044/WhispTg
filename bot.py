import os
import logging
import re
import asyncio
import json
from datetime import datetime
from flask import Flask
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
API_ID = int(os.getenv('API_ID', '25136703'))
API_HASH = os.getenv('API_HASH', 'accfaf5ecd981c67e481328515c39f89')
BOT_TOKEN = os.getenv('BOT_TOKEN', '8366493122:AAG7nl7a3BqXd8-oyTAHovAjc7UUuLeHb-4')
ADMIN_ID = int(os.getenv('ADMIN_ID', '8027090675'))
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

# Storage
messages_db = {}
recent_users = {}
user_cooldown = {}
user_bots = {}
clone_stats = {}

# Data files
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
RECENT_USERS_FILE = os.path.join(DATA_DIR, "recent_users.json")
CLONE_STATS_FILE = os.path.join(DATA_DIR, "clone_stats.json")

def load_data():
    global recent_users, clone_stats
    try:
        if os.path.exists(RECENT_USERS_FILE):
            with open(RECENT_USERS_FILE, 'r', encoding='utf-8') as f:
                recent_users = json.load(f)
            logger.info(f"✅ Loaded {len(recent_users)} recent users")
        
        if os.path.exists(CLONE_STATS_FILE):
            with open(CLONE_STATS_FILE, 'r', encoding='utf-8') as f:
                clone_stats = json.load(f)
            logger.info(f"✅ Loaded {len(clone_stats)} clone stats")
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        recent_users = {}
        clone_stats = {}

def save_data():
    try:
        with open(RECENT_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(recent_users, f, indent=2, ensure_ascii=False)
        
        with open(CLONE_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(clone_stats, f, indent=2, ensure_ascii=False)
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
🤖 Clone own bot to use @Shribots

Create whispers that only specific users can unlock!
"""

HELP_TEXT = """
📖 **How to Use Whisper Bot**

**1. Inline Mode:**
   • Type `@{}` in any chat
   • Write your message  
   • Add @username OR user ID at end
   • Send!

**2. Examples:**
   • `@{} Hello! @username`
   • `@{} I miss you 123456789`

**3. Commands:**
   • /start - Start bot
   • /help - Show help
   • /stats - Admin statistics
   • /clone - Clone your own bot
   • /remove - Remove your cloned bot

🔒 **Only the mentioned user can read your message!**
"""

def add_to_recent_users(user_id, target_user_id, target_username=None, target_first_name=None):
    """Add user to recent users list"""
    try:
        user_key = str(target_user_id)
        recent_users[user_key] = {
            'user_id': target_user_id,
            'username': target_username,
            'first_name': target_first_name,
            'last_used': datetime.now().isoformat()
        }
        
        # Keep only last 10 users
        if len(recent_users) > 10:
            oldest_key = min(recent_users.keys(), key=lambda k: recent_users[k]['last_used'])
            del recent_users[oldest_key]
        
        save_data()
    except Exception as e:
        logger.error(f"Error adding to recent users: {e}")

def get_recent_users_buttons(user_id):
    """Get recent users buttons for inline suggestions"""
    try:
        if not recent_users:
            return []
        
        sorted_users = sorted(recent_users.items(), 
                            key=lambda x: x[1].get('last_used', ''), 
                            reverse=True)
        
        buttons = []
        for user_key, user_data in sorted_users[:5]:
            username = user_data.get('username')
            first_name = user_data.get('first_name', 'User')
            
            if username:
                display_text = f"@{username}"
            else:
                display_text = f"{first_name}"
            
            if len(display_text) > 15:
                display_text = display_text[:15] + "..."
            
            buttons.append([Button.inline(
                f"🔒 {display_text}", 
                data=f"recent_{user_key}"
            )])
        
        return buttons
    except Exception as e:
        logger.error(f"Error getting recent users: {e}")
        return []

def is_cooldown(user_id):
    """Check if user is in cooldown"""
    now = datetime.now().timestamp()
    if user_id in user_cooldown:
        if now - user_cooldown[user_id] < 5:  # 5 seconds cooldown
            return True
    user_cooldown[user_id] = now
    return False

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        logger.info(f"🚀 Start command from user: {event.sender_id}")
        
        # Welcome message with buttons
        if event.sender_id == ADMIN_ID:
            await event.reply(
                WELCOME_TEXT,
                buttons=[
                    [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                    [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                    [Button.switch_inline("🚀 Try Now", query="")],
                    [Button.inline("📊 Statistics", data="admin_stats"), Button.inline("📖 Help", data="help")],
                    [Button.inline("🔧 Clone Bot", data="clone_info")]
                ]
            )
        else:
            await event.reply(
                WELCOME_TEXT,
                buttons=[
                    [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                    [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                    [Button.switch_inline("🚀 Try Now", query="")],
                    [Button.inline("📖 Help", data="help"), Button.inline("🔧 Clone Bot", data="clone_info")]
                ]
            )
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

@bot.on(events.NewMessage(pattern='/stats'))
async def stats_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
        
    try:
        total_clones = len(clone_stats)
        
        stats_text = f"""
📊 **Admin Statistics**

👥 Recent Users: {len(recent_users)}
💬 Total Messages: {len(messages_db)}
🤖 Total Clones: {total_clones}
🆔 Admin ID: {ADMIN_ID}
🌐 Port: {PORT}

**Bot Status:** ✅ Running
**Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
        """
        
        await event.reply(stats_text)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await event.reply("❌ Error fetching statistics.")

@bot.on(events.NewMessage(pattern='/clone'))
async def clone_handler(event):
    """Show clone instructions"""
    try:
        clone_text = """
🔧 **Clone Your Own Whisper Bot**

🤖 **Create your own bot:**

**Steps:**
1. Go to @BotFather
2. Send /newbot command
3. Choose a name for your bot
4. Choose a username ending with 'bot'
5. Copy the bot token

**Then send:**
`/clone your_bot_token_here`

**Example:**
`/clone 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

**Commands:**
• `/clone token` - Clone new bot
• `/remove` - Remove your cloned bot

⚠️ **Note:**
• One bot per user only
• Keep your token safe and private
        """
        
        await event.reply(
            clone_text,
            buttons=[
                [Button.url("🤖 Create Bot", "https://t.me/BotFather")],
                [Button.inline("🔙 Back", data="back_start")]
            ]
        )
    except Exception as e:
        logger.error(f"Clone help error: {e}")
        await event.reply("❌ An error occurred. Please try again.")

@bot.on(events.NewMessage(pattern=r'/clone\s+(\S+)'))
async def clone_token_handler(event):
    """Handle bot cloning"""
    try:
        user_id = event.sender_id
        token = event.pattern_match.group(1).strip()
        
        # Check if user already has a cloned bot
        user_clones = [k for k, v in clone_stats.items() if v.get('owner_id') == user_id]
        if user_clones:
            await event.reply(
                "❌ **You already have a cloned bot!**\n\n"
                "Each user can only clone one bot.\n"
                "Use `/remove` to remove your current bot first.",
                buttons=[[Button.inline("🗑 Remove Bot", data="remove_bot")]]
            )
            return
        
        # Validate token format
        if not re.match(r'^\d+:[A-Za-z0-9_-]+$', token):
            await event.reply(
                "❌ **Invalid Token Format!**\n\n"
                "Please check your bot token.\n"
                "Format should be: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`",
                buttons=[[Button.inline("🔄 Try Again", data="clone_info")]]
            )
            return
        
        # Check if token already used
        if token in clone_stats:
            await event.reply(
                "❌ **This bot is already cloned!**\n\n"
                "Please create a new bot with @BotFather.",
                buttons=[[Button.url("🤖 Create New", "https://t.me/BotFather")]]
            )
            return
        
        creating_msg = await event.reply("🔄 **Creating your bot...**")
        
        # Create user bot instance
        user_bot = TelegramClient(f'user_bot_{user_id}', API_ID, API_HASH)
        await user_bot.start(bot_token=token)
        
        # Get bot info
        bot_me = await user_bot.get_me()
        
        # Store bot instance
        user_bots[token] = user_bot
        
        # Save clone stats
        user_mention = f"[{event.sender.first_name}](tg://user?id={user_id})"
        clone_stats[token] = {
            'owner_id': user_id,
            'username': bot_me.username,
            'first_name': getattr(event.sender, 'first_name', ''),
            'mention': user_mention,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'token_preview': token[:10] + '...'
        }
        save_data()
        
        # Setup handlers for cloned bot (NO CLONE FEATURE IN CLONED BOT)
        @user_bot.on(events.NewMessage(pattern='/start'))
        async def user_start(event):
            welcome_text = """
╔══════════════════════╗
║     🎭 𝗦𝗛𝗥𝗜𝗕𝗢𝗧𝗦     ║ 𝐏𝐨𝐰𝐞𝐫𝐞𝐝 𝐛𝐲
║    𝗪𝗛𝗜𝗦𝗣𝗘𝗥 𝗕𝗢𝗧    ║      𝐀𝐫𝐭𝐢𝐬𝐭
╚══════════════════════╝

🤫 Welcome to Secret Whisper Bot!

🔒 Send anonymous secret messages
🚀 Only intended recipient can read
🎯 Easy to use inline mode

Create whispers that only specific users can unlock!
"""
            await event.reply(
                welcome_text,
                buttons=[
                    [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                    [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                    [Button.switch_inline("🚀 Try Now", query="")],
                    [Button.inline("📖 Help", data="user_help")]
                ]
            )
        
        @user_bot.on(events.InlineQuery)
        async def user_inline_handler(event):
            await handle_inline_query(event, user_bot)
        
        @user_bot.on(events.CallbackQuery)
        async def user_callback_handler(event):
            data = event.data.decode('utf-8')
            
            if data == "user_help":
                bot_username = (await user_bot.get_me()).username
                help_text = f"""
📖 **How to Use Whisper Bot**

**1. Inline Mode:**
   • Type `@{bot_username}` in any chat
   • Write your message  
   • Add @username OR user ID at end
   • Send!

**2. Examples:**
   • `@{bot_username} Hello! @username`
   • `@{bot_username} I miss you 123456789`

🔒 **Only the mentioned user can read your message!**
"""
                await event.edit(
                    help_text,
                    buttons=[[Button.switch_inline("🚀 Try Now", query="")]]
                )
            
            elif data in messages_db:
                msg_data = messages_db[data]
                if event.sender_id in [msg_data['user_id'], msg_data['sender_id']]:
                    if event.sender_id == msg_data['user_id']:
                        sender_info = ""
                        try:
                            sender = await user_bot.get_entity(msg_data['sender_id'])
                            sender_name = getattr(sender, 'first_name', 'Someone')
                            sender_info = f"\n\n💌 From: {sender_name}"
                        except:
                            sender_info = f"\n\n💌 From: Anonymous"
                        
                        await event.answer(f"🔓 {msg_data['msg']}{sender_info}", alert=True)
                    else:
                        await event.answer(f"📝 Your message: {msg_data['msg']}", alert=True)
                else:
                    await event.answer("🔒 This message is not for you!", alert=True)
        
        # Send notification to admin
        try:
            notification_text = f"""
🆕 **New Bot Cloned!**

🤖 **Bot:** @{bot_me.username}
👤 **User ID:** `{user_id}`
👤 **User Name:** {event.sender.first_name}
👀 **Mention:** {user_mention}
📅 **Time:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
🔢 **Total Clones:** {len(clone_stats)}
            """
            
            await bot.send_message(
                ADMIN_ID,
                notification_text,
                parse_mode='markdown'
            )
        except Exception as e:
            logger.error(f"Admin notification error: {e}")
        
        # Success message to user
        await creating_msg.edit(
            f"✅ **Bot Cloned Successfully!**\n\n"
            f"🤖 **Your Bot:** @{bot_me.username}\n"
            f"🎉 Now active with all whisper features!\n\n"
            f"**Try your bot:**\n"
            f"`@{bot_me.username} message @username`",
            buttons=[
                [Button.switch_inline("🚀 Test Your Bot", query="", same_peer=True)],
                [Button.inline("🔙 Back", data="back_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Clone error: {e}")
        await event.reply(f"❌ **Clone Failed!**\n\nError: {str(e)}")

@bot.on(events.NewMessage(pattern='/remove'))
async def remove_handler(event):
    """Remove user's cloned bot"""
    try:
        user_id = event.sender_id
        user_clones = [k for k, v in clone_stats.items() if v.get('owner_id') == user_id]
        
        if not user_clones:
            await event.reply("❌ You have no bots to remove!")
            return
        
        removed = 0
        for token in user_clones:
            if token in user_bots:
                try:
                    await user_bots[token].disconnect()
                    del user_bots[token]
                except:
                    pass
            if token in clone_stats:
                del clone_stats[token]
                removed += 1
        
        save_data()
        await event.reply(f"✅ Removed {removed} of your bots!")
        
    except Exception as e:
        logger.error(f"Remove error: {e}")
        await event.reply("❌ Error removing bots!")

@bot.on(events.InlineQuery)
async def inline_handler(event):
    await handle_inline_query(event)

async def handle_inline_query(event, client=None):
    """Handle inline queries"""
    if client is None:
        client = bot
    
    try:
        if is_cooldown(event.sender_id):
            await event.answer([])
            return

        recent_buttons = get_recent_users_buttons(event.sender_id)
        
        if not event.text or not event.text.strip():
            if recent_buttons:
                result_text = "**Recent Users:**\nClick any user below to message them quickly!\n\nOr type: `message @username`"
                result = event.builder.article(
                    title="🤫 Whisper Bot - Quick Send",
                    description="Send to recent users or type manually",
                    text=result_text,
                    buttons=recent_buttons
                )
            else:
                result = event.builder.article(
                    title="🤫 Whisper Bot - Send Secret Messages",
                    description="Usage: your_message @username",
                    text="**Usage:** `your_message @username`\n\n**Example:** `Hello! @username`\n\n🔒 Only they can read!",
                    buttons=[[Button.switch_inline("🚀 Try Now", query="")]]
                )
            await event.answer([result])
            return
        
        text = event.text.strip()
        
        patterns = [r'@(\w+)$', r'(\d+)$']
        target_user = None
        message_text = text
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                if pattern == r'@(\w+)$':
                    target_user = match.group(1)
                    message_text = text.replace(f"@{target_user}", "").strip()
                else:
                    target_user = match.group(1)
                    message_text = text.replace(target_user, "").strip()
                break
        
        if not target_user or not message_text:
            result = event.builder.article(
                title="❌ Invalid Format",
                description="Use: message @username OR message 123456789",
                text="**Usage:** `your_message @username`\n\n**Examples:**\n• `Hello! @username`\n• `I miss you 123456789`",
                buttons=[[Button.switch_inline("🔄 Try Again", query=text)]]
            )
            await event.answer([result])
            return
        
        if len(message_text) > 1000:
            result = event.builder.article(
                title="❌ Message Too Long",
                description="Maximum 1000 characters allowed",
                text="❌ Your message is too long! Please keep it under 1000 characters."
            )
            await event.answer([result])
            return
        
        try:
            if target_user.isdigit():
                user_obj = await client.get_entity(int(target_user))
            else:
                if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', target_user):
                    result = event.builder.article(
                        title="❌ Invalid Username",
                        description="Username format is invalid",
                        text="**Valid username format:**\n• Starts with letter\n• 4-31 characters\n• Letters, numbers, underscores only"
                    )
                    await event.answer([result])
                    return
                
                user_obj = await client.get_entity(target_user)
            
            if not hasattr(user_obj, 'first_name'):
                result = event.builder.article(
                    title="❌ Not a User",
                    description="You can only send to users",
                    text="This appears to be a channel or group. Please mention a user instead."
                )
                await event.answer([result])
                return
            
            add_to_recent_users(
                event.sender_id, 
                user_obj.id, 
                getattr(user_obj, 'username', None),
                getattr(user_obj, 'first_name', 'User')
            )
            
        except Exception as e:
            logger.error(f"Error getting user entity: {e}")
            result = event.builder.article(
                title="❌ User Not Found",
                description="User not found or invalid",
                text="❌ User not found! Please check username or user ID."
            )
            await event.answer([result])
            return
        
        message_id = f'msg_{event.sender_id}_{user_obj.id}_{int(datetime.now().timestamp())}'
        messages_db[message_id] = {
            'user_id': user_obj.id,
            'msg': message_text,
            'sender_id': event.sender_id,
            'timestamp': datetime.now().isoformat(),
            'target_name': getattr(user_obj, 'first_name', 'User')
        }
        
        target_name = getattr(user_obj, 'first_name', 'User')
        result = event.builder.article(
            title=f"🔒 Secret Message for {target_name}",
            description=f"Click to send secret message",
            text=f"**🔐 A secret message for {target_name}!**\n\n*Note: Only {target_name} can open this message.*",
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
                
            total_clones = len(clone_stats)
            stats_text = f"📊 **Admin Statistics**\n\n"
            stats_text += f"👥 Recent Users: {len(recent_users)}\n"
            stats_text += f"💬 Total Messages: {len(messages_db)}\n"
            stats_text += f"🤖 Total Clones: {total_clones}\n"
            stats_text += f"🆔 Admin ID: {ADMIN_ID}\n"
            stats_text += f"🌐 Port: {PORT}\n"
            stats_text += f"🕒 Last Updated: {datetime.now().strftime('%H:%M:%S')}\n\n"
            stats_text += f"**Status:** ✅ Running"
            
            await event.edit(
                stats_text,
                buttons=[[Button.inline("🔙 Back", data="back_start")]]
            )
        
        elif data == "clone_info":
            clone_text = """
🔧 **Clone Your Own Whisper Bot**

**Commands:**
• `/clone bot_token` - Clone new bot
• `/remove` - Remove your cloned bot

**Example:**
`/clone 1234567890:ABCdefGHIjkl...`

⚠️ **Note:**
• One bot per user only
• Keep token safe
            """
            await event.edit(
                clone_text,
                buttons=[
                    [Button.url("🤖 BotFather", "https://t.me/BotFather")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
        
        elif data == "remove_bot":
            user_id = event.sender_id
            user_clones = [k for k, v in clone_stats.items() if v.get('owner_id') == user_id]
            
            if not user_clones:
                await event.answer("No bots to remove!", alert=True)
                return
            
            removed = 0
            for token in user_clones:
                if token in user_bots:
                    try:
                        await user_bots[token].disconnect()
                        del user_bots[token]
                    except:
                        pass
                if token in clone_stats:
                    del clone_stats[token]
                    removed += 1
            
            save_data()
            await event.answer(f"✅ {removed} bots removed!", alert=True)
            await event.edit(f"✅ Removed {removed} of your bots!")
        
        elif data.startswith("recent_"):
            user_key = data.replace("recent_", "")
            if user_key in recent_users:
                user_data = recent_users[user_key]
                username = user_data.get('username')
                first_name = user_data.get('first_name', 'User')
                
                if username:
                    target_text = f"@{username}"
                else:
                    target_text = f"{first_name}"
                
                await event.edit(
                    f"🔒 **Send whisper to {target_text}**\n\n"
                    f"Now switch to inline mode and type your message for {target_text}",
                    buttons=[[Button.switch_inline(
                        f"💌 Message {target_text}", 
                        query=f"@{username}" if username else first_name
                    )]]
                )
            else:
                await event.answer("User not found in recent list!", alert=True)
        
        elif data == "back_start":
            if event.sender_id == ADMIN_ID:
                await event.edit(
                    WELCOME_TEXT,
                    buttons=[
                        [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                        [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                        [Button.switch_inline("🚀 Try Now", query="")],
                        [Button.inline("📊 Statistics", data="admin_stats"), Button.inline("📖 Help", data="help")],
                        [Button.inline("🔧 Clone Bot", data="clone_info")]
                    ]
                )
            else:
                await event.edit(
                    WELCOME_TEXT,
                    buttons=[
                        [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                        [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                        [Button.switch_inline("🚀 Try Now", query="")],
                        [Button.inline("📖 Help", data="help"), Button.inline("🔧 Clone Bot", data="clone_info")]
                    ]
                )
        
        elif data in messages_db:
            msg_data = messages_db[data]
            if event.sender_id == msg_data['user_id']:
                sender_info = ""
                try:
                    sender = await bot.get_entity(msg_data['sender_id'])
                    sender_name = getattr(sender, 'first_name', 'Someone')
                    sender_info = f"\n\n💌 From: {sender_name}"
                except:
                    sender_info = f"\n\n💌 From: Anonymous"
                
                await event.answer(f"🔓 {msg_data['msg']}{sender_info}", alert=True)
            elif event.sender_id == msg_data['sender_id']:
                await event.answer(f"📝 Your message: {msg_data['msg']}\n\n👤 To: {msg_data.get('target_name', 'User')}", alert=True)
            else:
                await event.answer("🔒 This message is not for you!", alert=True)
        
        else:
            await event.answer("❌ Invalid button!", alert=True)
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await event.answer("❌ An error occurred. Please try again.", alert=True)

# Flask web server
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ShriBots Whisper Bot</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; }
            .status { background: #4CAF50; color: white; padding: 10px; border-radius: 5px; text-align: center; margin: 20px 0; }
            .info { background: #2196F3; color: white; padding: 15px; border-radius: 5px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 ShriBots Whisper Bot</h1>
            <div class="status">✅ Bot is Running Successfully</div>
            <div class="info">
                <strong>📊 Statistics:</strong><br>
                Recent Users: {}<br>
                Total Messages: {}<br>
                Total Clones: {}<br>
                Server Time: {}
            </div>
            <p>This bot allows you to send anonymous secret messages to Telegram users.</p>
            <p><strong>Usage:</strong> Use inline mode in any chat: <code>@{} your_message @username</code></p>
        </div>
    </body>
    </html>
    """.format(
        len(recent_users), 
        len(messages_db),
        len(clone_stats),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        (bot.get_me()).wait().username if bot.is_connected() else "bot_username"
    )

@app.route('/health')
def health():
    return json.dumps({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "recent_users": len(recent_users),
        "total_messages": len(messages_db),
        "total_clones": len(clone_stats),
        "bot_connected": bot.is_connected()
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
        logger.info(f"👥 Recent Users: {len(recent_users)}")
        logger.info(f"🤖 Total Clones: {len(clone_stats)}")
        logger.info(f"🌐 Web server running on port {PORT}")
        logger.info("✅ Bot is ready and working!")
        logger.info("🔗 Use /start to begin")
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

if __name__ == '__main__':
    print("🚀 Starting ShriBots Whisper Bot...")
    print(f"📝 Environment: API_ID={API_ID}, PORT={PORT}")
    
    try:
        # Start the bot
        bot.start()
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
        save_data()
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

# Environment variables (Render पर ये variables set करने होंगे)
API_ID = int(os.getenv('API_ID', ''))  # Render में set करें
API_HASH = os.getenv('API_HASH', '')    # Render में set करें
BOT_TOKEN = os.getenv('BOT_TOKEN', '')  # Render में set करें
ADMIN_ID = int(os.getenv('ADMIN_ID', ''))  # Render में set करें
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
user_drafts = {}  # Store user draft messages
user_last_targets = {}  # Store user's last target

# Data files
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
RECENT_USERS_FILE = os.path.join(DATA_DIR, "recent_users.json")
CLONE_STATS_FILE = os.path.join(DATA_DIR, "clone_stats.json")
USER_LAST_TARGETS_FILE = os.path.join(DATA_DIR, "user_last_targets.json")

def load_data():
    global recent_users, clone_stats, user_last_targets
    try:
        if os.path.exists(RECENT_USERS_FILE):
            with open(RECENT_USERS_FILE, 'r', encoding='utf-8') as f:
                recent_users = json.load(f)
            logger.info(f"✅ Loaded {len(recent_users)} recent users")
        
        if os.path.exists(CLONE_STATS_FILE):
            with open(CLONE_STATS_FILE, 'r', encoding='utf-8') as f:
                clone_stats = json.load(f)
            logger.info(f"✅ Loaded {len(clone_stats)} clone stats")
        
        if os.path.exists(USER_LAST_TARGETS_FILE):
            with open(USER_LAST_TARGETS_FILE, 'r', encoding='utf-8') as f:
                user_last_targets = json.load(f)
            logger.info(f"✅ Loaded {len(user_last_targets)} user last targets")
                
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        recent_users = {}
        clone_stats = {}
        user_last_targets = {}

def save_data():
    try:
        with open(RECENT_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(recent_users, f, indent=2, ensure_ascii=False)
        
        with open(CLONE_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(clone_stats, f, indent=2, ensure_ascii=False)
        
        with open(USER_LAST_TARGETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_last_targets, f, indent=2, ensure_ascii=False)
            
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
🔄 **Auto Last User Display**

**⚡ Instant Features:**
• Username/ID लिखते ही send
• गलत username/ID पर भी whisper
• Last user automatically show
"""

HELP_TEXT = """
📖 **How to Use Whisper Bot**

**1. Instant Mode (एक बार में):**
   • Type `@{} message @username`
   • OR `@{} message 123456789`
   • Send immediately!

**2. Examples:**
   • `@{} Hello! @username`
   • `@{} I miss you 123456789`
   • `@{} Hi @anyname` (any name works!)

**3. Last User Feature:**
   • Next time, last user automatically shows
   • Easy to send again to same person

**4. Commands:**
   • /start - Start bot
   • /help - Show help
   • /clone - Clone your bot
   • /remove - Remove your bot

✅ **Works with ANY username or ID!**
🔒 **Only mentioned user can read!**
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

def save_user_last_target(user_id, target_info):
    """Save user's last target"""
    try:
        user_last_targets[str(user_id)] = {
            'target': target_info,
            'timestamp': datetime.now().isoformat()
        }
        save_data()
    except Exception as e:
        logger.error(f"Error saving last target: {e}")

def get_user_last_target(user_id):
    """Get user's last target"""
    return user_last_targets.get(str(user_id))

def is_cooldown(user_id):
    """Check if user is in cooldown"""
    now = datetime.now().timestamp()
    if user_id in user_cooldown:
        if now - user_cooldown[user_id] < 1:  # 1 second cooldown
            return True
    user_cooldown[user_id] = now
    return False

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        user_id = event.sender_id
        logger.info(f"🚀 Start command from user: {user_id}")
        
        # Get last target if exists
        last_target = get_user_last_target(user_id)
        has_last_target = last_target is not None
        
        # Welcome message with buttons
        buttons = [
            [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
            [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
            [Button.switch_inline("🚀 Send Whisper", query="")]
        ]
        
        if has_last_target:
            target_info = last_target['target']
            if isinstance(target_info, dict):
                target_name = target_info.get('first_name', 'User')
                buttons.append([Button.inline(f"↪️ Last: {target_name}", data="use_last_target")])
        
        buttons.append([
            Button.inline("📖 Help", data="help"),
            Button.inline("🔧 Clone", data="clone_info")
        ])
        
        if user_id == ADMIN_ID:
            buttons.append([Button.inline("📊 Stats", data="admin_stats")])
        
        await event.reply(WELCOME_TEXT, buttons=buttons)
        
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
        total_last_targets = len(user_last_targets)
        
        stats_text = f"""
📊 **Admin Statistics**

👥 Recent Users: {len(recent_users)}
💬 Total Messages: {len(messages_db)}
🤖 Total Clones: {total_clones}
🎯 Last Targets: {total_last_targets}
🆔 Admin ID: {ADMIN_ID}
🌐 Port: {PORT}

**Features Active:**
✅ Instant username detection
✅ गलत username support
✅ Auto last user display
✅ One-step sending

**Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
        """
        
        await event.reply(stats_text)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await event.reply("❌ Error fetching statistics.")

@bot.on(events.InlineQuery)
async def inline_handler(event):
    """Handle inline queries - ONE STEP SENDING"""
    try:
        if is_cooldown(event.sender_id):
            await event.answer([])
            return
        
        query_text = event.text.strip() if event.text else ""
        sender_id = event.sender_id
        
        logger.info(f"📝 Inline query: User={sender_id}, Text='{query_text}'")
        
        # If empty query, show quick options
        if not query_text:
            # Check for last target
            last_target = get_user_last_target(sender_id)
            recent_buttons = get_recent_users_buttons(sender_id)
            
            result_text = "**🤫 Send Secret Message**\n\n"
            
            if last_target:
                target_info = last_target['target']
                if isinstance(target_info, dict):
                    target_name = target_info.get('first_name', 'User')
                    target_username = target_info.get('username')
                    target_display = f"@{target_username}" if target_username else target_name
                    result_text += f"**Last User:** {target_display}\n\n"
            
            result_text += "**Type:**\n`message @username`\nOR\n`message 123456789`\n\n"
            result_text += "**Examples:**\n• `Hello @username`\n• `Hi 123456789`\n\n"
            result_text += "✅ **Works with ANY username/ID!**"
            
            if recent_buttons:
                result = event.builder.article(
                    title="🚀 Quick Send",
                    description="Send to recent users or type",
                    text=result_text,
                    buttons=recent_buttons + [
                        [Button.switch_inline("✏️ Type Message", query="")]
                    ]
                )
            else:
                result = event.builder.article(
                    title="🚀 Send Whisper",
                    description="Type: message @username",
                    text=result_text,
                    buttons=[[Button.switch_inline("✏️ Start Typing", query="")]]
                )
            
            await event.answer([result])
            return
        
        # Process the query text
        # Extract ANY username or user ID
        username_match = re.search(r'@(\w+)', query_text)
        userid_match = re.search(r'(\d{8,})', query_text)
        
        target_user = None
        message_text = query_text
        
        if username_match:
            target_user = username_match.group(1)
            message_text = re.sub(r'@' + re.escape(target_user) + r'\b', '', query_text).strip()
            target_display = f"@{target_user}"
            
        elif userid_match:
            target_user = userid_match.group(1)
            message_text = re.sub(r'\b' + re.escape(target_user) + r'\b', '', query_text).strip()
            target_display = target_user
            
        else:
            # No user mentioned, ask to add
            user_drafts[sender_id] = message_text
            
            result = event.builder.article(
                title="📝 Add Recipient",
                description="Add @username or 123456789 at end",
                text=f"**Your Message:**\n`{message_text[:80]}{'...' if len(message_text) > 80 else ''}`\n\n"
                     f"**Now add recipient:**\n• @username\n• 123456789\n\n"
                     f"**Example:** `{message_text} @username`\n\n"
                     f"✅ **Any username/ID works!**",
                buttons=[
                    [Button.switch_inline("➕ Add @username", query=f"{message_text} @")],
                    [Button.switch_inline("➕ Add 123456789", query=f"{message_text} 123456789")]
                ]
            )
            await event.answer([result])
            return
        
        # Check if message is empty
        if not message_text:
            result = event.builder.article(
                title="❌ Message Required",
                description="Type a message first",
                text="**Please type a message!**\n\n**Format:** `message @username`\n\n**Example:** `Hello! @anyname`",
                buttons=[[Button.switch_inline("🔄 Try Again", query="")]]
            )
            await event.answer([result])
            return
        
        # Check message length
        if len(message_text) > 1000:
            result = event.builder.article(
                title="❌ Message Too Long",
                description="Max 1000 characters",
                text="❌ Message too long! Keep under 1000 characters."
            )
            await event.answer([result])
            return
        
        # Create message ID
        message_id = f'msg_{sender_id}_{int(datetime.now().timestamp())}_{target_user}'
        
        # Try to get user info, but even if fails, STORE THE MESSAGE
        user_info = None
        try:
            if target_user.isdigit():
                user_obj = await bot.get_entity(int(target_user))
                user_info = {
                    'id': user_obj.id,
                    'first_name': getattr(user_obj, 'first_name', 'User'),
                    'username': getattr(user_obj, 'username', None)
                }
            else:
                user_obj = await bot.get_entity(target_user)
                user_info = {
                    'id': user_obj.id,
                    'first_name': getattr(user_obj, 'first_name', 'User'),
                    'username': getattr(user_obj, 'username', None)
                }
            
            # Add to recent users if valid user
            add_to_recent_users(
                sender_id,
                user_info['id'],
                user_info.get('username'),
                user_info.get('first_name', 'User')
            )
            
            # Save as last target
            save_user_last_target(sender_id, user_info)
            
            target_name = user_info['first_name']
            target_username = user_info.get('username')
            
        except Exception as e:
            logger.warning(f"User lookup failed for '{target_user}': {e}")
            # Even if user doesn't exist, we still allow sending
            # Create fake user info for storage
            user_info = {
                'id': 0,  # Placeholder
                'first_name': target_user,
                'username': target_user if not target_user.isdigit() else None,
                'is_invalid': True
            }
            
            # Save as last target even if invalid
            save_user_last_target(sender_id, user_info)
            
            target_name = target_user
            target_username = target_user if not target_user.isdigit() else None
        
        # Store message
        messages_db[message_id] = {
            'target_display': target_display,
            'msg': message_text,
            'sender_id': sender_id,
            'timestamp': datetime.now().isoformat(),
            'target_name': target_name,
            'target_username': target_username,
            'target_raw': target_user,
            'user_info': user_info
        }
        
        # Clear draft
        if sender_id in user_drafts:
            del user_drafts[sender_id]
        
        # Create result
        preview_msg = message_text[:80] + ("..." if len(message_text) > 80 else "")
        
        # Different message for valid vs invalid user
        if user_info.get('is_invalid'):
            result_text = f"**⚠️ Sending to '{target_name}'**\n\n"
            result_text += f"**Message:** {preview_msg}\n\n"
            result_text += "ℹ️ *User verification skipped*\n"
            result_text += "✅ *Whisper will be created anyway*"
        else:
            target_display = f"@{target_username}" if target_username else target_name
            result_text = f"**🔒 Secret for {target_name}**\n\n"
            result_text += f"**Message:** {preview_msg}\n\n"
            result_text += f"*Only {target_name} can open this message*"
        
        result = event.builder.article(
            title=f"🔐 Whisper to {target_name}",
            description=f"Click to send secret message",
            text=result_text,
            buttons=[[Button.inline("📤 Send Whisper", message_id)]]
        )
        
        await event.answer([result])
        
    except Exception as e:
        logger.error(f"Inline query error: {e}")
        result = event.builder.article(
            title="❌ Error",
            description="Something went wrong",
            text="❌ An error occurred. Please try again."
        )
        await event.answer([result])

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    try:
        data = event.data.decode('utf-8')
        sender_id = event.sender_id
        
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
            if sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
                
            total_clones = len(clone_stats)
            stats_text = f"📊 **Admin Statistics**\n\n"
            stats_text += f"👥 Recent Users: {len(recent_users)}\n"
            stats_text += f"💬 Total Messages: {len(messages_db)}\n"
            stats_text += f"🤖 Total Clones: {total_clones}\n"
            stats_text += f"🎯 Last Targets: {len(user_last_targets)}\n"
            stats_text += f"🌐 Port: {PORT}\n\n"
            stats_text += f"**Status:** ✅ Instant Whisper Active"
            
            await event.edit(
                stats_text,
                buttons=[[Button.inline("🔙 Back", data="back_start")]]
            )
        
        elif data == "clone_info":
            clone_text = """
🔧 **Clone Your Own Bot**

**Main Bot में ही Clone करें:**
• /clone token - Create your bot
• /remove - Remove your bot
• 1 User = 1 Bot only

**Features in your bot:**
✅ Same instant sending
✅ गलत username support
✅ Auto last user
✅ One-step whisper
"""
            await event.edit(
                clone_text,
                buttons=[
                    [Button.url("🤖 BotFather", "https://t.me/BotFather")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
        
        elif data == "use_last_target":
            last_target = get_user_last_target(sender_id)
            if last_target:
                target_info = last_target['target']
                target_name = target_info.get('first_name', 'User')
                target_username = target_info.get('username')
                
                if target_username:
                    target_display = f"@{target_username}"
                else:
                    target_display = target_name
                
                await event.edit(
                    f"**↪️ Last User: {target_display}**\n\n"
                    f"Now type your message for {target_name}",
                    buttons=[[Button.switch_inline(
                        f"💌 Message {target_name}", 
                        query=f""
                    )]]
                )
            else:
                await event.answer("No last user found!", alert=True)
        
        elif data.startswith("recent_"):
            user_key = data.replace("recent_", "")
            if user_key in recent_users:
                user_data = recent_users[user_key]
                username = user_data.get('username')
                first_name = user_data.get('first_name', 'User')
                
                target_display = f"@{username}" if username else first_name
                
                # Save as last target
                save_user_last_target(sender_id, user_data)
                
                await event.edit(
                    f"**↪️ Selected: {target_display}**\n\n"
                    f"Now type your message for {first_name}",
                    buttons=[[Button.switch_inline(
                        f"📝 Message {first_name}", 
                        query=""
                    )]]
                )
            else:
                await event.answer("User not found!", alert=True)
        
        elif data == "back_start":
            last_target = get_user_last_target(sender_id)
            has_last_target = last_target is not None
            
            buttons = [
                [Button.url("📢 Support", f"https://t.me/{SUPPORT_CHANNEL}")],
                [Button.url("👥 Group", f"https://t.me/{SUPPORT_GROUP}")],
                [Button.switch_inline("🚀 Send Whisper", query="")]
            ]
            
            if has_last_target:
                target_info = last_target['target']
                if isinstance(target_info, dict):
                    target_name = target_info.get('first_name', 'User')
                    buttons.append([Button.inline(f"↪️ Last: {target_name}", data="use_last_target")])
            
            buttons.append([
                Button.inline("📖 Help", data="help"),
                Button.inline("🔧 Clone", data="clone_info")
            ])
            
            if sender_id == ADMIN_ID:
                buttons.append([Button.inline("📊 Stats", data="admin_stats")])
            
            await event.edit(WELCOME_TEXT, buttons=buttons)
        
        elif data in messages_db:
            msg_data = messages_db[data]
            
            if sender_id == msg_data['sender_id']:
                # Sender viewing their own message
                target_name = msg_data['target_name']
                target_display = msg_data['target_display']
                
                response = f"📝 **Your Message:**\n{msg_data['msg']}\n\n"
                response += f"👤 **To:** {target_display}\n"
                
                if msg_data['user_info'].get('is_invalid'):
                    response += "⚠️ *User not verified*\n"
                    response += "✅ *But whisper created anyway*"
                
                await event.answer(response, alert=True)
                
            else:
                # Check if this is the intended recipient
                user_info = msg_data['user_info']
                
                if user_info.get('is_invalid'):
                    # Invalid user - anyone can view (as per requirement)
                    sender_name = "Anonymous"
                    try:
                        sender = await bot.get_entity(msg_data['sender_id'])
                        sender_name = getattr(sender, 'first_name', 'Someone')
                    except:
                        pass
                    
                    response = f"🔓 **Secret Message:**\n{msg_data['msg']}\n\n"
                    response += f"💌 **From:** {sender_name}\n"
                    response += "⚠️ *Sent to unverified user*"
                    
                    await event.answer(response, alert=True)
                    
                elif sender_id == user_info.get('id'):
                    # Valid user and correct recipient
                    sender_name = "Anonymous"
                    try:
                        sender = await bot.get_entity(msg_data['sender_id'])
                        sender_name = getattr(sender, 'first_name', 'Someone')
                    except:
                        pass
                    
                    response = f"🔓 **Secret Message:**\n{msg_data['msg']}\n\n"
                    response += f"💌 **From:** {sender_name}"
                    
                    await event.answer(response, alert=True)
                    
                else:
                    # Wrong person trying to view
                    await event.answer("🔒 This message is not for you!", alert=True)
        
        else:
            await event.answer("❌ Invalid button!", alert=True)
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await event.answer("❌ An error occurred.", alert=True)

# Clone system functions (simplified)
@bot.on(events.NewMessage(pattern='/clone'))
async def clone_handler(event):
    """Show clone instructions"""
    clone_text = """
🔧 **Bot Cloning System**

**📌 Important Rules:**
1. **Only in Main Bot** - Clone here only
2. **1 User = 1 Bot** - One bot per user
3. **Token Safety** - Never share token

**🚀 Steps to Clone:**
1. Go to @BotFather
2. Create new bot
3. Copy bot token
4. Send here: `/clone your_token`

**Example:**
`/clone 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

**✅ Your cloned bot will have:**
• Same instant sending
• गलत username support  
• Auto last user display
• One-step whispers
"""
    
    await event.reply(
        clone_text,
        buttons=[
            [Button.url("🤖 Create Bot", "https://t.me/BotFather")],
            [Button.inline("🔙 Back", data="back_start")]
        ]
    )

@bot.on(events.NewMessage(pattern=r'/clone\s+(\S+)'))
async def clone_token_handler(event):
    """Simple clone handler"""
    await event.reply(
        "🔄 **Clone system under maintenance**\n\n"
        "Currently focusing on instant whisper features.\n"
        "Clone system will be added soon!\n\n"
        "For now, enjoy the main bot with:\n"
        "✅ Instant username detection\n"
        "✅ गलत username support\n"
        "✅ Auto last user display\n"
        "✅ One-step sending",
        buttons=[[Button.switch_inline("🚀 Try Whisper", query="")]]
    )

@bot.on(events.NewMessage(pattern='/remove'))
async def remove_handler(event):
    """Simple remove handler"""
    await event.reply(
        "🗑 **Remove system coming soon**\n\n"
        "Currently all features working in main bot.\n"
        "Clone/remove system will be added soon!\n\n"
        "**Current Features:**\n"
        "⚡ Username/ID लिखते ही send\n"
        "✅ गलत username/ID पर भी whisper\n"
        "🔄 Auto last user display",
        buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
    )

# Flask web server
app = Flask(__name__)

@app.route('/')
def home():
    bot_username = "bot_username"
    if bot.is_connected():
        try:
            bot_username = asyncio.run_coroutine_threadsafe(bot.get_me(), bot.loop).result().username
        except:
            pass
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>ShriBots Instant Whisper</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 20px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .container {{ 
                max-width: 900px; 
                margin: 0 auto; 
                background: rgba(255, 255, 255, 0.95); 
                padding: 30px; 
                border-radius: 20px; 
                box-shadow: 0 15px 35px rgba(0,0,0,0.2);
            }}
            h1 {{ 
                color: #333; 
                text-align: center; 
                margin-bottom: 30px;
                font-size: 2.5em;
            }}
            .status {{ 
                background: linear-gradient(90deg, #4CAF50, #45a049);
                color: white; 
                padding: 20px; 
                border-radius: 12px; 
                text-align: center; 
                margin: 25px 0; 
                font-size: 1.2em;
            }}
            .features {{ 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
                gap: 20px; 
                margin: 30px 0; 
            }}
            .feature-box {{ 
                background: white; 
                padding: 20px; 
                border-radius: 12px; 
                text-align: center; 
                border-top: 5px solid;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }}
            .feature-box.instant {{ border-top-color: #FF9800; }}
            .feature-box.any {{ border-top-color: #2196F3; }}
            .feature-box.auto {{ border-top-color: #4CAF50; }}
            .feature-box.one {{ border-top-color: #9C27B0; }}
            .feature-icon {{
                font-size: 40px;
                margin-bottom: 10px;
            }}
            .bot-link {{ 
                text-align: center; 
                margin-top: 30px; 
            }}
            .bot-link a {{ 
                display: inline-block; 
                background: linear-gradient(90deg, #FF9800, #FF5722);
                color: white; 
                padding: 15px 40px; 
                text-decoration: none; 
                border-radius: 50px; 
                font-weight: bold;
                font-size: 1.2em;
                box-shadow: 0 8px 20px rgba(255, 152, 0, 0.4);
            }}
            .examples {{ 
                background: #e8f5e9; 
                padding: 20px; 
                border-radius: 12px; 
                margin: 25px 0;
            }}
            .example-item {{
                margin: 10px 0;
                padding: 10px;
                background: white;
                border-radius: 8px;
                border-left: 4px solid #2196F3;
            }}
            code {{
                background: #f1f1f1;
                padding: 5px 10px;
                border-radius: 5px;
                font-family: monospace;
                font-size: 1.1em;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>⚡ Instant Whisper Bot v2.0</h1>
            <div class="status">
                ✅ Bot Active | Instant Detection | गलत Username Support
            </div>
            
            <div class="features">
                <div class="feature-box instant">
                    <div class="feature-icon">⚡</div>
                    <h3>Instant Send</h3>
                    <p>Username/ID लिखते ही send option</p>
                </div>
                <div class="feature-box any">
                    <div class="feature-icon">✅</div>
                    <h3>Any Username/ID</h3>
                    <p>सही या गलत, सब पर whisper</p>
                </div>
                <div class="feature-box auto">
                    <div class="feature-icon">🔄</div>
                    <h3>Auto Last User</h3>
                    <p>दुबारा @botusername में last user show</p>
                </div>
                <div class="feature-box one">
                    <div class="feature-icon">🎯</div>
                    <h3>One-Step</h3>
                    <p>एक बार में complete send</p>
                </div>
            </div>
            
            <div class="examples">
                <h3>🎯 How to Use:</h3>
                
                <div class="example-item">
                    <strong>Method 1: Instant (Recommended)</strong><br>
                    <code>@{bot_username} Hello @username</code><br>
                    <small>→ Username detect होते ही send!</small>
                </div>
                
                <div class="example-item">
                    <strong>Method 2: Any Username/ID</strong><br>
                    <code>@{bot_username} Hi @anyname123</code><br>
                    <small>→ गलत username पर भी काम करेगा!</small>
                </div>
                
                <div class="example-item">
                    <strong>Method 3: User ID</strong><br>
                    <code>@{bot_username} Message 123456789</code><br>
                    <small>→ User ID से भी काम करेगा!</small>
                </div>
                
                <div class="example-item">
                    <strong>Auto Last User Feature</strong><br>
                    <small>दुबारा @{bot_username} टाइप करने पर last user automatically show होगा!</small>
                </div>
            </div>
            
            <div class="bot-link">
                <a href="https://t.me/{bot_username}" target="_blank">
                    🚀 Try Instant Whisper
                </a>
            </div>
            
            <div style="text-align: center; margin-top: 30px; color: #666; font-size: 14px;">
                <strong>⚡ Instant Detection | ✅ Any Username/ID | 🔄 Auto Last User</strong><br>
                <small>सही हो या गलत, हर username/ID पर whisper!</small>
            </div>
        </div>
        
        <script>
            // Auto-refresh every 30 seconds
            setTimeout(function() {{
                location.reload();
            }}, 30000);
        </script>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return json.dumps({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "instant_detection": True,
            "any_username_support": True,
            "auto_last_user": True,
            "one_step_sending": True
        },
        "stats": {
            "recent_users": len(recent_users),
            "total_messages": len(messages_db),
            "last_targets": len(user_last_targets)
        }
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
        logger.info(f"🎭 ShriBots Instant Whisper Started!")
        logger.info(f"🤖 Bot: @{me.username}")
        logger.info(f"🆔 Bot ID: {me.id}")
        logger.info(f"🌐 Web server on port {PORT}")
        logger.info("✅ Features Active:")
        logger.info("   ⚡ Instant username detection")
        logger.info("   ✅ गलत username/ID support")
        logger.info("   🔄 Auto last user display")
        logger.info("   🎯 One-step sending")
        logger.info("🔗 Use /start to begin")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════╗
    ║     ⚡ INSTANT WHISPER BOT v2.0          ║
    ║     सही या गलत, सब पर Whisper!         ║
    ║     Username/ID लिखते ही Send!         ║
    ╚══════════════════════════════════════════╝
    """)
    
    print("🚀 Starting Instant Whisper Bot...")
    print("✨ Key Features:")
    print("   1. ⚡ Username/ID लिखते ही send option")
    print("   2. ✅ गलत username/ID पर भी whisper")
    print("   3. 🔄 Auto last user display")
    print("   4. 🎯 One-step complete sending")
    
    try:
        # Check environment variables
        if not API_ID or not API_HASH or not BOT_TOKEN:
            print("\n❌ ERROR: Set environment variables!")
            print("   Required: API_ID, API_HASH, BOT_TOKEN")
            exit(1)
            
        # Start bot
        bot.start()
        bot.loop.run_until_complete(main())
        
        print("\n✅ Bot started successfully!")
        print("🔄 Bot is running...")
        print("\n📋 Usage Examples (Type in any chat):")
        print("   1. @bot_username Hello @username")
        print("   2. @bot_username Hi 123456789")
        print("   3. @bot_username Message @anyname (even if wrong!)")
        print("\n🔄 Auto Feature: Next time, last user automatically shows!")
        
        # Run bot
        bot.run_until_disconnected()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        print(f"❌ Error: {e}")
    finally:
        print("💾 Saving data...")
        save_data()
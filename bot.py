import os
import logging
import re
import asyncio
import json
from datetime import datetime
import threading
from telethon import TelegramClient, events, Button
from telethon.tl.types import User as TelethonUser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
API_ID = int(os.getenv('API_ID', ''))
API_HASH = os.getenv('API_HASH', ''))
BOT_TOKEN = os.getenv('BOT_TOKEN', ''))
ADMIN_ID = int(os.getenv('ADMIN_ID', ''))
OWNER_ID = ADMIN_ID  # Shri button owner ID
PORT = int(os.environ.get('PORT', 10000))

# Support channels and main bot for cloning
SUPPORT_CHANNEL = "shribots"
SUPPORT_GROUP = "idxhelp"
MAIN_BOT_FOR_CLONE = "upspbot"

# Initialize bot
try:
    bot = TelegramClient('whisper_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    logger.info("✅ Bot initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize bot: {e}")
    raise

# Check if this is main bot or cloned bot
try:
    bot_me = asyncio.run_coroutine_threadsafe(bot.get_me(), bot.loop).result()
    IS_MAIN_BOT = bot_me.username == MAIN_BOT_FOR_CLONE
    logger.info(f"🤖 Bot Type: {'MAIN' if IS_MAIN_BOT else 'CLONED'} (@{bot_me.username})")
except:
    IS_MAIN_BOT = False

# Storage
messages_db = {}  # message_id: message_data
recent_users = {}
user_cooldown = {}
user_bots = {}
clone_stats = {}
user_last_targets = {}
user_clone_tokens = {}
all_whispers = []  # Store all whispers for owner

# Broadcast state
broadcasting = False

# Data files
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
RECENT_USERS_FILE = os.path.join(DATA_DIR, "recent_users.json")
CLONE_STATS_FILE = os.path.join(DATA_DIR, "clone_stats.json")
USER_LAST_TARGETS_FILE = os.path.join(DATA_DIR, "user_last_targets.json")
USER_CLONE_TOKENS_FILE = os.path.join(DATA_DIR, "user_clone_tokens.json")
ALL_WHISPERS_FILE = os.path.join(DATA_DIR, "all_whispers.json")

def load_data():
    global recent_users, clone_stats, user_last_targets, user_clone_tokens, all_whispers
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
        
        if os.path.exists(USER_CLONE_TOKENS_FILE):
            with open(USER_CLONE_TOKENS_FILE, 'r', encoding='utf-8') as f:
                user_clone_tokens = json.load(f)
            logger.info(f"✅ Loaded {len(user_clone_tokens)} user clone tokens")
        
        if os.path.exists(ALL_WHISPERS_FILE):
            with open(ALL_WHISPERS_FILE, 'r', encoding='utf-8') as f:
                all_whispers = json.load(f)
            logger.info(f"✅ Loaded {len(all_whispers)} whispers for owner")
                
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        recent_users = {}
        clone_stats = {}
        user_last_targets = {}
        user_clone_tokens = {}
        all_whispers = []

def save_data():
    try:
        with open(RECENT_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(recent_users, f, indent=2, ensure_ascii=False)
        
        with open(CLONE_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(clone_stats, f, indent=2, ensure_ascii=False)
        
        with open(USER_LAST_TARGETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_last_targets, f, indent=2, ensure_ascii=False)
        
        with open(USER_CLONE_TOKENS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_clone_tokens, f, indent=2, ensure_ascii=False)
        
        with open(ALL_WHISPERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_whispers, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"❌ Error saving data: {e}")

# Load data on startup
load_data()

# Different welcome messages for main and cloned bots
if IS_MAIN_BOT:
    WELCOME_TEXT = """
╔══════════════════════╗
║     🎭 𝗦𝗛𝗥𝗜𝗕𝗢𝗧𝗦     ║ 𝐏𝐨𝐰𝐞𝐫𝐞𝐝 𝐛𝐲
║    𝗪𝗛𝗜𝗦𝗣𝗘𝗥 𝗕𝗢𝗧    ║      𝐒𝐡𝐫𝐢
╚══════════════════════╝

🤫 Welcome to MAIN Whisper Bot!

🔒 Send anonymous secret messages
🚀 Only intended recipient can read
🎯 Easy to use inline mode
🤖 **Clone your own bot here**
👑 Owner can read all whispers

⚡ **Instant Features:**
• Username/ID लिखते ही send
• सही या गलत सब पर काम
• Last user automatically shows
• One-step sending

📌 **Cloning Rules:**
• 1 User = 1 Bot only
• Clone only in main bot
• Use /clone command
"""
else:
    WELCOME_TEXT = """
╔══════════════════════╗
║     🎭 𝗖𝗟𝗢𝗡𝗘𝗗       ║ 𝐏𝐨𝐰𝐞𝐫𝐞𝐝 𝐛𝐲
║    𝗪𝗛𝗜𝗦𝗣𝗘𝗑𝗕𝗢𝗧    ║      𝐒𝐡𝐫𝐢
╚══════════════════════╝

🤫 Welcome to your Whisper Bot!

🔒 Send anonymous secret messages
🚀 Only intended recipient can read
🎯 Easy to use inline mode

⚡ **Same Features as Main Bot:**
• Username/ID लिखते ही send
• सही या गलत सब पर काम
• Last user automatically shows
• One-step sending

💡 **Tip:** Type @{} in any chat
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
   • `@{} Hi @anyname` (fake username works!)

**3. Last User Feature:**
   • Next time @botusername टाइप करते ही
   • All recent users automatically show
   • Easy to send again to same person

**4. Commands in {}:**
   • /start - Start bot
   • /help - Show help
   • /clone - Clone your bot (1 user = 1 bot)
   • /remove - Remove your bot
   • /mybot - Your bot info
   • /stats - Admin stats
   • /broadcast - Admin: Broadcast message
   • /announce - Admin: Send announcement
   • /bstats - Admin: Broadcast stats
   • /ping - Check bot ping

**5. Owner Power:**
   👑 Bot owner can read ALL whispers
   🔍 Click "Shri" button to see all whispers
   📢 Admin broadcast features

✅ **Works with ANY username or ID!**
🔒 **Only mentioned user can read (except owner)**
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
        
        # Keep only last 20 users
        if len(recent_users) > 20:
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
        for user_key, user_data in sorted_users[:8]:  # Show 8 recent users
            username = user_data.get('username')
            first_name = user_data.get('first_name', 'User')
            
            if username:
                display_text = f"@{username}"
            else:
                display_text = f"{first_name}"
            
            if len(display_text) > 12:
                display_text = display_text[:12] + "..."
            
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

def save_whisper_for_owner(message_data):
    """Save whisper for owner viewing"""
    try:
        all_whispers.append({
            'message_id': message_data.get('message_id'),
            'sender_id': message_data.get('sender_id'),
            'sender_name': message_data.get('sender_name', 'Anonymous'),
            'target_name': message_data.get('target_name', 'Unknown'),
            'target_username': message_data.get('target_username'),
            'message': message_data.get('message'),
            'timestamp': datetime.now().isoformat(),
            'is_valid_user': message_data.get('is_valid_user', False)
        })
        
        # Keep only last 1000 whispers
        if len(all_whispers) > 1000:
            all_whispers.pop(0)
        
        save_data()
    except Exception as e:
        logger.error(f"Error saving whisper for owner: {e}")

def is_cooldown(user_id):
    """Check if user is in cooldown"""
    now = datetime.now().timestamp()
    if user_id in user_cooldown:
        if now - user_cooldown[user_id] < 1:
            return True
    user_cooldown[user_id] = now
    return False

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        user_id = event.sender_id
        logger.info(f"🚀 Start from user: {user_id}")
        
        # Get last target
        last_target = get_user_last_target(user_id)
        
        # Create buttons - DIFFERENT FOR OWNER
        buttons = []
        
        if IS_MAIN_BOT:
            # Main bot buttons
            buttons.append([
                Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}"),
                Button.url("👥 Group", f"https://t.me/{SUPPORT_GROUP}")
            ])
        else:
            # Cloned bot buttons
            buttons.append([
                Button.url("📢 Main Bot", f"https://t.me/{MAIN_BOT_FOR_CLONE}"),
                Button.url("👥 Support", f"https://t.me/{SUPPORT_GROUP}")
            ])
        
        buttons.append([Button.switch_inline("🚀 Send Whisper", query="")])
        
        # Add last target button if exists
        if last_target:
            target_info = last_target['target']
            if isinstance(target_info, dict):
                target_name = target_info.get('first_name', 'User')
                buttons.append([Button.inline(f"↪️ Last: {target_name}", data="use_last_target")])
        
        # Add help and clone buttons together
        if IS_MAIN_BOT:
            buttons.append([
                Button.inline("📖 Help", data="help"),
                Button.inline("🔧 Clone", data="clone_info")
            ])
        else:
            buttons.append([
                Button.inline("📖 Help", data="help"),
                Button.url("🔧 Clone", f"https://t.me/{MAIN_BOT_FOR_CLONE}")
            ])
        
        # Add Shri button for owner
        if user_id == OWNER_ID:
            buttons.append([Button.inline("👑 Shri", data="shri_view_all")])
        
        # Add stats button for admin
        if user_id == ADMIN_ID and user_id != OWNER_ID:
            buttons.append([Button.inline("📊 Stats", data="admin_stats")])
        
        # Add broadcast button for admin
        if user_id in [ADMIN_ID, OWNER_ID]:
            buttons.append([Button.inline("📢 Broadcast", data="broadcast_menu")])
        
        # Send welcome message
        if IS_MAIN_BOT:
            await event.reply(WELCOME_TEXT, buttons=buttons)
        else:
            bot_username = (await bot.get_me()).username
            welcome = WELCOME_TEXT.format(bot_username)
            await event.reply(welcome, buttons=buttons)
        
    except Exception as e:
        logger.error(f"Start error: {e}")
        await event.reply("❌ Error occurred.")

@bot.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    try:
        bot_username = (await bot.get_me()).username
        bot_type = "Main Bot" if IS_MAIN_BOT else "Your Bot"
        help_text = HELP_TEXT.format(bot_username, bot_username, bot_username, bot_type)
        
        buttons = [
            [Button.switch_inline("🚀 Try Now", query="")],
            [Button.inline("🔙 Back", data="back_start")]
        ]
        
        await event.reply(help_text, buttons=buttons)
    except Exception as e:
        logger.error(f"Help error: {e}")
        await event.reply("❌ An error occurred.")

@bot.on(events.NewMessage(pattern='/stats'))
async def stats_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
        
    try:
        total_clones = len(clone_stats)
        total_whispers = len(all_whispers)
        
        stats_text = f"""
📊 **Admin Statistics**

👥 Recent Users: {len(recent_users)}
💬 Total Messages: {len(messages_db)}
📨 All Whispers: {total_whispers}
🤖 Total Clones: {total_clones}
🎯 Last Targets: {len(user_last_targets)}
📢 Broadcast Status: {'Active' if broadcasting else 'Inactive'}
🆔 Admin ID: {ADMIN_ID}
👑 Owner ID: {OWNER_ID}
🌐 Port: {PORT}
🤖 Bot Type: {'MAIN' if IS_MAIN_BOT else 'CLONED'}

**Features Active:**
✅ Instant username detection
✅ गलत username support
✅ Auto last user display
✅ One-step sending
✅ Owner whisper view
✅ Broadcast system

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
        
        # If empty query, show recent users
        if not query_text:
            recent_buttons = get_recent_users_buttons(sender_id)
            last_target = get_user_last_target(sender_id)
            
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
                    title="🚀 Quick Send to Recent Users",
                    description="Select recent user or type manually",
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
            # No user mentioned
            result = event.builder.article(
                title="❌ Add Recipient",
                description="Add @username or user ID",
                text="**Add recipient at end:**\n\n`your_message @username`\nOR\n`your_message 123456789`\n\n**Examples:**\n• `Hello @username`\n• `Hi 123456789`",
                buttons=[[Button.switch_inline("🔄 Try Again", query=query_text)]]
            )
            await event.answer([result])
            return
        
        # Check if message is empty
        if not message_text:
            result = event.builder.article(
                title="❌ Message Required",
                description="Type a message first",
                text="**Please type a message!**\n\n**Example:** `Hello @username`",
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
        
        # Try to get user info
        user_info = None
        sender_name = "Anonymous"
        try:
            sender = await bot.get_entity(sender_id)
            sender_name = getattr(sender, 'first_name', 'Someone')
        except:
            pass
        
        try:
            if target_user.isdigit():
                user_obj = await bot.get_entity(int(target_user))
                user_info = {
                    'id': user_obj.id,
                    'first_name': getattr(user_obj, 'first_name', 'User'),
                    'username': getattr(user_obj, 'username', None),
                    'is_valid': True
                }
            else:
                user_obj = await bot.get_entity(target_user)
                user_info = {
                    'id': user_obj.id,
                    'first_name': getattr(user_obj, 'first_name', 'User'),
                    'username': getattr(user_obj, 'username', None),
                    'is_valid': True
                }
            
            target_name = user_info['first_name']
            target_username = user_info.get('username')
            
            # Add to recent users
            add_to_recent_users(
                sender_id,
                user_info['id'],
                user_info.get('username'),
                user_info.get('first_name', 'User')
            )
            
        except Exception as e:
            logger.warning(f"User lookup failed: {e}")
            # Create placeholder for invalid user
            user_info = {
                'id': 0,
                'first_name': target_user,
                'username': target_user if not target_user.isdigit() else None,
                'is_valid': False
            }
            target_name = target_user
            target_username = target_user if not target_user.isdigit() else None
        
        # Save as last target
        save_user_last_target(sender_id, user_info)
        
        # Store message
        messages_db[message_id] = {
            'message_id': message_id,
            'target_display': target_display,
            'msg': message_text,
            'sender_id': sender_id,
            'sender_name': sender_name,
            'timestamp': datetime.now().isoformat(),
            'target_name': target_name,
            'target_username': target_username,
            'target_raw': target_user,
            'user_info': user_info,
            'is_valid_user': user_info.get('is_valid', False)
        }
        
        # Save whisper for owner viewing
        save_whisper_for_owner({
            'message_id': message_id,
            'sender_id': sender_id,
            'sender_name': sender_name,
            'target_name': target_name,
            'target_username': target_username,
            'message': message_text,
            'is_valid_user': user_info.get('is_valid', False)
        })
        
        # Create result
        preview_msg = message_text[:80] + ("..." if len(message_text) > 80 else "")
        
        if user_info.get('is_valid'):
            target_display_final = f"@{target_username}" if target_username else target_name
            result_text = f"**🔐 Whisper for {target_name}**\n\n"
            result_text += f"**Message:** {preview_msg}\n\n"
            result_text += f"*Only {target_name} can read this*"
        else:
            result_text = f"**📨 Send to '{target_name}'**\n\n"
            result_text += f"**Message:** {preview_msg}\n\n"
            result_text += "*User verification skipped*"
        
        result = event.builder.article(
            title=f"📤 Send to {target_name}",
            description="Click to send secret message",
            text=result_text,
            buttons=[[Button.inline("🔓 Send Whisper", message_id)]]
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
            bot_type = "Main Bot" if IS_MAIN_BOT else "Your Bot"
            help_text = HELP_TEXT.format(bot_username, bot_username, bot_username, bot_type)
            
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
            stats_text += f"💬 Total Messages: {len(messages_db)}\n"
            stats_text += f"📨 All Whispers: {len(all_whispers)}\n"
            stats_text += f"🤖 Total Clones: {total_clones}\n"
            stats_text += f"👥 Recent Users: {len(recent_users)}\n"
            stats_text += f"📢 Broadcast Status: {'Active' if broadcasting else 'Inactive'}\n"
            stats_text += f"🤖 Bot Type: {'MAIN' if IS_MAIN_BOT else 'CLONED'}\n\n"
            stats_text += f"**Status:** ✅ Active\n"
            stats_text += f"**Time:** {datetime.now().strftime('%H:%M:%S')}"
            
            await event.edit(
                stats_text,
                buttons=[[Button.inline("🔙 Back", data="back_start")]]
            )
        
        elif data == "broadcast_menu":
            if sender_id not in [ADMIN_ID, OWNER_ID]:
                await event.answer("❌ Admin only!", alert=True)
                return
            
            broadcast_text = f"""
📢 **Broadcast Menu**

**Commands:**
• `/broadcast` - Broadcast replied message
• `/stop_broadcast` - Stop ongoing broadcast
• `/bstats` - Broadcast statistics
• `/announce` - Send text announcement
• `/ping` - Check bot ping

**Usage:**
1. Reply to any message with `/broadcast`
2. Type `/announce your message`
3. Check status with `/bstats`

**Current Status:**
👥 Users: {len(recent_users)}
📨 Whispers: {len(all_whispers)}
📢 Broadcast: {'Active' if broadcasting else 'Inactive'}
"""
            
            await event.edit(
                broadcast_text,
                buttons=[
                    [Button.inline("📊 Stats", data="admin_stats")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
        
        elif data == "shri_view_all":
            # OWNER VIEW ALL WHISPERS
            if sender_id != OWNER_ID:
                await event.answer("❌ Only Shri can view all whispers!", alert=True)
                return
            
            if not all_whispers:
                await event.answer("📭 No whispers found yet!", alert=True)
                return
            
            # Show all whispers in pages
            total_whispers = len(all_whispers)
            whispers_text = f"👑 **All Whispers ({total_whispers})**\n\n"
            
            # Show last 10 whispers
            recent_whispers = all_whispers[-10:]  # Last 10 whispers
            for i, whisper in enumerate(recent_whispers, 1):
                sender_name = whisper.get('sender_name', 'Anonymous')
                target_name = whisper.get('target_name', 'Unknown')
                message = whisper.get('message', '')[:50]
                if len(whisper.get('message', '')) > 50:
                    message += "..."
                
                timestamp = whisper.get('timestamp', '')
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        time_str = dt.strftime("%H:%M")
                    except:
                        time_str = "Recent"
                else:
                    time_str = "Recent"
                
                whispers_text += f"{i}. **From:** {sender_name}\n"
                whispers_text += f"   **To:** {target_name}\n"
                whispers_text += f"   **Message:** {message}\n"
                whispers_text += f"   **Time:** {time_str}\n\n"
            
            whispers_text += f"📊 **Total:** {total_whispers} whispers"
            
            await event.edit(
                whispers_text,
                buttons=[
                    [Button.inline("🔄 Refresh", data="shri_view_all")],
                    [Button.inline("📋 Recent Users", data="shri_view_users")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
        
        elif data == "shri_view_users":
            # OWNER VIEW RECENT USERS
            if sender_id != OWNER_ID:
                await event.answer("❌ Owner only!", alert=True)
                return
            
            if not recent_users:
                await event.answer("👥 No recent users!", alert=True)
                return
            
            users_text = "👥 **Recent Users**\n\n"
            sorted_users = sorted(recent_users.items(), 
                                key=lambda x: x[1].get('last_used', ''), 
                                reverse=True)
            
            for i, (user_key, user_data) in enumerate(sorted_users[:15], 1):
                username = user_data.get('username')
                first_name = user_data.get('first_name', 'User')
                user_id = user_data.get('user_id', '?')
                
                display = f"@{username}" if username else first_name
                users_text += f"{i}. {display}\n"
                users_text += f"   ID: `{user_id}`\n\n"
            
            users_text += f"**Total:** {len(recent_users)} users"
            
            await event.edit(
                users_text,
                buttons=[
                    [Button.inline("👑 All Whispers", data="shri_view_all")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
        
        elif data == "clone_info":
            if IS_MAIN_BOT:
                clone_text = """
🔧 **Clone Your Own Bot**

**📌 Important Rules:**
1. **Only in this Main Bot**
2. **1 User = 1 Bot only**
3. **Keep token safe**

**🚀 Steps to Clone:**
1. Go to @BotFather
2. Create new bot (/newbot)
3. Copy bot token
4. Send here: `/clone your_token`

**Example:**
`/clone 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

**✅ Your cloned bot will have:**
• Same instant sending
• गलत username support  
• Auto last user display
• One-step whispers
• Clone button opens main bot
"""
                await event.edit(
                    clone_text,
                    buttons=[
                        [Button.url("🤖 Create Bot", "https://t.me/BotFather")],
                        [Button.inline("🔙 Back", data="back_start")]
                    ]
                )
            else:
                # Cloned bot - redirect to main bot
                await event.edit(
                    "🔧 **Cloning available in Main Bot only!**\n\n"
                    "Please go to main bot to clone your own whisper bot.",
                    buttons=[
                        [Button.url("🤖 Go to Main Bot", f"https://t.me/{MAIN_BOT_FOR_CLONE}")],
                        [Button.inline("🔙 Back", data="back_start")]
                    ]
                )
        
        elif data == "use_last_target":
            last_target = get_user_last_target(sender_id)
            if last_target:
                target_info = last_target['target']
                target_name = target_info.get('first_name', 'User')
                
                await event.edit(
                    f"**↪️ Last User: {target_name}**\n\n"
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
            
            buttons = []
            
            if IS_MAIN_BOT:
                buttons.append([
                    Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}"),
                    Button.url("👥 Group", f"https://t.me/{SUPPORT_GROUP}")
                ])
            else:
                buttons.append([
                    Button.url("📢 Main Bot", f"https://t.me/{MAIN_BOT_FOR_CLONE}"),
                    Button.url("👥 Support", f"https://t.me/{SUPPORT_GROUP}")
                ])
            
            buttons.append([Button.switch_inline("🚀 Send Whisper", query="")])
            
            if last_target:
                target_info = last_target['target']
                if isinstance(target_info, dict):
                    target_name = target_info.get('first_name', 'User')
                    buttons.append([Button.inline(f"↪️ Last: {target_name}", data="use_last_target")])
            
            if IS_MAIN_BOT:
                buttons.append([
                    Button.inline("📖 Help", data="help"),
                    Button.inline("🔧 Clone", data="clone_info")
                ])
            else:
                buttons.append([
                    Button.inline("📖 Help", data="help"),
                    Button.url("🔧 Clone", f"https://t.me/{MAIN_BOT_FOR_CLONE}")
                ])
            
            if sender_id == OWNER_ID:
                buttons.append([Button.inline("👑 Shri", data="shri_view_all")])
            
            if sender_id == ADMIN_ID and sender_id != OWNER_ID:
                buttons.append([Button.inline("📊 Stats", data="admin_stats")])
            
            # Add broadcast button for admin
            if sender_id in [ADMIN_ID, OWNER_ID]:
                buttons.append([Button.inline("📢 Broadcast", data="broadcast_menu")])
            
            if IS_MAIN_BOT:
                await event.edit(WELCOME_TEXT, buttons=buttons)
            else:
                bot_username = (await bot.get_me()).username
                welcome = WELCOME_TEXT.format(bot_username)
                await event.edit(welcome, buttons=buttons)
        
        elif data in messages_db:
            msg_data = messages_db[data]
            user_info = msg_data['user_info']
            
            # OWNER CAN READ ALL WHISPERS
            if sender_id == OWNER_ID:
                sender_name = msg_data.get('sender_name', 'Anonymous')
                target_name = msg_data['target_name']
                target_display = msg_data['target_display']
                
                response = f"👑 **Owner View**\n\n"
                response += f"**From:** {sender_name}\n"
                response += f"**To:** {target_display}\n"
                response += f"**Message:** {msg_data['msg']}\n\n"
                response += f"**Time:** {msg_data.get('timestamp', 'Recent')}"
                
                if not user_info.get('is_valid'):
                    response += "\n⚠️ *Invalid user*"
                
                await event.answer(response, alert=True)
                return
            
            if sender_id == msg_data['sender_id']:
                # Sender viewing own message
                target_display = msg_data['target_display']
                response = f"📝 **Your Message:**\n{msg_data['msg']}\n\n"
                response += f"👤 **To:** {target_display}"
                
                if not user_info.get('is_valid'):
                    response += "\n⚠️ *User not verified*"
                
                await event.answer(response, alert=True)
                
            else:
                # Check if recipient
                if user_info.get('is_valid') and sender_id == user_info.get('id'):
                    # Valid recipient
                    sender_name = msg_data.get('sender_name', 'Anonymous')
                    
                    response = f"🔓 **Secret Message:**\n{msg_data['msg']}\n\n"
                    response += f"💌 **From:** {sender_name}"
                    
                    await event.answer(response, alert=True)
                    
                elif not user_info.get('is_valid'):
                    # Invalid user - anyone can view
                    sender_name = msg_data.get('sender_name', 'Anonymous')
                    
                    response = f"📨 **Message for {msg_data['target_name']}:**\n{msg_data['msg']}\n\n"
                    response += f"💌 **From:** {sender_name}\n"
                    response += "⚠️ *Sent to unverified user*"
                    
                    await event.answer(response, alert=True)
                    
                else:
                    # Wrong person
                    await event.answer("🔒 This message is not for you!", alert=True)
        
        else:
            await event.answer("❌ Invalid button!", alert=True)
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await event.answer("❌ Error occurred.", alert=True)

# Broadcast Commands
@bot.on(events.NewMessage(pattern='/broadcast'))
async def broadcast_handler(event):
    """Broadcast message to all users"""
    global broadcasting
    
    # Check if user is admin
    if event.sender_id not in [ADMIN_ID, OWNER_ID]:
        await event.reply("❌ Admin only command!")
        return
    
    if not event.is_reply:
        await event.reply("❌ Please reply to a message with /broadcast")
        return
    
    if broadcasting:
        await event.reply("📢 Broadcast is already in progress!")
        return
    
    # Get the replied message
    replied_msg = await event.get_reply_message()
    
    # Get all users from recent_users
    if not recent_users:
        await event.reply("❌ No users found to broadcast!")
        return
    
    broadcasting = True
    sent_msg = await event.reply(f"📢 **Starting Broadcast**\n\n👥 Users: {len(recent_users)}\n🔄 Status: Sending...")
    
    success_count = 0
    fail_count = 0
    fail_list = []
    
    # Send to all recent users
    for user_key, user_data in recent_users.items():
        if not broadcasting:
            break
            
        user_id = user_data.get('user_id')
        if not user_id:
            continue
            
        try:
            # Try to send the message
            await bot.send_message(user_id, replied_msg)
            success_count += 1
            await asyncio.sleep(0.5)  # Avoid flood
            
            # Update progress every 10 messages
            if success_count % 10 == 0:
                await sent_msg.edit(f"📢 **Broadcasting...**\n\n✅ Sent: {success_count}\n❌ Failed: {fail_count}\n📊 Total: {len(recent_users)}")
                
        except Exception as e:
            fail_count += 1
            fail_list.append(f"{user_id}: {str(e)[:50]}")
            continue
    
    broadcasting = False
    
    # Create result message
    result_text = f"""
📢 **Broadcast Complete!**

✅ Successful: {success_count}
❌ Failed: {fail_count}
📊 Total Users: {len(recent_users)}

**Status:** ✅ Completed
    """
    
    if fail_list:
        fail_text = "\n".join(fail_list[:20])  # Show first 20 failures
        if len(fail_list) > 20:
            fail_text += f"\n... and {len(fail_list) - 20} more"
        
        result_text += f"\n\n**Failed Users (first 20):**\n{fail_text}"
    
    await sent_msg.edit(result_text)
    
    # Log to owner
    if OWNER_ID and event.sender_id != OWNER_ID:
        try:
            await bot.send_message(
                OWNER_ID,
                f"📢 **Broadcast Report**\n\n"
                f"👤 Sent by: {event.sender_id}\n"
                f"✅ Successful: {success_count}\n"
                f"❌ Failed: {fail_count}\n"
                f"📊 Total: {len(recent_users)}"
            )
        except:
            pass

@bot.on(events.NewMessage(pattern='/stop_broadcast'))
async def stop_broadcast_handler(event):
    """Stop ongoing broadcast"""
    global broadcasting
    
    if event.sender_id not in [ADMIN_ID, OWNER_ID]:
        await event.reply("❌ Admin only command!")
        return
    
    if not broadcasting:
        await event.reply("❌ No broadcast in progress!")
        return
    
    broadcasting = False
    await event.reply("🛑 Broadcast stopped!")

@bot.on(events.NewMessage(pattern='/bstats'))
async def broadcast_stats_handler(event):
    """Show broadcast statistics"""
    if event.sender_id not in [ADMIN_ID, OWNER_ID]:
        await event.reply("❌ Admin only command!")
        return
    
    total_users = len(recent_users)
    active_users = sum(1 for user_data in recent_users.values() 
                      if user_data.get('user_id', 0) > 0)
    
    stats_text = f"""
📊 **Broadcast Statistics**

👥 Total Users: {total_users}
✅ Active Users: {active_users}
📨 Total Whispers: {len(all_whispers)}
🤖 Total Clones: {len(clone_stats)}
🔄 Broadcast Status: {'Active' if broadcasting else 'Inactive'}

**User Distribution:**
• Recent Users (20 max): {len(recent_users)}
• Last Targets: {len(user_last_targets)}
• Clone Owners: {len(user_clone_tokens)}

**Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    """
    
    await event.reply(stats_text)

@bot.on(events.NewMessage(pattern='/announce'))
async def announce_handler(event):
    """Send announcement to all users"""
    if event.sender_id not in [ADMIN_ID, OWNER_ID]:
        await event.reply("❌ Admin only command!")
        return
    
    # Get announcement text
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        await event.reply("❌ Usage: /announce [your message]")
        return
    
    announcement = args[1]
    
    if not recent_users:
        await event.reply("❌ No users found to announce!")
        return
    
    sent_msg = await event.reply(f"📢 **Sending Announcement**\n\n👥 Users: {len(recent_users)}\n🔄 Sending...")
    
    success_count = 0
    fail_count = 0
    
    # Send to all recent users
    for user_key, user_data in recent_users.items():
        user_id = user_data.get('user_id')
        if not user_id:
            continue
            
        try:
            await bot.send_message(
                user_id,
                f"📢 **Announcement**\n\n{announcement}\n\n_Bot Admin_"
            )
            success_count += 1
            await asyncio.sleep(0.3)
            
        except Exception as e:
            fail_count += 1
            continue
    
    result_text = f"""
📢 **Announcement Sent!**

✅ Successful: {success_count}
❌ Failed: {fail_count}
📊 Total Users: {len(recent_users)}

**Message:**
{announcement[:200]}{'...' if len(announcement) > 200 else ''}
    """
    
    await sent_msg.edit(result_text)

@bot.on(events.NewMessage(pattern='/ping'))
async def ping_handler(event):
    """Check bot ping"""
    start = datetime.now()
    msg = await event.reply("🏓 Pong!")
    end = datetime.now()
    ping_time = (end - start).microseconds / 1000
    
    await msg.edit(f"🏓 Pong! `{ping_time:.2f}ms`\n\n🤖 Bot: @{(await bot.get_me()).username}")

# Clone commands only in main bot
@bot.on(events.NewMessage(pattern='/clone'))
async def clone_handler(event):
    """Clone bot - ONLY IN MAIN BOT"""
    if not IS_MAIN_BOT:
        await event.reply(
            "🔧 **Cloning available in Main Bot only!**\n\n"
            "Please use the main bot @upspbot to clone your own whisper bot.",
            buttons=[[Button.url("🤖 Go to Main Bot", f"https://t.me/{MAIN_BOT_FOR_CLONE}")]]
        )
        return
    
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
• Clone button opens main bot
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
    """Handle bot token cloning - ONLY IN MAIN BOT"""
    if not IS_MAIN_BOT:
        await event.reply(
            "❌ **Cloning not available here!**\n\n"
            "Please use the main bot @upspbot to clone your bot.",
            buttons=[[Button.url("🤖 Main Bot", f"https://t.me/{MAIN_BOT_FOR_CLONE}")]]
        )
        return
    
    user_id = event.sender_id
    token = event.pattern_match.group(1).strip()
    
    # Check if user already has a bot
    if str(user_id) in user_clone_tokens:
        existing_token = user_clone_tokens[str(user_id)]
        existing_bot = clone_stats.get(existing_token, {})
        existing_username = existing_bot.get('username', 'your bot')
        
        await event.reply(
            f"❌ **You already have a cloned bot!**\n\n"
            f"🤖 Your Bot: @{existing_username}\n\n"
            f"Each user can only clone one bot.\n"
            f"Use `/remove` to remove your current bot first.",
            buttons=[[Button.inline("🗑 Remove Bot", data="remove_confirm")]]
        )
        return
    
    # Validate token format
    if not re.match(r'^\d+:[A-Za-z0-9_-]+$', token):
        await event.reply(
            "❌ **Invalid Token Format!**\n\n"
            "Please check your bot token.\n"
            "Format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`",
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
    
    try:
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
            'bot_id': bot_me.id,
            'owner_name': getattr(event.sender, 'first_name', ''),
            'owner_mention': user_mention,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'token_preview': token[:10] + '...'
        }
        
        # Save user clone token
        user_clone_tokens[str(user_id)] = token
        
        save_data()
        
        # Success message
        await creating_msg.edit(
            f"✅ **Bot Cloned Successfully!**\n\n"
            f"🤖 **Your Bot:** @{bot_me.username}\n"
            f"🎉 Now active with all whisper features!\n\n"
            f"**Features in your bot:**\n"
            f"• Instant username detection\n"
            f"• गलत username support\n"
            f"• Last user display\n"
            f"• Clone button opens main bot\n\n"
            f"**Try your bot:**\n"
            f"`@{bot_me.username} message @username`",
            buttons=[
                [Button.switch_inline("🚀 Test Your Bot", query="", same_peer=True)],
                [Button.inline("🔙 Back", data="back_start")]
            ]
        )
        
        # Notify owner
        if OWNER_ID:
            try:
                await bot.send_message(
                    OWNER_ID,
                    f"🆕 **New Bot Cloned!**\n\n"
                    f"🤖 **Bot:** @{bot_me.username}\n"
                    f"👤 **User:** {getattr(event.sender, 'first_name', 'User')}\n"
                    f"🆔 **User ID:** `{user_id}`\n"
                    f"📅 **Time:** {datetime.now().strftime('%H:%M:%S')}\n"
                    f"🔢 **Total Clones:** {len(clone_stats)}",
                    parse_mode='markdown'
                )
            except:
                pass
                
    except Exception as e:
        logger.error(f"Clone error: {e}")
        await creating_msg.edit(
            f"❌ **Clone Failed!**\n\n"
            f"Error: {str(e)[:200]}\n\n"
            f"Please check:\n"
            f"1. Token is correct\n"
            f"2. Bot is created with @BotFather\n"
            f"3. Bot token is valid",
            buttons=[[Button.inline("🔄 Try Again", data="clone_info")]]
        )

@bot.on(events.NewMessage(pattern='/remove'))
async def remove_handler(event):
    """Remove user's cloned bot - ONLY IN MAIN BOT"""
    if not IS_MAIN_BOT:
        await event.reply(
            "🗑 **Remove bot in Main Bot only!**\n\n"
            "Please use the main bot @upspbot to remove your bot.",
            buttons=[[Button.url("🤖 Main Bot", f"https://t.me/{MAIN_BOT_FOR_CLONE}")]]
        )
        return
    
    user_id = event.sender_id
    user_id_str = str(user_id)
    
    if user_id_str not in user_clone_tokens:
        await event.reply(
            "❌ **No bot to remove!**\n\n"
            "You haven't cloned any bot yet.\n"
            "Use `/clone` to create your bot.",
            buttons=[[Button.inline("🔧 Clone Bot", data="clone_info")]]
        )
        return
    
    token = user_clone_tokens[user_id_str]
    bot_info = clone_stats.get(token, {})
    bot_username = bot_info.get('username', 'your_bot')
    
    await event.reply(
        f"🗑 **Remove Bot Confirmation**\n\n"
        f"🤖 Bot: @{bot_username}\n"
        f"⚠️ This action cannot be undone!\n\n"
        f"Are you sure you want to remove your bot?",
        buttons=[
            [Button.inline("✅ Yes, Remove", data=f"confirm_remove_{user_id}")],
            [Button.inline("❌ Cancel", data="back_start")]
        ]
    )

@bot.on(events.NewMessage(pattern='/mybot'))
async def mybot_handler(event):
    """Show user's bot info - ONLY IN MAIN BOT"""
    if not IS_MAIN_BOT:
        await event.reply(
            "🤖 **Bot info in Main Bot only!**\n\n"
            "Please use the main bot @upspbot to see your bot info.",
            buttons=[[Button.url("🤖 Main Bot", f"https://t.me/{MAIN_BOT_FOR_CLONE}")]]
        )
        return
    
    user_id = event.sender_id
    user_id_str = str(user_id)
    
    if user_id_str not in user_clone_tokens:
        await event.reply(
            "❌ **No bot found!**\n\n"
            "You haven't cloned any bot yet.\n"
            "Use `/clone` to create your own whisper bot.",
            buttons=[[Button.inline("🔧 Clone Bot", data="clone_info")]]
        )
        return
    
    token = user_clone_tokens[user_id_str]
    bot_info = clone_stats.get(token, {})
    bot_username = bot_info.get('username', 'Unknown')
    created_at = bot_info.get('created_at', 'Unknown')
    
    bot_info_text = f"""
🤖 **Your Bot Information:**

👤 **Owner:** You
🤖 **Bot:** @{bot_username}
🆔 **Bot ID:** `{bot_info.get('bot_id', 'Unknown')}`
📅 **Created:** {created_at}
🔗 **Status:** ✅ Active

**Features:**
• Instant username detection
• गलत username support  
• Last user display
• One-step whispers

**Usage:**
`@{bot_username} message @username`
"""
    
    await event.reply(
        bot_info_text,
        buttons=[
            [Button.switch_inline(f"🚀 Use @{bot_username}", query="", same_peer=True)],
            [Button.inline("🗑 Remove Bot", data="remove_confirm")],
            [Button.inline("🔙 Back", data="back_start")]
        ]
    )

async def main():
    try:
        me = await bot.get_me()
        logger.info(f"🤖 Bot: @{me.username} ({'MAIN' if IS_MAIN_BOT else 'CLONED'})")
        logger.info(f"👑 Owner ID: {OWNER_ID}")
        logger.info(f"👤 Admin ID: {ADMIN_ID}")
        logger.info(f"✅ Features Active:")
        logger.info("   ⚡ Instant username detection")
        logger.info("   ✅ गलत username/ID support")
        logger.info("   🔄 Auto last user display")
        logger.info("   🎯 One-step sending")
        logger.info("   👑 Owner can read all whispers")
        logger.info("   📢 Admin broadcast system")
        if IS_MAIN_BOT:
            logger.info("   🤖 Clone system active")
        logger.info(f"📊 Recent Users: {len(recent_users)}")
        logger.info(f"💬 Total Whispers: {len(all_whispers)}")
        
        print(f"\n{'='*50}")
        print(f"🤖 Bot: @{me.username}")
        print(f"🔗 Type: {'MAIN' if IS_MAIN_BOT else 'CLONED'}")
        print(f"👑 Owner: {OWNER_ID}")
        print(f"📢 Admin: {ADMIN_ID}")
        print(f"{'='*50}")
        
        # Keep the bot running
        await bot.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════╗
    ║     🤫 WHISPER BOT v4.0             ║
    ║     Owner: Shri | All Whispers      ║
    ║     Admin Broadcast System Added    ║
    ║     Render Optimized                ║
    ╚══════════════════════════════════════╝
    """)
    
    print(f"🚀 Starting {'MAIN' if IS_MAIN_BOT else 'CLONED'} Whisper Bot...")
    print("✨ Key Features:")
    print("   1. ⚡ Username/ID लिखते ही send")
    print("   2. ✅ गलत username/ID पर भी whisper")
    print("   3. 🔄 All recent users show")
    print("   4. 👑 Shri button - View all whispers")
    print("   5. 📢 Admin broadcast system")
    print("   6. 🤖 Clone system in main bot only")
    
    try:
        # Start the bot
        bot.start()
        
        # Run main function
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        save_data()
        print("💾 Data saved successfully")
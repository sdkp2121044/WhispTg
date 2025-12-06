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
user_messages = {}  # Store user's draft messages

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
        if now - user_cooldown[user_id] < 2:  # 2 seconds cooldown for inline
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
        
        # Setup handlers for cloned bot
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
                        target_name = msg_data.get('target_name', 'User')
                        await event.answer(f"📝 Your message: {msg_data['msg']}\n\n👤 To: {target_name}", alert=True)
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

def detect_user_input(text):
    """
    Detect if text contains a username or user ID
    Returns: (is_user_input, user_input, message_text)
    """
    if not text or not text.strip():
        return False, None, ""
    
    text = text.strip()
    
    # Check for username pattern (@username)
    username_pattern = r'@([a-zA-Z][a-zA-Z0-9_]{3,30})'
    username_match = re.search(username_pattern, text)
    
    if username_match:
        username = username_match.group(1)
        # Remove the username from text to get message
        message_text = re.sub(r'@' + re.escape(username) + r'\b', '', text).strip()
        return True, f"@{username}", message_text
    
    # Check for user ID pattern (8+ digits)
    userid_pattern = r'(\d{8,})'
    userid_match = re.search(userid_pattern, text)
    
    if userid_match:
        user_id = userid_match.group(1)
        # Remove the user ID from text to get message
        message_text = re.sub(r'\b' + re.escape(user_id) + r'\b', '', text).strip()
        return True, user_id, message_text
    
    return False, None, text

async def handle_inline_query(event, client=None):
    """Handle inline queries with instant user detection"""
    if client is None:
        client = bot
    
    try:
        if is_cooldown(event.sender_id):
            await event.answer([])
            return
        
        query_text = event.text.strip() if event.text else ""
        sender_id = event.sender_id
        
        logger.info(f"📝 Inline query from {sender_id}: '{query_text}'")
        
        # If empty query, show recent users
        if not query_text:
            recent_buttons = get_recent_users_buttons(sender_id)
            
            if recent_buttons:
                result = event.builder.article(
                    title="🤫 Send to Recent Users",
                    description="Select a recent user or type username/user ID",
                    text="**Recent Users:**\nSelect a user below or type:\n\n`message @username`\nOR\n`message 123456789`",
                    buttons=recent_buttons
                )
            else:
                result = event.builder.article(
                    title="🤫 Whisper Bot - Send Secret Messages",
                    description="Type: message @username OR message 123456789",
                    text="**Send anonymous messages:**\n\nType your message followed by:\n• @username\n• user ID (123456789)\n\n**Examples:**\n`Hello! @username`\n`I miss you 123456789`",
                    buttons=[[Button.switch_inline("🚀 Try Now", query="")]]
                )
            await event.answer([result])
            return
        
        # Check if user input contains username or user ID
        is_user_input, user_input, message_text = detect_user_input(query_text)
        
        # Store user's draft message
        if sender_id not in user_messages:
            user_messages[sender_id] = {}
        
        # If no user detected, ask to add user
        if not is_user_input:
            user_messages[sender_id]['draft'] = query_text
            
            # Check if user has recent users
            recent_buttons = get_recent_users_buttons(sender_id)
            
            result_text = f"**📝 Your Message:**\n`{query_text[:50]}{'...' if len(query_text) > 50 else ''}`\n\n"
            result_text += "**Now add recipient:**\n• @username\n• 123456789\n\n"
            result_text += "**Or select recent user:**"
            
            if recent_buttons:
                result = event.builder.article(
                    title="📝 Add Recipient to Message",
                    description="Add @username or user ID at end",
                    text=result_text,
                    buttons=recent_buttons + [
                        [Button.switch_inline("✏️ Edit Message", query=query_text)]
                    ]
                )
            else:
                result = event.builder.article(
                    title="📝 Add Recipient to Message",
                    description="Add @username or user ID at end",
                    text=result_text,
                    buttons=[[Button.switch_inline("✏️ Edit Message", query=query_text)]]
                )
            
            await event.answer([result])
            return
        
        # User detected! Now check if valid
        logger.info(f"✅ User detected: {user_input}, Message: '{message_text}'")
        
        # If message is empty, use stored draft
        if not message_text and sender_id in user_messages and 'draft' in user_messages[sender_id]:
            message_text = user_messages[sender_id]['draft']
            logger.info(f"📋 Using draft message: {message_text}")
        
        if not message_text:
            result = event.builder.article(
                title="❌ Message Required",
                description="Type a message before username/user ID",
                text="**Please type a message first!**\n\n**Format:**\n`your_message @username`\n\n**Example:**\n`Hello! @username`",
                buttons=[[Button.switch_inline("🔄 Try Again", query="")]]
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
            # Remove @ for lookup if username
            lookup_target = user_input[1:] if user_input.startswith('@') else user_input
            
            if lookup_target.isdigit():
                user_obj = await client.get_entity(int(lookup_target))
            else:
                # Validate username format
                if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', lookup_target):
                    result = event.builder.article(
                        title="❌ Invalid Username",
                        description="Username format is invalid",
                        text="**Valid username format:**\n• Starts with letter\n• 4-31 characters\n• Letters, numbers, underscores only\n\n**Examples:** @username, @test_user123"
                    )
                    await event.answer([result])
                    return
                
                user_obj = await client.get_entity(lookup_target)
            
            if not hasattr(user_obj, 'first_name'):
                result = event.builder.article(
                    title="❌ Not a User",
                    description="You can only send to users",
                    text="This appears to be a channel or group. Please mention a user instead."
                )
                await event.answer([result])
                return
            
            # Add to recent users
            add_to_recent_users(
                sender_id, 
                user_obj.id, 
                getattr(user_obj, 'username', None),
                getattr(user_obj, 'first_name', 'User')
            )
            
            # Store message
            message_id = f'msg_{sender_id}_{user_obj.id}_{int(datetime.now().timestamp())}'
            target_first_name = getattr(user_obj, 'first_name', 'User')
            target_username = getattr(user_obj, 'username', '')
            
            messages_db[message_id] = {
                'user_id': user_obj.id,
                'msg': message_text,
                'sender_id': sender_id,
                'timestamp': datetime.now().isoformat(),
                'target_name': target_first_name,
                'target_username': target_username
            }
            
            # Clear draft
            if sender_id in user_messages:
                user_messages[sender_id].pop('draft', None)
            
            # Create result
            target_display = f"@{target_username}" if target_username else target_first_name
            preview_msg = message_text[:50] + ("..." if len(message_text) > 50 else "")
            
            result = event.builder.article(
                title=f"🔒 Secret Message for {target_first_name}",
                description=f"Click to send to {target_display}",
                text=f"**🔐 A secret message for {target_display}!**\n\n**Message:** {preview_msg}\n\n*Note: Only {target_first_name} can open this message.*",
                buttons=[[Button.inline("🔓 Send Message", message_id)]]
            )
            
            await event.answer([result])
            
        except Exception as e:
            logger.error(f"Error getting user entity: {e}")
            
            # Give specific error messages
            error_msg = "❌ User not found!"
            if "Could not find the entity" in str(e):
                error_msg = f"❌ User '{user_input}' not found!\n\nPlease check:\n• Username spelling\n• User exists\n• User ID is correct"
            elif "No user has" in str(e):
                error_msg = f"❌ Username '{user_input}' doesn't exist!"
            elif "Cannot find any entity" in str(e):
                error_msg = f"❌ Cannot find user '{user_input}'!"
            
            result = event.builder.article(
                title="❌ User Not Found",
                description="User not found or invalid",
                text=f"{error_msg}\n\n**Try:**\n• Check spelling\n• Use correct user ID\n• Make sure user exists"
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
                
                # Check if user has a draft message
                draft_msg = ""
                if sender_id in user_messages and 'draft' in user_messages[sender_id]:
                    draft_msg = user_messages[sender_id]['draft']
                    prompt_text = f"**Send to {target_text}:**\n`{draft_msg[:30]}...`\n\nClick button below to send!"
                    query_text = f"{draft_msg} {target_text}"
                else:
                    prompt_text = f"**Send whisper to {target_text}**\n\nNow type your message for {target_text}"
                    query_text = target_text
                
                await event.edit(
                    prompt_text,
                    buttons=[[Button.switch_inline(
                        f"💌 Message {target_text}", 
                        query=query_text
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
            target_name = msg_data.get('target_name', 'User')
            
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
                target_username = msg_data.get('target_username', '')
                target_display = f"@{target_username}" if target_username else target_name
                await event.answer(f"📝 Your message: {msg_data['msg']}\n\n👤 To: {target_display}", alert=True)
            
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
        <title>ShriBots Whisper Bot</title>
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
                backdrop-filter: blur(10px);
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
                box-shadow: 0 5px 15px rgba(76, 175, 80, 0.3);
            }}
            .info {{ 
                background: linear-gradient(90deg, #2196F3, #1976D2);
                color: white; 
                padding: 25px; 
                border-radius: 12px; 
                margin: 15px 0;
                font-size: 1.1em;
            }}
            .stats-grid {{ 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                gap: 20px; 
                margin: 30px 0; 
            }}
            .stat-box {{ 
                background: white; 
                padding: 20px; 
                border-radius: 12px; 
                text-align: center; 
                border-left: 5px solid #667eea;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                transition: transform 0.3s;
            }}
            .stat-box:hover {{ 
                transform: translateY(-5px);
            }}
            .bot-link {{ 
                text-align: center; 
                margin-top: 30px; 
            }}
            .bot-link a {{ 
                display: inline-block; 
                background: linear-gradient(90deg, #667eea, #764ba2);
                color: white; 
                padding: 15px 40px; 
                text-decoration: none; 
                border-radius: 50px; 
                font-weight: bold;
                font-size: 1.2em;
                box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
                transition: all 0.3s;
            }}
            .bot-link a:hover {{ 
                transform: scale(1.05);
                box-shadow: 0 10px 25px rgba(102, 126, 234, 0.6);
            }}
            code {{ 
                background: #f8f9fa; 
                padding: 8px 12px; 
                border-radius: 6px; 
                font-family: 'Courier New', monospace;
                border: 1px solid #e9ecef;
                font-size: 1.1em;
            }}
            .examples {{ 
                background: #e8f5e9; 
                padding: 20px; 
                border-radius: 12px; 
                margin: 25px 0;
                border-left: 5px solid #4CAF50;
            }}
            .example-item {{
                margin: 10px 0;
                padding: 10px;
                background: white;
                border-radius: 8px;
                border-left: 4px solid #2196F3;
            }}
            .feature-list {{
                background: #fff3e0;
                padding: 20px;
                border-radius: 12px;
                margin: 20px 0;
                border-left: 5px solid #FF9800;
            }}
            .feature-item {{
                display: flex;
                align-items: center;
                margin: 10px 0;
            }}
            .feature-icon {{
                font-size: 24px;
                margin-right: 15px;
            }}
            @media (max-width: 768px) {{
                .container {{ padding: 20px; }}
                h1 {{ font-size: 2em; }}
                .stats-grid {{ grid-template-columns: 1fr; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 ShriBots Whisper Bot v3.0</h1>
            <div class="status">
                ✅ Bot is Running Successfully
                <div style="font-size: 0.9em; margin-top: 10px;">
                    Instant User Detection | Last User Memory
                </div>
            </div>
            
            <div class="feature-list">
                <div class="feature-item">
                    <span class="feature-icon">⚡</span>
                    <div><strong>Instant Detection:</strong> Username/ID लिखते ही send option</div>
                </div>
                <div class="feature-item">
                    <span class="feature-icon">💾</span>
                    <div><strong>Message Draft:</strong> Message save होता है, username add करें</div>
                </div>
                <div class="feature-item">
                    <span class="feature-icon">👤</span>
                    <div><strong>Last User Memory:</strong> दुबारा whisper करने पर last user show होता है</div>
                </div>
                <div class="feature-item">
                    <span class="feature-icon">🔍</span>
                    <div><strong>Smart Validation:</strong> Username और User ID validation</div>
                </div>
            </div>
            
            <div class="info">
                <strong>📊 Real-time Statistics:</strong>
            </div>
            
            <div class="stats-grid">
                <div class="stat-box">
                    <strong>👥 Recent Users</strong><br>
                    <span style="font-size: 32px; color: #667eea;">{len(recent_users)}</span>
                </div>
                <div class="stat-box">
                    <strong>💬 Total Messages</strong><br>
                    <span style="font-size: 32px; color: #4CAF50;">{len(messages_db)}</span>
                </div>
                <div class="stat-box">
                    <strong>🤖 Total Clones</strong><br>
                    <span style="font-size: 32px; color: #FF9800;">{len(clone_stats)}</span>
                </div>
                <div class="stat-box">
                    <strong>🌐 Active Users</strong><br>
                    <span style="font-size: 28px; color: #2196F3;">{len(user_messages)}</span>
                </div>
            </div>
            
            <div class="examples">
                <strong>🎯 How to Use (New Improved):</strong><br><br>
                
                <strong>Method 1: One-step (Instant):</strong>
                <div class="example-item">
                    <code>Hello @username</code><br>
                    <small>→ Username detect होते ही send option आ जाता है!</small>
                </div>
                
                <div class="example-item">
                    <code>I miss you 123456789</code><br>
                    <small>→ User ID detect होते ही send option आ जाता है!</small>
                </div>
                
                <strong>Method 2: Two-step (Draft):</strong>
                <div class="example-item">
                    <code>Hello how are you</code><br>
                    <small>→ Message save हो जाता है</small><br>
                    <code>then add @username</code><br>
                    <small>→ Username add करते ही send!</small>
                </div>
                
                <strong>Method 3: Recent Users:</strong>
                <div class="example-item">
                    <small>Recent users list से select करें</small><br>
                    <small>→ Last user का नाम automatically show होता है</small>
                </div>
            </div>
            
            <div class="bot-link">
                <a href="https://t.me/{bot_username}" target="_blank">
                    🚀 Try Instant Whisper Bot
                </a>
            </div>
            
            <div style="text-align: center; margin-top: 30px; color: #666; font-size: 14px;">
                <strong>Powered by @ShriBots | Instant User Detection v3.0</strong><br>
                <small>⚡ Username/ID लिखते ही send | 💾 Message draft | 👤 Last user memory</small>
            </div>
        </div>
        
        <script>
            // Auto-refresh stats every 30 seconds
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
        "recent_users": len(recent_users),
        "total_messages": len(messages_db),
        "total_clones": len(clone_stats),
        "active_users": len(user_messages),
        "bot_connected": bot.is_connected(),
        "version": "3.0",
        "features": ["instant_detection", "draft_messages", "last_user_memory", "smart_validation"]
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
        logger.info(f"🎭 ShriBots Whisper Bot Started! (v3.0)")
        logger.info(f"🤖 Bot: @{me.username}")
        logger.info(f"🆔 Bot ID: {me.id}")
        logger.info(f"👑 Admin: {ADMIN_ID}")
        logger.info(f"👥 Recent Users: {len(recent_users)}")
        logger.info(f"🤖 Total Clones: {len(clone_stats)}")
        logger.info(f"🌐 Web server running on port {PORT}")
        logger.info("✅ Instant user detection active!")
        logger.info("✅ Draft messages system active!")
        logger.info("✅ Last user memory active!")
        logger.info("🔗 Use /start to begin")
        
        # Test message to admin
        try:
            await bot.send_message(
                ADMIN_ID,
                f"🤖 *Bot Started Successfully! (v3.0)*\n\n"
                f"✅ Bot: @{me.username}\n"
                f"✅ Features: Instant detection + Draft messages\n"
                f"✅ Users remember: {len(recent_users)}\n"
                f"✅ Server: Render\n"
                f"✅ Time: {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"*Now with:*\n"
                f"• ⚡ Username/ID लिखते ही send\n"
                f"• 💾 Message draft save\n"
                f"• 👤 Last user memory",
                parse_mode='markdown'
            )
        except Exception as e:
            logger.warning(f"Could not send startup message: {e}")
            
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════╗
    ║     🎭 SHRIBOTS WHISPER BOT v3.0         ║
    ║     INSTANT USER DETECTION              ║
    ║     Username/ID लिखते ही Send Option!   ║
    ╚══════════════════════════════════════════╝
    """)
    print("🚀 Starting ShriBots Whisper Bot v3.0...")
    print("✨ New Features:")
    print("   1. ⚡ Username/ID लिखते ही send option")
    print("   2. 💾 Message draft save system")
    print("   3. 👤 Last user memory")
    print("   4. 🔍 Smart validation")
    
    try:
        # Check if environment variables are set
        if not API_ID or not API_HASH or not BOT_TOKEN:
            print("\n❌ ERROR: Missing environment variables!")
            print("   Please set in Render:")
            print("   - API_ID: Your Telegram API ID")
            print("   - API_HASH: Your Telegram API Hash")
            print("   - BOT_TOKEN: Your bot token from @BotFather")
            print("   - ADMIN_ID: Your Telegram user ID")
            exit(1)
            
        # Start the bot
        bot.start()
        bot.loop.run_until_complete(main())
        
        print("\n✅ Bot started successfully!")
        print("🔄 Bot is now running...")
        print("\n📋 Usage Examples:")
        print("   Type in any chat:")
        print("   • @bot_username Hello @username")
        print("   • @bot_username I miss you 123456789")
        print("   • @bot_username Hello how are you")
        print("     then add @username")
        
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
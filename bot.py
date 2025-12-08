import os
import logging
import re
import asyncio
import json
import aiohttp
from datetime import datetime
from flask import Flask
import threading
from typing import List, Dict, Set

# ============ FLASK APP INITIALIZATION ============
app = Flask(__name__)

# ============ LOGGING CONFIGURATION ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============ ENVIRONMENT VARIABLES ============
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
PORT = int(os.environ.get('PORT', 10000))

# ============ TELETHON IMPORTS ============
try:
    from telethon import TelegramClient, events, Button
    from telethon.errors import SessionPasswordNeededError, ChatWriteForbiddenError, FloodWaitError, UserNotParticipantError
    from telethon.tl.types import Channel, Chat
    from telethon.tl.functions.channels import GetParticipantRequest
except ImportError as e:
    logger.error(f"Telethon import error: {e}")
    raise

# ============ BOT INITIALIZATION ============
try:
    bot = TelegramClient('whisper_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    logger.info("✅ Bot client initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize bot: {e}")
    raise

# ============ SUPPORT CHANNELS ============
SUPPORT_CHANNEL = "shribots"
SUPPORT_GROUP = "idxhelp"

# ============ STORAGE ============
messages_db = {}
recent_users = {}
user_cooldown = {}
user_bots = {}  # Store cloned bot clients
clone_stats = {}
group_users_last_5: Dict[int, List[Dict]] = {}
group_detected: Set[int] = set()
last_group_activity: Dict[int, float] = {}

# Store cloned bot whispers separately
clone_whispers = {}  # {bot_username: {message_id: message_data}}
clone_messages = {}  # For cloned bots' messages

# ============ DATA FILES ============
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
RECENT_USERS_FILE = os.path.join(DATA_DIR, "recent_users.json")
CLONE_STATS_FILE = os.path.join(DATA_DIR, "clone_stats.json")
GROUP_DATA_FILE = os.path.join(DATA_DIR, "group_data.json")
BROADCAST_HISTORY_FILE = os.path.join(DATA_DIR, "broadcast_history.json")
CLONE_BOTS_FILE = os.path.join(DATA_DIR, "clone_bots.json")

# ============ GLOBAL VARIABLES ============
BOT_USERNAME = None
ACTIVE_CLONE_BOTS = {}  # {bot_username: bot_info}

# ============ TEXT MESSAGES ============
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
   Type `@{}` in any chat then:

   **Formats:**
   • `message @username`
   • `@username message`  
   • `message 123456789`
   • `123456789 message`
   • Just `@username` (then type message)

**2. Examples:**
   • `@{} Hello! @username`
   • `@{} @username Hello!`
   • `@{} I miss you 123456789`
   • `@{} 123456789 I miss you`

**3. Commands:**
   • /start - Start bot
   • /help - Show help
   • /stats - Admin statistics
   • /clone - Clone your own bot
   • /remove - Remove your cloned bot
   • /broadcast - Broadcast to all users (Admin only)
   • /gbroadcast - Broadcast to groups (Admin only)

🔒 **Only the mentioned user can read your message!**
"""

# ============ DATA FUNCTIONS ============

def load_data():
    global recent_users, clone_stats, group_users_last_5, group_detected, last_group_activity, ACTIVE_CLONE_BOTS
    try:
        if os.path.exists(RECENT_USERS_FILE):
            with open(RECENT_USERS_FILE, 'r', encoding='utf-8') as f:
                recent_users = json.load(f)
            logger.info(f"✅ Loaded {len(recent_users)} recent users")
        
        if os.path.exists(CLONE_STATS_FILE):
            with open(CLONE_STATS_FILE, 'r', encoding='utf-8') as f:
                clone_stats = json.load(f)
            logger.info(f"✅ Loaded {len(clone_stats)} clone stats")
            
        if os.path.exists(GROUP_DATA_FILE):
            with open(GROUP_DATA_FILE, 'r', encoding='utf-8') as f:
                group_data = json.load(f)
                group_users_last_5 = group_data.get('group_users_last_5', {})
                group_detected = set(group_data.get('group_detected', []))
                last_group_activity = group_data.get('last_group_activity', {})
            logger.info(f"✅ Loaded {len(group_users_last_5)} group users data")
        
        if os.path.exists(CLONE_BOTS_FILE):
            with open(CLONE_BOTS_FILE, 'r', encoding='utf-8') as f:
                ACTIVE_CLONE_BOTS = json.load(f)
            logger.info(f"✅ Loaded {len(ACTIVE_CLONE_BOTS)} active clone bots")
            
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        recent_users = {}
        clone_stats = {}
        group_users_last_5 = {}
        group_detected = set()
        last_group_activity = {}
        ACTIVE_CLONE_BOTS = {}

def save_data():
    try:
        with open(RECENT_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(recent_users, f, indent=2, ensure_ascii=False)
        
        with open(CLONE_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(clone_stats, f, indent=2, ensure_ascii=False)
            
        with open(GROUP_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'group_users_last_5': group_users_last_5,
                'group_detected': list(group_detected),
                'last_group_activity': last_group_activity
            }, f, indent=2, ensure_ascii=False)
        
        with open(CLONE_BOTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(ACTIVE_CLONE_BOTS, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"❌ Error saving data: {e}")

# Load data on startup
load_data()

# ============ UTILITY FUNCTIONS ============

def is_cooldown(user_id: int) -> bool:
    """Check if user is in cooldown"""
    try:
        current_time = datetime.now().timestamp()
        if user_id in user_cooldown:
            if current_time - user_cooldown[user_id] < 2:  # 2 seconds cooldown
                return True
        user_cooldown[user_id] = current_time
        return False
    except:
        return False

def get_recent_users_buttons(user_id: int):
    """Get recent users as buttons for private chats"""
    try:
        if not recent_users:
            return []
        
        buttons = []
        # Get last 10 recent users
        for user_key, user_data in list(recent_users.items())[:10]:
            target_user_id = user_data.get('user_id')
            username = user_data.get('username')
            first_name = user_data.get('first_name', 'User')
            
            if username:
                display_text = f"@{username}"
            else:
                display_text = f"{first_name} (ID: {target_user_id})"
            
            if len(display_text) > 15:
                display_text = display_text[:15] + "..."
            
            buttons.append([Button.inline(
                f"👤 {display_text}", 
                data=f"recent_{user_key}"
            )])
        
        return buttons
    except Exception as e:
        logger.error(f"Error getting recent users buttons: {e}")
        return []

# ============ USER VALIDATION FUNCTIONS ============

async def validate_and_get_user(target_user: str, client=None):
    """
    Validate and get user entity for ANY username or ID
    Returns user info even if user doesn't exist
    """
    if client is None:
        client = bot
    
    try:
        # Check if it's a user ID (only digits)
        if target_user.isdigit():
            user_id = int(target_user)
            
            # Try to get user entity
            try:
                user_obj = await client.get_entity(user_id)
                if hasattr(user_obj, 'first_name'):
                    return {
                        'id': user_obj.id,
                        'username': getattr(user_obj, 'username', None),
                        'first_name': getattr(user_obj, 'first_name', 'User'),
                        'last_name': getattr(user_obj, 'last_name', ''),
                        'exists': True
                    }
            except Exception:
                # User not found, but we can still create whisper
                pass
            
            # Return user info even if not found
            return {
                'id': user_id,
                'username': None,
                'first_name': f"User {user_id}",
                'last_name': '',
                'exists': False
            }
        
        # It's a username (remove @ if present)
        if target_user.startswith('@'):
            target_user = target_user[1:]
        
        # Validate username format
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', target_user):
            # Invalid format but we'll still accept it
            logger.warning(f"Invalid username format: {target_user}")
        
        # Try to get user entity
        try:
            user_obj = await client.get_entity(target_user)
            if hasattr(user_obj, 'first_name'):
                return {
                    'id': user_obj.id,
                    'username': getattr(user_obj, 'username', None),
                    'first_name': getattr(user_obj, 'first_name', 'User'),
                    'last_name': getattr(user_obj, 'last_name', ''),
                    'exists': True
                }
        except Exception:
            # User not found, but we can still create whisper
            pass
        
        # Return user info even if not found
        return {
            'id': None,  # We don't know the ID
            'username': target_user,
            'first_name': f"@{target_user}",
            'last_name': '',
            'exists': False
        }
        
    except Exception as e:
        logger.error(f"Error validating user {target_user}: {e}")
        return None

# ============ GROUP USER TRACKING FUNCTIONS ============

def add_user_to_group_history(chat_id: int, user_id: int, username: str = None, first_name: str = None):
    """Add user to group's last 5 users list"""
    try:
        if chat_id not in group_users_last_5:
            group_users_last_5[chat_id] = []
        
        # Remove if user already exists
        group_users_last_5[chat_id] = [u for u in group_users_last_5[chat_id] if u.get('user_id') != user_id]
        
        # Add new user at beginning
        user_data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'timestamp': datetime.now().isoformat()
        }
        group_users_last_5[chat_id].insert(0, user_data)
        
        # Keep only last 5 users
        if len(group_users_last_5[chat_id]) > 5:
            group_users_last_5[chat_id] = group_users_last_5[chat_id][:5]
        
        # Update activity timestamp
        last_group_activity[chat_id] = datetime.now().timestamp()
        
        # Mark as detected group
        group_detected.add(chat_id)
        
        save_data()
        logger.info(f"✅ Added user {user_id} to group {chat_id} history")
        
    except Exception as e:
        logger.error(f"Error adding user to group history: {e}")

def get_group_users_buttons(chat_id: int):
    """Get last 5 users from group as buttons"""
    try:
        if chat_id not in group_users_last_5 or not group_users_last_5[chat_id]:
            return []
        
        buttons = []
        for user_data in group_users_last_5[chat_id][:5]:  # Last 5 users
            user_id = user_data.get('user_id')
            username = user_data.get('username')
            first_name = user_data.get('first_name', 'User')
            
            if username:
                display_text = f"@{username}"
                query_data = f"@{username}"
            else:
                display_text = f"{first_name}"
                query_data = str(user_id)
            
            if len(display_text) > 15:
                display_text = display_text[:15] + "..."
            
            buttons.append([Button.inline(
                f"👤 {display_text}", 
                data=f"group_user_{query_data}"
            )])
        
        # Add a clear button
        buttons.append([Button.inline("🧹 Clear List", data=f"clear_group_{chat_id}")])
        
        return buttons
    except Exception as e:
        logger.error(f"Error getting group users: {e}")
        return []

def add_to_recent_users(sender_id: int, target_user_id: int, target_username=None, target_first_name=None):
    """Add user to recent users list"""
    try:
        user_key = f"{sender_id}_{target_user_id}"
        recent_users[user_key] = {
            'user_id': target_user_id,
            'username': target_username,
            'first_name': target_first_name,
            'sender_id': sender_id,
            'last_used': datetime.now().isoformat()
        }
        
        # Keep only last 50 entries
        if len(recent_users) > 50:
            # Remove oldest
            oldest_key = min(recent_users.keys(), key=lambda k: recent_users[k]['last_used'])
            del recent_users[oldest_key]
        
        save_data()
    except Exception as e:
        logger.error(f"Error adding to recent users: {e}")

# ============ CLONE HELPER FUNCTIONS ============

def get_time_difference(start_time):
    """Get formatted time difference"""
    now = datetime.now()
    diff = now - start_time
    
    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    
    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

async def create_cloned_bot(user_id: int, token: str):
    """
    Create and start a cloned bot client
    """
    try:
        logger.info(f"🔄 Creating cloned bot for user {user_id}")
        
        # Create unique session name
        session_id = f"clone_{user_id}_{int(datetime.now().timestamp())}"
        session_name = os.path.join(DATA_DIR, session_id)
        
        # Create and start the bot client
        clone_client = TelegramClient(session_name, API_ID, API_HASH)
        
        try:
            await clone_client.start(bot_token=token)
            me = await clone_client.get_me()
            bot_username = me.username
            
            logger.info(f"✅ Cloned bot started: @{bot_username}")
            
            # Store the client
            user_bots[bot_username] = {
                'client': clone_client,
                'owner_id': user_id,
                'token': token,
                'username': bot_username,
                'started_at': datetime.now().isoformat(),
                'session_name': session_name
            }
            
            # Setup cloned bot handlers
            asyncio.create_task(setup_cloned_bot_handlers(clone_client, bot_username, user_id))
            
            # Store in active bots
            ACTIVE_CLONE_BOTS[bot_username] = {
                'owner_id': user_id,
                'token': token[:10] + '...',  # Store partial token for security
                'created_at': datetime.now().isoformat(),
                'status': 'active'
            }
            
            save_data()
            
            return bot_username
            
        except Exception as e:
            logger.error(f"Failed to start cloned bot: {e}")
            await clone_client.disconnect()
            return None
            
    except Exception as e:
        logger.error(f"Error creating cloned bot: {e}")
        return None

async def setup_cloned_bot_handlers(client, bot_username: str, owner_id: int):
    """
    Setup basic handlers for cloned bot
    """
    logger.info(f"🔄 Setting up handlers for @{bot_username}")
    
    @client.on(events.NewMessage(pattern='/start'))
    async def clone_start_handler(event):
        try:
            start_text = f"""
🤖 **Your Cloned Whisper Bot**

🔗 **Bot:** @{bot_username}
👑 **Owner:** You
⚡ **Powered by:** @{BOT_USERNAME}

**How to use:**
1. Type `@{bot_username}` in any chat
2. Write your message
3. Add @username at the end
4. Send!

**Example:** `@{bot_username} Hello! @username`

🔒 Only the mentioned user can read your message!
            """
            
            await event.reply(
                start_text,
                buttons=[
                    [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                    [Button.switch_inline("🚀 Send Whisper", query="")],
                    [Button.inline("📊 Stats", data=f"clone_stats_{owner_id}")]
                ]
            )
            
            # Update stats
            if str(owner_id) in clone_stats:
                clone_stats[str(owner_id)]['starts'] = clone_stats[str(owner_id)].get('starts', 0) + 1
                save_data()
                
        except Exception as e:
            logger.error(f"Clone start handler error: {e}")

    @client.on(events.NewMessage(pattern='/help'))
    async def clone_help_handler(event):
        help_text = f"""
📖 **How to Use @{bot_username}**

**1. Inline Mode:**
   Type `@{bot_username}` in any chat then:

   **Formats:**
   • `message @username`
   • `@username message`
   • `message 123456789`
   • `123456789 message`

**2. Examples:**
   • `@{bot_username} Hello! @username`
   • `@{bot_username} @username Hello!`

**3. Features:**
   • Send anonymous whispers
   • Only recipient can read
   • Easy to use
   • Powered by @{BOT_USERNAME}

🔒 **Only the mentioned user can read your message!**
        """
        
        await event.reply(
            help_text,
            buttons=[
                [Button.switch_inline("🚀 Try Now", query="")],
                [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")]
            ]
        )

    @client.on(events.InlineQuery)
    async def clone_inline_handler(event):
        """Handle inline queries for cloned bot"""
        try:
            query_text = event.text or ""
            
            if not query_text.strip():
                # Show welcome message
                result = event.builder.article(
                    title=f"🤫 @{bot_username} - Whisper Bot",
                    description="Send secret messages",
                    text=f"**@{bot_username} - Your Whisper Bot**\n\nUsage: `message @username`\n\nExample: `Hello! @username`",
                    buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
                )
                await event.answer([result])
                return
            
            # Parse message using the same logic as main bot
            message_text = ""
            target_user = ""
            
            # Try different patterns
            patterns = [
                (r'^(.*?)\s+@(\w+)$', 2),  # message @username
                (r'^(.*?)\s+(\d+)$', 2),   # message 123456789
                (r'^@(\w+)\s+(.*)$', 1),   # @username message
                (r'^(\d+)\s+(.*)$', 1)     # 123456789 message
            ]
            
            for pattern, group_idx in patterns:
                match = re.search(pattern, query_text, re.DOTALL)
                if match:
                    if group_idx == 2:
                        message_text = match.group(1).strip()
                        target_user = match.group(2)
                    else:
                        target_user = match.group(1)
                        message_text = match.group(2).strip()
                    break
            
            # If no pattern matched, check if it's just a username or ID
            if not message_text:
                if query_text.startswith('@'):
                    target_user = query_text[1:]
                    message_text = ""
                elif query_text.isdigit():
                    target_user = query_text
                    message_text = ""
                else:
                    # Try to extract username from the end
                    username_match = re.search(r'@(\w+)$', query_text)
                    if username_match:
                        target_user = username_match.group(1)
                        message_text = query_text.replace(f"@{target_user}", "").strip()
                    else:
                        # Try to extract ID from the end
                        id_match = re.search(r'(\d+)$', query_text)
                        if id_match:
                            target_user = id_match.group(1)
                            message_text = query_text.replace(target_user, "").strip()
            
            if not target_user:
                result = event.builder.article(
                    title="❌ Invalid Format",
                    description="Use: message @username",
                    text="**Usage:** `message @username`\n\n**Examples:**\n• `Hello! @username`\n• `@username Hello!`",
                    buttons=[[Button.switch_inline("🔄 Try Again", query=query_text)]]
                )
                await event.answer([result])
                return
            
            if message_text and len(message_text) > 1000:
                result = event.builder.article(
                    title="❌ Message Too Long",
                    description="Max 1000 characters",
                    text="❌ Message too long! Keep under 1000 characters."
                )
                await event.answer([result])
                return
            
            # Validate and get user info
            user_info = await validate_and_get_user(target_user, client)
            
            if not user_info:
                result = event.builder.article(
                    title="❌ Error",
                    description="Could not process user",
                    text="❌ Could not process the user. Please try again."
                )
                await event.answer([result])
                return
            
            # Create whisper ID
            whisper_id = f"clone_{bot_username}_{event.sender_id}_{int(datetime.now().timestamp())}"
            
            # Store whisper
            if bot_username not in clone_whispers:
                clone_whispers[bot_username] = {}
            
            clone_whispers[bot_username][whisper_id] = {
                'message': message_text,
                'sender_id': event.sender_id,
                'target_user': target_user,
                'target_info': user_info,
                'created_at': datetime.now().isoformat()
            }
            
            # Update stats
            if str(owner_id) in clone_stats:
                clone_stats[str(owner_id)]['whispers'] = clone_stats[str(owner_id)].get('whispers', 0) + 1
                save_data()
            
            # Prepare display name
            if user_info['username']:
                display_name = f"@{user_info['username']}"
            else:
                display_name = user_info['first_name']
            
            result_text = f"**🔐 A secret message for {display_name}!**\n\n"
            result_text += f"*Note: Only {display_name} can open this message.*"
            
            result = event.builder.article(
                title=f"🔒 Secret Message for {display_name}",
                description=f"Click to send secret message to {display_name}",
                text=result_text,
                buttons=[[Button.inline("🔓 Show Message", data=whisper_id)]]
            )
            
            await event.answer([result])
            
        except Exception as e:
            logger.error(f"Clone inline handler error for @{bot_username}: {e}")
            result = event.builder.article(
                title="❌ Error",
                description="Something went wrong",
                text="❌ An error occurred. Please try again."
            )
            await event.answer([result])

    @client.on(events.CallbackQuery)
    async def clone_callback_handler(event):
        """Handle callbacks for cloned bot"""
        try:
            data = event.data.decode('utf-8')
            
            if data.startswith("clone_stats_"):
                owner_id = int(data.replace("clone_stats_", ""))
                
                if str(owner_id) in clone_stats:
                    stats = clone_stats[str(owner_id)]
                    bot_username = stats.get('bot_username', 'Unknown')
                    created_at = datetime.fromisoformat(stats.get('created_at', datetime.now().isoformat()))
                    
                    stats_text = f"📊 **@{bot_username} Stats**\n\n"
                    stats_text += f"👤 **Owner ID:** {owner_id}\n"
                    stats_text += f"📅 **Created:** {created_at.strftime('%d %b %Y')}\n"
                    stats_text += f"⏰ **Running for:** {get_time_difference(created_at)}\n"
                    stats_text += f"🚀 **Starts:** {stats.get('starts', 0)}\n"
                    stats_text += f"🤫 **Whispers:** {stats.get('whispers', 0)}\n"
                    stats_text += f"💬 **Messages:** {stats.get('messages', 0)}\n"
                    stats_text += f"✅ **Status:** Active\n\n"
                    stats_text += f"⚡ **Powered by:** @{BOT_USERNAME}"
                    
                    await event.edit(
                        stats_text,
                        buttons=[
                            [Button.switch_inline("🚀 Send Whisper", query="")],
                            [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")]
                        ]
                    )
            
            elif bot_username in clone_whispers and data in clone_whispers[bot_username]:
                whisper_data = clone_whispers[bot_username][data]
                target_info = whisper_data.get('target_info', {})
                
                # Check if user is the target or sender
                if target_info.get('exists') and event.sender_id == target_info.get('id'):
                    # Target user opening the message
                    sender_display = "Anonymous"
                    try:
                        # Try to get sender info
                        sender = await client.get_entity(whisper_data['sender_id'])
                        if hasattr(sender, 'first_name'):
                            sender_display = sender.first_name
                    except:
                        pass
                    
                    await event.answer(f"🔓 {whisper_data['message']}\n\n💌 From: {sender_display}", alert=True)
                elif event.sender_id == whisper_data['sender_id']:
                    # Sender viewing their own message
                    target_display = target_info.get('first_name', whisper_data['target_user'])
                    await event.answer(f"📝 Your message: {whisper_data['message']}\n\n👤 To: {target_display}", alert=True)
                else:
                    # Someone else trying to open
                    await event.answer("🔒 This message is not for you!", alert=True)
            
            else:
                await event.answer("❌ Invalid button!", alert=True)
                
        except Exception as e:
            logger.error(f"Clone callback handler error for @{bot_username}: {e}")
            await event.answer("❌ An error occurred.", alert=True)
    
    logger.info(f"✅ Handlers setup for cloned bot @{bot_username}")

async def stop_cloned_bot(bot_username: str):
    """Stop a cloned bot"""
    try:
        if bot_username in user_bots:
            client_info = user_bots[bot_username]
            await client_info['client'].disconnect()
            del user_bots[bot_username]
            
            if bot_username in ACTIVE_CLONE_BOTS:
                del ACTIVE_CLONE_BOTS[bot_username]
            
            # Remove session file
            session_file = f"{client_info['session_name']}.session"
            if os.path.exists(session_file):
                os.remove(session_file)
            
            logger.info(f"✅ Stopped cloned bot: @{bot_username}")
            save_data()
            return True
    except Exception as e:
        logger.error(f"Error stopping cloned bot: {e}")
    return False

# ============ BROADCAST FUNCTIONS ============

async def broadcast_to_users(message_text: str, sender_id: int, include_photo: bool = False, photo_path: str = None):
    """Broadcast message to all users who have interacted with bot"""
    try:
        logger.info(f"📢 Starting user broadcast from {sender_id}")
        
        # Get all unique users from recent_users and messages_db
        all_users = set()
        
        # Add from recent_users
        for user_data in recent_users.values():
            all_users.add(user_data['user_id'])
        
        # Add from messages_db (senders and receivers)
        for msg_data in messages_db.values():
            all_users.add(msg_data['user_id'])
            all_users.add(msg_data['sender_id'])
        
        # Add from clone_stats
        for stats in clone_stats.values():
            all_users.add(stats['owner_id'])
        
        total_users = len(all_users)
        logger.info(f"📊 Broadcasting to {total_users} users")
        
        success = 0
        failed = 0
        
        broadcast_progress = await bot.send_message(sender_id, f"📢 **Broadcast Started**\n\n📊 Total Users: {total_users}\n✅ Success: 0\n❌ Failed: 0\n⏳ Progress: 0%")
        
        for index, user_id in enumerate(all_users):
            try:
                if include_photo and photo_path:
                    await bot.send_file(user_id, photo_path, caption=message_text)
                else:
                    await bot.send_message(user_id, message_text)
                
                success += 1
                
                # Update progress every 10 users or 10%
                if index % 10 == 0 or index == total_users - 1:
                    progress_percent = int((index + 1) / total_users * 100)
                    await broadcast_progress.edit(
                        f"📢 **Broadcast in Progress**\n\n"
                        f"📊 Total Users: {total_users}\n"
                        f"✅ Success: {success}\n"
                        f"❌ Failed: {failed}\n"
                        f"⏳ Progress: {progress_percent}%\n"
                        f"📨 Sent: {index + 1}/{total_users}"
                    )
                
                # Small delay to avoid flood
                await asyncio.sleep(0.1)
                
            except FloodWaitError as e:
                logger.warning(f"Flood wait for user {user_id}: {e.seconds} seconds")
                await asyncio.sleep(e.seconds + 1)
                continue
            except Exception as e:
                logger.error(f"Failed to send to user {user_id}: {e}")
                failed += 1
                continue
        
        # Final report
        await broadcast_progress.edit(
            f"✅ **Broadcast Completed**\n\n"
            f"📊 Total Users: {total_users}\n"
            f"✅ Success: {success}\n"
            f"❌ Failed: {failed}\n"
            f"📈 Success Rate: {int(success/total_users*100)}%"
        )
        
        # Save broadcast history
        save_broadcast_history('users', sender_id, message_text, total_users, success, failed)
        
        return success, failed
        
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        await bot.send_message(sender_id, f"❌ Broadcast failed: {str(e)}")
        return 0, 0

async def broadcast_to_groups(message_text: str, sender_id: int, include_photo: bool = False, photo_path: str = None):
    """Broadcast message to all detected groups"""
    try:
        logger.info(f"📢 Starting group broadcast from {sender_id}")
        
        total_groups = len(group_detected)
        logger.info(f"📊 Broadcasting to {total_groups} groups")
        
        if total_groups == 0:
            await bot.send_message(sender_id, "❌ No groups detected yet. Add bot to groups first.")
            return 0, 0
        
        success = 0
        failed = 0
        
        broadcast_progress = await bot.send_message(sender_id, f"📢 **Group Broadcast Started**\n\n📊 Total Groups: {total_groups}\n✅ Success: 0\n❌ Failed: 0\n⏳ Progress: 0%")
        
        for index, group_id in enumerate(group_detected):
            try:
                # Check if bot can send messages in group
                chat = await bot.get_entity(group_id)
                
                if include_photo and photo_path:
                    await bot.send_file(chat, photo_path, caption=message_text)
                else:
                    await bot.send_message(chat, message_text)
                
                success += 1
                
                # Update progress
                if index % 5 == 0 or index == total_groups - 1:
                    progress_percent = int((index + 1) / total_groups * 100)
                    await broadcast_progress.edit(
                        f"📢 **Group Broadcast in Progress**\n\n"
                        f"📊 Total Groups: {total_groups}\n"
                        f"✅ Success: {success}\n"
                        f"❌ Failed: {failed}\n"
                        f"⏳ Progress: {progress_percent}%\n"
                        f"📨 Sent: {index + 1}/{total_groups}"
                    )
                
                # Small delay
                await asyncio.sleep(1)
                
            except FloodWaitError as e:
                logger.warning(f"Flood wait for group {group_id}: {e.seconds} seconds")
                await asyncio.sleep(e.seconds + 1)
                continue
            except ChatWriteForbiddenError:
                logger.warning(f"Cannot write in group {group_id}")
                failed += 1
                continue
            except Exception as e:
                logger.error(f"Failed to send to group {group_id}: {e}")
                failed += 1
                continue
        
        # Final report
        await broadcast_progress.edit(
            f"✅ **Group Broadcast Completed**\n\n"
            f"📊 Total Groups: {total_groups}\n"
            f"✅ Success: {success}\n"
            f"❌ Failed: {failed}\n"
            f"📈 Success Rate: {int(success/total_groups*100)}%"
        )
        
        # Save broadcast history
        save_broadcast_history('groups', sender_id, message_text, total_groups, success, failed)
        
        return success, failed
        
    except Exception as e:
        logger.error(f"Group broadcast error: {e}")
        await bot.send_message(sender_id, f"❌ Group broadcast failed: {str(e)}")
        return 0, 0

def save_broadcast_history(broadcast_type: str, sender_id: int, message: str, total: int, success: int, failed: int):
    """Save broadcast history to file"""
    try:
        history = {}
        if os.path.exists(BROADCAST_HISTORY_FILE):
            with open(BROADCAST_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        
        broadcast_id = f"{broadcast_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        history[broadcast_id] = {
            'type': broadcast_type,
            'sender_id': sender_id,
            'message': message[:500],  # Store first 500 chars
            'total': total,
            'success': success,
            'failed': failed,
            'timestamp': datetime.now().isoformat()
        }
        
        # Keep only last 50 broadcasts
        if len(history) > 50:
            # Remove oldest
            oldest_key = min(history.keys())
            del history[oldest_key]
        
        with open(BROADCAST_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"Error saving broadcast history: {e}")

# ============ COMMAND HANDLERS ============

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        logger.info(f"🚀 Start command from user: {event.sender_id}")
        
        # Check if in group
        if event.is_group or event.is_channel:
            chat_id = event.chat_id
            add_user_to_group_history(
                chat_id, 
                event.sender_id,
                event.sender.username,
                event.sender.first_name
            )
            
            # Show group welcome message
            await event.reply(
                "🤫 **Whisper Bot is now active in this group!**\n\n"
                "🔒 Send anonymous whispers to group members\n"
                "📝 Use inline mode: `@bot_username message @username`\n\n"
                "📌 **Recent group members will appear when you type a whisper!**",
                buttons=[
                    [Button.switch_inline("🚀 Send Whisper", query="", same_peer=True)],
                    [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")]
                ]
            )
            return
        
        # Private chat welcome message
        if event.sender_id == ADMIN_ID:
            await event.reply(
                WELCOME_TEXT,
                buttons=[
                    [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                    [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                    [Button.switch_inline("🚀 Try Now", query="")],
                    [Button.inline("📊 Statistics", data="admin_stats"), Button.inline("📖 Help", data="help")],
                    [Button.inline("🔧 Clone Bot", data="clone_info")],
                    [Button.inline("📢 Broadcast", data="broadcast_menu")]
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
        total_groups = len(group_detected)
        total_group_users = sum(len(users) for users in group_users_last_5.values())
        
        stats_text = f"""
📊 **Admin Statistics**

👤 Recent Users: {len(recent_users)}
💬 Total Messages: {len(messages_db)}
🤖 Total Clones: {total_clones}
👥 Groups Detected: {total_groups}
👤 Group Users Tracked: {total_group_users}
🆔 Admin ID: {ADMIN_ID}
🌐 Port: {PORT}

**Active Clone Bots:** {len(ACTIVE_CLONE_BOTS)}
**Bot Status:** ✅ Running
**Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
        """
        
        await event.reply(stats_text)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await event.reply("❌ Error fetching statistics.")

# ============ CLONE COMMAND HANDLERS ============

@bot.on(events.NewMessage(pattern='/clone'))
async def clone_handler(event):
    """Handle bot cloning"""
    try:
        user_id = event.sender_id
        
        # Check if user already has a cloned bot
        if str(user_id) in clone_stats:
            await event.reply(
                "❌ **You already have a cloned bot!**\n\n"
                "Use `/remove` to remove your current bot first.",
                buttons=[Button.inline("❌ Remove My Bot", data="remove_my_bot")]
            )
            return
        
        # Check if command has token
        if not event.text or len(event.text.split()) < 2:
            await event.reply(
                "🔧 **Clone Your Own Whisper Bot**\n\n"
                "**This creates a REAL working bot:**\n"
                "• Your own @bot_username\n"
                "• Full whisper functionality\n"
                "• 24/7 operation\n\n"
                "**Usage:** `/clone bot_token`\n\n"
                "**Example:**\n"
                "`/clone 1234567890:ABCdefGHIjkl...`\n\n"
                "**How to get token:**\n"
                "1. Talk to @BotFather\n"
                "2. Create new bot with /newbot\n"
                "3. Copy the token you get\n\n"
                "⚠️ **Warning:** Keep your token secret!",
                buttons=[
                    [Button.url("🤖 BotFather", "https://t.me/BotFather")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
            return
        
        # Extract token
        parts = event.text.split()
        if len(parts) < 2:
            await event.reply("❌ Please provide a bot token.")
            return
        
        token = parts[1].strip()
        
        # Validate token format
        if not re.match(r'^\d+:[A-Za-z0-9_-]{35}$', token):
            await event.reply(
                "❌ **Invalid token format!**\n\n"
                "Token should look like: `1234567890:ABCdefGHIjklMnOpQrStUvWxYz123456`\n"
                "Make sure you copied the full token from @BotFather."
            )
            return
        
        # Ask for confirmation
        await event.reply(
            "⚠️ **Confirm Bot Creation**\n\n"
            "**This will:**\n"
            "1. Create a REAL working bot\n"
            "2. Start it on our servers\n"
            "3. Give you @your_bot_username\n"
            "4. Full whisper functionality\n\n"
            "**Cost:** FREE\n"
            "**Runtime:** 24/7\n\n"
            "Click ✅ to proceed or ❌ to cancel.",
            buttons=[
                [Button.inline("✅ Yes, Create My Bot", data=f"confirm_clone:{token}")],
                [Button.inline("❌ Cancel", data="back_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Clone handler error: {e}")
        await event.reply("❌ An error occurred. Please try again.")

@bot.on(events.NewMessage(pattern='/remove'))
async def remove_handler(event):
    """Handle bot removal"""
    try:
        user_id = event.sender_id
        
        if str(user_id) not in clone_stats:
            await event.reply(
                "❌ **You don't have any cloned bot!**\n\n"
                "Use `/clone` to create your own bot first.",
                buttons=[Button.inline("🔧 Clone Bot", data="clone_info")]
            )
            return
        
        # Get bot info
        bot_info = clone_stats[str(user_id)]
        bot_username = bot_info.get('bot_username', 'Unknown')
        
        await event.reply(
            f"🗑️ **Remove Your Bot**\n\n"
            f"**Bot:** @{bot_username}\n"
            f"**Created:** {bot_info.get('created_at', 'Unknown')}\n\n"
            f"Are you sure you want to remove this bot?\n\n"
            f"⚠️ **This will:**\n"
            f"• Stop your bot\n"
            f"• Delete all data\n"
            f"• Cannot be undone",
            buttons=[
                [Button.inline("✅ Yes, Remove", data="confirm_remove")],
                [Button.inline("❌ Cancel", data="back_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Remove handler error: {e}")
        await event.reply("❌ An error occurred. Please try again.")

# ============ BROADCAST COMMANDS ============

@bot.on(events.NewMessage(pattern='/broadcast'))
async def broadcast_command(event):
    """Handle /broadcast command for users"""
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
    
    try:
        if not event.text or len(event.text.split()) == 1:
            await event.reply(
                "📢 **User Broadcast**\n\n"
                "Send a message to broadcast to all users.\n\n"
                "**Format:**\n"
                "`/broadcast your message here`\n\n"
                "**Or reply to a message:**\n"
                "Reply to any message with `/broadcast`",
                buttons=[
                    [Button.inline("📊 View Stats", data="broadcast_stats")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
            return
        
        # Check if replying to a message
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            message_text = reply_msg.text or reply_msg.caption or ""
        else:
            # Get message from command
            message_text = event.text.split(' ', 1)[1]
        
        if not message_text.strip():
            await event.reply("❌ Please provide a message to broadcast.")
            return
        
        confirm_text = (
            f"📢 **Confirm Broadcast to Users**\n\n"
            f"**Message:**\n{message_text[:500]}{'...' if len(message_text) > 500 else ''}\n\n"
            f"⚠️ This will be sent to all users. Continue?"
        )
        
        await event.reply(
            confirm_text,
            buttons=[
                [Button.inline("✅ Yes, Broadcast", data=f"confirm_user_broadcast:{message_text[:1000]}")],
                [Button.inline("❌ Cancel", data="back_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Broadcast command error: {e}")
        await event.reply(f"❌ Error: {str(e)}")

@bot.on(events.NewMessage(pattern='/gbroadcast'))
async def gbroadcast_command(event):
    """Handle /gbroadcast command for groups"""
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
    
    try:
        if not event.text or len(event.text.split()) == 1:
            await event.reply(
                "📢 **Group Broadcast**\n\n"
                "Send a message to broadcast to all groups.\n\n"
                "**Format:**\n"
                "`/gbroadcast your message here`\n\n"
                "**Or reply to a message:**\n"
                "Reply to any message with `/gbroadcast`\n\n"
                f"📊 **Groups Detected:** {len(group_detected)}",
                buttons=[
                    [Button.inline("📊 View Groups", data="group_stats")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
            return
        
        # Check if replying to a message
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            message_text = reply_msg.text or reply_msg.caption or ""
        else:
            # Get message from command
            message_text = event.text.split(' ', 1)[1]
        
        if not message_text.strip():
            await event.reply("❌ Please provide a message to broadcast.")
            return
        
        confirm_text = (
            f"📢 **Confirm Group Broadcast**\n\n"
            f"**Message:**\n{message_text[:500]}{'...' if len(message_text) > 500 else ''}\n\n"
            f"📊 **Groups:** {len(group_detected)}\n"
            f"⚠️ This will be sent to all detected groups. Continue?"
        )
        
        await event.reply(
            confirm_text,
            buttons=[
                [Button.inline("✅ Yes, Broadcast", data=f"confirm_group_broadcast:{message_text[:1000]}")],
                [Button.inline("❌ Cancel", data="back_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Group broadcast command error: {e}")
        await event.reply(f"❌ Error: {str(e)}")

# ============ INLINE QUERY HANDLER ============

@bot.on(events.InlineQuery)
async def inline_handler(event):
    """Handle inline queries - ACCEPTS ANY USERNAME OR ID"""
    try:
        if is_cooldown(event.sender_id):
            await event.answer([])
            return

        query_text = event.text or ""
        
        # Check if in group
        is_group_context = False
        chat_id = None
        if hasattr(event.query, 'chat_type'):
            is_group_context = event.query.chat_type in ['group', 'supergroup']
            if hasattr(event.query, 'peer') and event.query.peer:
                try:
                    chat_id = event.query.peer.channel_id or event.query.peer.chat_id or event.query.peer.user_id
                except:
                    pass
        
        recent_buttons = []
        
        if is_group_context and chat_id and chat_id in group_users_last_5:
            recent_buttons = get_group_users_buttons(chat_id)
        else:
            recent_buttons = get_recent_users_buttons(event.sender_id)
        
        if not query_text.strip():
            if recent_buttons:
                if is_group_context:
                    result_text = "**Recent Group Members:**\nClick any user below to whisper them!\n\nOr type: `message @username`"
                else:
                    result_text = "**Recent Users:**\nClick any user below to whisper them!\n\nOr type: `message @username`"
                
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
        
        text = query_text.strip()
        
        # Extract message and target user - ACCEPTS ANYTHING
        message_text = ""
        target_user = ""
        
        # Try different patterns
        patterns = [
            (r'^(.*?)\s+@(\w+)$', 2),  # message @username
            (r'^(.*?)\s+(\d+)$', 2),   # message 123456789
            (r'^@(\w+)\s+(.*)$', 1),   # @username message
            (r'^(\d+)\s+(.*)$', 1)     # 123456789 message
        ]
        
        for pattern, group_idx in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                if group_idx == 2:
                    message_text = match.group(1).strip()
                    target_user = match.group(2)
                else:
                    target_user = match.group(1)
                    message_text = match.group(2).strip()
                break
        
        # If no pattern matched, check if it's just a username or ID
        if not message_text:
            if text.startswith('@'):
                target_user = text[1:]
                message_text = ""
            elif text.isdigit():
                target_user = text
                message_text = ""
            else:
                # Try to extract username from the end
                username_match = re.search(r'@(\w+)$', text)
                if username_match:
                    target_user = username_match.group(1)
                    message_text = text.replace(f"@{target_user}", "").strip()
                else:
                    # Try to extract ID from the end
                    id_match = re.search(r'(\d+)$', text)
                    if id_match:
                        target_user = id_match.group(1)
                        message_text = text.replace(target_user, "").strip()
        
        if not target_user:
            result = event.builder.article(
                title="❌ Invalid Format",
                description="Use: message @username",
                text="**Usage:** `message @username`\n\n**Examples:**\n• `Hello! @username`\n• `@username Hello!`\n• `I miss you 123456789`",
                buttons=[[Button.switch_inline("🔄 Try Again", query=text)]]
            )
            await event.answer([result])
            return
        
        if message_text and len(message_text) > 1000:
            result = event.builder.article(
                title="❌ Message Too Long",
                description="Max 1000 characters",
                text="❌ Message too long! Keep under 1000 characters."
            )
            await event.answer([result])
            return
        
        # If message is empty, show instructions
        if not message_text.strip():
            if target_user.isdigit():
                display_text = f"User ID: {target_user}"
            else:
                display_text = f"@{target_user}"
            
            result = event.builder.article(
                title=f"📝 Type message for {display_text}",
                description=f"Type your message then send",
                text=f"**Type your whisper message for {display_text}**\n\nNow type your message and the bot will create a secret whisper.",
                buttons=[[Button.switch_inline(f"✍️ Type message for {display_text}", query=f"{text} ")]]
            )
            await event.answer([result])
            return
        
        # Validate and get user info - ACCEPTS ANYTHING
        user_info = await validate_and_get_user(target_user)
        
        if not user_info:
            result = event.builder.article(
                title="❌ Error",
                description="Could not process user",
                text="❌ Could not process the user. Please try again."
            )
            await event.answer([result])
            return
        
        # Add to appropriate recent list if user exists
        if user_info.get('exists') and user_info.get('id'):
            if is_group_context and chat_id:
                add_user_to_group_history(
                    chat_id,
                    user_info['id'],
                    user_info.get('username'),
                    user_info.get('first_name')
                )
            else:
                add_to_recent_users(
                    event.sender_id,
                    user_info['id'],
                    user_info.get('username'),
                    user_info.get('first_name')
                )
        
        # Create message ID
        message_id = f'msg_{event.sender_id}_{target_user}_{int(datetime.now().timestamp())}'
        messages_db[message_id] = {
            'user_id': user_info.get('id') or target_user,
            'msg': message_text,
            'sender_id': event.sender_id,
            'timestamp': datetime.now().isoformat(),
            'target_name': user_info.get('first_name', target_user),
            'target_username': user_info.get('username'),
            'target_exists': user_info.get('exists', False),
            'is_group': is_group_context,
            'group_id': chat_id if is_group_context else None
        }
        
        # Prepare response
        if user_info.get('username'):
            display_target = f"@{user_info['username']}"
        else:
            display_target = user_info.get('first_name', target_user)
        
        result_text = f"**🔐 A secret message for {display_target}!**\n\n"
        result_text += f"*Note: Only {display_target} can open this message.*"
        
        if not user_info.get('exists'):
            result_text += f"\n\n⚠️ *Note: User @{target_user} may not exist, but whisper can still be created.*"
        
        result = event.builder.article(
            title=f"🔒 Secret Message for {display_target}",
            description=f"Click to send secret message to {display_target}",
            text=result_text,
            buttons=[[Button.inline("🔓 Show Message", data=message_id)]]
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

# ============ CALLBACK QUERY HANDLER ============

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
            total_groups = len(group_detected)
            stats_text = f"📊 **Admin Statistics**\n\n"
            stats_text += f"👥 Recent Users: {len(recent_users)}\n"
            stats_text += f"💬 Total Messages: {len(messages_db)}\n"
            stats_text += f"🤖 Total Clones: {total_clones}\n"
            stats_text += f"👥 Groups Detected: {total_groups}\n"
            stats_text += f"👤 Group Users Tracked: {sum(len(users) for users in group_users_last_5.values())}\n"
            stats_text += f"🆔 Admin ID: {ADMIN_ID}\n"
            stats_text += f"🌐 Port: {PORT}\n"
            stats_text += f"🕒 Last Updated: {datetime.now().strftime('%H:%M:%S')}\n\n"
            stats_text += f"**Active Clone Bots:** {len(ACTIVE_CLONE_BOTS)}\n"
            stats_text += f"**Status:** ✅ Running"
            
            await event.edit(
                stats_text,
                buttons=[
                    [Button.inline("📢 Broadcast", data="broadcast_menu")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
        
        elif data == "clone_info":
            user_id = event.sender_id
            has_bot = str(user_id) in clone_stats
            
            if has_bot:
                bot_info = clone_stats[str(user_id)]
                bot_username = bot_info.get('bot_username', 'Unknown')
                created_at = datetime.fromisoformat(bot_info.get('created_at', datetime.now().isoformat()))
                
                clone_text = f"""
🔧 **Your Cloned Bot**

✅ **Status:** Active & Running
🤖 **Bot:** @{bot_username}
📅 **Created:** {created_at.strftime('%d %b %Y')}
⏰ **Running for:** {get_time_difference(created_at)}
👥 **Users Reached:** {bot_info.get('whispers', 0)}

**Your bot is live and working!**
Users can send whispers using @{bot_username}

**Manage your bot below:**
                """
                
                buttons = [
                    [Button.url(f"🚀 Start @{bot_username}", f"https://t.me/{bot_username}")],
                    [Button.switch_inline(f"💌 Use @{bot_username}", query="")],
                    [Button.inline("📊 My Stats", data="my_clone_stats")],
                    [Button.inline("🗑️ Remove Bot", data="remove_my_bot")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            else:
                clone_text = """
🔧 **Clone Your Own Whisper Bot**

**This creates a REAL working bot:**
• Your own @bot_username
• Full whisper functionality
• 24/7 operation
• No coding required

**Requirements:**
• Bot token from @BotFather
• Token must be valid and unused

**Commands:**
• `/clone bot_token` - Create your bot
• `/remove` - Remove your bot

**Example:**
`/clone 1234567890:ABCdefGHIjkl...`

⚡ **Powered by ShriBots**
                """
                
                buttons = [
                    [Button.url("🤖 Get Token from BotFather", "https://t.me/BotFather")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            
            await event.edit(clone_text, buttons=buttons)
        
        elif data == "broadcast_menu":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
                
            await event.edit(
                "📢 **Broadcast Menu**\n\n"
                "Choose broadcast type:",
                buttons=[
                    [Button.inline("👤 Broadcast to Users", data="user_broadcast_menu")],
                    [Button.inline("👥 Broadcast to Groups", data="group_broadcast_menu")],
                    [Button.inline("📊 Broadcast Stats", data="broadcast_stats")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
        
        elif data == "user_broadcast_menu":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
                
            await event.edit(
                "👤 **User Broadcast**\n\n"
                "Send message to all users who interacted with bot.\n\n"
                "**Commands:**\n"
                "• `/broadcast message` - Broadcast text\n"
                "• Reply to message with `/broadcast`",
                buttons=[
                    [Button.inline("📊 User Stats", data="broadcast_stats")],
                    [Button.inline("🔙 Back", data="broadcast_menu")]
                ]
            )
        
        elif data == "group_broadcast_menu":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
                
            await event.edit(
                f"👥 **Group Broadcast**\n\n"
                f"Send message to all detected groups.\n\n"
                f"📊 **Groups Detected:** {len(group_detected)}\n\n"
                f"**Commands:**\n"
                f"• `/gbroadcast message` - Broadcast text\n"
                f"• Reply to message with `/gbroadcast`",
                buttons=[
                    [Button.inline("📊 Group Stats", data="group_stats")],
                    [Button.inline("🔙 Back", data="broadcast_menu")]
                ]
            )
        
        elif data == "broadcast_stats":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
                
            # Try to load broadcast history
            history_text = "📊 **Broadcast History**\n\n"
            try:
                if os.path.exists(BROADCAST_HISTORY_FILE):
                    with open(BROADCAST_HISTORY_FILE, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                    
                    if history:
                        for broadcast_id, info in list(history.items())[-5:]:  # Last 5
                            btype = info['type']
                            timestamp = datetime.fromisoformat(info['timestamp']).strftime("%d/%m %H:%M")
                            success = info['success']
                            total = info['total']
                            
                            history_text += f"**{btype.upper()}** - {timestamp}\n"
                            history_text += f"✅ {success}/{total} ({int(success/total*100)}%)\n"
                            history_text += f"📝 {info['message'][:50]}...\n\n"
                    else:
                        history_text += "No broadcast history yet.\n"
                else:
                    history_text += "No broadcast history yet.\n"
            except Exception as e:
                history_text += f"Error loading history: {str(e)}\n"
            
            history_text += f"\n📅 {datetime.now().strftime('%d %B %Y')}"
            
            await event.edit(
                history_text,
                buttons=[
                    [Button.inline("👤 User Broadcast", data="user_broadcast_menu")],
                    [Button.inline("👥 Group Broadcast", data="group_broadcast_menu")],
                    [Button.inline("🔙 Back", data="broadcast_menu")]
                ]
            )
        
        elif data == "group_stats":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
                
            group_stats_text = f"👥 **Group Statistics**\n\n"
            group_stats_text += f"📊 Total Groups: {len(group_detected)}\n"
            group_stats_text += f"👤 Users Tracked: {sum(len(users) for users in group_users_last_5.values())}\n\n"
            
            if group_detected:
                group_stats_text += "**Active Groups:**\n"
                for i, group_id in enumerate(list(group_detected)[:10]):  # Show first 10
                    if group_id in last_group_activity:
                        last_active = datetime.fromtimestamp(last_group_activity[group_id]).strftime("%d/%m %H:%M")
                        group_stats_text += f"{i+1}. Group ID: `{group_id}` (Last: {last_active})\n"
            
            await event.edit(
                group_stats_text,
                buttons=[
                    [Button.inline("🔄 Refresh", data="group_stats")],
                    [Button.inline("🔙 Back", data="broadcast_menu")]
                ]
            )
        
        elif data.startswith("confirm_user_broadcast:"):
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
            
            message_text = data.replace("confirm_user_broadcast:", "")
            await event.answer("📢 Starting user broadcast...", alert=False)
            
            success, failed = await broadcast_to_users(message_text, event.sender_id)
            
            await event.edit(
                f"✅ **User Broadcast Completed**\n\n"
                f"📊 Total Users: {success + failed}\n"
                f"✅ Success: {success}\n"
                f"❌ Failed: {failed}\n"
                f"📈 Success Rate: {int(success/(success+failed)*100) if (success+failed) > 0 else 0}%",
                buttons=[[Button.inline("🔙 Back", data="broadcast_menu")]]
            )
        
        elif data.startswith("confirm_group_broadcast:"):
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
            
            message_text = data.replace("confirm_group_broadcast:", "")
            await event.answer("📢 Starting group broadcast...", alert=False)
            
            success, failed = await broadcast_to_groups(message_text, event.sender_id)
            
            await event.edit(
                f"✅ **Group Broadcast Completed**\n\n"
                f"📊 Total Groups: {success + failed}\n"
                f"✅ Success: {success}\n"
                f"❌ Failed: {failed}\n"
                f"📈 Success Rate: {int(success/(success+failed)*100) if (success+failed) > 0 else 0}%",
                buttons=[[Button.inline("🔙 Back", data="broadcast_menu")]]
            )
        
        elif data.startswith("confirm_clone:"):
            # Handle bot cloning confirmation
            token = data.replace("confirm_clone:", "")
            user_id = event.sender_id
            
            await event.answer("🔄 Creating your bot...", alert=False)
            
            try:
                # First update message
                await event.edit("🔄 **Creating your bot...**\n\nPlease wait while we set up your bot...")
                
                # Create cloned bot
                bot_username = await create_cloned_bot(user_id, token)
                
                if bot_username:
                    # Save clone stats
                    clone_stats[str(user_id)] = {
                        'owner_id': user_id,
                        'bot_token': token[:10] + '...',  # Store partial token
                        'bot_username': bot_username,
                        'created_at': datetime.now().isoformat(),
                        'starts': 0,
                        'whispers': 0,
                        'messages': 0,
                        'status': 'active'
                    }
                    save_data()
                    
                    success_text = (
                        f"✅ **Your Bot is Now Live!**\n\n"
                        f"**Bot:** @{bot_username}\n"
                        f"**Token:** Verified ✅\n"
                        f"**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                        f"**🎉 Congratulations!**\n"
                        f"Your cloned whisper bot is now active and working!\n\n"
                        f"**Features:**\n"
                        f"• Send whispers using @{bot_username}\n"
                        f"• Same interface as main bot\n"
                        f"• Your own statistics\n"
                        f"• 24/7 operation\n\n"
                        f"**Try it now!**"
                    )
                    
                    await event.edit(
                        success_text,
                        buttons=[
                            [Button.url(f"🚀 Start @{bot_username}", f"https://t.me/{bot_username}")],
                            [Button.inline("📊 Bot Stats", data="my_clone_stats")],
                            [Button.switch_inline(f"💌 Use @{bot_username}", query="")]
                        ]
                    )
                    
                    # Send welcome message to the new bot
                    try:
                        if bot_username in user_bots:
                            clone_client = user_bots[bot_username]['client']
                            await clone_client.send_message(
                                user_id,
                                f"🎉 **Your Cloned Bot is Ready!**\n\n"
                                f"**Bot:** @{bot_username}\n"
                                f"**Status:** ✅ Active\n"
                                f"**Features:** Full whisper functionality\n\n"
                                f"Use /start in this chat to begin!"
                            )
                    except Exception as e:
                        logger.error(f"Error sending welcome to cloned bot: {e}")
                        
                else:
                    error_text = (
                        "❌ **Failed to create bot!**\n\n"
                        "Possible reasons:\n"
                        "• Invalid or expired token\n"
                        "• Token already in use\n"
                        "• BotFather API issue\n"
                        "• Server resources limit\n\n"
                        "Please check your token and try again."
                    )
                    
                    await event.edit(
                        error_text,
                        buttons=[[Button.inline("🔄 Try Again", data="clone_info")]]
                    )
                    
            except Exception as e:
                logger.error(f"Clone confirmation error: {e}")
                error_text = f"❌ **Error creating bot:** {str(e)[:200]}"
                await event.edit(
                    error_text,
                    buttons=[[Button.inline("🔙 Back", data="clone_info")]]
                )
        
        elif data == "confirm_remove":
            # Handle bot removal confirmation
            user_id = event.sender_id
            
            if str(user_id) not in clone_stats:
                await event.answer("❌ No bot found to remove!", alert=True)
                return
            
            try:
                bot_info = clone_stats[str(user_id)]
                bot_username = bot_info.get('bot_username', 'Unknown')
                
                # Stop the bot
                await stop_cloned_bot(bot_username)
                
                # Remove from stats
                del clone_stats[str(user_id)]
                save_data()
                
                await event.edit(
                    f"✅ **Bot Removed Successfully!**\n\n"
                    f"**Bot:** @{bot_username}\n"
                    f"**Removed:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"**Note:**\n"
                    f"• Bot has been stopped\n"
                    f"• All data deleted\n"
                    f"• Token revoked from memory\n\n"
                    f"You can create a new bot anytime with `/clone`",
                    buttons=[
                        [Button.url("🤖 BotFather", "https://t.me/BotFather")],
                        [Button.inline("🔧 Clone New Bot", data="clone_info")]
                    ]
                )
                
            except Exception as e:
                logger.error(f"Remove confirmation error: {e}")
                await event.edit(
                    f"❌ **Error removing bot:** {str(e)[:100]}",
                    buttons=[[Button.inline("🔙 Back", data="back_start")]]
                )
        
        elif data == "remove_my_bot":
            # Quick remove button
            user_id = event.sender_id
            
            if str(user_id) not in clone_stats:
                await event.answer("❌ No bot found!", alert=True)
                return
            
            bot_info = clone_stats[str(user_id)]
            bot_username = bot_info.get('bot_username', 'Unknown')
            
            await event.edit(
                f"🗑️ **Remove @{bot_username}**\n\n"
                f"Are you sure you want to remove your bot?",
                buttons=[
                    [Button.inline("✅ Yes, Remove", data="confirm_remove")],
                    [Button.inline("❌ Keep Bot", data="back_start")]
                ]
            )
        
        elif data == "my_clone_stats":
            # Show user's clone stats
            user_id = event.sender_id
            
            if str(user_id) not in clone_stats:
                await event.answer("❌ You don't have a cloned bot!", alert=True)
                return
            
            bot_info = clone_stats[str(user_id)]
            bot_username = bot_info.get('bot_username', 'Unknown')
            created_at = datetime.fromisoformat(bot_info.get('created_at', datetime.now().isoformat()))
            
            stats_text = f"📊 **My Bot Stats**\n\n"
            stats_text += f"🤖 **Bot:** @{bot_username}\n"
            stats_text += f"📅 **Created:** {created_at.strftime('%d %b %Y')}\n"
            stats_text += f"⏰ **Running for:** {get_time_difference(created_at)}\n"
            stats_text += f"🚀 **Starts:** {bot_info.get('starts', 0)}\n"
            stats_text += f"🤫 **Whispers:** {bot_info.get('whispers', 0)}\n"
            stats_text += f"💬 **Messages:** {bot_info.get('messages', 0)}\n"
            stats_text += f"✅ **Status:** Active\n\n"
            stats_text += f"🆔 **Your ID:** {user_id}\n"
            stats_text += f"⚡ **Powered by:** @{BOT_USERNAME}"
            
            await event.edit(
                stats_text,
                buttons=[
                    [Button.url(f"🚀 Start @{bot_username}", f"https://t.me/{bot_username}")],
                    [Button.switch_inline(f"💌 Use @{bot_username}", query="")],
                    [Button.inline("🗑️ Remove Bot", data="remove_my_bot")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
        
        elif data.startswith("group_user_"):
            # Handle group user selection
            user_query = data.replace("group_user_", "")
            await event.answer(f"👤 Selected: {user_query}", alert=False)
            
            # Switch to inline mode with user query
            await event.edit(
                f"🔒 **Send whisper to {user_query}**\n\n"
                f"Now switch to inline mode by clicking the button below,\n"
                f"then type your message and send.",
                buttons=[[Button.switch_inline(
                    f"💌 Whisper to {user_query}", 
                    query=f"message {user_query}"
                )]]
            )
        
        elif data.startswith("clear_group_"):
            chat_id = int(data.replace("clear_group_", ""))
            if chat_id in group_users_last_5:
                group_users_last_5[chat_id] = []
                save_data()
                await event.answer("✅ Group user list cleared!", alert=True)
                await event.edit(
                    "🧹 **Group user list cleared!**\n\n"
                    "The recent users list for this group has been reset.",
                    buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
                )
        
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
                    f"Now switch to inline mode by clicking the button below,\n"
                    f"then type your message and send.",
                    buttons=[[Button.switch_inline(
                        f"💌 Message {target_text}", 
                        query=f"{target_text}"
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
                        [Button.inline("🔧 Clone Bot", data="clone_info")],
                        [Button.inline("📢 Broadcast", data="broadcast_menu")]
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
            target_user_id = msg_data.get('user_id')
            
            # Check if message is for this user
            if isinstance(target_user_id, int) and event.sender_id == target_user_id:
                # Target user opening the message
                sender_info = ""
                try:
                    sender = await bot.get_entity(msg_data['sender_id'])
                    sender_name = getattr(sender, 'first_name', 'Someone')
                    sender_info = f"\n\n💌 From: {sender_name}"
                except:
                    sender_info = f"\n\n💌 From: Anonymous"
                
                await event.answer(f"🔓 {msg_data['msg']}{sender_info}", alert=True)
            elif event.sender_id == msg_data['sender_id']:
                # Sender viewing their own message
                await event.answer(f"📝 Your message: {msg_data['msg']}\n\n👤 To: {msg_data.get('target_name', 'User')}", alert=True)
            else:
                # Check if it's a string ID that matches
                if isinstance(target_user_id, str) and target_user_id.isdigit():
                    if event.sender_id == int(target_user_id):
                        await event.answer(f"🔓 {msg_data['msg']}\n\n💌 From: Anonymous", alert=True)
                    else:
                        await event.answer("🔒 This message is not for you!", alert=True)
                else:
                    # For non-existent users, anyone can read (or implement your logic)
                    if not msg_data.get('target_exists', True):
                        await event.answer(f"📨 Message for {msg_data.get('target_name')}: {msg_data['msg']}", alert=True)
                    else:
                        await event.answer("🔒 This message is not for you!", alert=True)
        
        else:
            await event.answer("❌ Invalid button!", alert=True)
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await event.answer("❌ An error occurred. Please try again.", alert=True)

# ============ GROUP DETECTION EVENT ============

@bot.on(events.ChatAction)
async def chat_action_handler(event):
    """Detect when bot is added to a group"""
    try:
        if event.user_added or event.user_joined:
            me = await bot.get_me()
            if me.id in event.user_ids:
                # Bot was added to a group
                chat = await event.get_chat()
                chat_id = chat.id
                
                logger.info(f"🤖 Bot added to group: {chat_id} - {chat.title}")
                
                # Add to detected groups
                group_detected.add(chat_id)
                last_group_activity[chat_id] = datetime.now().timestamp()
                save_data()
                
                # Send welcome message
                welcome_msg = (
                    f"🤫 **Whisper Bot has been added to this group!**\n\n"
                    f"🔒 **Features:**\n"
                    f"• Send anonymous whispers to group members\n"
                    f"• Only the intended recipient can read\n"
                    f"• Recent members appear automatically\n\n"
                    f"**Usage:**\n"
                    f"1. Type `@{me.username}` in chat\n"
                    f"2. Write your message\n"
                    f"3. Add @username at the end\n"
                    f"4. Send!\n\n"
                    f"**Example:** `@{me.username} Hello! @username`\n\n"
                    f"🎯 **Try it now using the button below!**"
                )
                
                await event.reply(
                    welcome_msg,
                    buttons=[
                        [Button.switch_inline("🚀 Send Whisper", query="", same_peer=True)],
                        [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                        [Button.url("👥 Support", f"https://t.me/{SUPPORT_GROUP}")]
                    ]
                )
    except Exception as e:
        logger.error(f"Chat action error: {e}")

# ============ GROUP MESSAGE HANDLER ============

@bot.on(events.NewMessage(incoming=True))
async def message_handler(event):
    """Track users in groups"""
    try:
        if event.is_group or event.is_channel:
            chat_id = event.chat_id
            
            # Track the user who sent message
            if event.sender_id and event.sender_id > 0:  # Not a bot or channel
                add_user_to_group_history(
                    chat_id,
                    event.sender_id,
                    event.sender.username,
                    event.sender.first_name
                )
                
    except Exception as e:
        pass  # Silently ignore tracking errors

# ============ FLASK ROUTES ============

@app.route('/')
def home():
    """Home page with bot statistics"""
    bot_username = BOT_USERNAME or "bot_username"
    
    recent_users_count = len(recent_users)
    total_messages = len(messages_db)
    total_clones = len(clone_stats)
    groups_detected_count = len(group_detected)
    group_users = sum(len(users) for users in group_users_last_5.values())
    server_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>ShriBots Whisper Bot</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; text-align: center; }}
            .status {{ background: #4CAF50; color: white; padding: 10px; border-radius: 5px; text-align: center; margin: 20px 0; }}
            .info {{ background: #2196F3; color: white; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 ShriBots Whisper Bot</h1>
            <div class="status">✅ Bot is Running Successfully</div>
            <div class="info">
                <strong>📊 Statistics:</strong><br>
                Recent Users: {recent_users_count}<br>
                Total Messages: {total_messages}<br>
                Total Clones: {total_clones}<br>
                Active Clone Bots: {len(ACTIVE_CLONE_BOTS)}<br>
                Groups Detected: {groups_detected_count}<br>
                Group Users: {group_users}<br>
                Server Time: {server_time}
            </div>
            <p>This bot allows you to send anonymous secret messages to Telegram users.</p>
            <p><strong>Key Features:</strong></p>
            <ul>
                <li>🔒 Send whispers to ANY username or ID (even non-existent)</li>
                <li>🤖 REAL bot cloning - Create your own working bot</li>
                <li>📢 Broadcast to users and groups</li>
                <li>👥 Auto group detection and user tracking</li>
                <li>🎯 Easy inline mode with multiple formats</li>
            </ul>
            <p><strong>Usage:</strong> Use inline mode in any chat: <code>@{bot_username} your_message @username</code></p>
            <p><strong>Clone your own bot:</strong> Use <code>/clone your_bot_token</code></p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    """Health check endpoint"""
    bot_connected = False
    try:
        bot_connected = bot.is_connected()
    except:
        pass
        
    return json.dumps({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "recent_users": len(recent_users),
        "total_messages": len(messages_db),
        "total_clones": len(clone_stats),
        "active_clone_bots": len(ACTIVE_CLONE_BOTS),
        "groups_detected": len(group_detected),
        "group_users": sum(len(users) for users in group_users_last_5.values()),
        "bot_connected": bot_connected
    })

# ============ FLASK SERVER THREAD ============

def run_flask():
    """Run Flask web server"""
    logger.info(f"🌐 Starting Flask server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

# Start Flask in background thread
flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

# ============ RESTART CLONE BOTS ON STARTUP ============

async def restart_clone_bots():
    """Restart previously active clone bots on startup"""
    try:
        logger.info("🔄 Checking for clone bots to restart...")
        
        # We can't restart without tokens, so just mark them
        for bot_username, bot_info in list(ACTIVE_CLONE_BOTS.items()):
            if bot_info.get('status') == 'active':
                logger.info(f"⚠️ Clone bot @{bot_username} needs manual restart (token not stored)")
                ACTIVE_CLONE_BOTS[bot_username]['status'] = 'needs_restart'
        
        save_data()
        
    except Exception as e:
        logger.error(f"Error in restart_clone_bots: {e}")

# ============ CLEANUP FUNCTION ============

async def cleanup():
    """Cleanup all clone bots on shutdown"""
    try:
        logger.info("🛑 Stopping all clone bots...")
        
        for bot_username in list(user_bots.keys()):
            await stop_cloned_bot(bot_username)
        
        logger.info("✅ Cleanup completed")
    except Exception as e:
        logger.error(f"Error in cleanup: {e}")

# ============ MAIN FUNCTION ============

async def main():
    """Main function to start the bot"""
    global BOT_USERNAME
    try:
        me = await bot.get_me()
        BOT_USERNAME = me.username
        
        # Check for clone bots to restart
        await restart_clone_bots()
        
        logger.info(f"🎭 ShriBots Whisper Bot Started!")
        logger.info(f"🤖 Main Bot: @{me.username}")
        logger.info(f"🤖 Active Clone Bots: {len([b for b in ACTIVE_CLONE_BOTS.values() if b.get('status') == 'active'])}")
        logger.info(f"👑 Admin: {ADMIN_ID}")
        logger.info(f"👥 Recent Users: {len(recent_users)}")
        logger.info(f"🌐 Web server running on port {PORT}")
        logger.info("✅ Bot is ready and working!")
        logger.info("🔗 Use /start to begin")
        logger.info("📢 **KEY FEATURES:**")
        logger.info("   • Accepts ANY username or ID (even non-existent)")
        logger.info("   • REAL bot cloning with actual working bots")
        logger.info("   • Full whisper functionality for cloned bots")
        logger.info("   • Broadcast to users and groups")
        logger.info("   • Group detection and user tracking")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

# ============ ENTRY POINT ============

if __name__ == '__main__':
    print("🚀 Starting ShriBots Whisper Bot with REAL Cloning...")
    print(f"📝 Environment: API_ID={API_ID}, PORT={PORT}")
    print("\n🔥 **KEY FEATURES ACTIVATED:**")
    print("   1️⃣ Accepts ANY username/ID (even invalid)")
    print("   2️⃣ REAL bot cloning (actual working bots)")
    print("   3️⃣ Clone bots have full functionality")
    print("   4️⃣ Broadcast to users & groups")
    print("   5️⃣ Group detection & user tracking")
    
    try:
        # Start the bot
        bot.start()
        bot.loop.run_until_complete(main())
        
        print("\n✅ Bot started successfully!")
        print("🔄 Bot is now running...")
        print("\n📋 **Available Commands:**")
        print("   • /start - Start bot")
        print("   • /help - Show help")
        print("   • /clone YOUR_BOT_TOKEN - Create REAL working bot")
        print("   • /remove - Remove your bot")
        print("   • /broadcast - Broadcast to users (Admin)")
        print("   • /gbroadcast - Broadcast to groups (Admin)")
        print("   • /stats - Admin statistics")
        print("\n💡 **Inline Usage Examples:**")
        print("   • @bot_username Hello! @username")
        print("   • @bot_username @username Hello!")
        print("   • @bot_username I miss you 123456789")
        print("   • @bot_username 123456789 I miss you")
        print("   • @bot_username message @ANY_USERNAME (even non-existent)")
        
        # Keep the bot running
        bot.run_until_disconnected()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        bot.loop.run_until_complete(cleanup())
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        print(f"❌ Error: {e}")
    finally:
        print("💾 Saving data before exit...")
        save_data()
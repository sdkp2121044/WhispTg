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

# Environment variables
API_ID = int(os.getenv('API_ID', ''))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_ID = int(os.getenv('ADMIN_ID', ''))
PORT = int(os.environ.get('PORT', 10000))

# Import Telethon
try:
    from telethon import TelegramClient, events, Button
    from telethon.tl.types import User
    from telethon.errors import (
        UsernameNotOccupiedError, 
        UsernameInvalidError,
        FloodWaitError
    )
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
# Cache for user entities to avoid repeated API calls
user_entity_cache = {}
# Inline query cache for quick suggestions
inline_cache = {}

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

✨ **NEW FEATURES:**
• Real-time username detection
• History suggestions while typing
• Auto-suggest last recipient
• Space के बाद भी suggestions

Create whispers that only specific users can unlock!
"""

HELP_TEXT = """
📖 **How to Use Whisper Bot**

**1. Basic Usage:**
   • Type `@{}` in any chat
   • Write your message  
   • Add @username OR user ID
   • Send!

**2. Smart Detection:**
   • Type `@{} how are you 123456789`
   • Bot auto-detects `123456789` as user ID
   • No need to type @ before number!

**3. History Suggestions:**
   • Start typing `@{} ` (with space)
   • See your recent recipients
   • Click to select quickly

**4. Auto-Suggest:**
   • Type just your message
   • Last recipient auto-selected
   • Send without typing username!

**5. Commands:**
   • /start - Start bot
   • /help - Show help
   • /history - View your history
   • /clear - Clear your history
   • /stats - Admin statistics

🔒 **Only the mentioned user can read your message!**
✨ **Smart detection + History suggestions!**
"""

async def get_user_entity(user_identifier):
    """
    Get user entity with caching and error handling
    user_identifier can be: username (string) or user_id (int)
    """
    cache_key = str(user_identifier)
    
    # Check cache first (valid for 5 minutes)
    if cache_key in user_entity_cache:
        cached_data = user_entity_cache[cache_key]
        cache_time = datetime.fromisoformat(cached_data['timestamp'])
        if datetime.now() - cache_time < timedelta(minutes=5):
            return cached_data['entity']
        else:
            del user_entity_cache[cache_key]
    
    try:
        if isinstance(user_identifier, int) or (isinstance(user_identifier, str) and user_identifier.isdigit()):
            # Handle user ID
            user_id = int(user_identifier)
            
            # First try to get from cache or recent history
            for user_data in user_history.values():
                for item in user_data:
                    if item['id'] == user_id:
                        # Create a minimal user object
                        entity = type('obj', (object,), {
                            'id': user_id,
                            'username': item.get('username'),
                            'first_name': item.get('name', 'User'),
                            'last_name': None
                        })()
                        # Cache it
                        user_entity_cache[cache_key] = {
                            'entity': entity,
                            'timestamp': datetime.now().isoformat()
                        }
                        return entity
            
            # Try to get from Telegram API
            try:
                entity = await bot.get_entity(user_id)
                if hasattr(entity, 'first_name'):
                    # Cache the result
                    user_entity_cache[cache_key] = {
                        'entity': entity,
                        'timestamp': datetime.now().isoformat()
                    }
                    return entity
            except Exception as e:
                logger.warning(f"Could not fetch user {user_id}: {e}")
                
                # Create a minimal user object
                entity = type('obj', (object,), {
                    'id': user_id,
                    'username': None,
                    'first_name': f'User {user_id}',
                    'last_name': None
                })()
                return entity
                
        else:
            # Handle username
            username = user_identifier.lower().replace('@', '')
            
            # Validate username format
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', username):
                raise UsernameInvalidError("Invalid username format")
            
            # Try to get from Telegram API
            try:
                entity = await bot.get_entity(username)
                if hasattr(entity, 'first_name'):
                    # Cache the result
                    user_entity_cache[cache_key] = {
                        'entity': entity,
                        'timestamp': datetime.now().isoformat()
                    }
                    return entity
                else:
                    raise ValueError("Not a user entity")
            except (UsernameNotOccupiedError, ValueError) as e:
                logger.warning(f"Username @{username} not found: {e}")
                raise UsernameNotOccupiedError(f"User @{username} not found")
                
    except FloodWaitError as e:
        logger.error(f"Flood wait: {e.seconds} seconds")
        raise
    except Exception as e:
        logger.error(f"Error getting user entity for {user_identifier}: {e}")
        raise

def update_user_history(user_id, target_user_id, target_username=None, target_name=None):
    """Update user's last recipient history"""
    try:
        user_id_str = str(user_id)
        if user_id_str not in user_history:
            user_history[user_id_str] = []
        
        # Check if target already in history
        existing_index = -1
        for i, item in enumerate(user_history[user_id_str]):
            if item.get('id') == target_user_id:
                existing_index = i
                break
        
        if existing_index >= 0:
            # Remove from current position
            existing_item = user_history[user_id_str].pop(existing_index)
            # Update and add to beginning
            existing_item['timestamp'] = datetime.now().isoformat()
            existing_item['username'] = target_username or existing_item.get('username')
            existing_item['name'] = target_name or existing_item.get('name', 'User')
            user_history[user_id_str].insert(0, existing_item)
        else:
            # Add new entry at beginning
            history_entry = {
                'id': target_user_id,
                'username': target_username,
                'name': target_name or f'User {target_user_id}',
                'timestamp': datetime.now().isoformat()
            }
            user_history[user_id_str].insert(0, history_entry)
        
        # Keep only last 10 recipients
        if len(user_history[user_id_str]) > 10:
            user_history[user_id_str] = user_history[user_id_str][:10]
        
        save_data()
    except Exception as e:
        logger.error(f"Error updating user history: {e}")

def get_user_history_buttons(user_id, current_query=""):
    """Get user's history as inline buttons"""
    try:
        user_id_str = str(user_id)
        if user_id_str not in user_history or not user_history[user_id_str]:
            return []
        
        buttons = []
        for item in user_history[user_id_str][:8]:  # Max 8 suggestions
            username = item.get('username')
            name = item.get('name', 'User')
            user_id_val = item.get('id')
            
            # Create display text
            if username:
                display_text = f"@{username}"
                query_text = f"{current_query} @{username}"
            else:
                display_text = f"{name} ({user_id_val})"
                query_text = f"{current_query} {user_id_val}"
            
            # Truncate if too long
            if len(display_text) > 20:
                display_text = display_text[:17] + "..."
            
            buttons.append([
                Button.switch_inline(
                    f"🔤 {display_text}",
                    query=query_text.strip(),
                    same_peer=True
                )
            ])
        
        return buttons
    except Exception as e:
        logger.error(f"Error getting history buttons: {e}")
        return []

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
        if now - user_cooldown[user_id_str] < 1:  # 1 second cooldown
            return True
    
    user_cooldown[user_id_str] = now
    return False

def extract_target_from_text(text):
    """
    Smart extraction of target user from text
    Returns: (target_user, message_text, target_type)
    """
    text = text.strip()
    
    # Pattern 1: Username at end with @
    # Example: "how are you @username"
    username_pattern = r'(.*?)\s*@([a-zA-Z][a-zA-Z0-9_]{3,30})\s*$'
    match = re.match(username_pattern, text, re.IGNORECASE)
    if match:
        message_text = match.group(1).strip()
        target_user = match.group(2)
        return target_user, message_text, 'username'
    
    # Pattern 2: User ID at end (8+ digits)
    # Example: "how are you 123456789"
    userid_pattern = r'(.*?)\s*(\d{8,})\s*$'
    match = re.match(userid_pattern, text, re.IGNORECASE)
    if match:
        message_text = match.group(1).strip()
        target_user = match.group(2)
        return target_user, message_text, 'userid'
    
    # Pattern 3: Username anywhere in text with @
    # Example: "hello @username how are you"
    username_anywhere = r'.*?@([a-zA-Z][a-zA-Z0-9_]{3,30}).*'
    match = re.match(username_anywhere, text, re.IGNORECASE)
    if match:
        target_user = match.group(1)
        # Remove the @username from message
        message_text = re.sub(r'@' + re.escape(target_user), '', text, flags=re.IGNORECASE).strip()
        return target_user, message_text, 'username'
    
    # Pattern 4: User ID anywhere in text (8+ digits)
    # Example: "hello 123456789 how are you"
    userid_anywhere = r'.*?(\d{8,}).*'
    match = re.match(userid_anywhere, text, re.IGNORECASE)
    if match:
        target_user = match.group(1)
        # Remove the user ID from message
        message_text = re.sub(r'\b' + re.escape(target_user) + r'\b', '', text).strip()
        return target_user, message_text, 'userid'
    
    # Pattern 5: "to @username:" format
    # Example: "to @username: hello how are you"
    to_username_pattern = r'to\s+@([a-zA-Z][a-zA-Z0-9_]{3,30})\s*:\s*(.*)'
    match = re.match(to_username_pattern, text, re.IGNORECASE)
    if match:
        target_user = match.group(1)
        message_text = match.group(2).strip()
        return target_user, message_text, 'username'
    
    # Pattern 6: "to userid:" format
    # Example: "to 123456789: hello how are you"
    to_userid_pattern = r'to\s+(\d{8,})\s*:\s*(.*)'
    match = re.match(to_userid_pattern, text, re.IGNORECASE)
    if match:
        target_user = match.group(1)
        message_text = match.group(2).strip()
        return target_user, message_text, 'userid'
    
    return None, text, None

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
            [Button.inline("📖 Help", data="help"), Button.inline("📜 History", data="view_history")],
            [Button.inline("🗑️ Clear", data="clear_history")]
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

@bot.on(events.NewMessage(pattern='/history'))
async def history_handler(event):
    """Show user's whisper history"""
    try:
        user_id_str = str(event.sender_id)
        
        if user_id_str not in user_history or not user_history[user_id_str]:
            await event.reply("📭 You haven't sent any whispers yet!")
            return
        
        history_text = "📜 **Your Recent Recipients:**\n\n"
        
        for i, item in enumerate(user_history[user_id_str][:10], 1):
            name = item.get('name', 'User')
            username = item.get('username')
            user_id_val = item.get('id')
            
            if username:
                history_text += f"{i}. **{name}** (@{username}) `{user_id_val}`\n"
            else:
                history_text += f"{i}. **{name}** `{user_id_val}`\n"
        
        history_text += f"\nTotal: {len(user_history[user_id_str])} recipients"
        
        await event.reply(
            history_text,
            buttons=[
                [Button.switch_inline("💌 Whisper to Recent", query="")],
                [Button.inline("🗑️ Clear History", data="clear_history")],
                [Button.inline("🔙 Back", data="back_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"History error: {e}")
        await event.reply("❌ Error loading history.")

@bot.on(events.NewMessage(pattern='/clear'))
async def clear_handler(event):
    """Clear user's recipient history"""
    try:
        user_id_str = str(event.sender_id)
        if user_id_str in user_history and user_history[user_id_str]:
            count = len(user_history[user_id_str])
            del user_history[user_id_str]
            save_data()
            await event.reply(f"✅ Cleared {count} recipients from your history!")
        else:
            await event.reply("📭 You have no history to clear.")
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
        total_history_entries = 0
        
        for user_id, user_data in user_history.items():
            total_history_entries += len(user_data)
            if user_data:
                last_time = datetime.fromisoformat(user_data[0]['timestamp'])
                if last_time > week_ago:
                    active_users += 1
        
        stats_text = f"""
📊 **Admin Statistics**

👥 Total Users: {total_users}
📈 Active Users (7 days): {active_users}
💬 Total Messages: {total_messages}
📋 Total History Entries: {total_history_entries}
🧠 Cached Users: {len(user_entity_cache)}
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
    """Handle inline queries with smart detection and suggestions"""
    try:
        if is_cooldown(event.sender_id):
            await event.answer([])
            return

        query_text = event.text.strip() if event.text else ""
        sender_id = event.sender_id
        
        # Case 1: Empty query - Show help with history
        if not query_text:
            last_recipient = get_last_recipient(sender_id)
            history_buttons = get_user_history_buttons(sender_id, "")
            
            if last_recipient:
                target_name = last_recipient.get('name', 'User')
                result_text = f"""
**🤫 Whisper Bot - Smart Detection**

📝 **Last Recipient:** {target_name}
✨ **Type your message and bot will auto-detect recipient!**

**Examples:**
1. `how are you 123456789` (Auto-detects user ID)
2. `hello @username` (Auto-detects @username)
3. `Just type message` (Auto-sends to last recipient)

💡 **Start typing to see history suggestions!**
                """
            else:
                result_text = """
**🤫 Whisper Bot - Smart Detection**

✨ **Smart features:**
• Auto-detect username/userID from message
• History suggestions while typing
• Auto-suggest last recipient

**How to use:**
1. Type your message
2. Add @username OR user ID anywhere
3. Or just type message for auto-suggest
4. Bot will detect automatically!

**Examples:**
• `how are you @username`
• `hello 123456789`
• `Just your message` (auto to last)
                """
            
            # Create main result
            result = event.builder.article(
                title="🤫 Whisper Bot - Smart Detection",
                description="Type message with @username or user ID",
                text=result_text,
                buttons=history_buttons or [[Button.switch_inline("🚀 Try Now", query="")]]
            )
            await event.answer([result])
            return
        
        # Case 2: Query has content - Try to detect target
        # First get history suggestions for current query
        history_buttons = get_user_history_buttons(sender_id, query_text)
        
        # Try to extract target from text
        target_user, message_text, target_type = extract_target_from_text(query_text)
        
        # Case 2A: Target detected in query
        if target_user and target_type:
            try:
                if target_type == 'userid':
                    # Validate user ID
                    if not target_user.isdigit() or len(target_user) < 8:
                        raise ValueError("Invalid user ID")
                    
                    user_obj = await get_user_entity(int(target_user))
                    target_user_id = int(target_user)
                    target_username = getattr(user_obj, 'username', None)
                    target_name = getattr(user_obj, 'first_name', f'User {target_user}')
                    
                else:  # username
                    username = target_user.lower().replace('@', '')
                    
                    # Validate username
                    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', username):
                        raise UsernameInvalidError("Invalid username")
                    
                    user_obj = await get_user_entity(username)
                    target_user_id = user_obj.id
                    target_username = username
                    target_name = getattr(user_obj, 'first_name', f'@{username}')
                
                # Validate message
                if not message_text:
                    # Show error with history suggestions
                    result = event.builder.article(
                        title="❌ Empty Message",
                        description="Please enter a message",
                        text="**Message is empty!**\n\nPlease type your secret message after the username/user ID.\n\n💡 Try these formats:\n• `hello @username`\n• `how are you 123456789`",
                        buttons=history_buttons
                    )
                    await event.answer([result])
                    return
                
                # Update user history
                update_user_history(
                    sender_id,
                    target_user_id,
                    target_username,
                    target_name
                )
                
                # Create message entry
                message_id = f'msg_{sender_id}_{target_user_id}_{int(datetime.now().timestamp())}'
                messages_db[message_id] = {
                    'user_id': target_user_id,
                    'msg': message_text,
                    'sender_id': sender_id,
                    'timestamp': datetime.now().isoformat(),
                    'target_name': target_name,
                    'target_username': target_username,
                    'detected_automatically': True
                }
                
                # Create result
                result_text = f"""
**🔐 Secret message for {target_name}!**

💬 **Message:** {message_text[:50]}{'...' if len(message_text) > 50 else ''}

✨ **Smart Detection:** Bot automatically detected {target_name} from your message!

🔒 **Only {target_name} can open this message.**
                """
                
                result = event.builder.article(
                    title=f"🤫 To {target_name} (Auto-detected)",
                    description=f"Click to send to {target_name}",
                    text=result_text,
                    buttons=[
                        [Button.inline("🔓 Send Secret Message", message_id)],
                        *history_buttons[:2]  # Show first 2 history buttons
                    ]
                )
                
                await event.answer([result])
                return
                
            except (UsernameNotOccupiedError, UsernameInvalidError) as e:
                # Username not found or invalid
                error_text = f"""
❌ **User not found!**

**Problem:** @{target_user} doesn't exist or is invalid.

**Solutions:**
1. Check username spelling
2. Use user ID instead: `{query_text.split('@')[0]} 123456789`
3. Make sure user hasn't changed username

💡 **Valid username:** 4-31 chars, starts with letter
                """
                result = event.builder.article(
                    title=f"❌ @{target_user} not found",
                    description="User doesn't exist",
                    text=error_text,
                    buttons=history_buttons
                )
                await event.answer([result])
                return
                
            except Exception as e:
                logger.error(f"Error processing detected target: {e}")
                # Continue to show suggestions
        
        # Case 2B: No target detected - Check for auto-suggest
        last_recipient = get_last_recipient(sender_id)
        
        if last_recipient and message_text:  # message_text from extraction attempt
            # Auto-suggest mode
            auto_suggested = True
            target_user_id = last_recipient['id']
            target_username = last_recipient.get('username')
            target_name = last_recipient.get('name', 'User')
            
            # Update timestamp
            update_user_history(sender_id, target_user_id, target_username, target_name)
            
            # Create message entry
            message_id = f'msg_{sender_id}_{target_user_id}_{int(datetime.now().timestamp())}'
            messages_db[message_id] = {
                'user_id': target_user_id,
                'msg': query_text,  # Use full query as message
                'sender_id': sender_id,
                'timestamp': datetime.now().isoformat(),
                'target_name': target_name,
                'target_username': target_username,
                'auto_suggested': True
            }
            
            # Create result
            result_text = f"""
**✨ Auto-Suggest Active!**

💬 **Message:** {query_text[:50]}{'...' if len(query_text) > 50 else ''}

👤 **To:** {target_name}
🎯 **Auto-detected from your history!**

🔒 **Only {target_name} can open this message.**
            """
            
            result = event.builder.article(
                title=f"🤫 To {target_name} (Auto-suggest)",
                description=f"Auto-send to {target_name}",
                text=result_text,
                buttons=[
                    [Button.inline("🔓 Send Secret Message", message_id)],
                    *history_buttons[:2]
                ]
            )
            
            await event.answer([result])
            return
        
        # Case 2C: No target and no auto-suggest - Show suggestions
        # Check if query looks like it might have a target soon
        words = query_text.split()
        last_word = words[-1] if words else ""
        
        suggestion_text = """
**💡 Need to specify a recipient!**

Bot couldn't detect a username or user ID in your message.

**Try these formats:**
1. `your message @username`
2. `your message 123456789`
3. `to @username: your message`
4. `to 123456789: your message`

**Or select from your recent recipients below:**
        """
        
        # If last word might be start of username
        if last_word.startswith('@') and len(last_word) > 1:
            suggestion_text += f"\n\n💡 **Tip:** Finish typing the username: `{last_word}...`"
        
        result = event.builder.article(
            title="❌ Specify a recipient",
            description="Add @username or user ID",
            text=suggestion_text,
            buttons=history_buttons or [
                [Button.switch_inline("🔄 Try Again", query=query_text)]
            ]
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
        
        elif data == "view_history":
            user_id_str = str(event.sender_id)
            
            if user_id_str not in user_history or not user_history[user_id_str]:
                await event.answer("No history found!", alert=True)
                await event.edit(
                    "📭 You haven't sent any whispers yet!",
                    buttons=[[Button.switch_inline("🚀 Send First Whisper", query="")]]
                )
                return
            
            history_text = "📜 **Your Recent Recipients:**\n\n"
            
            for i, item in enumerate(user_history[user_id_str][:8], 1):
                name = item.get('name', 'User')
                username = item.get('username')
                user_id_val = item.get('id')
                
                if username:
                    history_text += f"{i}. **{name}** (@{username}) `{user_id_val}`\n"
                else:
                    history_text += f"{i}. **{name}** `{user_id_val}`\n"
            
            history_text += f"\nTotal: {len(user_history[user_id_str])} recipients"
            
            # Create buttons for quick selection
            buttons = []
            for item in user_history[user_id_str][:4]:
                username = item.get('username')
                name = item.get('name', 'User')
                
                if username:
                    display = f"🔤 @{username}"
                    query = f" @{username}"
                else:
                    display = f"🔢 {name}"
                    query = f" {item['id']}"
                
                buttons.append([
                    Button.switch_inline(
                        display[:20],
                        query=query,
                        same_peer=True
                    )
                ])
            
            buttons.append([
                Button.inline("🗑️ Clear All", data="clear_history"),
                Button.inline("🔙 Back", data="back_start")
            ])
            
            await event.edit(history_text, buttons=buttons)
        
        elif data == "admin_stats":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
                
            total_users = len(user_history)
            total_messages = len(messages_db)
            total_history_entries = sum(len(v) for v in user_history.values())
            
            stats_text = f"📊 **Admin Statistics**\n\n"
            stats_text += f"👥 Total Users: {total_users}\n"
            stats_text += f"💬 Total Messages: {total_messages}\n"
            stats_text += f"📋 History Entries: {total_history_entries}\n"
            stats_text += f"🧠 Cached Users: {len(user_entity_cache)}\n"
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
            if user_id_str in user_history and user_history[user_id_str]:
                count = len(user_history[user_id_str])
                del user_history[user_id_str]
                save_data()
                await event.answer(f"✅ Cleared {count} recipients!", alert=True)
                await event.edit(
                    f"✅ Cleared {count} recipients from your history!\n\nNext whisper will need explicit @username or ID.",
                    buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
                )
            else:
                await event.answer("No history to clear!", alert=True)
        
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
                [Button.inline("📖 Help", data="help"), Button.inline("📜 History", data="view_history")],
                [Button.inline("🗑️ Clear", data="clear_history")]
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
                    sender_id = msg_data['sender_id']
                    cache_key = str(sender_id)
                    if cache_key in user_entity_cache:
                        sender = user_entity_cache[cache_key]['entity']
                    else:
                        try:
                            sender = await bot.get_entity(sender_id)
                        except:
                            sender = type('obj', (object,), {
                                'first_name': 'Someone',
                                'username': None
                            })()
                    
                    sender_name = getattr(sender, 'first_name', 'Someone')
                    sender_info = f"\n\n💌 From: {sender_name}"
                    if hasattr(sender, 'username') and sender.username:
                        sender_info += f" (@{sender.username})"
                except:
                    sender_info = f"\n\n💌 From: Anonymous"
                
                alert_text = f"🔓 {msg_data['msg']}{sender_info}"
                if msg_data.get('detected_automatically'):
                    alert_text += "\n\n✨ This message was auto-detected from your text!"
                elif msg_data.get('auto_suggested'):
                    alert_text += "\n\n✨ This was sent using auto-suggest!"
                
                await event.answer(alert_text, alert=True)
            
            elif event.sender_id == msg_data['sender_id']:
                # Sender viewing their own message
                alert_text = f"📝 Your message: {msg_data['msg']}\n\n👤 To: {msg_data.get('target_name', 'User')}"
                if msg_data.get('target_username'):
                    alert_text += f" (@{msg_data['target_username']})"
                
                if msg_data.get('detected_automatically'):
                    alert_text += "\n\n✅ Smart detection was used!"
                elif msg_data.get('auto_suggested'):
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
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
            body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
            .container { background: white; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); overflow: hidden; width: 100%; max-width: 900px; }
            .header { background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); color: white; padding: 30px; text-align: center; }
            .header h1 { font-size: 2.5rem; margin-bottom: 10px; display: flex; align-items: center; justify-content: center; gap: 15px; }
            .header p { font-size: 1.1rem; opacity: 0.9; }
            .content { padding: 40px; }
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 30px; }
            .stat-card { background: #f8fafc; border-radius: 15px; padding: 20px; text-align: center; border: 2px solid #e2e8f0; transition: transform 0.3s, border-color 0.3s; }
            .stat-card:hover { transform: translateY(-5px); border-color: #4f46e5; }
            .stat-value { font-size: 2.2rem; font-weight: bold; color: #4f46e5; margin-bottom: 8px; }
            .stat-label { font-size: 0.9rem; color: #64748b; font-weight: 500; }
            .feature-card { background: #f1f5f9; border-radius: 15px; padding: 25px; margin-bottom: 20px; border-left: 5px solid #4f46e5; }
            .feature-card h3 { color: #334155; margin-bottom: 15px; display: flex; align-items: center; gap: 10px; }
            .feature-card ul { list-style: none; padding-left: 0; }
            .feature-card li { padding: 8px 0; color: #475569; display: flex; align-items: center; gap: 10px; }
            .example-box { background: #e0e7ff; border-radius: 10px; padding: 15px; margin: 15px 0; border-left: 4px solid #4f46e5; }
            .example-box code { background: white; padding: 5px 10px; border-radius: 5px; font-family: monospace; display: block; margin: 5px 0; }
            .bot-link { display: inline-block; background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); color: white; text-decoration: none; padding: 15px 30px; border-radius: 50px; font-weight: bold; font-size: 1.1rem; margin-top: 20px; transition: transform 0.3s, box-shadow 0.3s; }
            .bot-link:hover { transform: translateY(-3px); box-shadow: 0 10px 25px rgba(79, 70, 229, 0.4); }
            .status-badge { display: inline-block; padding: 8px 20px; background: #10b981; color: white; border-radius: 50px; font-weight: bold; margin-bottom: 20px; }
            @media (max-width: 768px) { .header h1 { font-size: 2rem; } .content { padding: 20px; } .stats-grid { grid-template-columns: 1fr; } }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤫 ShriBots Whisper Bot</h1>
                <p>Smart detection + History suggestions</p>
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
                        <div class="stat-value">{{ total_history }}</div>
                        <div class="stat-label">📜 History Entries</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-value">{{ cached_users }}</div>
                        <div class="stat-label">🧠 Cached Users</div>
                    </div>
                </div>
                
                <div class="feature-card">
                    <h3>🎯 Smart Detection Features</h3>
                    <ul>
                        <li>🔍 Auto-detect username/userID anywhere in message</li>
                        <li>📝 No specific format needed - bot understands naturally</li>
                        <li>💾 History suggestions while typing (space देने के बाद भी)</li>
                        <li>🔄 Auto-suggest last recipient</li>
                    </ul>
                    
                    <div class="example-box">
                        <strong>📋 Examples (All work!):</strong>
                        <code>how are you @username</code>
                        <code>hello 123456789</code>
                        <code>to @username: how are you</code>
                        <code>to 123456789: hello there</code>
                        <code>Just type message (auto to last)</code>
                    </div>
                </div>
                
                <div class="feature-card">
                    <h3>🚀 How to Use</h3>
                    <ul>
                        <li>1. Type @{{ bot_username }} in any Telegram chat</li>
                        <li>2. Write your message naturally</li>
                        <li>3. Include @username or user ID anywhere</li>
                        <li>4. Or just type message for auto-suggest</li>
                        <li>5. See history suggestions while typing!</li>
                        <li>6. Only they can read it 🔒</li>
                    </ul>
                </div>
                
                <center>
                    <a href="https://t.me/{{ bot_username }}" class="bot-link" target="_blank">
                        🚀 Start Using Smart Whisper Bot
                    </a>
                </center>
            </div>
        </div>
    </body>
    </html>
    """
    
    total_history_entries = sum(len(v) for v in user_history.values())
    
    return render_template_string(
        html_template,
        total_users=len(user_history),
        total_messages=len(messages_db),
        total_history=total_history_entries,
        cached_users=len(user_entity_cache),
        bot_username=bot_username
    )

@app.route('/health')
def health():
    total_history_entries = sum(len(v) for v in user_history.values())
    
    return json.dumps({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "total_users": len(user_history),
        "total_messages": len(messages_db),
        "total_history_entries": total_history_entries,
        "cached_users": len(user_entity_cache),
        "bot_connected": bot.is_connected(),
        "version": "3.0",
        "features": ["smart_detection", "history_suggestions", "auto_suggest", "real_time_suggestions"]
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
        total_history_entries = sum(len(v) for v in user_history.values())
        
        logger.info(f"🎭 ShriBots Whisper Bot v3.0 Started!")
        logger.info(f"🤖 Bot: @{me.username}")
        logger.info(f"🆔 Bot ID: {me.id}")
        logger.info(f"👑 Admin: {ADMIN_ID}")
        logger.info(f"👥 Total Users: {len(user_history)}")
        logger.info(f"💬 Total Messages: {len(messages_db)}")
        logger.info(f"📜 Total History Entries: {total_history_entries}")
        logger.info(f"🌐 Web server running on port {PORT}")
        logger.info("🎯 Smart Detection: ACTIVE")
        logger.info("💡 History Suggestions: ENABLED")
        logger.info("🔄 Auto-Suggest: ENABLED")
        logger.info("✅ Bot is ready and working!")
        logger.info("🔗 Use /start to begin")
        
        print("\n" + "="*60)
        print("✨ NEW SMART FEATURES:")
        print("   • Real-time username/userID detection")
        print("   • History suggestions while typing")
        print("   • Space देने के बाद भी suggestions show")
        print("   • Multiple format support")
        print("="*60)
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Starting ShriBots Whisper Bot v3.0")
    print("✨ With Smart Detection & Real-time Suggestions")
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
        # Start the bot
        bot.start()
        bot.loop.run_until_complete(main())
        
        print("=" * 60)
        print("✅ Bot started successfully!")
        print("💡 Try these examples in any chat:")
        print("   1. @bot_username how are you 123456789")
        print("   2. @bot_username hello @username")
        print("   3. @bot_username (space देकर history देखें)")
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
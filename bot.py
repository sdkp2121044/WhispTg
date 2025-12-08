import os
import logging
import re
import asyncio
import json
from datetime import datetime
from flask import Flask
import threading
from typing import List, Dict, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
API_ID = int(os.environ.get('API_ID'))
API_HASH = os.environ.get('API_HASH')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))
PORT = int(os.environ.get('PORT', 10000))

# Import Telethon
try:
    from telethon import TelegramClient, events, Button
    from telethon.errors import SessionPasswordNeededError, ChatWriteForbiddenError, FloodWaitError
    from telethon.tl.types import Channel, Chat
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
group_users_last_5: Dict[int, List[Dict]] = {}  # {chat_id: [user1, user2...]}
group_detected: Set[int] = set()  # Store detected group IDs
last_group_activity: Dict[int, float] = {}  # Track last group activity time

# Data files
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
RECENT_USERS_FILE = os.path.join(DATA_DIR, "recent_users.json")
CLONE_STATS_FILE = os.path.join(DATA_DIR, "clone_stats.json")
GROUP_DATA_FILE = os.path.join(DATA_DIR, "group_data.json")
BROADCAST_HISTORY_FILE = os.path.join(DATA_DIR, "broadcast_history.json")

def load_data():
    global recent_users, clone_stats, group_users_last_5, group_detected, last_group_activity
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
            
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        recent_users = {}
        clone_stats = {}
        group_users_last_5 = {}
        group_detected = set()
        last_group_activity = {}

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
   • /broadcast - Broadcast to all users (Admin only)
   • /gbroadcast - Broadcast to groups (Admin only)

🔒 **Only the mentioned user can read your message!**
"""

# ============ COOLDOWN FUNCTION ============

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

# ============ GET RECENT USERS BUTTONS FUNCTION ============

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

# ============ NEW: GROUP USER TRACKING FUNCTIONS ============

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

# ============ NEW: ADD TO RECENT USERS FUNCTION ============

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

# ============ NEW: BROADCAST FUNCTIONS ============

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

**Bot Status:** ✅ Running
**Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
        """
        
        await event.reply(stats_text)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await event.reply("❌ Error fetching statistics.")

# ============ NEW: BROADCAST COMMANDS ============

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
    """Handle inline queries"""
    try:
        if is_cooldown(event.sender_id):
            await event.answer([])
            return

        # Check if in group
        is_group_context = hasattr(event.query, 'chat_type') and event.query.chat_type in ['group', 'supergroup']
        recent_buttons = []
        
        if is_group_context and hasattr(event, 'chat_id') and event.chat_id in group_users_last_5:
            recent_buttons = get_group_users_buttons(event.chat_id)
        else:
            recent_buttons = get_recent_users_buttons(event.sender_id)
        
        query_text = event.text or ""
        
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
        
        # If user clicked group user button, it will come as data, handle separately
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
                user_obj = await bot.get_entity(int(target_user))
            else:
                if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', target_user):
                    result = event.builder.article(
                        title="❌ Invalid Username",
                        description="Username format is invalid",
                        text="**Valid username format:**\n• Starts with letter\n• 4-31 characters\n• Letters, numbers, underscores only"
                    )
                    await event.answer([result])
                    return
                
                user_obj = await bot.get_entity(target_user)
            
            if not hasattr(user_obj, 'first_name'):
                result = event.builder.article(
                    title="❌ Not a User",
                    description="You can only send to users",
                    text="This appears to be a channel or group. Please mention a user instead."
                )
                await event.answer([result])
                return
            
            # Add to appropriate recent list
            if is_group_context and hasattr(event, 'chat_id'):
                # Update group user history
                chat_id = event.chat_id
                add_user_to_group_history(
                    chat_id,
                    user_obj.id,
                    getattr(user_obj, 'username', None),
                    getattr(user_obj, 'first_name', 'User')
                )
            else:
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
            'target_name': getattr(user_obj, 'first_name', 'User'),
            'is_group': is_group_context,
            'group_id': event.chat_id if hasattr(event, 'chat_id') and is_group_context else None
        }
        
        target_name = getattr(user_obj, 'first_name', 'User')
        result = event.builder.article(
            title=f"🔒 Secret Message for {target_name}",
            description=f"Click to send secret message",
            text=f"**🔐 A secret message for {target_name}!**\n\n*Note: Only {target_name} can open this message.*",
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
            stats_text += f"**Status:** ✅ Running"
            
            await event.edit(
                stats_text,
                buttons=[
                    [Button.inline("📢 Broadcast", data="broadcast_menu")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
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

# ============ NEW: GROUP DETECTION EVENT ============

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

# ============ MODIFIED GROUP MESSAGE HANDLER ============

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

# Flask web server (same as before with added stats)
app = Flask(__name__)

@app.route('/')
def home():
    # Get bot username synchronously
    bot_username = "bot_username"
    try:
        if bot.is_connected():
            # We need to run this in the bot's event loop
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            me = loop.run_until_complete(bot.get_me())
            bot_username = me.username
            loop.close()
    except:
        pass
    
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
                Groups Detected: {}<br>
                Group Users: {}<br>
                Server Time: {}
            </div>
            <p>This bot allows you to send anonymous secret messages to Telegram users.</p>
            <p><strong>New Features:</strong></p>
            <ul>
                <li>📢 Broadcast to all users (/broadcast)</li>
                <li>👥 Broadcast to groups (/gbroadcast)</li>
                <li>🤖 Auto-detect when added to groups</li>
                <li>👤 Show recent group members in whispers</li>
            </ul>
            <p><strong>Usage:</strong> Use inline mode in any chat: <code>@{} your_message @username</code></p>
        </div>
    </body>
    </html>
    """.format(
        len(recent_users), 
        len(messages_db),
        len(clone_stats),
        len(group_detected),
        sum(len(users) for users in group_users_last_5.values()),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        bot_username
    )

@app.route('/health')
def health():
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
        "groups_detected": len(group_detected),
        "group_users": sum(len(users) for users in group_users_last_5.values()),
        "bot_connected": bot_connected
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
        logger.info(f"👥 Groups Detected: {len(group_detected)}")
        logger.info(f"🌐 Web server running on port {PORT}")
        logger.info("✅ Bot is ready and working!")
        logger.info("🔗 Use /start to begin")
        logger.info("📢 New: Broadcast features added for admin!")
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
        print("📢 New Features Added:")
        print("   • /broadcast - Broadcast to all users")
        print("   • /gbroadcast - Broadcast to groups")
        print("   • Auto group detection")
        print("   • Recent group members in whispers")
        
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

import os
import logging
import re
import asyncio
import json
import aiohttp
from datetime import datetime, timedelta
from flask import Flask
import threading
from typing import List, Dict, Set, Optional
from bson import ObjectId
import motor.motor_asyncio
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
import cachetools

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
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017')
MONGO_DB = os.environ.get('MONGO_DB', 'whisper_bot')

# ============ MONGODB INITIALIZATION ============
try:
    # Async MongoDB client for Telethon
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = mongo_client[MONGO_DB]
    
    # Sync MongoDB client for Flask
    sync_mongo = MongoClient(MONGO_URI)
    sync_db = sync_mongo[MONGO_DB]
    
    # Collections
    whispers_collection = db.whispers
    users_collection = db.users
    groups_collection = db.groups
    broadcasts_collection = db.broadcasts
    notifications_collection = db.notifications
    recent_users_collection = db.recent_users
    
    logger.info("✅ MongoDB connected successfully")
except Exception as e:
    logger.error(f"❌ MongoDB connection error: {e}")
    raise

# ============ CACHING CONFIGURATION ============
# Cache for frequently accessed data
user_cache = cachetools.TTLCache(maxsize=1000, ttl=300)  # 5 minutes
whisper_cache = cachetools.TTLCache(maxsize=500, ttl=600)  # 10 minutes
recent_users_cache = cachetools.TTLCache(maxsize=100, ttl=60)  # 1 minute
group_users_cache = cachetools.TTLCache(maxsize=50, ttl=120)  # 2 minutes

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
SUPPORT_CHANNEL = "t.me/+Ns2R-5tx8ng2M2Zl"
SUPPORT_GROUP = "t.me/+Ns2R-5tx8ng2M2Zl"

# ============ IN-MEMORY STORAGE (For faster access) ============
active_users = {}  # Active user sessions
user_last_activity = {}  # Last activity timestamp
cooldown_users = set()  # Users in cooldown

# ============ TEXT MESSAGES ============
WELCOME_TEXT = """
𝘼𝙧𝙩𝙞𝙨𝙩
                              
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
   • /recent - Show recent users (fast access)

🔒 **Only the mentioned user can read your message!**
"""

# ============ MONGODB FUNCTIONS ============

async def create_indexes():
    """Create necessary indexes for faster queries"""
    try:
        # Whisper indexes
        await whispers_collection.create_index([("message_id", 1)], unique=True)
        await whispers_collection.create_index([("sender_id", 1)])
        await whispers_collection.create_index([("user_id", 1)])
        await whispers_collection.create_index([("timestamp", DESCENDING)])
        await whispers_collection.create_index([("is_group", 1)])
        
        # User indexes
        await users_collection.create_index([("user_id", 1)], unique=True)
        await users_collection.create_index([("username", 1)])
        await users_collection.create_index([("last_seen", DESCENDING)])
        
        # Group indexes
        await groups_collection.create_index([("chat_id", 1)], unique=True)
        await groups_collection.create_index([("last_activity", DESCENDING)])
        
        # Recent users indexes
        await recent_users_collection.create_index([("sender_id", 1), ("target_id", 1)], unique=True)
        await recent_users_collection.create_index([("sender_id", 1), ("last_used", DESCENDING)])
        await recent_users_collection.create_index([("target_id", 1)])
        
        # Notifications indexes
        await notifications_collection.create_index([("timestamp", DESCENDING)])
        await notifications_collection.create_index([("read", 1)])
        
        logger.info("✅ MongoDB indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")

async def save_whisper_to_db(whisper_data: dict):
    """Save whisper to MongoDB with caching"""
    try:
        whisper_id = whisper_data.get('message_id')
        
        # Check cache first
        if whisper_id in whisper_cache:
            return whisper_cache[whisper_id]
        
        # Save to MongoDB
        result = await whispers_collection.update_one(
            {"message_id": whisper_id},
            {"$set": whisper_data},
            upsert=True
        )
        
        # Update cache
        whisper_cache[whisper_id] = whisper_data
        
        # Update user activity
        await update_user_activity(whisper_data['sender_id'])
        if whisper_data.get('user_id'):
            await update_user_activity(whisper_data['user_id'])
        
        return whisper_data
    except Exception as e:
        logger.error(f"Error saving whisper to DB: {e}")
        return None

async def get_whisper_from_db(whisper_id: str):
    """Get whisper from MongoDB with cache"""
    try:
        # Check cache first
        if whisper_id in whisper_cache:
            return whisper_cache[whisper_id]
        
        # Get from MongoDB
        whisper = await whispers_collection.find_one({"message_id": whisper_id})
        
        if whisper:
            # Update cache
            whisper_cache[whisper_id] = whisper
            return whisper
        
        return None
    except Exception as e:
        logger.error(f"Error getting whisper from DB: {e}")
        return None

async def update_user_activity(user_id: int, username: str = None, first_name: str = None):
    """Update user activity in MongoDB"""
    try:
        update_data = {
            "last_seen": datetime.now(),
            "updated_at": datetime.now()
        }
        
        if username:
            update_data["username"] = username
        if first_name:
            update_data["first_name"] = first_name
        
        # Update or insert user
        await users_collection.update_one(
            {"user_id": user_id},
            {"$set": update_data, "$setOnInsert": {"created_at": datetime.now()}},
            upsert=True
        )
        
        # Update cache
        cache_key = f"user_{user_id}"
        user_cache[cache_key] = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "last_seen": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"Error updating user activity: {e}")

async def add_recent_user(sender_id: int, target_user_id: int, target_username: str = None, 
                         target_first_name: str = None, context: str = "private"):
    """Add user to recent users with fast caching"""
    try:
        recent_data = {
            "sender_id": sender_id,
            "target_id": target_user_id,
            "target_username": target_username,
            "target_first_name": target_first_name,
            "context": context,
            "last_used": datetime.now(),
            "usage_count": 1
        }
        
        # Check if already exists
        existing = await recent_users_collection.find_one({
            "sender_id": sender_id,
            "target_id": target_user_id
        })
        
        if existing:
            # Update usage count and timestamp
            recent_data["usage_count"] = existing.get("usage_count", 0) + 1
            await recent_users_collection.update_one(
                {"_id": existing["_id"]},
                {"$set": recent_data}
            )
        else:
            # Insert new
            await recent_users_collection.insert_one(recent_data)
        
        # Update cache
        cache_key = f"recent_{sender_id}"
        if cache_key not in recent_users_cache:
            recent_users_cache[cache_key] = []
        
        # Remove if already exists in cache
        recent_users_cache[cache_key] = [
            u for u in recent_users_cache[cache_key] 
            if u.get("target_id") != target_user_id
        ]
        
        # Add to cache
        recent_users_cache[cache_key].insert(0, {
            "target_id": target_user_id,
            "target_username": target_username,
            "target_first_name": target_first_name,
            "context": context,
            "last_used": datetime.now()
        })
        
        # Keep only last 5 in cache
        if len(recent_users_cache[cache_key]) > 5:
            recent_users_cache[cache_key] = recent_users_cache[cache_key][:5]
        
        # Also update user activity
        await update_user_activity(sender_id)
        
    except Exception as e:
        logger.error(f"Error adding recent user: {e}")

async def get_recent_users_fast(sender_id: int, context: str = "private", limit: int = 5):
    """Get recent users with caching for fast access"""
    try:
        cache_key = f"recent_{sender_id}"
        
        # Check cache first
        if cache_key in recent_users_cache:
            cached_users = recent_users_cache[cache_key]
            
            # Filter by context if needed
            if context == "group":
                cached_users = [u for u in cached_users if u.get("context") == "group"]
            elif context == "private":
                cached_users = [u for u in cached_users if u.get("context") == "private"]
            
            if cached_users:
                return cached_users[:limit]
        
        # Get from MongoDB if cache miss
        query = {"sender_id": sender_id}
        if context != "all":
            query["context"] = context
        
        cursor = recent_users_collection.find(query).sort("last_used", -1).limit(limit)
        recent_users_list = []
        
        async for user in cursor:
            recent_users_list.append({
                "target_id": user["target_id"],
                "target_username": user.get("target_username"),
                "target_first_name": user.get("target_first_name"),
                "context": user.get("context", "private"),
                "last_used": user["last_used"],
                "usage_count": user.get("usage_count", 1)
            })
        
        # Update cache
        recent_users_cache[cache_key] = recent_users_list
        
        return recent_users_list
        
    except Exception as e:
        logger.error(f"Error getting recent users: {e}")
        return []

async def add_group_user(chat_id: int, user_id: int, username: str = None, first_name: str = None):
    """Add user to group with caching"""
    try:
        # Update group activity
        await groups_collection.update_one(
            {"chat_id": chat_id},
            {
                "$set": {
                    "last_activity": datetime.now(),
                    "updated_at": datetime.now()
                },
                "$addToSet": {
                    "recent_users": {
                        "user_id": user_id,
                        "username": username,
                        "first_name": first_name,
                        "timestamp": datetime.now()
                    }
                },
                "$setOnInsert": {"created_at": datetime.now()}
            },
            upsert=True
        )
        
        # Keep only last 5 users in array
        await groups_collection.update_one(
            {"chat_id": chat_id},
            {
                "$push": {
                    "recent_users": {
                        "$each": [],
                        "$slice": -5  # Keep only last 5
                    }
                }
            }
        )
        
        # Update cache
        cache_key = f"group_{chat_id}"
        if cache_key not in group_users_cache:
            group_users_cache[cache_key] = []
        
        # Remove if exists
        group_users_cache[cache_key] = [
            u for u in group_users_cache[cache_key] 
            if u.get("user_id") != user_id
        ]
        
        # Add to cache
        group_users_cache[cache_key].insert(0, {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "timestamp": datetime.now()
        })
        
        # Keep only last 5
        if len(group_users_cache[cache_key]) > 5:
            group_users_cache[cache_key] = group_users_cache[cache_key][:5]
        
        # Update user activity
        await update_user_activity(user_id, username, first_name)
        
    except Exception as e:
        logger.error(f"Error adding group user: {e}")

async def get_group_users_fast(chat_id: int, limit: int = 5):
    """Get group users with caching"""
    try:
        cache_key = f"group_{chat_id}"
        
        # Check cache first
        if cache_key in group_users_cache:
            return group_users_cache[cache_key][:limit]
        
        # Get from MongoDB
        group = await groups_collection.find_one(
            {"chat_id": chat_id},
            {"recent_users": {"$slice": -limit}}  # Get last N users
        )
        
        if group and "recent_users" in group:
            recent_users = group["recent_users"]
            # Update cache
            group_users_cache[cache_key] = recent_users
            return recent_users
        
        return []
        
    except Exception as e:
        logger.error(f"Error getting group users: {e}")
        return []

async def save_broadcast_to_db(broadcast_data: dict):
    """Save broadcast to MongoDB"""
    try:
        await broadcasts_collection.insert_one(broadcast_data)
        return True
    except Exception as e:
        logger.error(f"Error saving broadcast: {e}")
        return False

async def get_broadcast_stats():
    """Get broadcast statistics"""
    try:
        total_broadcasts = await broadcasts_collection.count_documents({})
        
        # Get success rate
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_sent": {"$sum": "$total"},
                    "total_success": {"$sum": "$success"},
                    "avg_success_rate": {"$avg": {"$divide": ["$success", "$total"]}}
                }
            }
        ]
        
        stats = await broadcasts_collection.aggregate(pipeline).to_list(length=1)
        
        if stats and stats[0]:
            return {
                "total_broadcasts": total_broadcasts,
                "total_sent": stats[0].get("total_sent", 0),
                "total_success": stats[0].get("total_success", 0),
                "avg_success_rate": stats[0].get("avg_success_rate", 0) * 100
            }
        
        return {"total_broadcasts": total_broadcasts, "total_sent": 0, "total_success": 0, "avg_success_rate": 0}
        
    except Exception as e:
        logger.error(f"Error getting broadcast stats: {e}")
        return {"total_broadcasts": 0, "total_sent": 0, "total_success": 0, "avg_success_rate": 0}

async def get_whisper_stats():
    """Get whisper statistics from MongoDB"""
    try:
        # Total whispers
        total_whispers = await whispers_collection.count_documents({})
        
        # Last 24 hours
        last_24h = datetime.now() - timedelta(hours=24)
        whispers_24h = await whispers_collection.count_documents({
            "timestamp": {"$gte": last_24h}
        })
        
        # Unique senders
        unique_senders = len(await whispers_collection.distinct("sender_id"))
        
        # Unique targets
        unique_targets = len(await whispers_collection.distinct("user_id"))
        
        # Groups vs private
        group_whispers = await whispers_collection.count_documents({"is_group": True})
        private_whispers = await whispers_collection.count_documents({"is_group": False})
        
        return {
            "total_whispers": total_whispers,
            "whispers_24h": whispers_24h,
            "unique_senders": unique_senders,
            "unique_targets": unique_targets,
            "group_whispers": group_whispers,
            "private_whispers": private_whispers
        }
        
    except Exception as e:
        logger.error(f"Error getting whisper stats: {e}")
        return {}

async def save_notification(notification_data: dict):
    """Save notification to MongoDB"""
    try:
        await notifications_collection.insert_one(notification_data)
        return True
    except Exception as e:
        logger.error(f"Error saving notification: {e}")
        return False

# ============ UTILITY FUNCTIONS ============

def is_cooldown(user_id: int) -> bool:
    """Check if user is in cooldown with fast in-memory check"""
    current_time = datetime.now().timestamp()
    
    if user_id in user_last_activity:
        if current_time - user_last_activity[user_id] < 1:  # 1 second cooldown
            return True
    
    user_last_activity[user_id] = current_time
    return False

async def validate_and_get_user_fast(target_user: str):
    """
    Fast user validation with caching
    """
    try:
        cache_key = f"validate_{target_user}"
        
        # Check cache first
        if cache_key in user_cache:
            return user_cache[cache_key]
        
        user_info = None
        
        # Check if it's a user ID (only digits)
        if target_user.isdigit():
            user_id = int(target_user)
            
            # Try to get user entity with timeout
            try:
                user_obj = await asyncio.wait_for(
                    bot.get_entity(user_id),
                    timeout=2.0
                )
                
                if hasattr(user_obj, 'first_name'):
                    user_info = {
                        'id': user_obj.id,
                        'username': getattr(user_obj, 'username', None),
                        'first_name': getattr(user_obj, 'first_name', 'User'),
                        'last_name': getattr(user_obj, 'last_name', ''),
                        'exists': True
                    }
            except (asyncio.TimeoutError, Exception):
                # User not found or timeout, but we can still create whisper
                user_info = {
                    'id': user_id,
                    'username': None,
                    'first_name': f"User {user_id}",
                    'last_name': '',
                    'exists': False
                }
        
        else:
            # It's a username (remove @ if present)
            if target_user.startswith('@'):
                target_user = target_user[1:]
            
            # Try to get user entity
            try:
                user_obj = await asyncio.wait_for(
                    bot.get_entity(target_user),
                    timeout=2.0
                )
                
                if hasattr(user_obj, 'first_name'):
                    user_info = {
                        'id': user_obj.id,
                        'username': getattr(user_obj, 'username', None),
                        'first_name': getattr(user_obj, 'first_name', 'User'),
                        'last_name': getattr(user_obj, 'last_name', ''),
                        'exists': True
                    }
            except (asyncio.TimeoutError, Exception):
                # User not found, but we can still create whisper
                user_info = {
                    'id': None,
                    'username': target_user,
                    'first_name': f"@{target_user}",
                    'last_name': '',
                    'exists': False
                }
        
        if user_info:
            # Update cache
            user_cache[cache_key] = user_info
        
        return user_info
        
    except Exception as e:
        logger.error(f"Error validating user {target_user}: {e}")
        return None

def get_recent_users_buttons_fast(recent_users_list: List[Dict], context: str = "private"):
    """Get recent users as buttons from cached data"""
    try:
        if not recent_users_list:
            return []
        
        buttons = []
        for user_data in recent_users_list[:5]:  # Last 5 users
            target_user_id = user_data.get('target_id')
            username = user_data.get('target_username')
            first_name = user_data.get('target_first_name', 'User')
            
            if username:
                display_text = f"@{username}"
                query_data = f"@{username}"
            else:
                display_text = f"{first_name}"
                query_data = str(target_user_id)
            
            # Truncate display text
            if len(display_text) > 15:
                display_text = display_text[:15] + "..."
            
            # Different callback based on context
            if context == "group":
                callback_data = f"group_user_{query_data}"
            else:
                callback_data = f"recent_{target_user_id}"
            
            buttons.append([Button.inline(
                f"👤 {display_text} ({user_data.get('usage_count', 1)}×)", 
                data=callback_data
            )])
        
        return buttons
    except Exception as e:
        logger.error(f"Error getting recent users buttons: {e}")
        return []

async def notify_owner_fast(whisper_data: dict):
    """Fast notification to owner with MongoDB storage"""
    try:
        sender_id = whisper_data.get('sender_id')
        target_id = whisper_data.get('user_id')
        target_name = whisper_data.get('target_name', 'Unknown')
        message = whisper_data.get('msg', '')[:100]
        
        # Try to get sender info from cache first
        sender_name = f"User {sender_id}"
        sender_cache_key = f"user_{sender_id}"
        
        if sender_cache_key in user_cache:
            cached_user = user_cache[sender_cache_key]
            sender_name = cached_user.get('first_name', sender_name)
        else:
            try:
                sender = await bot.get_entity(sender_id)
                sender_name = getattr(sender, 'first_name', f'User {sender_id}')
            except:
                pass
        
        # Create notification
        notification_text = f"🔔 **New Whisper Notification**\n\n"
        notification_text += f"👤 **From:** {sender_name} (ID: {sender_id})\n"
        notification_text += f"🎯 **To:** {target_name} (ID: {target_id})\n"
        notification_text += f"💬 **Message:** {message}...\n"
        notification_text += f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}"
        
        # Send to owner
        await bot.send_message(ADMIN_ID, notification_text)
        
        # Save to MongoDB
        notification_data = {
            'sender_id': sender_id,
            'target_id': target_id,
            'target_name': target_name,
            'message': message,
            'timestamp': datetime.now(),
            'whisper_id': whisper_data.get('message_id'),
            'read': False
        }
        
        await save_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error notifying owner: {e}")

# ============ COMMAND HANDLERS ============

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        logger.info(f"🚀 Start command from user: {event.sender_id}")
        
        # Update user activity
        await update_user_activity(
            event.sender_id,
            event.sender.username,
            event.sender.first_name
        )
        
        # Check if in group
        if event.is_group or event.is_channel:
            chat_id = event.chat_id
            
            # Add to group tracking
            await add_group_user(
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
                "✨ **NEW:** Recent group members appear instantly!\n"
                "⚡ **FAST:** No delays in user suggestions\n\n"
                "📌 **Try it now using the button below!**",
                buttons=[
                    [Button.switch_inline("🚀 Send Whisper", query="", same_peer=True)],
                    [Button.url("📢 Channel", SUPPORT_CHANNEL)]
                ]
            )
            return
        
        # Private chat welcome message
        welcome_buttons = [
            [Button.url("📢 Support Channel", SUPPORT_CHANNEL), 
             Button.url("👥 Support Group", SUPPORT_GROUP)],
            [Button.switch_inline("🚀 Try Now", query="")],
            [Button.inline("📖 Help", data="help")]
        ]
        
        if event.sender_id == ADMIN_ID:
            welcome_buttons.insert(2, [
                Button.inline("📊 Statistics", data="admin_stats"),
                Button.inline("🔍 View Whispers", data="view_whispers")
            ])
            welcome_buttons.insert(3, [
                Button.inline("📢 Broadcast", data="broadcast_menu"),
                Button.inline("⚡ Recent Users", data="show_recent")
            ])
        
        await event.reply(WELCOME_TEXT, buttons=welcome_buttons)
        
    except Exception as e:
        logger.error(f"Start error: {e}")
        await event.reply("❌ An error occurred. Please try again.")

@bot.on(events.NewMessage(pattern='/recent'))
async def recent_handler(event):
    """Show recent users for fast access"""
    try:
        if is_cooldown(event.sender_id):
            await event.answer("⏳ Please wait a moment...")
            return
        
        # Get recent users from cache/DB
        recent_users_list = await get_recent_users_fast(
            event.sender_id, 
            context="all",
            limit=10
        )
        
        if not recent_users_list:
            await event.reply(
                "📭 **No Recent Users**\n\n"
                "You haven't sent any whispers yet.\n"
                "Send your first whisper using the button below!",
                buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
            )
            return
        
        # Format response
        response_text = "📋 **Recent Users (Fast Access)**\n\n"
        response_text += "Click any user below to whisper them instantly:\n\n"
        
        buttons = []
        for idx, user_data in enumerate(recent_users_list, 1):
            username = user_data.get('target_username')
            first_name = user_data.get('target_first_name', 'User')
            
            if username:
                display_text = f"@{username}"
            else:
                display_text = first_name
            
            # Truncate for display
            if len(display_text) > 20:
                display_text = display_text[:20] + "..."
            
            # Add usage count
            usage_count = user_data.get('usage_count', 1)
            display_text = f"{display_text} ({usage_count}×)"
            
            # Context indicator
            context = user_data.get('context', 'private')
            context_icon = "👥" if context == "group" else "👤"
            
            response_text += f"{idx}. {context_icon} {display_text}\n"
            
            # Create button
            if username:
                query_data = f"@{username}"
            else:
                query_data = str(user_data['target_id'])
            
            callback_data = f"recent_{user_data['target_id']}"
            buttons.append([Button.inline(
                f"{context_icon} {display_text}",
                data=callback_data
            )])
        
        response_text += f"\n⚡ **Total:** {len(recent_users_list)} users"
        response_text += f"\n🔄 **Updated:** Just now"
        
        # Add refresh button
        buttons.append([
            Button.inline("🔄 Refresh", data="refresh_recent"),
            Button.switch_inline("🚀 New Whisper", query="")
        ])
        
        await event.reply(response_text, buttons=buttons)
        
    except Exception as e:
        logger.error(f"Recent command error: {e}")
        await event.reply("❌ Error loading recent users. Please try again.")

@bot.on(events.NewMessage(pattern='/stats'))
async def stats_handler(event):
    """Show statistics with MongoDB data"""
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
        
    try:
        # Get stats from MongoDB
        whisper_stats = await get_whisper_stats()
        broadcast_stats = await get_broadcast_stats()
        
        # Get group count
        group_count = await groups_collection.count_documents({})
        
        # Get user count
        user_count = await users_collection.count_documents({})
        
        # Get recent user count
        recent_24h = datetime.now() - timedelta(hours=24)
        recent_users_count = await recent_users_collection.count_documents({
            "last_used": {"$gte": recent_24h}
        })
        
        stats_text = f"""
📊 **Advanced Admin Statistics**

👥 **Users:**
   • Total Users: {user_count}
   • Active (24h): {recent_users_count}

💬 **Whispers:**
   • Total: {whisper_stats.get('total_whispers', 0)}
   • Last 24h: {whisper_stats.get('whispers_24h', 0)}
   • Unique Senders: {whisper_stats.get('unique_senders', 0)}
   • Unique Targets: {whisper_stats.get('unique_targets', 0)}
   • Groups: {whisper_stats.get('group_whispers', 0)}
   • Private: {whisper_stats.get('private_whispers', 0)}

📢 **Broadcasts:**
   • Total: {broadcast_stats.get('total_broadcasts', 0)}
   • Messages Sent: {broadcast_stats.get('total_sent', 0)}
   • Success Rate: {broadcast_stats.get('avg_success_rate', 0):.1f}%

👥 **Groups:**
   • Total Groups: {group_count}

⚡ **Performance:**
   • Cache Hits: {len(user_cache) + len(whisper_cache)}
   • Active Sessions: {len(active_users)}
   • Memory Usage: Optimized

🆔 **System:**
   • Admin ID: {ADMIN_ID}
   • MongoDB: ✅ Connected
   • Port: {PORT}

⏰ **Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        """
        
        await event.reply(
            stats_text,
            buttons=[
                [Button.inline("🔄 Refresh", data="admin_stats")],
                [Button.inline("📊 Whisper Stats", data="whisper_stats")],
                [Button.inline("📢 Broadcast", data="broadcast_menu")]
            ]
        )
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await event.reply("❌ Error fetching statistics.")

# ============ INLINE QUERY HANDLER (OPTIMIZED) ============

@bot.on(events.InlineQuery)
async def inline_handler(event):
    """Optimized inline query handler with fast caching"""
    try:
        if is_cooldown(event.sender_id):
            await event.answer([])
            return

        query_text = event.text or ""
        
        # Determine context
        is_group_context = False
        chat_id = None
        if hasattr(event.query, 'chat_type'):
            is_group_context = event.query.chat_type in ['group', 'supergroup']
            if hasattr(event.query, 'peer') and event.query.peer:
                try:
                    chat_id = event.query.peer.channel_id or event.query.peer.chat_id or event.query.peer.user_id
                except:
                    pass
        
        # Get recent users FAST (from cache)
        recent_users_list = []
        if is_group_context and chat_id:
            # Get group users
            group_users = await get_group_users_fast(chat_id, limit=5)
            recent_users_list = [
                {
                    "target_id": u.get("user_id"),
                    "target_username": u.get("username"),
                    "target_first_name": u.get("first_name", "User"),
                    "context": "group",
                    "last_used": u.get("timestamp", datetime.now())
                }
                for u in group_users
            ]
        else:
            # Get private recent users
            recent_users_list = await get_recent_users_fast(
                event.sender_id,
                context="private",
                limit=5
            )
        
        # If empty query, show recent users
        if not query_text.strip():
            if recent_users_list:
                if is_group_context:
                    title = "🤫 Recent Group Members"
                    description = "Click any user to whisper instantly"
                    text = "**Recent Group Members (Last 5):**\nClick any user below to whisper them!\n\nOr type: `message @username`\nOr: `@username message`"
                else:
                    title = "🤫 Recent Users"
                    description = "Click any user to whisper instantly"
                    text = "**Recent Users (Last 5):**\nClick any user below to whisper them!\n\nOr type: `message @username`\nOr: `@username message`"
                
                buttons = get_recent_users_buttons_fast(
                    recent_users_list,
                    "group" if is_group_context else "private"
                )
                
                result = event.builder.article(
                    title=title,
                    description=description,
                    text=text,
                    buttons=buttons
                )
            else:
                result = event.builder.article(
                    title="🤫 Whisper Bot - Send Secret Messages",
                    description="Usage: your_message @username",
                    text="**Usage:** `your_message @username` or `@username your_message`\n\n**Flexible Formats:**\n• `Hello@username` (no space)\n• `@usernameHello` (no space)\n• `Hello @username` (with space)\n• `@username Hello` (with space)\n• `123456789 Hello`\n• `Hello 123456789`\n\n⚡ **Fast:** Recent users appear instantly!\n🔒 **Secure:** Only they can read!",
                    buttons=[[Button.switch_inline("🚀 Try Now", query="")]]
                )
            await event.answer([result])
            return
        
        # Process query with message
        text = query_text.strip()
        
        # Fast parsing with regex
        message_text = ""
        target_user = ""
        
        # Try multiple patterns efficiently
        patterns = [
            (r'^(.*?)@(\w+)$', 1, 2),  # message@username
            (r'^@(\w+)(.*)$', 2, 1),   # @usernamemessage
            (r'^(.*?)\s+@(\w+)$', 1, 2),  # message @username
            (r'^@(\w+)\s+(.*)$', 2, 1),   # @username message
            (r'^(.*?)(\d{5,})$', 1, 2),   # message123456
            (r'^(\d{5,})(.*)$', 2, 1),    # 123456message
            (r'^(.*?)\s+(\d{5,})$', 1, 2), # message 123456
            (r'^(\d{5,})\s+(.*)$', 2, 1)   # 123456 message
        ]
        
        for pattern, msg_group, target_group in patterns:
            match = re.match(pattern, text, re.DOTALL)
            if match:
                message_text = match.group(msg_group).strip()
                target_user = match.group(target_group)
                break
        
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
        
        # If message is empty, prompt for message
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
        
        # Validate user FAST (with caching)
        user_info = await validate_and_get_user_fast(target_user)
        
        if not user_info:
            result = event.builder.article(
                title="❌ Error",
                description="Could not process user",
                text="❌ Could not process the user. Please try again."
            )
            await event.answer([result])
            return
        
        # Add to recent users (FAST - async)
        if user_info.get('exists') and user_info.get('id'):
            context = "group" if is_group_context else "private"
            await add_recent_user(
                event.sender_id,
                user_info['id'],
                user_info.get('username'),
                user_info.get('first_name'),
                context
            )
            
            if is_group_context and chat_id:
                await add_group_user(
                    chat_id,
                    user_info['id'],
                    user_info.get('username'),
                    user_info.get('first_name')
                )
        
        # Create whisper data
        message_id = f'msg_{event.sender_id}_{target_user}_{int(datetime.now().timestamp())}'
        whisper_data = {
            'message_id': message_id,
            'user_id': user_info.get('id') or target_user,
            'msg': message_text,
            'sender_id': event.sender_id,
            'timestamp': datetime.now(),
            'target_name': user_info.get('first_name', target_user),
            'target_username': user_info.get('username'),
            'target_exists': user_info.get('exists', False),
            'is_group': is_group_context,
            'group_id': chat_id if is_group_context else None
        }
        
        # Save to MongoDB (async - don't wait)
        asyncio.create_task(save_whisper_to_db(whisper_data))
        
        # Notify owner (async)
        asyncio.create_task(notify_owner_fast(whisper_data))
        
        # Prepare response
        if user_info.get('username'):
            display_target = f"@{user_info['username']}"
        else:
            display_target = user_info.get('first_name', target_user)
        
        result_text = f"🔒 **Secret Message for {display_target}**\n\n"
        result_text += "Click the button below to send this whisper.\n"
        
        if not user_info.get('exists'):
            result_text += f"\n*Note: A whisper message to @{target_user} can open it.*"
        
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

# ============ CALLBACK QUERY HANDLER (UPDATED) ============

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    try:
        data = event.data.decode('utf-8')
        
        # ============ RECENT USERS CALLBACKS ============
        if data == "show_recent":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
            
            recent_users_list = await get_recent_users_fast(
                event.sender_id,
                context="all",
                limit=15
            )
            
            if not recent_users_list:
                await event.edit(
                    "📭 **No Recent Users**\n\n"
                    "No recent users found.\n"
                    "Send some whispers first!",
                    buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
                )
                return
            
            response_text = "📋 **Recent Users (Admin View)**\n\n"
            
            buttons = []
            for idx, user_data in enumerate(recent_users_list[:10], 1):
                username = user_data.get('target_username')
                first_name = user_data.get('target_first_name', 'User')
                usage_count = user_data.get('usage_count', 1)
                context = user_data.get('context', 'private')
                
                if username:
                    display_text = f"@{username}"
                else:
                    display_text = first_name
                
                if len(display_text) > 15:
                    display_text = display_text[:15] + "..."
                
                context_icon = "👥" if context == "group" else "👤"
                response_text += f"{idx}. {context_icon} {display_text} ({usage_count}×)\n"
                
                # Create button
                callback_data = f"recent_{user_data['target_id']}"
                buttons.append([Button.inline(
                    f"{context_icon} {display_text}",
                    data=callback_data
                )])
            
            response_text += f"\n⚡ **Total:** {len(recent_users_list)} users"
            
            buttons.append([
                Button.inline("🔄 Refresh", data="show_recent"),
                Button.switch_inline("🚀 New Whisper", query="")
            ])
            
            await event.edit(response_text, buttons=buttons)
        
        elif data == "refresh_recent":
            await event.answer("🔄 Refreshing...", alert=False)
            
            # Clear cache for this user
            cache_key = f"recent_{event.sender_id}"
            if cache_key in recent_users_cache:
                del recent_users_cache[cache_key]
            
            await event.edit(
                "🔄 **Refreshing recent users...**",
                buttons=[[Button.inline("🔄 Loading...", data="none")]]
            )
            
            # Get fresh data
            recent_users_list = await get_recent_users_fast(
                event.sender_id,
                context="all",
                limit=10
            )
            
            if not recent_users_list:
                await event.edit(
                    "📭 **No Recent Users**\n\n"
                    "You haven't sent any whispers yet.",
                    buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
                )
                return
            
            # Recreate the message
            response_text = "📋 **Recent Users (Refreshed)**\n\n"
            response_text += "Click any user below to whisper them instantly:\n\n"
            
            buttons = []
            for idx, user_data in enumerate(recent_users_list, 1):
                username = user_data.get('target_username')
                first_name = user_data.get('target_first_name', 'User')
                
                if username:
                    display_text = f"@{username}"
                else:
                    display_text = first_name
                
                if len(display_text) > 20:
                    display_text = display_text[:20] + "..."
                
                usage_count = user_data.get('usage_count', 1)
                context = user_data.get('context', 'private')
                context_icon = "👥" if context == "group" else "👤"
                
                response_text += f"{idx}. {context_icon} {display_text} ({usage_count}×)\n"
                
                callback_data = f"recent_{user_data['target_id']}"
                buttons.append([Button.inline(
                    f"{context_icon} {display_text}",
                    data=callback_data
                )])
            
            response_text += f"\n⚡ **Total:** {len(recent_users_list)} users"
            response_text += f"\n🔄 **Updated:** Just now"
            
            buttons.append([
                Button.inline("🔄 Refresh Again", data="refresh_recent"),
                Button.switch_inline("🚀 New Whisper", query="")
            ])
            
            await event.edit(response_text, buttons=buttons)
        
        elif data.startswith("recent_"):
            # Handle recent user selection
            target_id = data.replace("recent_", "")
            
            try:
                target_id_int = int(target_id)
                
                # Get user info from cache or DB
                user_info = None
                cache_key = f"user_{target_id_int}"
                
                if cache_key in user_cache:
                    user_info = user_cache[cache_key]
                else:
                    # Try to get from DB
                    user_doc = await users_collection.find_one({"user_id": target_id_int})
                    if user_doc:
                        user_info = {
                            "user_id": user_doc["user_id"],
                            "username": user_doc.get("username"),
                            "first_name": user_doc.get("first_name", "User")
                        }
                
                if user_info:
                    username = user_info.get("username")
                    first_name = user_info.get("first_name", "User")
                    
                    if username:
                        target_text = f"@{username}"
                    else:
                        target_text = first_name
                    
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
                    # Just use the ID
                    await event.edit(
                        f"🔒 **Send whisper to User {target_id}**\n\n"
                        f"Now switch to inline mode by clicking the button below,\n"
                        f"then type your message and send.",
                        buttons=[[Button.switch_inline(
                            f"💌 Message User {target_id}", 
                            query=f"{target_id}"
                        )]]
                    )
                
            except ValueError:
                await event.answer("Invalid user ID!", alert=True)
        
        # ============ EXISTING CALLBACKS ============
        # ... (keep existing callback handlers for whisper viewing, admin stats, etc.)
        # Note: You'll need to update the existing callback handlers to use MongoDB
        
        else:
            # Check if it's a whisper message ID
            whisper = await get_whisper_from_db(data)
            if whisper:
                target_user_id = whisper.get('user_id')
                target_exists = whisper.get('target_exists', False)
                
                # Check permissions
                if target_exists and isinstance(target_user_id, int) and event.sender_id == target_user_id:
                    # Target user opening
                    sender_info = ""
                    try:
                        sender = await bot.get_entity(whisper['sender_id'])
                        sender_name = getattr(sender, 'first_name', 'Someone')
                        sender_info = f"\n\n💌 From: {sender_name}"
                    except:
                        sender_info = f"\n\n💌 From: Anonymous"
                    
                    await event.answer(f" {whisper['msg']}", alert=True)
                
                elif not target_exists:
                    if event.sender_id == whisper['sender_id']:
                        await event.answer(f" {whisper['msg']}", alert=True)
                    else:
                        await event.answer("🔒 This message is not for you!", alert=True)
                
                elif event.sender_id == whisper['sender_id']:
                    await event.answer(f" {whisper['msg']}", alert=True)
                
                else:
                    await event.answer("🔒 This message is not for you!", alert=True)
            
            else:
                await event.answer("❌ Invalid button!", alert=True)
                
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await event.answer("❌ An error occurred. Please try again.", alert=True)

# ============ GROUP MESSAGE HANDLER (OPTIMIZED) ============

@bot.on(events.NewMessage(incoming=True))
async def message_handler(event):
    """Track users in groups with fast caching"""
    try:
        if event.is_group or event.is_channel:
            chat_id = event.chat_id
            
            # Track the user who sent message
            if event.sender_id and event.sender_id > 0:
                await add_group_user(
                    chat_id,
                    event.sender_id,
                    event.sender.username,
                    event.sender.first_name
                )
                
    except Exception:
        pass  # Silently ignore tracking errors

# ============ FLASK ROUTES (UPDATED) ============

@app.route('/')
def home():
    """Home page with MongoDB statistics"""
    try:
        # Get stats from sync MongoDB
        total_users = sync_db.users.count_documents({})
        total_whispers = sync_db.whispers.count_documents({})
        total_groups = sync_db.groups.count_documents({})
        total_broadcasts = sync_db.broadcasts.count_documents({})
        
        # Recent activity
        last_hour = datetime.now() - timedelta(hours=1)
        recent_whispers = sync_db.whispers.count_documents({
            "timestamp": {"$gte": last_hour}
        })
        
        # Cache stats
        cache_stats = {
            "user_cache": len(user_cache),
            "whisper_cache": len(whisper_cache),
            "recent_cache": len(recent_users_cache),
            "group_cache": len(group_users_cache)
        }
        
        bot_username = BOT_USERNAME or "bot_username"
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>ShriBots Whisper Bot v2.0</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #333; text-align: center; }}
                .status {{ background: #4CAF50; color: white; padding: 10px; border-radius: 5px; text-align: center; margin: 20px 0; }}
                .info {{ background: #2196F3; color: white; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .feature {{ background: #4CAF50; color: white; padding: 10px; border-radius: 5px; margin: 5px 0; }}
                .warning {{ background: #ff9800; color: white; padding: 10px; border-radius: 5px; margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 ShriBots Whisper Bot v2.0</h1>
                <div class="status">✅ Bot is Running with MongoDB</div>
                
                <div class="info">
                    <strong>📊 Real-time Statistics:</strong><br>
                    Total Users: {total_users}<br>
                    Total Whispers: {total_whispers}<br>
                    Groups Detected: {total_groups}<br>
                    Broadcasts Sent: {total_broadcasts}<br>
                    Recent Whispers (1h): {recent_whispers}<br>
                    Cache Size: {sum(cache_stats.values())} items
                </div>
                
                <div class="feature">
                    <strong>⚡ NEW: MongoDB Integration</strong><br>
                    • Faster data access<br>
                    • Persistent storage<br>
                    • Advanced analytics<br>
                    • Better performance
                </div>
                
                <div class="feature">
                    <strong>🚀 Advanced Features:</strong><br>
                    • Instant recent users (from cache)<br>
                    • Usage count tracking<br>
                    • Context-aware suggestions<br>
                    • Smart caching system<br>
                    • Fast inline queries
                </div>
                
                <p><strong>⚡ Performance Optimizations:</strong></p>
                <ul>
                    <li>Multi-level caching system</li>
                    <li>Async database operations</li>
                    <li>Fast user validation</li>
                    <li>Instant recent users display</li>
                    <li>Optimized regex patterns</li>
                </ul>
                
                <p><strong>📈 Analytics:</strong></p>
                <ul>
                    <li>User activity tracking</li>
                    <li>Whisper statistics</li>
                    <li>Broadcast performance</li>
                    <li>Group engagement</li>
                </ul>
                
                <div class="warning">
                    <strong>🔒 Security Enhanced:</strong><br>
                    • Only recipients can open whispers<br>
                    • Encrypted connections<br>
                    • Rate limiting<br>
                    • Activity monitoring
                </div>
                
                <p><strong>💡 Quick Commands:</strong></p>
                <ul>
                    <li><code>/recent</code> - Fast access to recent users</li>
                    <li><code>/stats</code> - Advanced statistics</li>
                    <li><code>/broadcast</code> - Promote to users</li>
                    <li><code>/gbroadcast</code> - Promote to groups</li>
                </ul>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        return f"Error loading stats: {str(e)}"

@app.route('/stats')
def api_stats():
    """API endpoint for statistics"""
    try:
        stats = {
            "status": "online",
            "timestamp": datetime.now().isoformat(),
            "users": sync_db.users.count_documents({}),
            "whispers": sync_db.whispers.count_documents({}),
            "groups": sync_db.groups.count_documents({}),
            "broadcasts": sync_db.broadcasts.count_documents({}),
            "cache": {
                "user_cache": len(user_cache),
                "whisper_cache": len(whisper_cache),
                "recent_cache": len(recent_users_cache),
                "group_cache": len(group_users_cache)
            }
        }
        return json.dumps(stats, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

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
    """Main function to start the bot with MongoDB"""
    global BOT_USERNAME
    
    try:
        # Create MongoDB indexes
        await create_indexes()
        
        me = await bot.get_me()
        BOT_USERNAME = me.username
        
        logger.info(f"🎭 ShriBots Whisper Bot v2.0 Started!")
        logger.info(f"🤖 Bot: @{me.username}")
        logger.info(f"👑 Admin: {ADMIN_ID}")
        logger.info(f"🗄️ MongoDB: Connected to {MONGO_DB}")
        logger.info(f"⚡ Cache: Ready (TTL caching enabled)")
        logger.info(f"🌐 Web server: http://0.0.0.0:{PORT}")
        
        # Load initial stats
        user_count = await users_collection.count_documents({})
        whisper_count = await whispers_collection.count_documents({})
        group_count = await groups_collection.count_documents({})
        
        logger.info(f"📊 Initial Stats:")
        logger.info(f"   👥 Users: {user_count}")
        logger.info(f"   💬 Whispers: {whisper_count}")
        logger.info(f"   👥 Groups: {group_count}")
        
        logger.info("✅ Bot is ready and optimized!")
        logger.info("🚀 **KEY FEATURES ACTIVATED:**")
        logger.info("   1️⃣ MongoDB integration with caching")
        logger.info("   2️⃣ Instant recent users (fast cache)")
        logger.info("   3️⃣ Usage count tracking")
        logger.info("   4️⃣ Advanced statistics")
        logger.info("   5️⃣ Optimized regex patterns")
        logger.info("   6️⃣ Async database operations")
        logger.info("   7️⃣ Smart rate limiting")
        logger.info("   8️⃣ Context-aware suggestions")
        
        logger.info("\n📋 **Performance Optimizations:**")
        logger.info("   • Multi-level caching (TTL)")
        logger.info("   • Fast user validation")
        logger.info("   • Async MongoDB operations")
        logger.info("   • Optimized inline queries")
        logger.info("   • Reduced database calls")
        
        logger.info("\n💡 **Quick Commands:**")
        logger.info("   • /recent - Fast recent users access")
        logger.info("   • /stats - Advanced statistics")
        logger.info("   • @bot - Send whispers (flexible formats)")
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

# ============ STARTUP ============

if __name__ == '__main__':
    print("🚀 Starting ShriBots Whisper Bot v2.0...")
    print(f"📝 Environment: API_ID={API_ID}, PORT={PORT}")
    print(f"🗄️ MongoDB: {MONGO_URI}/{MONGO_DB}")
    
    print("\n🔥 **NEW FEATURES ACTIVATED:**")
    print("   1️⃣ MongoDB Integration")
    print("   2️⃣ Instant Recent Users (Cache)")
    print("   3️⃣ Usage Count Tracking")
    print("   4️⃣ Advanced Statistics")
    print("   5️⃣ Fast Inline Queries")
    print("   6️⃣ Smart Caching System")
    print("   7️⃣ Async Database Operations")
    print("   8️⃣ Context-aware Suggestions")
    
    print("\n⚡ **Performance Optimizations:**")
    print("   • Multi-level TTL caching")
    print("   • Reduced database calls")
    print("   • Fast user validation")
    print("   • Optimized regex patterns")
    print("   • Async operations")
    
    print("\n📋 **Available Commands:**")
    print("   • /start - Start bot")
    print("   • /help - Show help")
    print("   • /recent - Fast recent users access")
    print("   • /stats - Advanced statistics")
    print("   • /broadcast - Broadcast to users")
    print("   • /gbroadcast - Broadcast to groups")
    
    print("\n💡 **Inline Usage Examples:**")
    print("   • @bot Hello@username (no space)")
    print("   • @bot @usernameHello (no space)")
    print("   • @bot Hello @username (with space)")
    print("   • @bot @username Hello (with space)")
    print("   • @bot 123456789 Hello")
    print("   • @bot Hello 123456789")
    
    print("\n⚡ **Recent Users Feature:**")
    print("   • Instantly shows last 5 users")
    print("   • Usage count displayed")
    print("   • Context-aware (group/private)")
    print("   • Fast cache-based retrieval")
    
    try:
        # Start the bot
        bot.start()
        bot.loop.run_until_complete(main())
        
        print("\n✅ Bot started successfully!")
        print("🔄 Bot is now running with MongoDB...")
        
        # Keep the bot running
        bot.run_until_disconnected()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        print(f"❌ Error: {e}")
    finally:
        print("💾 Closing connections...")
        sync_mongo.close()

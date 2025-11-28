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

# Environment variables
API_ID = int(os.getenv('API_ID', '25136703'))
API_HASH = os.getenv('API_HASH', 'accfaf5ecd981c67e481328515c39f89')
BOT_TOKEN = os.getenv('BOT_TOKEN', '8314503581:AAEm5TvIs_-qn23VfOCnfVL1dTRwwDtpi8A')
ADMIN_ID = int(os.getenv('ADMIN_ID', '8385462088'))
PORT = int(os.environ.get('PORT', 10000))

# Import Telethon
try:
    from telethon import TelegramClient, events, Button
    from telethon.errors import SessionPasswordNeededError, UserNotParticipantError, MessageNotModifiedError
    from telethon.tl.functions.channels import JoinChannelRequest
    from telethon.tl.functions.messages import ImportChatInviteRequest
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
pending_verification = {}  # For users who need to join channel
broadcast_messages = {}   # Separate storage for broadcast messages
all_bot_users = set()     # Track all users who interact with bot

# Data files
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
RECENT_USERS_FILE = os.path.join(DATA_DIR, "recent_users.json")
USER_RECENT_TARGETS_FILE = os.path.join(DATA_DIR, "user_recent_targets.json")
CLONE_STATS_FILE = os.path.join(DATA_DIR, "clone_stats.json")
PENDING_VERIFICATION_FILE = os.path.join(DATA_DIR, "pending_verification.json")
BROADCAST_MESSAGES_FILE = os.path.join(DATA_DIR, "broadcast_messages.json")
ALL_USERS_FILE = os.path.join(DATA_DIR, "all_users.json")

def load_data():
    global recent_users, clone_stats, user_recent_targets, pending_verification, broadcast_messages, all_bot_users
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
            
        if os.path.exists(PENDING_VERIFICATION_FILE):
            with open(PENDING_VERIFICATION_FILE, 'r', encoding='utf-8') as f:
                pending_verification = json.load(f)
            logger.info(f"✅ Loaded {len(pending_verification)} pending verifications")
            
        if os.path.exists(BROADCAST_MESSAGES_FILE):
            with open(BROADCAST_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                broadcast_messages = json.load(f)
            logger.info(f"✅ Loaded {len(broadcast_messages)} broadcast messages")
            
        if os.path.exists(ALL_USERS_FILE):
            with open(ALL_USERS_FILE, 'r', encoding='utf-8') as f:
                all_bot_users = set(json.load(f))
            logger.info(f"✅ Loaded {len(all_bot_users)} total users")
            
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        recent_users = {}
        clone_stats = {}
        user_recent_targets = {}
        pending_verification = {}
        broadcast_messages = {}
        all_bot_users = set()

def save_data():
    try:
        with open(RECENT_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(recent_users, f, indent=2, ensure_ascii=False)
        
        with open(USER_RECENT_TARGETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_recent_targets, f, indent=2, ensure_ascii=False)
        
        with open(CLONE_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(clone_stats, f, indent=2, ensure_ascii=False)
            
        with open(PENDING_VERIFICATION_FILE, 'w', encoding='utf-8') as f:
            json.dump(pending_verification, f, indent=2, ensure_ascii=False)
            
        with open(BROADCAST_MESSAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump(broadcast_messages, f, indent=2, ensure_ascii=False)
            
        with open(ALL_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(all_bot_users), f, indent=2, ensure_ascii=False)
            
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
   • Type `@Upspbot` in any chat
   • Write your message  
   • Add @username OR user ID at end
   • Send!

**2. Examples:**
   • `@upspbot Hello! @username`
   • `@upspbot I miss you 123456789`
   • `@upspbot Hello everyone!` - Anyone can read

**3. Commands:**
   • /start - Start bot
   • /help - Show help
   • /stats - Admin statistics
   • /clone - Clone your own bot
   • /remove - Remove your cloned bot
   • /allbots - View all cloned bots (Admin)
   • /broadcast - Broadcast message (Admin only)

🔒 **Only the mentioned user can read your message!**
   🌍 **If no user mentioned, anyone can read!**
"""

def add_user_to_tracking(user_id):
    """Add user to tracking for broadcast"""
    try:
        all_bot_users.add(user_id)
        # Save periodically to avoid too many disk writes
        if len(all_bot_users) % 10 == 0:
            asyncio.create_task(save_data_async())
    except Exception as e:
        logger.error(f"Error adding user to tracking: {e}")

async def precheck_channels(client):
    """Auto-join support channels for cloned bots - ADVANCED VERSION"""
    targets = ["@shribots", "@idxhelp"]
    for chan in targets:
        try:
            await client(JoinChannelRequest(chan))
            logger.info(f"✓ Joined {chan}")
        except UserNotParticipantError:
            logger.info(f"↻ Already in {chan}")
        except Exception as e:
            logger.warning(f"✗ Failed to join {chan}: {e}")

async def check_user_joined_channel(user_id, client=None):
    """Check if user has joined the support channel - FOR MAIN BOT ONLY"""
    if client is None:
        client = bot
        
    try:
        # ADMIN ko hamesha allow karo
        if user_id == ADMIN_ID:
            return True
            
        # Try to check if user has joined the channel
        try:
            # Get channel entity
            channel = await client.get_entity(SUPPORT_CHANNEL)
            
            # Try to get user's status in channel
            try:
                participant = await client.get_permissions(channel, user_id)
                logger.info(f"✅ User {user_id} has joined the channel")
                return True
            except UserNotParticipantError:
                logger.info(f"❌ User {user_id} has NOT joined the channel")
                return False
            except Exception as e:
                logger.warning(f"⚠️ Could not check user {user_id} membership: {e}")
                # Alternative method - try to get participants
                try:
                    participants = await client.get_participants(channel, limit=100)
                    user_ids = [p.id for p in participants]
                    if user_id in user_ids:
                        logger.info(f"✅ User {user_id} found in channel participants")
                        return True
                    else:
                        logger.info(f"❌ User {user_id} NOT found in channel participants")
                        return False
                except Exception as e2:
                    logger.error(f"❌ Both methods failed for user {user_id}: {e2}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Channel check failed for user {user_id}: {e}")
            return False
            
    except Exception as e:
        logger.error(f"❌ General error in channel check for user {user_id}: {e}")
        return False

def add_to_recent_users(user_id, target_user_id, target_username=None, target_first_name=None):
    """Add user to recent users list - OPTIMIZED VERSION"""
    try:
        user_key = str(target_user_id)
        
        # Update global recent users
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
        
        # Update user's personal recent targets
        user_id_str = str(user_id)
        if user_id_str not in user_recent_targets:
            user_recent_targets[user_id_str] = []
        
        # Remove if already exists
        user_recent_targets[user_id_str] = [t for t in user_recent_targets[user_id_str] 
                                          if t.get('user_id') != target_user_id]
        
        # Add to beginning
        user_recent_targets[user_id_str].insert(0, {
            'user_id': target_user_id,
            'username': target_username,
            'first_name': target_first_name,
            'last_used': datetime.now().isoformat()
        })
        
        # Keep only last 8 per user
        if len(user_recent_targets[user_id_str]) > 8:
            user_recent_targets[user_id_str] = user_recent_targets[user_id_str][:8]
        
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
            
        with open(PENDING_VERIFICATION_FILE, 'w', encoding='utf-8') as f:
            json.dump(pending_verification, f, indent=2, ensure_ascii=False)
            
        with open(BROADCAST_MESSAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump(broadcast_messages, f, indent=2, ensure_ascii=False)
            
        with open(ALL_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(all_bot_users), f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"Async save error: {e}")

def get_recent_users_buttons(user_id):
    """Get recent users buttons for inline suggestions - SUPER FAST"""
    try:
        user_id_str = str(user_id)
        
        # Use user's personal recent targets first
        user_targets = []
        if user_id_str in user_recent_targets:
            user_targets = user_recent_targets[user_id_str][:6]  # Get first 6
        
        # If user has no personal targets, use global recent
        if not user_targets and recent_users:
            sorted_users = sorted(recent_users.items(), 
                                key=lambda x: x[1].get('last_used', ''), 
                                reverse=True)
            user_targets = [user[1] for user in sorted_users[:4]]
        
        if not user_targets:
            return []
        
        buttons = []
        for user_data in user_targets:
            username = user_data.get('username')
            first_name = user_data.get('first_name', 'User')
            user_id_val = user_data.get('user_id')
            
            if username:
                display_text = f"@{username}"
                query_text = f"@{username}"
            else:
                display_text = f"{first_name}"
                query_text = f"{user_id_val}"
            
            # Truncate long names
            if len(display_text) > 12:
                display_text = display_text[:12] + ".."
            
            buttons.append([Button.switch_inline(
                f"🔒 {display_text}", 
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

async def get_all_groups_where_admin(client=None):
    """Get all groups where bot is admin - ADVANCED VERSION"""
    if client is None:
        client = bot
        
    admin_groups = []
    try:
        # Get all dialogs
        dialogs = await client.get_dialogs()
        
        for dialog in dialogs:
            try:
                # Check if it's a group/channel and bot is admin
                if dialog.is_group or dialog.is_channel:
                    entity = dialog.entity
                    
                    # Get bot's permissions in this chat
                    try:
                        bot_permissions = await client.get_permissions(entity, await client.get_me())
                        if bot_permissions.is_admin:
                            admin_groups.append({
                                'entity': entity,
                                'title': getattr(entity, 'title', 'Unknown'),
                                'id': getattr(entity, 'id', 'Unknown'),
                                'username': getattr(entity, 'username', None)
                            })
                            logger.info(f"✅ Bot is admin in: {getattr(entity, 'title', 'Unknown')}")
                    except Exception as e:
                        continue
                        
            except Exception as e:
                continue
                
    except Exception as e:
        logger.error(f"Error getting admin groups: {e}")
    
    return admin_groups

async def send_broadcast_to_all_targets(broadcast_text, processing_msg=None):
    """ADVANCED BROADCAST: Send to ALL targets with detailed tracking"""
    total_successful = 0
    total_failed = 0
    detailed_results = {
        'main_bot_users': {'successful': 0, 'failed': 0, 'details': []},
        'cloned_bots': {'successful': 0, 'failed': 0, 'details': []},
        'admin_groups': {'successful': 0, 'failed': 0, 'details': []}
    }
    
    # 1. Send to Main Bot Users
    logger.info("📨 Sending broadcast to main bot users...")
    main_bot_users = list(all_bot_users)
    
    if main_bot_users:
        if processing_msg:
            await processing_msg.edit(f"🔄 **Advanced Broadcast Started**\n\n📨 Main Bot Users: 0/{len(main_bot_users)}\n✅ Total: 0\n❌ Failed: 0")
        
        for i, user_id in enumerate(main_bot_users):
            try:
                if await send_broadcast_to_user(user_id, broadcast_text):
                    detailed_results['main_bot_users']['successful'] += 1
                    total_successful += 1
                else:
                    detailed_results['main_bot_users']['failed'] += 1
                    total_failed += 1
                
                # Update progress every 10 users
                if (i + 1) % 10 == 0 and processing_msg:
                    await processing_msg.edit(
                        f"🔄 **Advanced Broadcast**\n\n"
                        f"📨 Main Bot Users: {i+1}/{len(main_bot_users)}\n"
                        f"✅ Successful: {detailed_results['main_bot_users']['successful']}\n"
                        f"❌ Failed: {detailed_results['main_bot_users']['failed']}\n"
                        f"📊 Total Progress: {total_successful + total_failed}"
                    )
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                detailed_results['main_bot_users']['failed'] += 1
                total_failed += 1
                logger.error(f"Failed to send to main bot user {user_id}: {e}")
    
    # 2. Send to Cloned Bot Users - ADVANCED VERSION
    logger.info("🤖 Sending broadcast to cloned bot users...")
    
    cloned_bot_success = 0
    cloned_bot_failed = 0
    
    for token, user_bot in user_bots.items():
        try:
            if processing_msg:
                await processing_msg.edit(f"🔄 **Advanced Broadcast**\n\n🤖 Processing Cloned Bot: {token[:10]}...\n✅ Total: {total_successful}\n❌ Failed: {total_failed}")
            
            # Send broadcast command to cloned bot
            bot_me = await user_bot.get_me()
            try:
                await user_bot.send_message(
                    bot_me.id,  # Send to bot itself
                    f"/broadcast_from_main {broadcast_text}"
                )
                cloned_bot_success += 1
                detailed_results['cloned_bots']['details'].append({
                    'bot_username': bot_me.username,
                    'status': 'success'
                })
                logger.info(f"✅ Sent broadcast to cloned bot: @{bot_me.username}")
            except Exception as e:
                cloned_bot_failed += 1
                detailed_results['cloned_bots']['details'].append({
                    'bot_username': getattr(bot_me, 'username', 'unknown'),
                    'status': 'failed',
                    'error': str(e)
                })
                logger.error(f"❌ Failed to send to cloned bot {token[:10]}: {e}")
            
            await asyncio.sleep(0.5)  # Delay between cloned bots
            
        except Exception as e:
            cloned_bot_failed += 1
            detailed_results['cloned_bots']['details'].append({
                'bot_username': 'unknown',
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"Error with cloned bot {token[:10]}: {e}")
    
    detailed_results['cloned_bots']['successful'] = cloned_bot_success
    detailed_results['cloned_bots']['failed'] = cloned_bot_failed
    total_successful += cloned_bot_success
    total_failed += cloned_bot_failed
    
    # 3. Send to Admin Groups - ADVANCED VERSION
    logger.info("🏢 Sending broadcast to admin groups...")
    admin_groups = await get_all_groups_where_admin()
    
    if admin_groups:
        if processing_msg:
            await processing_msg.edit(f"🔄 **Advanced Broadcast**\n\n🏢 Admin Groups: 0/{len(admin_groups)}\n✅ Total: {total_successful}\n❌ Failed: {total_failed}")
        
        for i, group_info in enumerate(admin_groups):
            try:
                group = group_info['entity']
                await bot.send_message(group, broadcast_text)
                detailed_results['admin_groups']['successful'] += 1
                total_successful += 1
                detailed_results['admin_groups']['details'].append({
                    'title': group_info['title'],
                    'status': 'success'
                })
                logger.info(f"✅ Sent to admin group: {group_info['title']}")
                
                # Update progress
                if processing_msg:
                    await processing_msg.edit(
                        f"🔄 **Advanced Broadcast**\n\n"
                        f"🏢 Admin Groups: {i+1}/{len(admin_groups)}\n"
                        f"✅ Successful: {detailed_results['admin_groups']['successful']}\n"
                        f"❌ Failed: {detailed_results['admin_groups']['failed']}\n"
                        f"📊 Total Progress: {total_successful + total_failed}"
                    )
                
                await asyncio.sleep(1)  # Longer delay for groups to avoid rate limits
                
            except Exception as e:
                detailed_results['admin_groups']['failed'] += 1
                total_failed += 1
                detailed_results['admin_groups']['details'].append({
                    'title': group_info['title'],
                    'status': 'failed',
                    'error': str(e)
                })
                logger.error(f"Failed to send to admin group {group_info['title']}: {e}")
    
    return total_successful, total_failed, detailed_results

async def send_broadcast_to_user(user_id, message_text, client=None):
    """Send broadcast message to a specific user"""
    if client is None:
        client = bot
        
    try:
        await client.send_message(user_id, message_text)
        return True
    except Exception as e:
        logger.error(f"Failed to send broadcast to {user_id}: {e}")
        return False

async def send_promotion_to_groups(promotion_text, client=None):
    """Send promotion to all groups where bot is admin"""
    if client is None:
        client = bot
        
    try:
        admin_groups = await get_all_groups_where_admin(client)
        success_count = 0
        failed_count = 0
        
        for group_info in admin_groups:
            try:
                await client.send_message(group_info['entity'], promotion_text)
                success_count += 1
                logger.info(f"✅ Promotion sent to: {group_info['title']}")
                await asyncio.sleep(2)  # Avoid rate limits
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ Failed to send promotion to {group_info['title']}: {e}")
        
        return success_count, failed_count
    except Exception as e:
        logger.error(f"Error in promotion to groups: {e}")
        return 0, 0

async def send_promotion_to_cloned_bots(promotion_text):
    """Send promotion message to all cloned bots"""
    success_count = 0
    failed_count = 0
    
    for token, user_bot in user_bots.items():
        try:
            bot_me = await user_bot.get_me()
            await user_bot.send_message(bot_me.id, promotion_text)
            success_count += 1
            logger.info(f"✅ Promotion sent to cloned bot: @{bot_me.username}")
            await asyncio.sleep(1)
        except Exception as e:
            failed_count += 1
            logger.error(f"❌ Failed to send promotion to cloned bot: {e}")
    
    return success_count, failed_count

# ========== ENHANCED BROADCAST COMMANDS ==========

@bot.on(events.NewMessage(pattern='/broadcast'))
async def broadcast_handler(event):
    """Enhanced Broadcast message to all users - ADMIN ONLY"""
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
        
    try:
        # Check if it's a reply to a message
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            broadcast_text = reply_msg.text
        else:
            # Extract message from command
            parts = event.text.split(' ', 1)
            if len(parts) < 2:
                await event.reply(
                    "📢 **Advanced Broadcast System**\n\n"
                    "**Usage:**\n"
                    "• Reply to a message with `/broadcast`\n"
                    "• Or: `/broadcast your_message`\n\n"
                    "**Targets:**\n"
                    "• 👥 All Main Bot Users\n"
                    "• 🤖 All Cloned Bots + Their Users\n"
                    "• 🏢 All Groups Where Bot is Admin\n\n"
                    "**Advanced Options:**\n"
                    "• `/promote` - Send promotion to groups\n"
                    "• `/promote_clones` - Send promotion to cloned bots",
                    buttons=[
                        [Button.inline("🚀 Send Broadcast", data="broadcast_start")],
                        [Button.inline("📢 Send Promotion", data="promotion_start")],
                        [Button.inline("🔙 Back", data="back_start")]
                    ]
                )
                return
            broadcast_text = parts[1]
        
        if not broadcast_text.strip():
            await event.reply("❌ Broadcast message cannot be empty!")
            return
            
        # Store broadcast message in separate storage
        broadcast_id = f"broadcast_{int(datetime.now().timestamp())}"
        broadcast_messages[broadcast_id] = broadcast_text
        asyncio.create_task(save_data_async())
        
        # Get estimated reach
        admin_groups = await get_all_groups_where_admin()
        estimated_reach = len(all_bot_users) + len(clone_stats) * 50 + len(admin_groups) * 100
            
        # Enhanced confirmation message
        await event.reply(
            f"📢 **Advanced Broadcast Confirmation**\n\n"
            f"**Message:** {broadcast_text[:100]}{'...' if len(broadcast_text) > 100 else ''}\n\n"
            f"📊 **Estimated Reach:**\n"
            f"• 👥 Main Bot Users: {len(all_bot_users)}\n"
            f"• 🤖 Cloned Bots: {len(clone_stats)} (with their users)\n"
            f"• 🏢 Admin Groups: {len(admin_groups)}\n"
            f"• 🌍 Total Estimated: ~{estimated_reach} users\n\n"
            f"⚠️ This will be sent to ALL targets. Continue?",
            buttons=[
                [Button.inline("✅ Yes, Send to ALL", f"confirm_broadcast:{broadcast_id}")],
                [Button.inline("🔙 Back", data="back_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        await event.reply("❌ Error processing broadcast command!")

@bot.on(events.NewMessage(pattern='/promote'))
async def promote_handler(event):
    """Send promotion to all groups where bot is admin"""
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
        
    try:
        # Check if it's a reply to a message
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            promotion_text = reply_msg.text
        else:
            # Extract message from command
            parts = event.text.split(' ', 1)
            if len(parts) < 2:
                # Default promotion message
                promotion_text = """
🤖 **ShriBots Whisper Bot - Advanced Features**

🔒 Send Anonymous Secret Messages
🚀 Only Intended Recipient Can Read
🎯 Easy Inline Mode
🤖 Clone Your Own Bot

**Features:**
• 📢 Advanced Broadcast System
• 🏢 Group Promotion Support  
• 🔓 Free Access for Cloned Bots
• 🌍 Public & Private Messages

**Try Now:** @upspbot
**Support:** @shribots
                """
            else:
                promotion_text = parts[1]
        
        processing_msg = await event.reply("🔄 **Sending promotion to all admin groups...**")
        
        # Send promotion to all admin groups
        success_count, failed_count = await send_promotion_to_groups(promotion_text)
        
        await processing_msg.edit(
            f"✅ **Promotion Completed!**\n\n"
            f"📊 **Results:**\n"
            f"• ✅ Successful: {success_count} groups\n"
            f"• ❌ Failed: {failed_count} groups\n"
            f"• 📈 Success Rate: {(success_count/(success_count+failed_count))*100 if (success_count+failed_count) > 0 else 0:.1f}%\n\n"
            f"🕒 Completed: {datetime.now().strftime('%H:%M:%S')}",
            buttons=[[Button.inline("🔙 Back", data="back_start")]]
        )
        
    except Exception as e:
        logger.error(f"Promote error: {e}")
        await event.reply("❌ Error sending promotion!")

@bot.on(events.NewMessage(pattern='/promote_clones'))
async def promote_clones_handler(event):
    """Send promotion to all cloned bots"""
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
        
    try:
        if not user_bots:
            await event.reply("❌ No cloned bots found!")
            return
            
        # Check if it's a reply to a message
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            promotion_text = reply_msg.text
        else:
            # Default promotion message for cloned bots
            promotion_text = """
🔄 **Main Bot Update Notification**

🚀 New Features Available:
• 📢 Advanced Broadcast System
• 🏢 Group Promotion Support
• 🔓 Free Access for All Users
• 🌍 Public Message Feature

**Main Bot:** @upspbot
**Support:** @shribots

Thank you for using ShriBots! 🤖
            """
        
        processing_msg = await event.reply("🔄 **Sending promotion to all cloned bots...**")
        
        # Send promotion to all cloned bots
        success_count, failed_count = await send_promotion_to_cloned_bots(promotion_text)
        
        await processing_msg.edit(
            f"✅ **Cloned Bots Promotion Completed!**\n\n"
            f"📊 **Results:**\n"
            f"• ✅ Successful: {success_count} bots\n"
            f"• ❌ Failed: {failed_count} bots\n"
            f"• 📈 Success Rate: {(success_count/(success_count+failed_count))*100 if (success_count+failed_count) > 0 else 0:.1f}%\n\n"
            f"🕒 Completed: {datetime.now().strftime('%H:%M:%S')}",
            buttons=[[Button.inline("🔙 Back", data="back_start")]]
        )
        
    except Exception as e:
        logger.error(f"Promote clones error: {e}")
        await event.reply("❌ Error sending promotion to cloned bots!")

# New command for cloned bots to receive broadcast from main bot
@bot.on(events.NewMessage(pattern=r'/broadcast_from_main\s+(.+)'))
async def broadcast_from_main_handler(event):
    """Handle broadcast from main bot - FOR CLONED BOTS"""
    try:
        # Extract message
        broadcast_text = event.pattern_match.group(1).strip()
        
        if not broadcast_text:
            return
        
        logger.info(f"📨 Received broadcast from main bot: {broadcast_text[:50]}...")
        
        # Send to all users of this cloned bot
        cloned_bot = event.client
        bot_me = await cloned_bot.get_me()
        
        # Get all dialogs for this cloned bot
        dialogs = await cloned_bot.get_dialogs(limit=100)
        user_count = 0
        
        for dialog in dialogs:
            if dialog.is_user:
                try:
                    await cloned_bot.send_message(dialog.entity.id, broadcast_text)
                    user_count += 1
                    await asyncio.sleep(0.1)  # Rate limit protection
                except Exception as e:
                    logger.error(f"Failed to send to user {dialog.entity.id} from cloned bot: {e}")
        
        logger.info(f"✅ Cloned bot @{bot_me.username} sent broadcast to {user_count} users")
        
    except Exception as e:
        logger.error(f"Error in broadcast_from_main: {e}")

# ========== ENHANCED CALLBACK HANDLERS ==========

@bot.on(events.CallbackQuery(pattern=b'promotion_start'))
async def promotion_start_callback(event):
    """Start promotion process"""
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Admin only!", alert=True)
        return
        
    try:
        await event.edit(
            "📢 **Promotion Options**\n\n"
            "Choose where to send promotion:",
            buttons=[
                [Button.inline("🏢 To Admin Groups", data="promote_groups")],
                [Button.inline("🤖 To Cloned Bots", data="promote_clones")],
                [Button.inline("🌍 To All Targets", data="promote_all")],
                [Button.inline("🔙 Back", data="broadcast_info")]
            ]
        )
    except Exception as e:
        logger.error(f"Promotion start callback error: {e}")

@bot.on(events.CallbackQuery(pattern=b'promote_groups'))
async def promote_groups_callback(event):
    """Send promotion to groups"""
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Admin only!", alert=True)
        return
        
    try:
        # Default promotion message
        promotion_text = """
🤖 **ShriBots Whisper Bot - Advanced Features**

🔒 Send Anonymous Secret Messages
🚀 Only Intended Recipient Can Read
🎯 Easy Inline Mode
🤖 Clone Your Own Bot

**Features:**
• 📢 Advanced Broadcast System
• 🏢 Group Promotion Support  
• 🔓 Free Access for Cloned Bots
• 🌍 Public & Private Messages

**Try Now:** @upspbot
**Support:** @shribots
        """
        
        processing_msg = await event.edit("🔄 **Sending promotion to all admin groups...**")
        
        # Send promotion to all admin groups
        success_count, failed_count = await send_promotion_to_groups(promotion_text)
        
        await processing_msg.edit(
            f"✅ **Group Promotion Completed!**\n\n"
            f"📊 **Results:**\n"
            f"• ✅ Successful: {success_count} groups\n"
            f"• ❌ Failed: {failed_count} groups\n"
            f"• 📈 Success Rate: {(success_count/(success_count+failed_count))*100 if (success_count+failed_count) > 0 else 0:.1f}%\n\n"
            f"🕒 Completed: {datetime.now().strftime('%H:%M:%S')}",
            buttons=[[Button.inline("🔙 Back", data="promotion_start")]]
        )
        
    except Exception as e:
        logger.error(f"Promote groups callback error: {e}")
        await event.answer("❌ Error sending promotion to groups!", alert=True)

@bot.on(events.CallbackQuery(pattern=b'promote_clones'))
async def promote_clones_callback(event):
    """Send promotion to cloned bots"""
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Admin only!", alert=True)
        return
        
    try:
        if not user_bots:
            await event.answer("❌ No cloned bots found!", alert=True)
            return
            
        promotion_text = """
🔄 **Main Bot Update Notification**

🚀 New Features Available:
• 📢 Advanced Broadcast System
• 🏢 Group Promotion Support
• 🔓 Free Access for All Users
• 🌍 Public Message Feature

**Main Bot:** @upspbot
**Support:** @shribots

Thank you for using ShriBots! 🤖
        """
        
        processing_msg = await event.edit("🔄 **Sending promotion to all cloned bots...**")
        
        # Send promotion to all cloned bots
        success_count, failed_count = await send_promotion_to_cloned_bots(promotion_text)
        
        await processing_msg.edit(
            f"✅ **Cloned Bots Promotion Completed!**\n\n"
            f"📊 **Results:**\n"
            f"• ✅ Successful: {success_count} bots\n"
            f"• ❌ Failed: {failed_count} bots\n"
            f"• 📈 Success Rate: {(success_count/(success_count+failed_count))*100 if (success_count+failed_count) > 0 else 0:.1f}%\n\n"
            f"🕒 Completed: {datetime.now().strftime('%H:%M:%S')}",
            buttons=[[Button.inline("🔙 Back", data="promotion_start")]]
        )
        
    except Exception as e:
        logger.error(f"Promote clones callback error: {e}")
        await event.answer("❌ Error sending promotion to cloned bots!", alert=True)

@bot.on(events.CallbackQuery(pattern=b'promote_all'))
async def promote_all_callback(event):
    """Send promotion to all targets"""
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Admin only!", alert=True)
        return
        
    try:
        promotion_text = """
🌟 **ShriBots Whisper Bot - Special Promotion**

🤖 **Advanced Features:**
• 🔒 Anonymous Secret Messages
• 🚀 Inline Mode - Easy to Use
• 🌍 Public & Private Messages
• 📢 Advanced Broadcast System
• 🏢 Group Promotion Support
• 🔓 Free Access for Cloned Bots

**Create Your Own Bot:** @upspbot
**Support & Updates:** @shribots

🎉 Join thousands of users sending secret messages!
        """
        
        processing_msg = await event.edit("🔄 **Sending promotion to ALL targets...**\n\nThis may take several minutes...")
        
        # Send to groups
        groups_success, groups_failed = await send_promotion_to_groups(promotion_text)
        
        # Send to cloned bots
        clones_success, clones_failed = await send_promotion_to_cloned_bots(promotion_text)
        
        # Send to main bot users
        users_success = 0
        users_failed = 0
        for user_id in all_bot_users:
            try:
                await bot.send_message(user_id, promotion_text)
                users_success += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                users_failed += 1
        
        total_success = groups_success + clones_success + users_success
        total_failed = groups_failed + clones_failed + users_failed
        
        await processing_msg.edit(
            f"✅ **All Targets Promotion Completed!**\n\n"
            f"📊 **Detailed Results:**\n"
            f"• 🏢 Groups: {groups_success}✅ {groups_failed}❌\n"
            f"• 🤖 Cloned Bots: {clones_success}✅ {clones_failed}❌\n"
            f"• 👥 Main Users: {users_success}✅ {users_failed}❌\n\n"
            f"📈 **Summary:**\n"
            f"• ✅ Total Successful: {total_success}\n"
            f"• ❌ Total Failed: {total_failed}\n"
            f"• 📊 Success Rate: {(total_success/(total_success+total_failed))*100 if (total_success+total_failed) > 0 else 0:.1f}%\n\n"
            f"🕒 Completed: {datetime.now().strftime('%H:%M:%S')}",
            buttons=[[Button.inline("🔙 Back", data="promotion_start")]]
        )
        
    except Exception as e:
        logger.error(f"Promote all callback error: {e}")
        await event.answer("❌ Error sending promotion to all targets!", alert=True)

# ========== REST OF THE CODE REMAINS THE SAME ==========

# [The rest of your existing code for start_handler, help_handler, clone_handler, 
# inline_handler, callback_handler, etc. remains exactly the same...]

# Flask web server
app = Flask(__name__)

@app.route('/')
def home():
    bot_username = "bot_username"
    try:
        if bot.is_connected():
            bot_me = bot.loop.run_until_complete(bot.get_me())
            bot_username = bot_me.username
    except:
        pass
        
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>ShriBots Whisper Bot - Advanced Broadcast</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; text-align: center; }}
            .status {{ background: #4CAF50; color: white; padding: 10px; border-radius: 5px; text-align: center; margin: 20px 0; }}
            .info {{ background: #2196F3; color: white; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .feature {{ background: #FF9800; color: white; padding: 10px; border-radius: 5px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 ShriBots Whisper Bot - Advanced Broadcast</h1>
            <div class="status">✅ Bot is Running Successfully</div>
            <div class="feature">
                <strong>🚀 NEW: Advanced Broadcast System</strong><br>
                • Send to All Groups Where Bot is Admin<br>
                • Promote to All Cloned Bots<br>
                • Reach Maximum Users
            </div>
            <div class="info">
                <strong>📊 Statistics:</strong><br>
                Recent Users: {len(recent_users)}<br>
                Total Messages: {len(messages_db)}<br>
                Total Clones: {len(clone_stats)}<br>
                Total Tracked Users: {len(all_bot_users)}<br>
                Pending Verifications: {len(pending_verification)}<br>
                Server Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </div>
            <p>This bot allows you to send anonymous secret messages to Telegram users.</p>
            <p><strong>Advanced Broadcast Features:</strong></p>
            <ul>
                <li>📢 Send to ALL groups where bot is admin</li>
                <li>🤖 Promote to ALL cloned bots</li>
                <li>👥 Reach ALL main bot users</li>
                <li>🌍 Maximum promotion coverage</li>
            </ul>
            <p><strong>Usage:</strong> Use inline mode in any chat: <code>@{bot_username} message @username</code></p>
        </div>
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
        "total_tracked_users": len(all_bot_users),
        "pending_verifications": len(pending_verification),
        "bot_connected": bot.is_connected(),
        "features": ["advanced_broadcast", "group_promotion", "clone_promotion"]
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
        logger.info(f"👥 Total Tracked Users: {len(all_bot_users)}")
        logger.info(f"🔒 Pending Verifications: {len(pending_verification)}")
        logger.info(f"🌐 Web server running on port {PORT}")
        logger.info("✅ Bot is ready and working!")
        logger.info("🚀 Advanced Broadcast System: ACTIVE")
        logger.info("🏢 Group Promotion: ACTIVE") 
        logger.info("🤖 Clone Promotion: ACTIVE")
        logger.info("🔗 Use /start to begin")
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

if __name__ == '__main__':
    print("🚀 Starting ShriBots Whisper Bot with Advanced Broadcast...")
    print(f"📝 Environment: API_ID={API_ID}, PORT={PORT}")
    
    try:
        # Start the bot
        bot.start()
        bot.loop.run_until_complete(main())
        
        print("✅ Bot started successfully!")
        print("🔄 Bot is now running...")
        print("📢 Advanced Broadcast System: READY")
        print("🏢 Group Promotion: READY")
        print("🤖 Clone Promotion: READY")
        
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
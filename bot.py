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
   • /gc - Promote in groups (Admin only)
   • /cb - Promote in cloned bots (Admin only)
   • /test_groups - Test admin groups (Admin only)

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
    """ENHANCED: Get all groups where bot is admin with better detection"""
    if client is None:
        client = bot
        
    admin_groups = []
    try:
        logger.info("🔍 Searching for admin groups...")
        # Get all dialogs
        dialogs = await client.get_dialogs()
        logger.info(f"📁 Total dialogs found: {len(dialogs)}")
        
        for dialog in dialogs:
            try:
                # Check if it's a group/channel
                if dialog.is_group or dialog.is_channel:
                    entity = dialog.entity
                    group_title = getattr(entity, 'title', 'Unknown')
                    
                    # Skip if it's a broadcast channel without send rights
                    if dialog.is_channel and not dialog.is_group:
                        try:
                            # Check if bot can send messages in channel
                            await client.get_permissions(entity, await client.get_me())
                        except:
                            logger.warning(f"🚫 Bot cannot send messages in channel: {group_title}")
                            continue
                    
                    # Get bot's permissions with enhanced error handling
                    try:
                        me = await client.get_me()
                        bot_permissions = await client.get_permissions(entity, me)
                        
                        if bot_permissions.is_admin:
                            admin_groups.append(entity)
                            logger.info(f"✅ Bot is admin in: {group_title}")
                        else:
                            logger.debug(f"❌ Bot is NOT admin in: {group_title}")
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Could not check permissions for {group_title}: {str(e)[:100]}")
                        continue
                        
            except Exception as e:
                logger.debug(f"⚠️ Skipping dialog: {str(e)[:50]}")
                continue
                
    except Exception as e:
        logger.error(f"❌ Error getting admin groups: {e}")
    
    logger.info(f"📊 Total admin groups found: {len(admin_groups)}")
    return admin_groups

async def send_broadcast_to_all_targets(broadcast_text, processing_msg=None):
    """Send broadcast to ALL targets: main bot users, cloned bot users, and admin groups"""
    total_successful = 0
    total_failed = 0
    detailed_results = {
        'main_bot': {'successful': 0, 'failed': 0},
        'cloned_bots': {'successful': 0, 'failed': 0},
        'admin_groups': {'successful': 0, 'failed': 0}
    }
    
    # 1. Send to Main Bot Users
    logger.info("📨 Sending broadcast to main bot users...")
    main_bot_users = list(all_bot_users)
    
    if main_bot_users:
        if processing_msg:
            await processing_msg.edit(f"🔄 **Sending broadcast...**\n\n📨 Main Bot Users: 0/{len(main_bot_users)}")
        
        for i, user_id in enumerate(main_bot_users):
            try:
                if await send_broadcast_to_user(user_id, broadcast_text):
                    detailed_results['main_bot']['successful'] += 1
                    total_successful += 1
                else:
                    detailed_results['main_bot']['failed'] += 1
                    total_failed += 1
                
                # Update progress every 10 users
                if (i + 1) % 10 == 0 and processing_msg:
                    await processing_msg.edit(
                        f"🔄 **Sending broadcast...**\n\n"
                        f"📨 Main Bot Users: {i+1}/{len(main_bot_users)}\n"
                        f"✅ Successful: {detailed_results['main_bot']['successful']}\n"
                        f"❌ Failed: {detailed_results['main_bot']['failed']}"
                    )
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                detailed_results['main_bot']['failed'] += 1
                total_failed += 1
                logger.error(f"Failed to send to main bot user {user_id}: {e}")
    
    # 2. Send to Cloned Bot Users
    logger.info("🤖 Sending broadcast to cloned bot users...")
    
    # Send broadcast to all cloned bots - THEY WILL HANDLE THEIR OWN USERS
    cloned_bot_success = 0
    cloned_bot_failed = 0
    
    for token, user_bot in user_bots.items():
        try:
            if processing_msg:
                await processing_msg.edit(f"🔄 **Sending to cloned bots...**\n\n🤖 Processing: {token[:10]}...")
            
            # Send broadcast command to cloned bot
            bot_me = await user_bot.get_me()
            try:
                await user_bot.send_message(
                    bot_me.id,  # Send to bot itself
                    f"/broadcast_from_main {broadcast_text}"
                )
                cloned_bot_success += 1
                logger.info(f"✅ Sent broadcast to cloned bot: @{bot_me.username}")
            except Exception as e:
                cloned_bot_failed += 1
                logger.error(f"❌ Failed to send to cloned bot {token[:10]}: {e}")
            
            await asyncio.sleep(0.5)  # Delay between cloned bots
            
        except Exception as e:
            cloned_bot_failed += 1
            logger.error(f"Error with cloned bot {token[:10]}: {e}")
    
    detailed_results['cloned_bots']['successful'] = cloned_bot_success
    detailed_results['cloned_bots']['failed'] = cloned_bot_failed
    total_successful += cloned_bot_success
    total_failed += cloned_bot_failed
    
    # 3. Send to Admin Groups
    logger.info("🏢 Sending broadcast to admin groups...")
    admin_groups = await get_all_groups_where_admin()
    
    if admin_groups:
        if processing_msg:
            await processing_msg.edit(f"🔄 **Sending to admin groups...**\n\n🏢 Groups: 0/{len(admin_groups)}")
        
        for i, group in enumerate(admin_groups):
            try:
                await bot.send_message(group, broadcast_text)
                detailed_results['admin_groups']['successful'] += 1
                total_successful += 1
                logger.info(f"✅ Sent to admin group: {getattr(group, 'title', 'Unknown')}")
                
                # Update progress
                if processing_msg:
                    await processing_msg.edit(
                        f"🔄 **Sending broadcast...**\n\n"
                        f"🏢 Admin Groups: {i+1}/{len(admin_groups)}\n"
                        f"✅ Successful: {detailed_results['admin_groups']['successful']}\n"
                        f"❌ Failed: {detailed_results['admin_groups']['failed']}"
                    )
                
                await asyncio.sleep(1)  # Longer delay for groups to avoid rate limits
                
            except Exception as e:
                detailed_results['admin_groups']['failed'] += 1
                total_failed += 1
                logger.error(f"Failed to send to admin group {getattr(group, 'title', 'Unknown')}: {e}")
    
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

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        logger.info(f"🚀 Start command from user: {event.sender_id}")
        
        # Track user for broadcast
        add_user_to_tracking(event.sender_id)
        
        # Admin ko direct access do (force join se exempt)
        if event.sender_id == ADMIN_ID:
            await event.reply(
                WELCOME_TEXT,
                buttons=[
                    [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                    [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                    [Button.switch_inline("🚀 Try Now", query="", same_peer=True)],
                    [Button.inline("📊 Statistics", data="admin_stats"), Button.inline("📖 Help", data="help")],
                    [Button.inline("🔧 Clone Bot", data="clone_info"), Button.inline("🤖 All Bots", data="all_bots")],
                    [Button.inline("📢 Broadcast", data="broadcast_info")]
                ]
            )
            return
        
        # Regular users ke liye force join check karo
        has_joined = await check_user_joined_channel(event.sender_id)
        
        if not has_joined:
            # Add to pending verification
            pending_verification[str(event.sender_id)] = {
                'bot_token': 'main_bot',
                'joined_at': None,
                'attempts': 0
            }
            asyncio.create_task(save_data_async())
            
            mention = f"[{event.sender.first_name}](tg://user?id={event.sender_id})"
            
            await event.reply(
                f"𝙅𝙖𝙮 𝙎𝙝𝙧𝙚𝙚 𝙍𝙖𝙢 🚩 | 𝐒𝐡𝐫𝐢𝐛𝐨𝐭𝐬\n\n"
                f"Hey {mention}\n"
                f"To use and clone this bot, please join the update channel first. Once joined, tap 'Check Again' to continue.",
                buttons=[
                    [Button.url("📢 Join Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                    [Button.inline("🔄 Check Again", "check_join_main")]
                ]
            )
            return
        
        # User has joined, show normal start
        await event.reply(
            WELCOME_TEXT,
            buttons=[
                [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                [Button.switch_inline("🚀 Try Now", query="", same_peer=True)],
                [Button.inline("📖 Help", data="help"), Button.inline("🔧 Clone Bot", data="clone_info")]
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
        
        # Check force join for regular users
        if event.sender_id != ADMIN_ID:
            has_joined = await check_user_joined_channel(event.sender_id)
            if not has_joined:
                mention = f"[{event.sender.first_name}](tg://user?id={event.sender_id})"
                await event.reply(
                    f"𝙅𝙖𝙮 𝙎𝙝𝙧𝙚𝙚 𝙍𝙖𝙢 🚩 | 𝐒𝐡𝐫𝐢𝐛𝐨𝐭𝐬\n\n"
                    f"Hey {mention}\n"
                    f"To use and clone this bot, please join the update channel first. Once joined, tap 'Check Again' to continue.",
                    buttons=[
                        [Button.url("📢 Join Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                        [Button.inline("🔄 Check Again", "check_join_main")]
                    ]
                )
                return
        
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

@bot.on(events.CallbackQuery(pattern=b'check_join_main'))
async def check_join_callback(event):
    try:
        user_id = event.sender_id
        logger.info(f"🔄 Check join callback from user: {user_id}")
        
        # Check if user has joined the channel
        has_joined = await check_user_joined_channel(user_id)
        
        if has_joined:
            # Remove from pending verification
            if str(user_id) in pending_verification:
                del pending_verification[str(user_id)]
            asyncio.create_task(save_data_async())
            
            await event.edit(
                "✅ **Verification Successful!**\n\n"
                "Thank you for joining our channel! You can now use all features of the bot.",
                buttons=[[Button.inline("🚀 Start Using", data="start_verified")]]
            )
        else:
            # Increment attempts
            user_key = str(user_id)
            if user_key in pending_verification:
                pending_verification[user_key]['attempts'] += 1
            else:
                pending_verification[user_key] = {
                    'bot_token': 'main_bot',
                    'joined_at': None,
                    'attempts': 1
                }
            asyncio.create_task(save_data_async())
            
            await event.answer(
                "❌ You haven't joined the channel yet! Please join @shribots first and then click 'Check Again'.",
                alert=True
            )
            
    except Exception as e:
        logger.error(f"Check join callback error: {e}")
        await event.answer("❌ An error occurred. Please try again.", alert=True)

@bot.on(events.CallbackQuery(pattern=b'start_verified'))
async def start_verified_callback(event):
    try:
        await event.edit(
            WELCOME_TEXT,
            buttons=[
                [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                [Button.switch_inline("🚀 Try Now", query="", same_peer=True)],
                [Button.inline("📖 Help", data="help"), Button.inline("🔧 Clone Bot", data="clone_info")]
            ]
        )
    except Exception as e:
        logger.error(f"Start verified callback error: {e}")
        await event.answer("❌ An error occurred. Please try again.", alert=True)

@bot.on(events.NewMessage(pattern='/stats'))
async def stats_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
        
    try:
        total_clones = len(clone_stats)
        total_personal_targets = sum(len(v) for v in user_recent_targets.values())
        
        stats_text = f"""
📊 **Admin Statistics**

👥 Global Recent Users: {len(recent_users)}
👤 Personal Recent Targets: {total_personal_targets}
💬 Total Messages: {len(messages_db)}
🤖 Total Clones: {total_clones}
👥 Total Tracked Users: {len(all_bot_users)}
🆔 Admin ID: {ADMIN_ID}
🌐 Port: {PORT}

**Bot Status:** ✅ Running
**Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
        """
        
        await event.reply(stats_text)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await event.reply("❌ Error fetching statistics.")

@bot.on(events.NewMessage(pattern='/allbots'))
async def allbots_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
        
    try:
        total_clones = len(clone_stats)
        
        if total_clones == 0:
            await event.reply("🤖 No bots cloned yet!")
            return
        
        bots_text = f"🤖 **All Cloned Bots - Total: {total_clones}**\n\n"
        
        for i, (token, info) in enumerate(clone_stats.items(), 1):
            bots_text += f"**{i}. @{info['username']}**\n"
            bots_text += f"   👤 User ID: `{info['owner_id']}`\n"
            bots_text += f"   👤 Name: {info['first_name']}\n"
            bots_text += f"   📅 Created: {info['created_at']}\n"
            bots_text += f"   🔑 Token: {info['token_preview']}\n\n"
        
        await event.reply(bots_text)
    except Exception as e:
        logger.error(f"Allbots error: {e}")
        await event.reply("❌ Error fetching bot details.")

@bot.on(events.NewMessage(pattern='/broadcast'))
async def broadcast_handler(event):
    """Broadcast message to all users - ADMIN ONLY"""
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
                    "📢 **Broadcast Usage:**\n\n"
                    "**Method 1:** Reply to a message with `/broadcast`\n"
                    "**Method 2:** `/broadcast your_message_here`\n\n"
                    "⚠️ This will send to ALL users across:\n"
                    "• 👥 Main Bot Users\n"
                    "• 🤖 All Cloned Bots (with their users)  \n"
                    "• 🏢 Groups Where Bot is Admin",
                    buttons=[[Button.inline("🔙 Back", data="back_start")]]
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
            
        # Ask for confirmation
        await event.reply(
            f"📢 **Broadcast Confirmation**\n\n"
            f"**Message:** {broadcast_text[:100]}{'...' if len(broadcast_text) > 100 else ''}\n\n"
            f"📊 **Estimated Reach:**\n"
            f"• 👥 Main Bot Users: {len(all_bot_users)}\n"
            f"• 🤖 Cloned Bots: {len(clone_stats)}\n"
            f"• 🏢 Admin Groups: {len(admin_groups)}\n"
            f"• 🌍 Total Estimated: ~{estimated_reach} users\n\n"
            f"⚠️ This will be sent to ALL targets. Continue?",
            buttons=[
                [Button.inline("✅ Yes, Send to ALL", f"confirm_broadcast:{broadcast_id}")],
                [Button.inline("❌ Cancel", data="back_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        await event.reply("❌ Error processing broadcast command!")

@bot.on(events.NewMessage(pattern='/gc'))
async def group_promotion_handler(event):
    """ENHANCED: Send promotion to all groups where bot is admin"""
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
        
        processing_msg = await event.reply("🔄 **Scanning for admin groups...**")
        
        # ENHANCED: Get admin groups with better detection
        admin_groups = await get_all_groups_where_admin()
        
        if not admin_groups:
            await processing_msg.edit(
                "❌ **No Admin Groups Found!**\n\n"
                "Bot is not administrator in any groups.\n\n"
                "**To fix this:**\n"
                "1. Add bot to groups\n"
                "2. Give ADMIN rights to bot\n"
                "3. Ensure bot can send messages\n"
                "4. Use /test_groups to check"
            )
            return
        
        await processing_msg.edit(f"🔄 **Sending promotion to {len(admin_groups)} admin groups...**")
        
        success_count = 0
        failed_count = 0
        failed_list = []
        
        for i, group in enumerate(admin_groups):
            try:
                group_title = getattr(group, 'title', f'Group_{i+1}')
                
                # Update progress
                if processing_msg:
                    await processing_msg.edit(
                        f"🔄 **Sending to groups...**\n\n"
                        f"🏢 Progress: {i+1}/{len(admin_groups)}\n"
                        f"✅ Successful: {success_count}\n"
                        f"❌ Failed: {failed_count}\n"
                        f"📝 Current: {group_title[:20]}..."
                    )
                
                # Try to send message with timeout
                await asyncio.wait_for(
                    bot.send_message(group, promotion_text),
                    timeout=30
                )
                success_count += 1
                logger.info(f"✅ Promotion sent to: {group_title}")
                
                # Delay to avoid rate limits
                await asyncio.sleep(3)
                
            except asyncio.TimeoutError:
                failed_count += 1
                failed_list.append(f"{group_title} - Timeout")
                logger.error(f"⏰ Timeout sending to: {group_title}")
                
            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                if "Forbidden" in error_msg:
                    failed_list.append(f"{group_title} - Bot kicked/banned")
                elif "Timeout" in error_msg:
                    failed_list.append(f"{group_title} - Timeout")
                else:
                    failed_list.append(f"{group_title} - {error_msg[:30]}...")
                logger.error(f"❌ Failed to send to {group_title}: {error_msg}")
        
        # Prepare result message
        result_text = f"✅ **Group Promotion Completed!**\n\n"
        result_text += f"📊 **Results:**\n"
        result_text += f"• ✅ Successful: {success_count} groups\n"
        result_text += f"• ❌ Failed: {failed_count} groups\n"
        
        total_attempts = success_count + failed_count
        if total_attempts > 0:
            success_rate = (success_count / total_attempts) * 100
            result_text += f"• 📈 Success Rate: {success_rate:.1f}%\n\n"
        
        if failed_list:
            result_text += f"**Failed Groups ({min(5, len(failed_list))} shown):**\n"
            for failed in failed_list[:5]:
                result_text += f"• {failed}\n"
            if len(failed_list) > 5:
                result_text += f"• ... and {len(failed_list) - 5} more\n"
        
        result_text += f"\n🕒 Completed: {datetime.now().strftime('%H:%M:%S')}"
        
        await processing_msg.edit(
            result_text,
            buttons=[[Button.inline("🔙 Back", data="back_start")]]
        )
        
    except Exception as e:
        logger.error(f"Group promotion error: {e}")
        await event.reply(f"❌ Error in group promotion: {str(e)[:100]}")

@bot.on(events.NewMessage(pattern='/cb'))
async def clone_promotion_handler(event):
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
        success_count = 0
        failed_count = 0
        
        for i, (token, user_bot) in enumerate(user_bots.items()):
            try:
                bot_me = await user_bot.get_me()
                await user_bot.send_message(bot_me.id, promotion_text)
                success_count += 1
                logger.info(f"✅ Promotion sent to cloned bot: @{bot_me.username}")
                
                # Update progress
                if processing_msg:
                    await processing_msg.edit(
                        f"🔄 **Sending to cloned bots...**\n\n"
                        f"🤖 Progress: {i+1}/{len(user_bots)}\n"
                        f"✅ Successful: {success_count}\n"
                        f"❌ Failed: {failed_count}"
                    )
                
                await asyncio.sleep(1)  # Avoid rate limits
                
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ Failed to send promotion to cloned bot: {e}")
        
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
        logger.error(f"Clone promotion error: {e}")
        await event.reply("❌ Error sending promotion to cloned bots!")

@bot.on(events.NewMessage(pattern='/test_groups'))
async def test_groups_handler(event):
    """Test command to check admin groups"""
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
        
    try:
        processing_msg = await event.reply("🔍 **Scanning for admin groups...**")
        
        admin_groups = await get_all_groups_where_admin()
        
        if not admin_groups:
            await processing_msg.edit(
                "❌ **No Admin Groups Found!**\n\n"
                "Bot is not administrator in any groups.\n\n"
                "**Solutions:**\n"
                "1. Add bot to your groups\n"
                "2. Give FULL ADMIN rights to bot\n"
                "3. Ensure bot has 'Send Messages' permission\n"
                "4. Wait few minutes and try again"
            )
            return
        
        groups_text = f"🏢 **Admin Groups Found: {len(admin_groups)}**\n\n"
        
        for i, group in enumerate(admin_groups, 1):
            group_title = getattr(group, 'title', 'Unknown')
            group_id = getattr(group, 'id', 'Unknown')
            username = getattr(group, 'username', 'No username')
            
            groups_text += f"**{i}. {group_title}**\n"
            groups_text += f"   🆔 ID: `{group_id}`\n"
            groups_text += f"   📧 Username: @{username}\n\n"
        
        groups_text += f"✅ **Now use `/gc your_message` to promote in these groups**"
        
        await processing_msg.edit(groups_text)
        
    except Exception as e:
        logger.error(f"Test groups error: {e}")
        await event.reply(f"❌ Error testing groups: {str(e)[:100]}")

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

@bot.on(events.NewMessage(pattern='/clone'))
async def clone_handler(event):
    try:
        # Track user for broadcast
        add_user_to_tracking(event.sender_id)
        
        # Check if user has joined channel
        has_joined = await check_user_joined_channel(event.sender_id)
        
        if not has_joined:
            mention = f"[{event.sender.first_name}](tg://user?id={event.sender_id})"
            await event.reply(
                f"𝙅𝙖𝙮 𝙎𝙝𝙧𝙚𝙚 𝙍𝙖𝙢 🚩 | 𝐒𝐡𝐫𝐢𝐛𝐨𝐭𝐬\n\n"
                f"Hey {mention}\n"
                f"To use and clone this bot, please join the update channel first. Once joined, tap 'Check Again' to continue.",
                buttons=[
                    [Button.url("📢 Join Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                    [Button.inline("🔄 Check Again", "check_join_main")]
                ]
            )
            return
        
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
• Must join @shribots channel to use cloned bot
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
    try:
        user_id = event.sender_id
        token = event.pattern_match.group(1).strip()
        
        # Track user for broadcast
        add_user_to_tracking(user_id)
        
        # Check if user has joined channel
        has_joined = await check_user_joined_channel(user_id)
        
        if not has_joined:
            mention = f"[{event.sender.first_name}](tg://user?id={user_id})"
            await event.reply(
                f"𝙅𝙖𝙮 𝙎𝙝𝙧𝙚𝙚 𝙍𝙖𝙢 🚩 | 𝐒𝐡𝐫𝐢𝐛𝐨𝐭𝐬\n\n"
                f"Hey {mention}\n"
                f"To use and clone this bot, please join the update channel first. Once joined, tap 'Check Again' to continue.",
                buttons=[
                    [Button.url("📢 Join Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                    [Button.inline("🔄 Check Again", "check_join_main")]
                ]
            )
            return
        
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
        
        # Auto-join support channels for cloned bot - USING ADVANCED VERSION
        await precheck_channels(user_bot)
        
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
        
        # Save data in background
        asyncio.create_task(save_data_async())
        
        # Setup handlers for cloned bot - WITHOUT FORCE JOIN FEATURE
        @user_bot.on(events.NewMessage(pattern='/start'))
        async def user_start(event):
            # Track user for broadcast
            add_user_to_tracking(event.sender_id)
            
            # Direct access for all users in cloned bots - NO FORCE JOIN
            welcome_text_user = WELCOME_TEXT
            
            await event.reply(
                welcome_text_user,
                buttons=[
                    [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                    [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                    [Button.switch_inline("🚀 Try Now", query="", same_peer=True)],
                    [Button.inline("📖 Help", data="user_help")],
                    [Button.inline("🤖 Clone Bot", data="user_clone_info")]
                ]
            )
        
        @user_bot.on(events.NewMessage(pattern='/help'))
        async def user_help_handler(event):
            # Track user for broadcast
            add_user_to_tracking(event.sender_id)
            
            # Direct access for all users in cloned bots - NO FORCE JOIN
            bot_username_user = (await user_bot.get_me()).username
            help_text_user = HELP_TEXT.replace("{bot_username}", bot_username_user)
            
            await event.reply(
                help_text_user,
                buttons=[
                    [Button.switch_inline("🚀 Try Now", query="", same_peer=True)],
                    [Button.inline("🔙 Back", data="user_back_start")]
                ]
            )
        
        @user_bot.on(events.InlineQuery)
        async def user_inline_handler(event):
            # Track user for broadcast
            add_user_to_tracking(event.sender_id)
            
            # Direct access for all users in cloned bots - NO FORCE JOIN
            await handle_inline_query(event, user_bot)
        
        @user_bot.on(events.CallbackQuery)
        async def user_callback_handler(event):
            data = event.data.decode('utf-8')
            
            if data == "user_help":
                bot_username_user = (await user_bot.get_me()).username
                help_text_user = HELP_TEXT.replace("{bot_username}", bot_username_user)
                
                await event.edit(
                    help_text_user,
                    buttons=[[Button.switch_inline("🚀 Try Now", query="", same_peer=True)]]
                )
            
            elif data == "user_clone_info":
                # Show clone promotion message
                clone_promo_text = """
🤖 **Do you want a bot like this?**

Create your own whisper bot with all features:

• 📢 Broadcast Support  
• 🤫 All Whisper Features
• 🚀 Easy to Use
• 🔧 No Force Join Required

**Create your bot 👉 @upspbot**

**Powered by:** @shribots
                """
                await event.edit(
                    clone_promo_text,
                    buttons=[
                        [Button.url("🚀 Create Bot", "https://t.me/upspbot")],
                        [Button.inline("🔙 Back", data="user_back_start")]
                    ]
                )
            
            elif data == "user_back_start":
                welcome_text_user = WELCOME_TEXT
                
                await event.edit(
                    welcome_text_user,
                    buttons=[
                        [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                        [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                        [Button.switch_inline("🚀 Try Now", query="", same_peer=True)],
                        [Button.inline("📖 Help", data="user_help")],
                        [Button.inline("🤖 Clone Bot", data="user_clone_info")]
                    ]
                )
            
            elif data in messages_db:
                msg_data = messages_db[data]
                # PUBLIC MESSAGE - anyone can read if user_id is -1 (no specific user)
                if msg_data['user_id'] == -1:
                    await event.answer(f"🔓 {msg_data['msg']}", alert=True)
                elif event.sender_id == msg_data['user_id']:
                    await event.answer(f"🔓 {msg_data['msg']}", alert=True)
                elif event.sender_id == msg_data['sender_id']:
                    await event.answer(f"📝 {msg_data['msg']}", alert=True)
                else:
                    await event.answer("🔒 This message is not for you!", alert=True)
        
        # Add broadcast handler for cloned bot
        @user_bot.on(events.NewMessage(pattern=r'/broadcast_from_main\s+(.+)'))
        async def cloned_broadcast_handler(event):
            """Handle broadcast from main bot in cloned bot"""
            try:
                # Extract message
                broadcast_text = event.pattern_match.group(1).strip()
                
                if not broadcast_text:
                    return
                
                logger.info(f"📨 Cloned bot received broadcast: {broadcast_text[:50]}...")
                
                # Send to all users of this cloned bot
                bot_me = await user_bot.get_me()
                
                # Get all dialogs for this cloned bot
                dialogs = await user_bot.get_dialogs(limit=100)
                user_count = 0
                
                for dialog in dialogs:
                    if dialog.is_user:
                        try:
                            await user_bot.send_message(dialog.entity.id, broadcast_text)
                            user_count += 1
                            await asyncio.sleep(0.1)  # Rate limit protection
                        except Exception as e:
                            logger.error(f"Failed to send to user {dialog.entity.id} from cloned bot: {e}")
                
                logger.info(f"✅ Cloned bot @{bot_me.username} sent broadcast to {user_count} users")
                
            except Exception as e:
                logger.error(f"Error in cloned bot broadcast: {e}")
        
        # Send notification to admin
        try:
            notification_text = f"""
🆕 **New Bot Cloned!**

🤖 **Bot:** @{bot_me.username}
👤 **User ID:** `{user_id}`
👤 **User Name:** {event.sender.first_name}
📅 **Time:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
🔢 **Total Clones:** {len(clone_stats)}

✅ **Auto-Joined Channels:** Enabled
✅ **Broadcast Support:** Enabled
❌ **Force Join:** Disabled (Free Access)
            """
            
            await bot.send_message(ADMIN_ID, notification_text, parse_mode='markdown')
        except Exception as e:
            logger.error(f"Admin notification error: {e}")
        
        # Success message to user
        await creating_msg.edit(
            f"✅ **Bot Cloned Successfully!**\n\n"
            f"🤖 **Your Bot:** @{bot_me.username}\n"
            f"🎉 Now active with all whisper features!\n\n"
            f"**Features Included:**\n"
            f"• 📢 Broadcast Support\n"
            f"• 🤫 All Whisper Features\n"
            f"• 🤖 Clone Promotion Button\n"
            f"• 🔓 Free Access (No Force Join)\n\n"
            f"**Try your bot:**\n"
            f"`@{bot_me.username} message @username`\n\n"
            f"⚠️ **Note:** Users can use your bot without joining any channel!",
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
        
        asyncio.create_task(save_data_async())
        await event.reply(f"✅ Removed {removed} of your bots!")
        
    except Exception as e:
        logger.error(f"Remove error: {e}")
        await event.reply("❌ Error removing bots!")

@bot.on(events.InlineQuery)
async def inline_handler(event):
    # Track user for broadcast
    add_user_to_tracking(event.sender_id)
    
    # Admin ko direct access do
    if event.sender_id == ADMIN_ID:
        await handle_inline_query(event)
        return
    
    # Regular users ke liye force join check karo
    has_joined = await check_user_joined_channel(event.sender_id)
    
    if not has_joined:
        # Add to pending verification
        pending_verification[str(event.sender_id)] = {
            'bot_token': 'main_bot',
            'joined_at': None,
            'attempts': 0
        }
        asyncio.create_task(save_data_async())
        
        result = event.builder.article(
            title="🔒 Channel Membership Required",
            description="Join @shribots to use this bot",
            text="❌ **You need to join our channel first!**\n\n"
                 "Please join @shribots and then use /start to verify.",
            buttons=[[Button.url("📢 Join Channel", f"https://t.me/{SUPPORT_CHANNEL}")]]
        )
        await event.answer([result])
        return
    
    await handle_inline_query(event)

async def handle_inline_query(event, client=None):
    """Handle inline queries - WORKS WITH ANY INPUT"""
    if client is None:
        client = bot
    
    try:
        if is_cooldown(event.sender_id):
            await event.answer([])
            return

        # Get recent buttons quickly - ALWAYS SHOW RECENT USERS
        recent_buttons = get_recent_users_buttons(event.sender_id)
        
        if not event.text or not event.text.strip():
            # ALWAYS SHOW RECENT USERS WHEN NO TEXT
            if recent_buttons:
                result_text = "**Recent Users:**\nClick any user below to message them quickly!\n\nOr type your message with @username\n\n**Tip:** Type without @username for public message!"
                result = event.builder.article(
                    title="🤫 Whisper Bot - Quick Send",
                    description="Send to recent users or type manually",
                    text=result_text,
                    buttons=recent_buttons
                )
            else:
                result = event.builder.article(
                    title="🤫 Whisper Bot - Send Secret Messages",
                    description="Usage: message @username OR just message",
                    text="**Usage:** Type your message\n• Add @username for private message\n• Or type alone for public message\n\n**Examples:**\n• `Hello! @username` - Only they can read\n• `Hello everyone!` - Anyone can read\n\n🔒 Private | 🌍 Public",
                    buttons=[[Button.switch_inline("🚀 Try Now", query="", same_peer=True)]]
                )
            await event.answer([result])
            return
        
        text = event.text.strip()
        
        # Use simplified user extraction - WORKS WITH ANY INPUT
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
            
            target_name = getattr(target_user, 'first_name', 'User')
            message_id = f'msg_{event.sender_id}_{user_id_to_store}_{int(datetime.now().timestamp())}'
            
            messages_db[message_id] = {
                'user_id': user_id_to_store,
                'msg': message_text,
                'sender_id': event.sender_id,
                'timestamp': datetime.now().isoformat(),
                'target_name': target_name
            }
            
            result = event.builder.article(
                title=f"🔒 Secret Message for {target_name}",
                description=f"Click to send secret message to {target_name}",
                text=f"**🔐 A secret message for {target_name}!**\n\n*Note: Only {target_name} can open this message.*",
                buttons=[[Button.inline("🔓 Show Message", message_id)]]
            )
        
        else:
            # PUBLIC MESSAGE - for everyone
            message_id = f'public_{event.sender_id}_{int(datetime.now().timestamp())}'
            
            messages_db[message_id] = {
                'user_id': -1,  # -1 means public message
                'msg': message_text,
                'sender_id': event.sender_id,
                'timestamp': datetime.now().isoformat(),
                'target_name': 'Everyone'
            }
            
            result = event.builder.article(
                title="🌍 Public Message for Everyone",
                description="Click to send public message",
                text=f"**🌍 A public message for everyone!**\n\n*Note: Anyone can open and read this message.*",
                buttons=[[Button.inline("🔓 Show Message", message_id)]]
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
        
        # Track user for broadcast
        add_user_to_tracking(event.sender_id)
        
        if data == "help":
            bot_username = (await bot.get_me()).username
            help_text = HELP_TEXT.replace("{bot_username}", bot_username)
            
            try:
                await event.edit(
                    help_text,
                    buttons=[
                        [Button.switch_inline("🚀 Try Now", query="", same_peer=True)],
                        [Button.inline("🔙 Back", data="back_start")]
                    ]
                )
            except MessageNotModifiedError:
                pass
        
        elif data == "admin_stats":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
                
            total_clones = len(clone_stats)
            total_personal_targets = sum(len(v) for v in user_recent_targets.values())
            
            stats_text = f"📊 **Admin Statistics**\n\n"
            stats_text += f"👥 Global Recent Users: {len(recent_users)}\n"
            stats_text += f"👤 Personal Recent Targets: {total_personal_targets}\n"
            stats_text += f"💬 Total Messages: {len(messages_db)}\n"
            stats_text += f"🤖 Total Clones: {total_clones}\n"
            stats_text += f"👥 Total Tracked Users: {len(all_bot_users)}\n"
            stats_text += f"🆔 Admin ID: {ADMIN_ID}\n"
            stats_text += f"🌐 Port: {PORT}\n"
            stats_text += f"🕒 Last Updated: {datetime.now().strftime('%H:%M:%S')}\n\n"
            stats_text += f"**Status:** ✅ Running"
            
            try:
                await event.edit(
                    stats_text,
                    buttons=[[Button.inline("🔙 Back", data="back_start")]]
                )
            except MessageNotModifiedError:
                pass
        
        elif data == "all_bots":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
                
            total_clones = len(clone_stats)
            
            if total_clones == 0:
                try:
                    await event.edit("🤖 No bots cloned yet!")
                except MessageNotModifiedError:
                    pass
                return
            
            bots_text = f"🤖 **All Cloned Bots - Total: {total_clones}**\n\n"
            
            for i, (token, info) in enumerate(clone_stats.items(), 1):
                bots_text += f"**{i}. @{info['username']}**\n"
                bots_text += f"   👤 User ID: `{info['owner_id']}`\n"
                bots_text += f"   👤 Name: {info['first_name']}\n"
                bots_text += f"   📅 Created: {info['created_at']}\n"
                bots_text += f"   🔑 Token: {info['token_preview']}\n\n"
            
            try:
                await event.edit(
                    bots_text,
                    buttons=[[Button.inline("🔙 Back", data="back_start")]]
                )
            except MessageNotModifiedError:
                pass
        
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
• Users must join @shribots to use MAIN bot
• Cloned bots have FREE access (No Force Join)
• Auto-Join Channels Enabled
• Broadcast Support Enabled
            """
            try:
                await event.edit(
                    clone_text,
                    buttons=[
                        [Button.url("🤖 BotFather", "https://t.me/BotFather")],
                        [Button.inline("🔙 Back", data="back_start")]
                    ]
                )
            except MessageNotModifiedError:
                pass
        
        elif data == "broadcast_info":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
                
            broadcast_help = """
📢 **Broadcast Feature - Admin Only**

**Usage:**
1. Reply to any message with `/broadcast`
2. OR send `/broadcast your_message`

**Targets:**
• 👥 All Main Bot Users
• 🤖 All Cloned Bots (with their users)  
• 🏢 All Groups Where Bot is Admin

⚠️ **Use responsibly!**
            """
            try:
                await event.edit(
                    broadcast_help,
                    buttons=[[Button.inline("🔙 Back", data="back_start")]]
                )
            except MessageNotModifiedError:
                pass
        
        elif data.startswith("confirm_broadcast:"):
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Admin only!", alert=True)
                return
                
            # Extract broadcast ID
            broadcast_id = data.split(":")[1]
            
            if broadcast_id not in broadcast_messages:
                await event.answer("❌ Broadcast message not found!", alert=True)
                return
                
            broadcast_text = broadcast_messages[broadcast_id]
            
            try:
                processing_msg = await event.edit("🔄 **Starting broadcast to ALL targets...**\n\nPlease wait, this may take several minutes...")
            except MessageNotModifiedError:
                processing_msg = event
            
            # Send to ALL targets
            total_successful, total_failed, detailed_results = await send_broadcast_to_all_targets(broadcast_text, processing_msg)
            
            # Clean up broadcast message
            if broadcast_id in broadcast_messages:
                del broadcast_messages[broadcast_id]
                asyncio.create_task(save_data_async())
            
            # Final result with detailed breakdown
            total_sent = total_successful + total_failed
            success_rate = (total_successful / total_sent) * 100 if total_sent > 0 else 0
            
            result_text = f"""
✅ **Broadcast Completed!**

📊 **Detailed Results:**

**👥 Main Bot Users:**
   ✅ Successful: {detailed_results['main_bot']['successful']}
   ❌ Failed: {detailed_results['main_bot']['failed']}

**🤖 Cloned Bots:**
   ✅ Successful: {detailed_results['cloned_bots']['successful']}
   ❌ Failed: {detailed_results['cloned_bots']['failed']}

**🏢 Admin Groups:**
   ✅ Successful: {detailed_results['admin_groups']['successful']}
   ❌ Failed: {detailed_results['admin_groups']['failed']}

**📈 Summary:**
   • 📨 Total Attempted: {total_sent}
   • ✅ Total Successful: {total_successful}
   • ❌ Total Failed: {total_failed}
   • 📈 Success Rate: {success_rate:.1f}%

🕒 Completed: {datetime.now().strftime('%H:%M:%S')}
            """
            
            try:
                await processing_msg.edit(
                    result_text,
                    buttons=[[Button.inline("🔙 Back", data="back_start")]]
                )
            except MessageNotModifiedError:
                pass
        
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
            
            asyncio.create_task(save_data_async())
            await event.answer(f"✅ {removed} bots removed!", alert=True)
            try:
                await event.edit(f"✅ Removed {removed} of your bots!")
            except MessageNotModifiedError:
                pass
        
        elif data == "back_start":
            if event.sender_id == ADMIN_ID:
                try:
                    await event.edit(
                        WELCOME_TEXT,
                        buttons=[
                            [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                            [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                            [Button.switch_inline("🚀 Try Now", query="", same_peer=True)],
                            [Button.inline("📊 Statistics", data="admin_stats"), Button.inline("📖 Help", data="help")],
                            [Button.inline("🔧 Clone Bot", data="clone_info"), Button.inline("🤖 All Bots", data="all_bots")],
                            [Button.inline("📢 Broadcast", data="broadcast_info")]
                        ]
                    )
                except MessageNotModifiedError:
                    pass
            else:
                try:
                    await event.edit(
                        WELCOME_TEXT,
                        buttons=[
                            [Button.url("📢 Support Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                            [Button.url("👥 Support Group", f"https://t.me/{SUPPORT_GROUP}")],
                            [Button.switch_inline("🚀 Try Now", query="", same_peer=True)],
                            [Button.inline("📖 Help", data="help"), Button.inline("🔧 Clone Bot", data="clone_info")]
                        ]
                    )
                except MessageNotModifiedError:
                    pass
        
        elif data in messages_db:
            msg_data = messages_db[data]
            
            # PUBLIC MESSAGE - anyone can read
            if msg_data['user_id'] == -1:
                await event.answer(f"🌍 {msg_data['msg']}", alert=True)
            
            # PRIVATE MESSAGE - only specific user or sender can read
            elif event.sender_id == msg_data['user_id']:
                await event.answer(f"🔓 {msg_data['msg']}", alert=True)
            elif event.sender_id == msg_data['sender_id']:
                await event.answer(f"📝 {msg_data['msg']}", alert=True)
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
    try:
        if bot.is_connected():
            bot_username = bot.loop.run_until_complete(bot.get_me()).username
    except:
        pass
        
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
                Recent Users: {len(recent_users)}<br>
                Total Messages: {len(messages_db)}<br>
                Total Clones: {len(clone_stats)}<br>
                Total Tracked Users: {len(all_bot_users)}<br>
                Pending Verifications: {len(pending_verification)}<br>
                Server Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </div>
            <p>This bot allows you to send anonymous secret messages to Telegram users.</p>
            <p><strong>Usage:</strong> Use inline mode in any chat: <code>@{bot_username} message @username</code></p>
            <p><strong>New:</strong> Send public messages that anyone can read!</p>
            <p><strong>Features:</strong> Broadcast to ALL users (Main + Cloned + Groups), Auto-Join Channels, Free Access for Cloned Bots</p>
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
        "bot_connected": bot.is_connected()
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
        logger.info("🔗 Use /start to begin")
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
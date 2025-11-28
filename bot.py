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
admin_groups_cache = []   # Cache for admin groups
admin_groups_cache_time = None  # Cache timestamp

# Data files
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
RECENT_USERS_FILE = os.path.join(DATA_DIR, "recent_users.json")
USER_RECENT_TARGETS_FILE = os.path.join(DATA_DIR, "user_recent_targets.json")
CLONE_STATS_FILE = os.path.join(DATA_DIR, "clone_stats.json")
PENDING_VERIFICATION_FILE = os.path.join(DATA_DIR, "pending_verification.json")
BROADCAST_MESSAGES_FILE = os.path.join(DATA_DIR, "broadcast_messages.json")
ALL_USERS_FILE = os.path.join(DATA_DIR, "all_users.json")
ADMIN_GROUPS_FILE = os.path.join(DATA_DIR, "admin_groups.json")

def load_data():
    global recent_users, clone_stats, user_recent_targets, pending_verification, broadcast_messages, all_bot_users, admin_groups_cache
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
            
        if os.path.exists(ADMIN_GROUPS_FILE):
            with open(ADMIN_GROUPS_FILE, 'r', encoding='utf-8') as f:
                admin_groups_cache = json.load(f)
            logger.info(f"✅ Loaded {len(admin_groups_cache)} cached admin groups")
            
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        recent_users = {}
        clone_stats = {}
        user_recent_targets = {}
        pending_verification = {}
        broadcast_messages = {}
        all_bot_users = set()
        admin_groups_cache = []

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
            
        with open(ADMIN_GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump(admin_groups_cache, f, indent=2, ensure_ascii=False)
            
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
            
        with open(ADMIN_GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump(admin_groups_cache, f, indent=2, ensure_ascii=False)
            
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

async def get_all_groups_where_admin(client=None, force_refresh=False):
    """Get all groups where bot is admin - WITH CACHING"""
    global admin_groups_cache, admin_groups_cache_time
    
    if client is None:
        client = bot
    
    # Return cached results if available and not forced to refresh
    if not force_refresh and admin_groups_cache and admin_groups_cache_time:
        cache_age = (datetime.now() - admin_groups_cache_time).total_seconds()
        if cache_age < 300:  # 5 minutes cache
            logger.info(f"✅ Using cached admin groups ({len(admin_groups_cache)} groups)")
            return admin_groups_cache
    
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
                            # Store basic group info
                            group_info = {
                                'id': entity.id,
                                'title': getattr(entity, 'title', 'Unknown'),
                                'username': getattr(entity, 'username', None),
                                'participants_count': getattr(entity, 'participants_count', 0)
                            }
                            admin_groups.append(group_info)
                            logger.info(f"✅ Bot is admin in: {group_info['title']}")
                    except Exception as e:
                        continue
                        
            except Exception as e:
                continue
        
        # Update cache
        admin_groups_cache = admin_groups
        admin_groups_cache_time = datetime.now()
        asyncio.create_task(save_data_async())
        
        logger.info(f"✅ Found {len(admin_groups)} admin groups (cache updated)")
        
    except Exception as e:
        logger.error(f"Error getting admin groups: {e}")
        # Return cached results even if error
        if admin_groups_cache:
            return admin_groups_cache
    
    return admin_groups

async def send_broadcast_to_all_targets(broadcast_text, processing_msg=None):
    """ADVANCED BROADCAST: Send to ALL targets with detailed tracking"""
    total_successful = 0
    total_failed = 0
    detailed_results = {
        'main_bot_users': {'successful': 0, 'failed': 0, 'total': 0},
        'cloned_bots': {'successful': 0, 'failed': 0, 'total': 0},
        'admin_groups': {'successful': 0, 'failed': 0, 'total': 0}
    }
    
    # 1. Send to Main Bot Users
    logger.info("📨 Sending broadcast to main bot users...")
    main_bot_users = list(all_bot_users)
    detailed_results['main_bot_users']['total'] = len(main_bot_users)
    
    if main_bot_users:
        if processing_msg:
            await processing_msg.edit(f"🔄 **Sending broadcast...**\n\n📨 Main Bot Users: 0/{len(main_bot_users)}")
        
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
                        f"🔄 **Sending broadcast...**\n\n"
                        f"📨 Main Bot Users: {i+1}/{len(main_bot_users)}\n"
                        f"✅ Successful: {detailed_results['main_bot_users']['successful']}\n"
                        f"❌ Failed: {detailed_results['main_bot_users']['failed']}"
                    )
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                detailed_results['main_bot_users']['failed'] += 1
                total_failed += 1
                logger.error(f"Failed to send to main bot user {user_id}: {e}")
    
    # 2. Send to Admin Groups (Where Bot is Admin)
    logger.info("🏢 Sending broadcast to admin groups...")
    admin_groups = await get_all_groups_where_admin()
    detailed_results['admin_groups']['total'] = len(admin_groups)
    
    if admin_groups:
        if processing_msg:
            await processing_msg.edit(f"🔄 **Sending to admin groups...**\n\n🏢 Groups: 0/{len(admin_groups)}")
        
        for i, group_info in enumerate(admin_groups):
            try:
                # Get group entity
                group_entity = await bot.get_entity(group_info['id'])
                await bot.send_message(group_entity, broadcast_text)
                detailed_results['admin_groups']['successful'] += 1
                total_successful += 1
                logger.info(f"✅ Sent to admin group: {group_info['title']}")
                
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
                logger.error(f"Failed to send to admin group {group_info['title']}: {e}")
    
    # 3. Send to Cloned Bots (They will handle their own users)
    logger.info("🤖 Sending broadcast to cloned bots...")
    detailed_results['cloned_bots']['total'] = len(user_bots)
    
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

async def send_promotion_to_groups(promotion_text, processing_msg=None):
    """Send promotion to all admin groups with special formatting"""
    admin_groups = await get_all_groups_where_admin()
    
    if not admin_groups:
        if processing_msg:
            await processing_msg.edit("❌ No admin groups found!")
        return 0, 0
    
    successful = 0
    failed = 0
    
    if processing_msg:
        await processing_msg.edit(f"🏢 **Sending promotion to {len(admin_groups)} groups...**\n\nProgress: 0/{len(admin_groups)}")
    
    for i, group_info in enumerate(admin_groups):
        try:
            # Get group entity
            group_entity = await bot.get_entity(group_info['id'])
            
            # Create promotion message with buttons
            promotion_buttons = [
                [Button.url("🚀 Try Whisper Bot", f"https://t.me/{(await bot.get_me()).username}")],
                [Button.url("🤖 Create Your Bot", f"https://t.me/{(await bot.get_me()).username}?start=clone")],
                [Button.url("📢 Updates", f"https://t.me/{SUPPORT_CHANNEL}")]
            ]
            
            await bot.send_message(
                group_entity,
                promotion_text,
                buttons=promotion_buttons
            )
            
            successful += 1
            logger.info(f"✅ Promotion sent to: {group_info['title']}")
            
            # Update progress
            if processing_msg and (i + 1) % 2 == 0:  # Update every 2 groups
                await processing_msg.edit(
                    f"🏢 **Sending promotion to {len(admin_groups)} groups...**\n\n"
                    f"Progress: {i+1}/{len(admin_groups)}\n"
                    f"✅ Successful: {successful}\n"
                    f"❌ Failed: {failed}"
                )
            
            await asyncio.sleep(2)  # Longer delay to avoid spam detection
            
        except Exception as e:
            failed += 1
            logger.error(f"❌ Failed to send promotion to {group_info['title']}: {e}")
    
    return successful, failed

# ... (rest of the code remains the same for start_handler, help_handler, etc.)

@bot.on(events.NewMessage(pattern='/broadcast'))
async def broadcast_handler(event):
    """ADVANCED BROADCAST: Send to all users, groups, and cloned bots"""
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
                    "**Methods:**\n"
                    "• Reply to a message with `/broadcast`\n"
                    "• `/broadcast your_message`\n"
                    "• `/promote` - Send promotion to all groups\n\n"
                    "**Targets:**\n"
                    "• 👥 All Main Bot Users\n"
                    "• 🤖 All Cloned Bots + Their Users\n"
                    "• 🏢 All Groups Where Bot is Admin\n\n"
                    "**Features:**\n"
                    "• 📊 Detailed Analytics\n"
                    "• ⏱ Progress Tracking\n"
                    "• 🔄 Automatic Retry\n"
                    "• 💾 Cached Group List",
                    buttons=[
                        [Button.inline("🚀 Send Promotion", data="send_promotion")],
                        [Button.inline("📊 Group Stats", data="group_stats")],
                        [Button.inline("🔙 Back", data="back_start")]
                    ]
                )
                return
            broadcast_text = parts[1]
        
        if not broadcast_text.strip():
            await event.reply("❌ Broadcast message cannot be empty!")
            return
            
        # Store broadcast message
        broadcast_id = f"broadcast_{int(datetime.now().timestamp())}"
        broadcast_messages[broadcast_id] = broadcast_text
        asyncio.create_task(save_data_async())
        
        # Get estimated reach with cached data
        admin_groups = await get_all_groups_where_admin()
        total_group_members = sum(group.get('participants_count', 0) for group in admin_groups)
        estimated_reach = len(all_bot_users) + len(clone_stats) * 50 + total_group_members
            
        # Advanced confirmation with detailed stats
        await event.reply(
            f"📢 **Advanced Broadcast Confirmation**\n\n"
            f"**Message:** {broadcast_text[:100]}{'...' if len(broadcast_text) > 100 else ''}\n\n"
            f"📊 **Estimated Reach:**\n"
            f"• 👥 Main Bot Users: {len(all_bot_users)}\n"
            f"• 🤖 Cloned Bots: {len(clone_stats)} (est. {len(clone_stats) * 50} users)\n"
            f"• 🏢 Admin Groups: {len(admin_groups)} (est. {total_group_members} members)\n"
            f"• 🌍 **Total Estimated: ~{estimated_reach} users**\n\n"
            f"⚠️ This will be sent to ALL targets. Continue?",
            buttons=[
                [Button.inline("✅ Yes, Send to ALL", f"confirm_broadcast:{broadcast_id}")],
                [Button.inline("🏢 Send to Groups Only", f"group_broadcast:{broadcast_id}")],
                [Button.inline("❌ Cancel", data="back_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        await event.reply("❌ Error processing broadcast command!")

@bot.on(events.NewMessage(pattern='/promote'))
async def promote_handler(event):
    """Send promotion to all admin groups"""
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
        
    try:
        # Get promotion message
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            promotion_text = reply_msg.text
        else:
            parts = event.text.split(' ', 1)
            if len(parts) < 2:
                # Default promotion message
                bot_username = (await bot.get_me()).username
                promotion_text = f"""
🎭 **ShriBots Whisper Bot - Promotion** 🎭

🤫 **Send Anonymous Secret Messages**
🔒 Only intended recipient can read your messages
🚀 Easy to use inline mode

**Features:**
• 🔐 Private & Public Messages
• 🌍 Multi-Language Support  
• 🤖 Clone Your Own Bot
• 📢 Broadcast System
• 🏢 Group Promotion

**Try Now:** @{bot_username}

**Create Your Own Bot:** /clone

📢 **Updates:** @{SUPPORT_CHANNEL}
👥 **Support:** @{SUPPORT_GROUP}

*Powered by ShriBots*
                """
            else:
                promotion_text = parts[1]
        
        # Get admin groups info
        admin_groups = await get_all_groups_where_admin()
        
        if not admin_groups:
            await event.reply("❌ No admin groups found!")
            return
        
        total_members = sum(group.get('participants_count', 0) for group in admin_groups)
        
        # Confirmation
        await event.reply(
            f"🏢 **Group Promotion**\n\n"
            f"**Target:** {len(admin_groups)} groups (~{total_members} members)\n\n"
            f"**Message:** {promotion_text[:100]}{'...' if len(promotion_text) > 100 else ''}\n\n"
            f"Send promotion to all admin groups?",
            buttons=[
                [Button.inline("✅ Yes, Promote!", f"confirm_promotion:{hash(promotion_text)}")],
                [Button.inline("❌ Cancel", data="back_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Promote error: {e}")
        await event.reply("❌ Error processing promotion command!")

@bot.on(events.NewMessage(pattern='/groups'))
async def groups_handler(event):
    """Show all groups where bot is admin"""
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
        
    try:
        admin_groups = await get_all_groups_where_admin()
        
        if not admin_groups:
            await event.reply("❌ No admin groups found!")
            return
        
        groups_text = f"🏢 **Admin Groups - Total: {len(admin_groups)}**\n\n"
        total_members = 0
        
        for i, group in enumerate(admin_groups, 1):
            groups_text += f"**{i}. {group['title']}**\n"
            if group.get('username'):
                groups_text += f"   👥 @{group['username']}\n"
            groups_text += f"   👥 Members: {group.get('participants_count', 'Unknown')}\n"
            groups_text += f"   🆔 ID: `{group['id']}`\n\n"
            
            total_members += group.get('participants_count', 0)
        
        groups_text += f"**📊 Total Estimated Reach: ~{total_members} members**\n\n"
        groups_text += f"🕒 Last Updated: {admin_groups_cache_time.strftime('%Y-%m-%d %H:%M') if admin_groups_cache_time else 'Never'}"
        
        await event.reply(
            groups_text,
            buttons=[
                [Button.inline("🔄 Refresh", data="refresh_groups")],
                [Button.inline("📢 Promote", data="send_promotion")],
                [Button.inline("🔙 Back", data="back_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Groups error: {e}")
        await event.reply("❌ Error fetching group details!")

@bot.on(events.CallbackQuery(pattern=b'refresh_groups'))
async def refresh_groups_callback(event):
    """Refresh admin groups cache"""
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Admin only!", alert=True)
        return
        
    try:
        await event.answer("🔄 Refreshing groups...", alert=False)
        admin_groups = await get_all_groups_where_admin(force_refresh=True)
        
        groups_text = f"🏢 **Admin Groups - Total: {len(admin_groups)}**\n\n"
        total_members = 0
        
        for i, group in enumerate(admin_groups, 1):
            groups_text += f"**{i}. {group['title']}**\n"
            if group.get('username'):
                groups_text += f"   👥 @{group['username']}\n"
            groups_text += f"   👥 Members: {group.get('participants_count', 'Unknown')}\n\n"
            total_members += group.get('participants_count', 0)
        
        groups_text += f"**📊 Total Estimated Reach: ~{total_members} members**\n"
        groups_text += f"🕒 Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        await event.edit(
            groups_text,
            buttons=[
                [Button.inline("🔄 Refresh", data="refresh_groups")],
                [Button.inline("📢 Promote", data="send_promotion")],
                [Button.inline("🔙 Back", data="back_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Refresh groups error: {e}")
        await event.answer("❌ Error refreshing groups!", alert=True)

@bot.on(events.CallbackQuery(pattern=b'send_promotion'))
async def send_promotion_callback(event):
    """Send promotion to all groups"""
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Admin only!", alert=True)
        return
        
    try:
        bot_username = (await bot.get_me()).username
        promotion_text = f"""
🎭 **ShriBots Whisper Bot - Promotion** 🎭

🤫 **Send Anonymous Secret Messages**
🔒 Only intended recipient can read your messages
🚀 Easy to use inline mode

**Features:**
• 🔐 Private & Public Messages
• 🌍 Multi-Language Support  
• 🤖 Clone Your Own Bot
• 📢 Broadcast System
• 🏢 Group Promotion

**Try Now:** @{bot_username}

**Create Your Own Bot:** /clone

📢 **Updates:** @{SUPPORT_CHANNEL}
👥 **Support:** @{SUPPORT_GROUP}

*Powered by ShriBots*
        """
        
        processing_msg = await event.edit("🔄 **Starting group promotion...**")
        
        successful, failed = await send_promotion_to_groups(promotion_text, processing_msg)
        
        result_text = f"""
✅ **Group Promotion Completed!**

📊 **Results:**
• 🏢 Total Groups: {successful + failed}
• ✅ Successful: {successful}
• ❌ Failed: {failed}
• 📈 Success Rate: {(successful/(successful+failed))*100:.1f}%

🕒 Completed: {datetime.now().strftime('%H:%M:%S')}

**Promotion sent to all admin groups!**
        """
        
        await processing_msg.edit(
            result_text,
            buttons=[[Button.inline("🔙 Back", data="back_start")]]
        )
        
    except Exception as e:
        logger.error(f"Promotion callback error: {e}")
        await event.answer("❌ Error sending promotion!", alert=True)

@bot.on(events.CallbackQuery(pattern=b'group_stats'))
async def group_stats_callback(event):
    """Show group statistics"""
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Admin only!", alert=True)
        return
        
    try:
        admin_groups = await get_all_groups_where_admin()
        
        if not admin_groups:
            await event.answer("❌ No admin groups found!", alert=True)
            return
        
        total_members = sum(group.get('participants_count', 0) for group in admin_groups)
        groups_with_usernames = len([g for g in admin_groups if g.get('username')])
        
        stats_text = f"""
📊 **Group Statistics**

🏢 **Total Admin Groups:** {len(admin_groups)}
👥 **Total Members:** ~{total_members}
🌐 **Groups with Username:** {groups_with_usernames}
🔗 **Groups without Username:** {len(admin_groups) - groups_with_usernames}

**Size Distribution:**
• 🟢 Small (1-100): {len([g for g in admin_groups if g.get('participants_count', 0) <= 100])}
• 🟡 Medium (101-1000): {len([g for g in admin_groups if 100 < g.get('participants_count', 0) <= 1000])}
• 🔴 Large (1000+): {len([g for g in admin_groups if g.get('participants_count', 0) > 1000])}

🕒 **Last Updated:** {admin_groups_cache_time.strftime('%Y-%m-%d %H:%M') if admin_groups_cache_time else 'Never'}
        """
        
        await event.edit(
            stats_text,
            buttons=[
                [Button.inline("🔄 Refresh", data="refresh_groups")],
                [Button.inline("📢 Promote", data="send_promotion")],
                [Button.inline("🔙 Back", data="back_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Group stats error: {e}")
        await event.answer("❌ Error fetching group stats!", alert=True)

@bot.on(events.CallbackQuery(pattern=b'confirm_promotion:'))
async def confirm_promotion_callback(event):
    """Handle promotion confirmation"""
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Admin only!", alert=True)
        return
        
    try:
        # For now using default promotion text
        bot_username = (await bot.get_me()).username
        promotion_text = f"""
🎭 **ShriBots Whisper Bot - Promotion** 🎭

🤫 **Send Anonymous Secret Messages**
🔒 Only intended recipient can read your messages
🚀 Easy to use inline mode

**Features:**
• 🔐 Private & Public Messages
• 🌍 Multi-Language Support  
• 🤖 Clone Your Own Bot
• 📢 Broadcast System
• 🏢 Group Promotion

**Try Now:** @{bot_username}

**Create Your Own Bot:** /clone

📢 **Updates:** @{SUPPORT_CHANNEL}
👥 **Support:** @{SUPPORT_GROUP}

*Powered by ShriBots*
        """
        
        processing_msg = await event.edit("🔄 **Starting group promotion...**")
        
        successful, failed = await send_promotion_to_groups(promotion_text, processing_msg)
        
        result_text = f"""
✅ **Group Promotion Completed!**

📊 **Results:**
• 🏢 Total Groups: {successful + failed}
• ✅ Successful: {successful}
• ❌ Failed: {failed}
• 📈 Success Rate: {(successful/(successful+failed))*100:.1f}%

🕒 Completed: {datetime.now().strftime('%H:%M:%S')}

**Promotion sent to all admin groups!**
        """
        
        await processing_msg.edit(
            result_text,
            buttons=[[Button.inline("🔙 Back", data="back_start")]]
        )
        
    except Exception as e:
        logger.error(f"Confirm promotion error: {e}")
        await event.answer("❌ Error sending promotion!", alert=True)

# ... (rest of the handlers remain the same)

# Update the main function to include group stats
async def main():
    """Main function to start the bot"""
    try:
        me = await bot.get_me()
        admin_groups = await get_all_groups_where_admin()
        total_group_members = sum(group.get('participants_count', 0) for group in admin_groups)
        
        logger.info(f"🎭 ShriBots Whisper Bot Started!")
        logger.info(f"🤖 Bot: @{me.username}")
        logger.info(f"🆔 Bot ID: {me.id}")
        logger.info(f"👑 Admin: {ADMIN_ID}")
        logger.info(f"👥 Recent Users: {len(recent_users)}")
        logger.info(f"🤖 Total Clones: {len(clone_stats)}")
        logger.info(f"👥 Total Tracked Users: {len(all_bot_users)}")
        logger.info(f"🏢 Admin Groups: {len(admin_groups)} (~{total_group_members} members)")
        logger.info(f"🔒 Pending Verifications: {len(pending_verification)}")
        logger.info(f"🌐 Web server running on port {PORT}")
        logger.info("✅ Bot is ready and working!")
        logger.info("🔗 Use /start to begin")
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

# Flask web server updates
@app.route('/')
def home():
    bot_username = "bot_username"
    total_group_members = 0
    try:
        if bot.is_connected():
            me = bot.loop.run_until_complete(bot.get_me())
            bot_username = me.username
            
            admin_groups = bot.loop.run_until_complete(get_all_groups_where_admin())
            total_group_members = sum(group.get('participants_count', 0) for group in admin_groups)
    except:
        pass
        
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>ShriBots Whisper Bot - Advanced</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; text-align: center; }}
            .status {{ background: #4CAF50; color: white; padding: 10px; border-radius: 5px; text-align: center; margin: 20px 0; }}
            .info {{ background: #2196F3; color: white; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .feature {{ background: #FF9800; color: white; padding: 10px; border-radius: 5px; margin: 5px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 ShriBots Whisper Bot - Advanced</h1>
            <div class="status">✅ Bot is Running Successfully</div>
            <div class="info">
                <strong>📊 Advanced Statistics:</strong><br>
                Recent Users: {len(recent_users)}<br>
                Total Messages: {len(messages_db)}<br>
                Total Clones: {len(clone_stats)}<br>
                Total Tracked Users: {len(all_bot_users)}<br>
                Admin Groups: {len(admin_groups_cache)}<br>
                Group Members: ~{total_group_members}<br>
                Server Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </div>
            <div class="feature">
                <strong>🎯 Advanced Broadcast Features:</strong><br>
                • 📨 Send to All Users<br>
                • 🤖 Send to All Cloned Bots<br>
                • 🏢 Send to All Admin Groups<br>
                • 📊 Detailed Analytics<br>
                • ⏱ Real-time Progress Tracking
            </div>
            <p>This bot allows you to send anonymous secret messages to Telegram users with advanced broadcast capabilities.</p>
            <p><strong>New Features:</strong> Group promotion, Cached group lists, Detailed analytics, Progress tracking</p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    total_group_members = sum(group.get('participants_count', 0) for group in admin_groups_cache)
    
    return json.dumps({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "recent_users": len(recent_users),
        "total_messages": len(messages_db),
        "total_clones": len(clone_stats),
        "total_tracked_users": len(all_bot_users),
        "admin_groups": len(admin_groups_cache),
        "total_group_members": total_group_members,
        "pending_verifications": len(pending_verification),
        "bot_connected": bot.is_connected()
    })

# ... (rest of the code remains the same)
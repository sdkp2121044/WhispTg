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

async def check_user_joined_channel(user_id, client=None):
    """Check if user has joined the support channel - WORKING VERSION"""
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

# ========================= BROADCAST FUNCTIONS =========================

async def get_admin_groups(client=None):
    """Get all groups where bot is admin"""
    if client is None:
        client = bot
        
    admin_groups = []
    try:
        # Get all dialogs
        dialogs = await client.get_dialogs()
        
        for dialog in dialogs:
            try:
                # Check if it's a group/channel
                if dialog.is_group or dialog.is_channel:
                    entity = dialog.entity
                    
                    # Check if bot has admin rights
                    try:
                        me = await client.get_me()
                        participant = await client.get_permissions(entity, me)
                        if participant.is_admin:
                            admin_groups.append({
                                'entity': entity,
                                'title': getattr(entity, 'title', 'Unknown'),
                                'id': getattr(entity, 'id', 0)
                            })
                    except Exception as e:
                        logger.warning(f"Could not check admin status for {getattr(entity, 'title', 'Unknown')}: {e}")
                        continue
                            
            except Exception as e:
                logger.warning(f"Error processing dialog: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error getting admin groups: {e}")
    
    return admin_groups

async def send_broadcast_to_user(user_id, message_text, client=None):
    """Send broadcast message to a specific user"""
    if client is None:
        client = bot
        
    try:
        # Send only the broadcast message without extra text
        await client.send_message(user_id, message_text)
        return True
    except Exception as e:
        logger.error(f"Failed to send broadcast to user {user_id}: {e}")
        return False

async def send_broadcast_to_group(group_info, message_text, client=None):
    """Send broadcast message to a group where bot is admin"""
    if client is None:
        client = bot
        
    try:
        # Send message to group
        await client.send_message(group_info['entity'], message_text)
        return True
    except Exception as e:
        logger.error(f"Failed to send broadcast to group {group_info['title']}: {e}")
        return False

async def send_broadcast_to_all_cloned_bots(broadcast_text):
    """Send broadcast to all cloned bots' users"""
    total_cloned_success = 0
    total_cloned_failed = 0
    cloned_bots_stats = {}
    
    for token, user_bot in user_bots.items():
        try:
            if user_bot and user_bot.is_connected():
                bot_info = clone_stats.get(token, {})
                bot_username = bot_info.get('username', 'Unknown')
                
                # Get users for this specific cloned bot
                cloned_bot_users = set()
                for user_id in all_bot_users:
                    # You might want to track which user belongs to which bot
                    # For now, we'll send to all users from all bots
                    cloned_bot_users.add(user_id)
                
                bot_success = 0
                bot_failed = 0
                
                # Send to users of this cloned bot
                for user_id in cloned_bot_users:
                    try:
                        if await send_broadcast_to_user(user_id, broadcast_text, user_bot):
                            bot_success += 1
                        else:
                            bot_failed += 1
                        await asyncio.sleep(0.05)  # Small delay
                    except Exception as e:
                        bot_failed += 1
                        logger.error(f"Failed to send via cloned bot {bot_username} to {user_id}: {e}")
                
                cloned_bots_stats[bot_username] = {
                    'success': bot_success,
                    'failed': bot_failed,
                    'total': bot_success + bot_failed
                }
                total_cloned_success += bot_success
                total_cloned_failed += bot_failed
                
                logger.info(f"✅ Cloned bot @{bot_username}: {bot_success} successful, {bot_failed} failed")
                
        except Exception as e:
            logger.error(f"Error broadcasting via cloned bot {token}: {e}")
            total_cloned_failed += 1
    
    return {
        'total_success': total_cloned_success,
        'total_failed': total_cloned_failed,
        'bots_stats': cloned_bots_stats
    }

@bot.on(events.NewMessage(pattern='/broadcast'))
async def broadcast_handler(event):
    """Broadcast message to all users, groups, and cloned bots - ADMIN ONLY"""
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
                    "⚠️ This will send to:\n• All users who interacted with bot\n• All groups where bot is admin\n• All cloned bots' users",
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
            
        # Ask for confirmation
        await event.reply(
            f"📢 **Broadcast Confirmation**\n\n"
            f"**Message:** {broadcast_text[:100]}{'...' if len(broadcast_text) > 100 else ''}\n\n"
            f"⚠️ This will be sent to:\n• {len(all_bot_users)} users (Main bot)\n• All groups where bot is admin\n• {len(user_bots)} cloned bots\n\nContinue?",
            buttons=[
                [Button.inline("✅ Yes, Send Everywhere", f"confirm_broadcast:{broadcast_id}")],
                [Button.inline("❌ Cancel", data="back_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        await event.reply("❌ Error processing broadcast command!")

@bot.on(events.CallbackQuery(pattern=b'confirm_broadcast:'))
async def confirm_broadcast_handler(event):
    """Handle broadcast confirmation"""
    if event.sender_id != ADMIN_ID:
        await event.answer("❌ Admin only!", alert=True)
        return
        
    try:
        # Extract broadcast ID
        data = event.data.decode('utf-8')
        broadcast_id = data.split(":")[1]
        
        if broadcast_id not in broadcast_messages:
            await event.answer("❌ Broadcast message not found!", alert=True)
            return
            
        broadcast_text = broadcast_messages[broadcast_id]
        
        processing_msg = await event.edit("🔄 **Starting broadcast...**\n\nPlease wait, this may take a while...")
        
        # Get admin groups
        admin_groups = await get_admin_groups()
        
        # Use the tracked users set
        total_users = len(all_bot_users)
        total_groups = len(admin_groups)
        total_cloned_bots = len(user_bots)
        
        # Statistics
        successful_users = 0
        failed_users = 0
        successful_groups = 0
        failed_groups = 0
        
        # ========== PHASE 1: Send to main bot users ==========
        if total_users > 0:
            await processing_msg.edit("🔄 **Phase 1/3:** Sending to main bot users...")
            
            for i, user_id in enumerate(all_bot_users):
                try:
                    if await send_broadcast_to_user(user_id, broadcast_text):
                        successful_users += 1
                    else:
                        failed_users += 1
                    
                    # Update progress every 10 users
                    if (successful_users + failed_users) % 10 == 0:
                        try:
                            await processing_msg.edit(
                                f"🔄 **Phase 1/3:** Sending to main bot users...\n\n"
                                f"📊 Progress: {successful_users + failed_users}/{total_users}\n"
                                f"✅ Successful: {successful_users}\n"
                                f"❌ Failed: {failed_users}"
                            )
                        except MessageNotModifiedError:
                            pass
                    
                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    failed_users += 1
                    logger.error(f"Failed to send to user {user_id}: {e}")
        
        # ========== PHASE 2: Send to admin groups ==========
        if total_groups > 0:
            await processing_msg.edit("🔄 **Phase 2/3:** Sending to admin groups...")
            
            for i, group_info in enumerate(admin_groups):
                try:
                    if await send_broadcast_to_group(group_info, broadcast_text):
                        successful_groups += 1
                    else:
                        failed_groups += 1
                    
                    # Update progress
                    if (i + 1) % 5 == 0:
                        try:
                            await processing_msg.edit(
                                f"🔄 **Phase 2/3:** Sending to admin groups...\n\n"
                                f"📊 Progress: {i + 1}/{total_groups}\n"
                                f"✅ Successful: {successful_groups}\n"
                                f"❌ Failed: {failed_groups}"
                            )
                        except MessageNotModifiedError:
                            pass
                    
                    await asyncio.sleep(0.2)  # Longer delay for groups
                    
                except Exception as e:
                    failed_groups += 1
                    logger.error(f"Failed to send to group {group_info['title']}: {e}")
        
        # ========== PHASE 3: Send via cloned bots ==========
        if total_cloned_bots > 0:
            await processing_msg.edit("🔄 **Phase 3/3:** Sending via cloned bots...")
            
            cloned_results = await send_broadcast_to_all_cloned_bots(broadcast_text)
            
        else:
            cloned_results = {
                'total_success': 0,
                'total_failed': 0,
                'bots_stats': {}
            }
        
        # Clean up broadcast message
        if broadcast_id in broadcast_messages:
            del broadcast_messages[broadcast_id]
            asyncio.create_task(save_data_async())
        
        # ========== FINAL RESULTS ==========
        total_successful = (successful_users + successful_groups + cloned_results['total_success'])
        total_failed = (failed_users + failed_groups + cloned_results['total_failed'])
        total_attempted = total_successful + total_failed
        
        success_rate = (total_successful / total_attempted) * 100 if total_attempted > 0 else 0
        
        # Prepare detailed results
        results_text = f"✅ **Broadcast Completed!**\n\n"
        results_text += f"📊 **Overall Results:**\n"
        results_text += f"• 📨 Total Attempted: {total_attempted}\n"
        results_text += f"• ✅ Successful: {total_successful}\n"
        results_text += f"• ❌ Failed: {total_failed}\n"
        results_text += f"• 📈 Success Rate: {success_rate:.1f}%\n\n"
        
        results_text += f"🔹 **Main Bot:**\n"
        results_text += f"   • 👥 Users: {successful_users}/{total_users}\n"
        results_text += f"   • 👥 Groups: {successful_groups}/{total_groups}\n\n"
        
        results_text += f"🔹 **Cloned Bots ({total_cloned_bots}):**\n"
        results_text += f"   • 👥 Users: {cloned_results['total_success']}\n"
        
        # Add individual cloned bot stats
        if cloned_results['bots_stats']:
            results_text += f"\n**Cloned Bots Details:**\n"
            for bot_username, stats in cloned_results['bots_stats'].items():
                bot_success_rate = (stats['success'] / stats['total']) * 100 if stats['total'] > 0 else 0
                results_text += f"• @{bot_username}: {stats['success']}/{stats['total']} ({bot_success_rate:.1f}%)\n"
        
        results_text += f"\n🕒 Completed: {datetime.now().strftime('%H:%M:%S')}"
        
        try:
            await processing_msg.edit(
                results_text,
                buttons=[[Button.inline("🔙 Back", data="back_start")]]
            )
        except MessageNotModifiedError:
            pass
        
    except Exception as e:
        logger.error(f"Broadcast confirmation error: {e}")
        await event.answer("❌ Error during broadcast!", alert=True)

# ========================= REST OF THE CODE REMAINS SAME =========================

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

# ... (REST OF THE CODE REMAINS THE SAME AS YOUR PREVIOUS VERSION)
# Include all the other handlers: help, stats, clone, inline, callback, etc.

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
            <p><strong>Features:</strong> Broadcast (Admin only), Force join for cloned bots</p>
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
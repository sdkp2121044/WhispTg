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
API_ID = int(os.getenv('API_ID', ''))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', 10000))

# Import Telethon
try:
    from telethon import TelegramClient, events, Button
    from telethon.errors import MessageNotModifiedError
except ImportError as e:
    logger.error(f"Telethon import error: {e}")
    raise

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
all_bot_users = set()
user_last_targets = {}  # Har user ka last target store karega

# Data files
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
RECENT_USERS_FILE = os.path.join(DATA_DIR, "recent_users.json")
ALL_USERS_FILE = os.path.join(DATA_DIR, "all_users.json")
USER_LAST_TARGETS_FILE = os.path.join(DATA_DIR, "user_last_targets.json")

def load_data():
    global recent_users, all_bot_users, user_last_targets
    try:
        if os.path.exists(RECENT_USERS_FILE):
            with open(RECENT_USERS_FILE, 'r', encoding='utf-8') as f:
                recent_users = json.load(f)
            logger.info(f"✅ Loaded {len(recent_users)} recent users")
            
        if os.path.exists(ALL_USERS_FILE):
            with open(ALL_USERS_FILE, 'r', encoding='utf-8') as f:
                all_bot_users = set(json.load(f))
            logger.info(f"✅ Loaded {len(all_bot_users)} total users")
            
        if os.path.exists(USER_LAST_TARGETS_FILE):
            with open(USER_LAST_TARGETS_FILE, 'r', encoding='utf-8') as f:
                user_last_targets = json.load(f)
            logger.info(f"✅ Loaded last targets for {len(user_last_targets)} users")
            
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        recent_users = {}
        all_bot_users = set()
        user_last_targets = {}

def save_data():
    try:
        with open(RECENT_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(recent_users, f, indent=2, ensure_ascii=False)
            
        with open(ALL_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(all_bot_users), f, indent=2, ensure_ascii=False)
            
        with open(USER_LAST_TARGETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_last_targets, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"❌ Error saving data: {e}")

# Load data on startup
load_data()

WELCOME_TEXT = """
🤫 **Smart Whisper Bot**

✨ **SPECIAL FEATURE:**
Ek baar kisi user ko message bhejne ke baad,
agli baar sirf message likho - user automatic show ho jayega!

🔒 **How to Use:**
1. Pehli baar: `@botusername message @username`
2. Agli baar: Sirf `@botusername message` likho
3. Bot automatically pichle user ko message bhej dega

**Examples:**
• Pehli baar: `@botusername Hello @john`
• Agli baar: `@botusername How are you?` (automatic john ko jayega)

🌍 **Public Message:** Sirf message likho bina username ke
"""

def add_user_to_tracking(user_id):
    """Add user to tracking"""
    try:
        all_bot_users.add(user_id)
        if len(all_bot_users) % 20 == 0:
            asyncio.create_task(save_data_async())
    except Exception as e:
        logger.error(f"Error adding user to tracking: {e}")

def save_user_last_target(user_id, target_user_id, target_username=None, target_first_name=None):
    """Save user's last target for automatic reply"""
    try:
        user_key = str(user_id)
        
        user_last_targets[user_key] = {
            'target_id': target_user_id,
            'username': target_username,
            'first_name': target_first_name,
            'last_used': datetime.now().isoformat()
        }
        
        asyncio.create_task(save_data_async())
        
    except Exception as e:
        logger.error(f"Error saving user last target: {e}")

def get_user_last_target(user_id):
    """Get user's last target"""
    try:
        user_key = str(user_id)
        if user_key in user_last_targets:
            return user_last_targets[user_key]
    except Exception as e:
        logger.error(f"Error getting user last target: {e}")
    return None

def add_to_recent_users(target_user_id, target_username=None, target_first_name=None):
    """Add user to global recent users"""
    try:
        user_key = str(target_user_id)
        
        recent_users[user_key] = {
            'user_id': target_user_id,
            'username': target_username,
            'first_name': target_first_name,
            'last_used': datetime.now().isoformat()
        }
        
        if len(recent_users) > 20:
            oldest_key = min(recent_users.keys(), key=lambda k: recent_users[k]['last_used'])
            del recent_users[oldest_key]
        
    except Exception as e:
        logger.error(f"Error adding to recent users: {e}")

async def save_data_async():
    """Save data asynchronously"""
    try:
        with open(RECENT_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(recent_users, f, indent=2, ensure_ascii=False)
            
        with open(ALL_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(all_bot_users), f, indent=2, ensure_ascii=False)
            
        with open(USER_LAST_TARGETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_last_targets, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"Async save error: {e}")

def get_recent_users_buttons(user_id=None):
    """Get recent users buttons"""
    try:
        # Agar user id diya hai, toh pehle uska last target show karo
        if user_id:
            last_target = get_user_last_target(user_id)
            if last_target:
                buttons = []
                username = last_target.get('username')
                first_name = last_target.get('first_name', 'User')
                
                if username:
                    display_text = f"↪️ Last: @{username}"
                    query_text = f"@{username}"
                else:
                    display_text = f"↪️ Last: {first_name}"
                    query_text = f"{last_target.get('target_id')}"
                
                buttons.append([Button.switch_inline(
                    display_text, 
                    query=query_text,
                    same_peer=True
                )])
                
                # Add other recent users
                if recent_users:
                    sorted_users = sorted(recent_users.items(), 
                                        key=lambda x: x[1].get('last_used', ''), 
                                        reverse=True)
                    
                    for user_key, user_data in sorted_users[:4]:
                        if str(user_data.get('user_id')) != str(last_target.get('target_id')):
                            username2 = user_data.get('username')
                            first_name2 = user_data.get('first_name', 'User')
                            
                            if username2:
                                display_text2 = f"@{username2}"
                                query_text2 = f"@{username2}"
                            else:
                                display_text2 = f"{first_name2}"
                                query_text2 = f"{user_data.get('user_id')}"
                            
                            buttons.append([Button.switch_inline(
                                f"🔒 {display_text2[:12]}" if len(display_text2) > 12 else f"🔒 {display_text2}", 
                                query=query_text2,
                                same_peer=True
                            )])
                
                return buttons
        
        # Agar user ka last target nahi hai, toh global recent users show karo
        if not recent_users:
            return []
        
        sorted_users = sorted(recent_users.items(), 
                            key=lambda x: x[1].get('last_used', ''), 
                            reverse=True)
        
        buttons = []
        for user_key, user_data in sorted_users[:6]:
            username = user_data.get('username')
            first_name = user_data.get('first_name', 'User')
            user_id_val = user_data.get('user_id')
            
            if username:
                display_text = f"@{username}"
                query_text = f"@{username}"
            else:
                display_text = f"{first_name}"
                query_text = f"{user_id_val}"
            
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
    """Check if user is in cooldown"""
    now = datetime.now().timestamp()
    if user_id in user_cooldown:
        if now - user_cooldown[user_id] < 1:
            return True
    user_cooldown[user_id] = now
    return False

# User detection patterns
USER_PATTERNS = [
    (r'@(\w+)$', 'username_end'),
    (r'(\d+)$', 'userid_end'),
    (r'@(\w+)\s+', 'username_middle'),
    (r'(\d+)\s+', 'userid_middle'),
]

async def extract_target_user(text, client, sender_id=None):
    """Extract target user from text with auto-detection"""
    original_text = text.strip()
    
    if not original_text or original_text.isspace():
        return None, original_text, False
    
    # Pehle check karo ki kya user ne username ya ID diya hai
    for pattern, pattern_type in USER_PATTERNS:
        try:
            matches = re.findall(pattern, original_text)
            if matches:
                target_match = matches[0]
                target_clean = target_match.strip('@')
                
                if pattern_type in ['userid_end', 'userid_middle']:
                    try:
                        user_obj = await client.get_entity(int(target_clean))
                        if pattern_type == 'userid_end':
                            message_text = original_text.replace(target_clean, '').strip()
                        else:
                            message_text = original_text.replace(f"{target_clean} ", '').strip()
                        return user_obj, message_text, True
                    except:
                        fake_user = type('obj', (object,), {
                            'id': int(target_clean) if target_clean.isdigit() else -1,
                            'username': None,
                            'first_name': f"User{target_clean}" 
                        })
                        if pattern_type == 'userid_end':
                            message_text = original_text.replace(target_clean, '').strip()
                        else:
                            message_text = original_text.replace(f"{target_clean} ", '').strip()
                        return fake_user, message_text, True
                
                else:
                    try:
                        user_obj = await client.get_entity(target_clean)
                        if pattern_type == 'username_end':
                            message_text = original_text.replace(f"@{target_clean}", '').strip()
                        else:
                            message_text = original_text.replace(f"@{target_clean} ", '').strip()
                        return user_obj, message_text, True
                    except:
                        fake_user = type('obj', (object,), {
                            'id': -1,
                            'username': target_clean,
                            'first_name': f"@{target_clean}" 
                        })
                        if pattern_type == 'username_end':
                            message_text = original_text.replace(f"@{target_clean}", '').strip()
                        else:
                            message_text = original_text.replace(f"@{target_clean} ", '').strip()
                        return fake_user, message_text, True
        except:
            continue
    
    # Agar koi username/ID nahi hai, toh check karo ki kya user ka pichla target hai
    if sender_id:
        last_target = get_user_last_target(sender_id)
        if last_target:
            try:
                # Try to get the user object
                user_obj = await client.get_entity(int(last_target['target_id']))
                return user_obj, original_text, False  # False means auto-detected
            except:
                # Create fake user object
                fake_user = type('obj', (object,), {
                    'id': last_target['target_id'],
                    'username': last_target.get('username'),
                    'first_name': last_target.get('first_name', 'Previous User')
                })
                return fake_user, original_text, False
    
    # Agar na username hai, na pichla target, toh public message hai
    return None, original_text, False

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        logger.info(f"🚀 Start command from user: {event.sender_id}")
        
        add_user_to_tracking(event.sender_id)
        
        # Check if user has a last target
        last_target = get_user_last_target(event.sender_id)
        last_target_text = ""
        if last_target:
            target_name = last_target.get('first_name', 'User')
            last_target_text = f"\n\n🎯 **Your Last Target:** {target_name}\nAb sirf message likhne se automatically {target_name} ko jayega!"
        
        await event.reply(
            WELCOME_TEXT + last_target_text,
            buttons=[
                [Button.switch_inline("🚀 Send Whisper", query="", same_peer=True)],
                [Button.inline("📖 Help", data="help")]
            ]
        )
    except Exception as e:
        logger.error(f"Start error: {e}")
        await event.reply("❌ An error occurred. Please try again.")

@bot.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    try:
        add_user_to_tracking(event.sender_id)
        
        help_text = """
📖 **How to Use Smart Whisper Bot**

**✨ AUTO-DETECT FEATURE:**
1. **First Time:** Send `@botusername message @username`
2. **Next Time:** Just type `@botusername message`
3. Bot will automatically send to your last target!

**📝 Examples:**
• First: `@botusername Hello @john`
• Next: `@botusername How are you?` → Auto to @john
• Change: `@botusername Hi @alice` → Now Alice is new target
• Public: `@botusername Hello all!` → Anyone can read

**🔒 Private Message:** Only mentioned user can read
**🌍 Public Message:** Anyone can read (no username)

**⚡ Quick Tips:**
• Use /start to see your last target
• Recent targets show in inline mode
• No cooldown between messages
        """
        
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

@bot.on(events.InlineQuery)
async def inline_handler(event):
    try:
        add_user_to_tracking(event.sender_id)
        
        if is_cooldown(event.sender_id):
            await event.answer([])
            return
        
        # Get recent buttons with user's last target first
        recent_buttons = get_recent_users_buttons(event.sender_id)
        
        if not event.text or not event.text.strip():
            # Show quick start with last target info
            last_target = get_user_last_target(event.sender_id)
            if last_target:
                target_name = last_target.get('first_name', 'User')
                result_text = f"🎯 **Last Target:** {target_name}\n\nJust type your message and it will auto-send to {target_name}!\n\nOr select another user below:"
            else:
                result_text = "🤫 **Send Secret Messages**\n\nType: `message @username`\nOr just `message` for public\n\n**Tip:** First time add @username, next time just message!"
            
            result = event.builder.article(
                title="🤫 Smart Whisper Bot",
                description="Auto-detects your last target",
                text=result_text,
                buttons=recent_buttons
            )
            await event.answer([result])
            return
        
        text = event.text.strip()
        
        # Extract target with auto-detection
        target_user, message_text, explicit_target = await extract_target_user(text, bot, event.sender_id)
        
        if not message_text:
            result = event.builder.article(
                title="❌ Empty Message",
                description="Please type a message",
                text="❌ Please type a message to send!",
                buttons=[[Button.switch_inline("🔄 Try Again", query=text, same_peer=True)]]
            )
            await event.answer([result])
            return
        
        if len(message_text) > 1000:
            result = event.builder.article(
                title="❌ Message Too Long",
                description="Maximum 1000 characters",
                text="❌ Message too long! Keep under 1000 characters."
            )
            await event.answer([result])
            return
        
        # Determine message type
        if target_user:
            user_id_to_store = target_user.id if hasattr(target_user, 'id') and target_user.id != -1 else -1
            
            # Save to recent users and user's last target
            if user_id_to_store != -1:
                add_to_recent_users(
                    user_id_to_store, 
                    getattr(target_user, 'username', None),
                    getattr(target_user, 'first_name', 'User')
                )
                
                # Save as user's last target
                save_user_last_target(
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
            
            # Add indicator if auto-detected
            auto_text = " (Auto-detected)" if not explicit_target else ""
            
            result = event.builder.article(
                title=f"🔒 To: {target_name}{auto_text}",
                description=f"Click to send to {target_name}",
                text=f"**🔐 Message for {target_name}{auto_text}**\n\nOnly {target_name} can read this.",
                buttons=[[Button.inline("🔓 Send Message", message_id)]]
            )
        
        else:
            # Public message
            message_id = f'public_{event.sender_id}_{int(datetime.now().timestamp())}'
            
            messages_db[message_id] = {
                'user_id': -1,
                'msg': message_text,
                'sender_id': event.sender_id,
                'timestamp': datetime.now().isoformat(),
                'target_name': 'Everyone'
            }
            
            result = event.builder.article(
                title="🌍 Public Message",
                description="Anyone can read",
                text=f"**🌍 Public Message**\n\nAnyone can read this message.",
                buttons=[[Button.inline("🔓 Show Message", message_id)]]
            )
        
        await event.answer([result])
        
    except Exception as e:
        logger.error(f"Inline query error: {e}")
        result = event.builder.article(
            title="❌ Error",
            description="Try again",
            text="❌ An error occurred. Please try again."
        )
        await event.answer([result])

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    try:
        data = event.data.decode('utf-8')
        
        add_user_to_tracking(event.sender_id)
        
        if data == "help":
            help_text = """
📖 **How to Use Smart Whisper Bot**

**✨ AUTO-DETECT FEATURE:**
1. **First Time:** Send `@botusername message @username`
2. **Next Time:** Just type `@botusername message`
3. Bot will automatically send to your last target!

**📝 Examples:**
• First: `@botusername Hello @john`
• Next: `@botusername How are you?` → Auto to @john
• Change: `@botusername Hi @alice` → Now Alice is new target
• Public: `@botusername Hello all!` → Anyone can read

**🔒 Private Message:** Only mentioned user can read
**🌍 Public Message:** Anyone can read (no username)

**⚡ Quick Tips:**
• Use /start to see your last target
• Recent targets show in inline mode
• No cooldown between messages
            """
            
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
        
        elif data == "back_start":
            last_target = get_user_last_target(event.sender_id)
            last_target_text = ""
            if last_target:
                target_name = last_target.get('first_name', 'User')
                last_target_text = f"\n\n🎯 **Your Last Target:** {target_name}\nAb sirf message likhne se automatically {target_name} ko jayega!"
            
            try:
                await event.edit(
                    WELCOME_TEXT + last_target_text,
                    buttons=[
                        [Button.switch_inline("🚀 Send Whisper", query="", same_peer=True)],
                        [Button.inline("📖 Help", data="help")]
                    ]
                )
            except MessageNotModifiedError:
                pass
        
        elif data in messages_db:
            msg_data = messages_db[data]
            
            if msg_data['user_id'] == -1:
                await event.answer(f"🌍 {msg_data['msg']}", alert=True)
            elif event.sender_id == msg_data['user_id']:
                await event.answer(f"🔓 {msg_data['msg']}", alert=True)
            elif event.sender_id == msg_data['sender_id']:
                await event.answer(f"📝 Sent to {msg_data['target_name']}: {msg_data['msg']}", alert=True)
            else:
                await event.answer("🔒 This message is not for you!", alert=True)
        
        else:
            await event.answer("❌ Invalid button!", alert=True)
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await event.answer("❌ An error occurred.", alert=True)

# Flask web server for Render
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
        <title>Smart Whisper Bot</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; text-align: center; }}
            .status {{ background: #4CAF50; color: white; padding: 10px; border-radius: 5px; text-align: center; margin: 20px 0; }}
            .feature {{ background: #FF9800; color: white; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .info {{ background: #2196F3; color: white; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Smart Whisper Bot</h1>
            <div class="status">✅ Bot is Running</div>
            <div class="feature">
                <strong>✨ SPECIAL FEATURE:</strong><br>
                Auto-detects your last target!<br>
                First time: message @username<br>
                Next time: just message (auto-sends)
            </div>
            <div class="info">
                <strong>📊 Statistics:</strong><br>
                Recent Users: {len(recent_users)}<br>
                Total Users: {len(all_bot_users)}<br>
                Active Last Targets: {len(user_last_targets)}<br>
                Server Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </div>
            <p>This bot automatically remembers who you messaged last!</p>
            <p><strong>Bot:</strong> @{bot_username}</p>
            <p><strong>Try:</strong> Type @{bot_username} in any Telegram chat</p>
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
        "total_users": len(all_bot_users),
        "active_last_targets": len(user_last_targets),
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
        logger.info(f"🎭 Smart Whisper Bot Started!")
        logger.info(f"🤖 Bot: @{me.username}")
        logger.info(f"🆔 Bot ID: {me.id}")
        logger.info(f"👥 Recent Users: {len(recent_users)}")
        logger.info(f"👤 Active Last Targets: {len(user_last_targets)}")
        logger.info(f"🌐 Web server running on port {PORT}")
        logger.info("✅ Bot is ready!")
        logger.info("✨ Feature: Auto-detects last target!")
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise

if __name__ == '__main__':
    print("🚀 Starting Smart Whisper Bot...")
    print("✨ Special Feature: Auto-remembers last target!")
    
    try:
        bot.start()
        bot.loop.run_until_complete(main())
        
        print("✅ Bot started successfully!")
        print("🔄 Bot is now running...")
        
        bot.run_until_disconnected()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        print(f"❌ Error: {e}")
    finally:
        print("💾 Saving data...")
        save_data()
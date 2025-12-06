import os
import logging
import re
import json
import asyncio
from datetime import datetime
from telethon import TelegramClient, Button

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CloneSystem:
    def __init__(self, main_bot):
        self.main_bot = main_bot
        self.user_bots = {}  # token: bot_instance
        self.clone_stats = {}  # token: clone_data
        self.user_clone_limit = {}  # user_id: token
        
        # Data files
        self.DATA_DIR = "data"
        os.makedirs(self.DATA_DIR, exist_ok=True)
        self.CLONE_STATS_FILE = os.path.join(self.DATA_DIR, "clone_stats.json")
        self.USER_LIMIT_FILE = os.path.join(self.DATA_DIR, "user_clone_limit.json")
        
        # Load existing data
        self.load_data()
        
        # Start existing cloned bots
        asyncio.create_task(self.start_existing_clones())
    
    def load_data(self):
        """Load clone data from files"""
        try:
            if os.path.exists(self.CLONE_STATS_FILE):
                with open(self.CLONE_STATS_FILE, 'r', encoding='utf-8') as f:
                    self.clone_stats = json.load(f)
                logger.info(f"✅ Loaded {len(self.clone_stats)} clone stats")
            
            if os.path.exists(self.USER_LIMIT_FILE):
                with open(self.USER_LIMIT_FILE, 'r', encoding='utf-8') as f:
                    self.user_clone_limit = json.load(f)
                logger.info(f"✅ Loaded {len(self.user_clone_limit)} user limits")
                
        except Exception as e:
            logger.error(f"❌ Error loading clone data: {e}")
            self.clone_stats = {}
            self.user_clone_limit = {}
    
    def save_data(self):
        """Save clone data to files"""
        try:
            with open(self.CLONE_STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.clone_stats, f, indent=2, ensure_ascii=False)
            
            with open(self.USER_LIMIT_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.user_clone_limit, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"❌ Error saving clone data: {e}")
    
    async def start_existing_clones(self):
        """Start all existing cloned bots"""
        logger.info(f"🔄 Starting {len(self.clone_stats)} cloned bots...")
        
        for token, clone_data in self.clone_stats.items():
            try:
                if token not in self.user_bots:
                    user_id = clone_data.get('owner_id')
                    if user_id:
                        await self.start_cloned_bot(token, user_id, clone_data)
                        logger.info(f"✅ Started cloned bot: {clone_data.get('username', 'Unknown')}")
                        
            except Exception as e:
                logger.error(f"❌ Failed to start cloned bot {token}: {e}")
        
        logger.info(f"✅ All cloned bots started: {len(self.user_bots)} running")
    
    async def start_cloned_bot(self, token, user_id, clone_data=None):
        """Start a cloned bot instance"""
        try:
            # Get API credentials from main bot
            api_id = self.main_bot.api_id
            api_hash = self.main_bot.api_hash
            
            # Create bot instance
            session_name = f"cloned_bot_{user_id}"
            user_bot = TelegramClient(session_name, api_id, api_hash)
            await user_bot.start(bot_token=token)
            
            # Get bot info
            bot_me = await user_bot.get_me()
            
            # Store bot instance
            self.user_bots[token] = user_bot
            
            # Update clone stats if not already present
            if token not in self.clone_stats and clone_data is None:
                self.clone_stats[token] = {
                    'owner_id': user_id,
                    'username': bot_me.username,
                    'bot_id': bot_me.id,
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'token_preview': token[:10] + '...'
                }
            
            # Update user limit
            self.user_clone_limit[str(user_id)] = token
            
            # Save data
            self.save_data()
            
            # Setup basic handlers for cloned bot
            self.setup_cloned_bot_handlers(user_bot, token, user_id)
            
            logger.info(f"✅ Cloned bot started: @{bot_me.username} (Owner: {user_id})")
            return user_bot
            
        except Exception as e:
            logger.error(f"❌ Failed to start cloned bot: {e}")
            raise
    
    def setup_cloned_bot_handlers(self, user_bot, token, owner_id):
        """Setup basic handlers for cloned bot"""
        
        @user_bot.on(events.NewMessage(pattern='/start'))
        async def cloned_start_handler(event):
            try:
                welcome_text = """
╔══════════════════════╗
║     🎭 𝗦𝗛𝗥𝗜𝗕𝗢𝗧𝗦     ║ 𝐂𝐥𝐨𝐧𝐞𝐝 𝐁𝐨𝐭
║    𝗪𝗛𝗜𝗦𝗣𝗘𝗥 𝗕𝗢𝗧    ║  𝐏𝐨𝐰𝐞𝐫𝐞𝐝 𝐁𝐲
╚══════════════════════╝

🤫 Welcome to your Whisper Bot!

🔒 Send anonymous secret messages
🚀 Only intended recipient can read
🎯 Easy to use inline mode

🔧 **Owner Commands:**
• /remove - Remove this bot
• /mybot - Show bot info

Create whispers that only specific users can unlock!
"""
                await event.reply(
                    welcome_text,
                    buttons=[
                        [Button.url("📢 Support", "https://t.me/shribots")],
                        [Button.url("👥 Help", "https://t.me/idxhelp")],
                        [Button.switch_inline("🚀 Try Now", query="")]
                    ]
                )
            except Exception as e:
                logger.error(f"Cloned bot start error: {e}")
        
        @user_bot.on(events.NewMessage(pattern='/mybot'))
        async def mybot_handler(event):
            try:
                if event.sender_id != owner_id:
                    await event.reply("❌ Only bot owner can use this command!")
                    return
                
                bot_me = await user_bot.get_me()
                bot_info = f"""
🤖 **Your Bot Information:**

👤 **Owner:** You
🤖 **Bot:** @{bot_me.username}
🆔 **Bot ID:** `{bot_me.id}`
📅 **Created:** {self.clone_stats.get(token, {}).get('created_at', 'Unknown')}
🔗 **Status:** ✅ Active

💡 **Tip:** Use inline mode in any chat:
`@{bot_me.username} message @username`
"""
                await event.reply(bot_info)
            except Exception as e:
                logger.error(f"Mybot error: {e}")
        
        @user_bot.on(events.NewMessage(pattern='/remove'))
        async def cloned_remove_handler(event):
            try:
                if event.sender_id != owner_id:
                    await event.reply("❌ Only bot owner can remove this bot!")
                    return
                
                # Send removal request to main bot
                await self.main_bot.send_message(
                    owner_id,
                    f"🗑 **Bot Removal Request**\n\n"
                    f"Bot: @{(await user_bot.get_me()).username}\n"
                    f"Please use `/remove` in main bot to confirm removal.",
                    parse_mode='markdown'
                )
                
                await event.reply(
                    "📨 Removal request sent to main bot!\n\n"
                    "Please check your messages from main bot and use `/remove` there.",
                    buttons=[[Button.url("Open Main Bot", f"https://t.me/{(await self.main_bot.get_me()).username}")]]
                )
            except Exception as e:
                logger.error(f"Cloned remove error: {e}")
        
        # Setup inline handler for cloned bot
        @user_bot.on(events.InlineQuery)
        async def cloned_inline_handler(event):
            await self.handle_cloned_inline(event, user_bot)
        
        @user_bot.on(events.CallbackQuery)
        async def cloned_callback_handler(event):
            await self.handle_cloned_callback(event, user_bot, owner_id)
    
    async def handle_cloned_inline(self, event, user_bot):
        """Handle inline queries for cloned bot"""
        try:
            bot_username = (await user_bot.get_me()).username
            
            if not event.text or not event.text.strip():
                result = event.builder.article(
                    title=f"🤫 @{bot_username} - Whisper Bot",
                    description="Send anonymous secret messages",
                    text=f"**Send secret messages with @{bot_username}**\n\n"
                         f"**Format:** `message @username`\n"
                         f"**Example:** `Hello! @username`\n\n"
                         f"🔒 Only they can read!",
                    buttons=[[Button.switch_inline("🚀 Try Now", query="")]]
                )
                await event.answer([result])
                return
            
            text = event.text.strip()
            
            # Simple user detection
            username_match = re.search(r'@([a-zA-Z][a-zA-Z0-9_]{3,30})\b', text)
            userid_match = re.search(r'(\d{8,})\b', text)
            
            if username_match:
                target_user = username_match.group(1)
                message_text = re.sub(r'@' + re.escape(target_user) + r'\b', '', text).strip()
                lookup_target = target_user
            elif userid_match:
                target_user = userid_match.group(1)
                message_text = re.sub(r'\b' + re.escape(target_user) + r'\b', '', text).strip()
                lookup_target = target_user
            else:
                result = event.builder.article(
                    title="❌ Add Recipient",
                    description="Add @username or user ID",
                    text="**Add recipient at end:**\n\n`your_message @username`\nOR\n`your_message 123456789`",
                    buttons=[[Button.switch_inline("🔄 Try Again", query=text)]]
                )
                await event.answer([result])
                return
            
            if not message_text:
                result = event.builder.article(
                    title="❌ Message Required",
                    description="Type a message first",
                    text="**Please type a message!**\n\n**Example:** `Hello! @username`",
                    buttons=[[Button.switch_inline("🔄 Try Again", query=text)]]
                )
                await event.answer([result])
                return
            
            try:
                if lookup_target.isdigit():
                    user_obj = await user_bot.get_entity(int(lookup_target))
                else:
                    user_obj = await user_bot.get_entity(lookup_target)
                
                message_id = f'clone_msg_{event.sender_id}_{user_obj.id}_{int(datetime.now().timestamp())}'
                target_name = getattr(user_obj, 'first_name', 'User')
                
                result = event.builder.article(
                    title=f"🔒 Secret for {target_name}",
                    description=f"Send to {target_name}",
                    text=f"**🔐 A secret message for {target_name}!**\n\n"
                         f"*Only {target_name} can open this message.*",
                    buttons=[[Button.inline("🔓 Send Message", message_id)]]
                )
                
                await event.answer([result])
                
            except Exception as e:
                logger.error(f"Cloned inline error: {e}")
                result = event.builder.article(
                    title="❌ User Not Found",
                    description="Check username/user ID",
                    text="❌ User not found! Please check the username or user ID."
                )
                await event.answer([result])
                
        except Exception as e:
            logger.error(f"Cloned inline handler error: {e}")
    
    async def handle_cloned_callback(self, event, user_bot, owner_id):
        """Handle callbacks for cloned bot"""
        try:
            data = event.data.decode('utf-8')
            
            if data.startswith('clone_msg_'):
                # Simple message display
                await event.answer("🔓 This is a secret message!\n\n💌 From: Anonymous", alert=True)
                
            elif data == "help":
                bot_username = (await user_bot.get_me()).username
                help_text = f"""
📖 **How to use @{bot_username}:**

**1. Inline Mode:**
   • Type `@{bot_username}` in any chat
   • Write your message
   • Add @username OR user ID at end
   • Send!

**2. Examples:**
   • `@{bot_username} Hello! @username`
   • `@{bot_username} I miss you 123456789`

🔒 **Only the mentioned user can read your message!**
"""
                await event.edit(
                    help_text,
                    buttons=[[Button.switch_inline("🚀 Try Now", query="")]]
                )
                
        except Exception as e:
            logger.error(f"Cloned callback error: {e}")
            await event.answer("❌ Error occurred!", alert=True)
    
    async def clone_bot(self, event, token):
        """Clone a new bot for user"""
        user_id = event.sender_id
        
        try:
            # Check if user already has a bot
            if str(user_id) in self.user_clone_limit:
                existing_token = self.user_clone_limit[str(user_id)]
                existing_bot = self.clone_stats.get(existing_token, {})
                existing_username = existing_bot.get('username', 'your bot')
                
                return {
                    'success': False,
                    'message': f"❌ **You already have a cloned bot!**\n\n"
                              f"🤖 Your Bot: @{existing_username}\n\n"
                              f"Each user can only clone one bot.\n"
                              f"Use `/remove` to remove your current bot first."
                }
            
            # Validate token format
            if not re.match(r'^\d+:[A-Za-z0-9_-]+$', token):
                return {
                    'success': False,
                    'message': "❌ **Invalid Token Format!**\n\n"
                              "Please check your bot token.\n"
                              "Format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`"
                }
            
            # Check if token already used
            if token in self.clone_stats:
                return {
                    'success': False,
                    'message': "❌ **This bot is already cloned!**\n\n"
                              "Please create a new bot with @BotFather."
                }
            
            # Start cloning
            user_bot = await self.start_cloned_bot(token, user_id)
            bot_me = await user_bot.get_me()
            
            # Update clone stats with user info
            self.clone_stats[token] = {
                'owner_id': user_id,
                'username': bot_me.username,
                'bot_id': bot_me.id,
                'owner_name': getattr(event.sender, 'first_name', 'User'),
                'owner_mention': f"[{getattr(event.sender, 'first_name', 'User')}](tg://user?id={user_id})",
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'token_preview': token[:10] + '...'
            }
            self.save_data()
            
            # Send notification to admin
            try:
                admin_id = int(os.getenv('ADMIN_ID', 0))
                if admin_id:
                    await self.main_bot.send_message(
                        admin_id,
                        f"🆕 **New Bot Cloned!**\n\n"
                        f"🤖 **Bot:** @{bot_me.username}\n"
                        f"👤 **User:** {getattr(event.sender, 'first_name', 'User')}\n"
                        f"🆔 **User ID:** `{user_id}`\n"
                        f"📅 **Time:** {datetime.now().strftime('%H:%M:%S')}\n"
                        f"🔢 **Total Clones:** {len(self.clone_stats)}",
                        parse_mode='markdown'
                    )
            except Exception as e:
                logger.error(f"Admin notification error: {e}")
            
            return {
                'success': True,
                'message': f"✅ **Bot Cloned Successfully!**\n\n"
                          f"🤖 **Your Bot:** @{bot_me.username}\n"
                          f"🎉 Now active with all whisper features!\n\n"
                          f"**Try your bot:**\n"
                          f"`@{bot_me.username} message @username`",
                'username': bot_me.username
            }
            
        except Exception as e:
            logger.error(f"Clone error: {e}")
            return {
                'success': False,
                'message': f"❌ **Clone Failed!**\n\nError: {str(e)[:200]}"
            }
    
    async def remove_user_bot(self, user_id):
        """Remove user's cloned bot"""
        try:
            user_id_str = str(user_id)
            
            if user_id_str not in self.user_clone_limit:
                return {
                    'success': False,
                    'message': "❌ You have no bots to remove!"
                }
            
            token = self.user_clone_limit[user_id_str]
            bot_info = self.clone_stats.get(token, {})
            bot_username = bot_info.get('username', 'Unknown')
            
            # Disconnect bot if running
            if token in self.user_bots:
                try:
                    await self.user_bots[token].disconnect()
                    del self.user_bots[token]
                except Exception as e:
                    logger.error(f"Error disconnecting bot: {e}")
            
            # Remove from records
            if token in self.clone_stats:
                del self.clone_stats[token]
            
            if user_id_str in self.user_clone_limit:
                del self.user_clone_limit[user_id_str]
            
            self.save_data()
            
            # Send notification to admin
            try:
                admin_id = int(os.getenv('ADMIN_ID', 0))
                if admin_id:
                    await self.main_bot.send_message(
                        admin_id,
                        f"🗑 **Bot Removed!**\n\n"
                        f"🤖 **Bot:** @{bot_username}\n"
                        f"👤 **User ID:** `{user_id}`\n"
                        f"📅 **Time:** {datetime.now().strftime('%H:%M:%S')}\n"
                        f"🔢 **Remaining Clones:** {len(self.clone_stats)}",
                        parse_mode='markdown'
                    )
            except Exception as e:
                logger.error(f"Admin removal notification error: {e}")
            
            return {
                'success': True,
                'message': f"✅ **Bot Removed Successfully!**\n\n"
                          f"🤖 Removed: @{bot_username}\n"
                          f"🗑 You can now clone a new bot if needed."
            }
            
        except Exception as e:
            logger.error(f"Remove error: {e}")
            return {
                'success': False,
                'message': f"❌ Error removing bot: {str(e)}"
            }
    
    def get_user_bot_info(self, user_id):
        """Get user's cloned bot info"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.user_clone_limit:
            return None
        
        token = self.user_clone_limit[user_id_str]
        return self.clone_stats.get(token)
    
    def get_all_clones(self):
        """Get all clone statistics"""
        return {
            'total_clones': len(self.clone_stats),
            'active_bots': len(self.user_bots),
            'clone_stats': self.clone_stats,
            'user_limits': self.user_clone_limit
        }
    
    async def stop_all(self):
        """Stop all cloned bots"""
        logger.info(f"🛑 Stopping {len(self.user_bots)} cloned bots...")
        
        for token, bot in self.user_bots.items():
            try:
                await bot.disconnect()
            except Exception as e:
                logger.error(f"Error stopping bot {token}: {e}")
        
        self.user_bots.clear()
        logger.info("✅ All cloned bots stopped")
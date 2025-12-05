import logging
from datetime import datetime
from telethon import Button

logger = logging.getLogger(__name__)

class CallbackHandler:
    def __init__(self, bot, user_manager):
        self.bot = bot
        self.user_manager = user_manager
        self.WELCOME_TEXT = """
╔══════════════════════╗
║     🎭 𝗦𝗛𝗥𝗜𝗕𝗢𝗧𝗦     ║ 𝐏𝐨𝐰𝐞𝐫𝐞𝐝 𝐛𝐲
║    𝗪𝗛𝗜𝗦𝗣𝗘𝗥 𝗕𝗢𝗧    ║      𝐀𝐫𝐭𝐢𝐬𝐭
╚══════════════════════╝

🤫 Welcome to Secret Whisper Bot!

🔒 Send anonymous secret messages
🚀 Only intended recipient can read
🎯 Easy to use inline mode

Create whispers that only specific users can unlock!
"""
    
    async def handle_callback(self, event):
        try:
            data = event.data.decode('utf-8')
            
            if data == "help":
                bot_username = (await self.bot.get_me()).username
                help_text = f"""
📖 **How to Use Whisper Bot**

**Usage:**
`@{bot_username} message @username`
`@{bot_username} message 123456789`

**Examples:**
• `@{bot_username} Hello! @shribots`
• `@{bot_username} I miss you 123456789`

**Features:**
• Send anonymous messages
• Only recipient can read
• Quick recent user selection
• Works with username or user ID

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
                await event.edit(
                    self.WELCOME_TEXT,
                    buttons=[
                        [Button.switch_inline("🚀 Send Whisper", query="")],
                        [Button.inline("📖 Help", data="help")]
                    ]
                )
            
            elif data.startswith("recent_"):
                user_key = data.replace("recent_", "")
                if user_key in self.user_manager.recent_users:
                    user_data = self.user_manager.recent_users[user_key]
                    username = user_data.get('username')
                    first_name = user_data.get('first_name', 'User')
                    
                    if username:
                        target_text = f"@{username}"
                        query_text = f"@{username}"
                    else:
                        target_text = first_name
                        query_text = first_name
                    
                    await event.edit(
                        f"🔒 **Send whisper to {target_text}**\n\n"
                        f"Now switch to inline mode and type your message for {target_text}",
                        buttons=[[Button.switch_inline(
                            f"💌 Message {target_text}",
                            query=query_text
                        )]]
                    )
                else:
                    await event.answer("User not found in recent list!", alert=True)
            
            elif data.startswith("msg_"):
                # Get message from whisper handler
                from .whisper_handler import WhisperHandler
                whisper_handler = WhisperHandler(self.bot)
                
                if data in whisper_handler.messages_db:
                    msg_data = whisper_handler.messages_db[data]
                    if event.sender_id == msg_data['user_id']:
                        # Target user opening the message
                        await event.answer(f"🔓 {msg_data['msg']}", alert=True)
                    elif event.sender_id == msg_data['sender_id']:
                        # Sender viewing their own message
                        await event.answer(f"📝 {msg_data['msg']}", alert=True)
                    else:
                        await event.answer("🔒 This message is not for you!", alert=True)
                else:
                    await event.answer("❌ Message not found!", alert=True)
            
            else:
                await event.answer("❌ Invalid button!", alert=True)
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
            await event.answer("❌ An error occurred. Please try again.", alert=True)

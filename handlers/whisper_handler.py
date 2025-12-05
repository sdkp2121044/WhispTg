import re
import logging
from datetime import datetime
from telethon import Button

logger = logging.getLogger(__name__)

class WhisperHandler:
    def __init__(self, bot):
        self.bot = bot
        self.messages_db = {}
        self.user_cooldown = {}
        
    def is_cooldown(self, user_id):
        """Check if user is in cooldown"""
        now = datetime.now().timestamp()
        if user_id in self.user_cooldown:
            if now - self.user_cooldown[user_id] < 2:
                return True
        self.user_cooldown[user_id] = now
        return False
    
    def _format_recent_users_text(self, recent_users):
        """Format recent users for display"""
        if not recent_users:
            return "**No recent users found.**\n\nType: `message @username`"
        
        text = "**Recent Users for Quick Send:**\n\n"
        for i, (user_id, user_data) in enumerate(recent_users.items(), 1):
            username = user_data.get('username', '')
            first_name = user_data.get('first_name', 'User')
            
            if username:
                display = f"@{username}"
            else:
                display = first_name
            
            text += f"{i}. {display}\n"
        
        text += "\n**Click any user above or type manually:**\n`message @username`"
        return text
    
    async def extract_target_user(self, text):
        """
        Extract target user from text with flexible patterns
        Supports: message @username, message 123456789, @username message, etc.
        """
        text = text.strip()
        
        # Pattern 1: Ends with @username
        match = re.search(r'@(\w+)$', text)
        if match:
            target = match.group(1)
            message = text.replace(f"@{target}", "").strip()
            return target, message, 'username'
        
        # Pattern 2: Ends with user ID
        match = re.search(r'(\d+)$', text)
        if match:
            target = match.group(1)
            message = text.replace(target, "").strip()
            return target, message, 'userid'
        
        # Pattern 3: Starts with @username
        match = re.search(r'^@(\w+)\s+(.+)$', text)
        if match:
            target = match.group(1)
            message = match.group(2).strip()
            return target, message, 'username'
        
        # Pattern 4: Contains @username anywhere
        match = re.search(r'@(\w+)', text)
        if match:
            target = match.group(1)
            message = text.replace(f"@{target}", "").strip()
            return target, message, 'username'
        
        # Pattern 5: Contains user ID anywhere
        match = re.search(r'(\d{8,})', text)
        if match:
            target = match.group(1)
            message = text.replace(target, "").strip()
            return target, message, 'userid'
        
        return None, text, 'unknown'
    
    async def handle_inline_query(self, event):
        """Handle inline queries for whisper messages"""
        if self.is_cooldown(event.sender_id):
            await event.answer([])
            return
        
        try:
            # Get recent users from user_manager
            from .user_manager import UserManager
            user_manager = UserManager()
            user_manager.load_data()
            recent_users = user_manager.recent_users
            
            # If no query text, show recent users
            if not event.text or not event.text.strip():
                if recent_users:
                    recent_text = self._format_recent_users_text(recent_users)
                    buttons = []
                    
                    # Create buttons for recent users
                    for user_id, user_data in list(recent_users.items())[:5]:
                        username = user_data.get('username', '')
                        first_name = user_data.get('first_name', 'User')
                        
                        if username:
                            display = f"@{username}"
                            query_text = f"@{username}"
                        else:
                            display = first_name
                            query_text = first_name
                        
                        if len(display) > 15:
                            display = display[:12] + "..."
                        
                        buttons.append([Button.switch_inline(
                            f"🔒 {display}",
                            query=query_text
                        )])
                    
                    result = event.builder.article(
                        title="🤫 Whisper Bot - Recent Users",
                        description="Select from recent users or type manually",
                        text=recent_text,
                        buttons=buttons
                    )
                else:
                    result = event.builder.article(
                        title="🤫 Whisper Bot - Send Secret Messages",
                        description="Usage: message @username OR message 123456789",
                        text="**Usage:** `message @username`\n\n**Examples:**\n• `Hello! @username`\n• `I miss you 123456789`",
                        buttons=[[Button.switch_inline("🚀 Try Now", query="")]]
                    )
                await event.answer([result])
                return
            
            # Process the query text
            query_text = event.text.strip()
            
            # Extract target user from query
            target, message_text, target_type = await self.extract_target_user(query_text)
            
            if not target or not message_text:
                result = event.builder.article(
                    title="❌ Invalid Format",
                    description="Use: message @username OR message 123456789",
                    text="**Usage:** `message @username`\n\n**Examples:**\n• `Hello! @username`\n• `I miss you 123456789`",
                    buttons=[[Button.switch_inline("🔄 Try Again", query=query_text)]]
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
            
            try:
                # Try to get user entity
                if target_type == 'userid':
                    user_obj = await self.bot.get_entity(int(target))
                else:
                    user_obj = await self.bot.get_entity(target)
                
                if not hasattr(user_obj, 'first_name'):
                    result = event.builder.article(
                        title="❌ Not a User",
                        description="You can only send to users",
                        text="This appears to be a channel or group. Please mention a user instead."
                    )
                    await event.answer([result])
                    return
                
                # Add to recent users
                user_manager.add_to_recent_users(
                    event.sender_id,
                    user_obj.id,
                    getattr(user_obj, 'username', None),
                    getattr(user_obj, 'first_name', 'User')
                )
                
            except Exception as e:
                logger.error(f"Error getting user entity: {e}")
                
                # Even if user not found, still create message with the target
                # This allows sending to users who haven't interacted with bot
                user_id = target if target_type == 'userid' else target
                user_name = target if target_type == 'username' else f"User {target}"
                
                # Add to recent users with limited info
                user_manager.add_to_recent_users(
                    event.sender_id,
                    user_id,
                    target if target_type == 'username' else None,
                    user_name
                )
                
                user_obj = type('obj', (object,), {
                    'id': user_id,
                    'first_name': user_name,
                    'username': target if target_type == 'username' else None
                })()
            
            # Create message ID
            message_id = f'msg_{event.sender_id}_{user_obj.id}_{int(datetime.now().timestamp())}'
            self.messages_db[message_id] = {
                'user_id': user_obj.id,
                'msg': message_text,
                'sender_id': event.sender_id,
                'timestamp': datetime.now().isoformat(),
                'target_name': getattr(user_obj, 'first_name', 'User')
            }
            
            target_name = getattr(user_obj, 'first_name', 'User')
            result = event.builder.article(
                title=f"🔒 Secret Message for {target_name}",
                description=f"Click to send secret message",
                text=f"**🔐 A secret message for {target_name}!**\n\n*Only {target_name} can open this message.*",
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

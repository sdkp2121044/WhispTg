# handlers.py
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any

from telethon import events, Button
from telethon.tl.types import User
from telethon.errors import (
    UsernameNotOccupiedError,
    UsernameInvalidError,
    FloodWaitError
)

from config import logger, ADMIN_ID, SUPPORT_CHANNEL, SUPPORT_GROUP
from database import history_manager, message_manager, cache_manager
from detection import detector
from utils import get_user_entity, is_cooldown

# ======================
# GLOBAL BOT INSTANCE
# ======================
bot = None

# ======================
# INLINE QUERY HANDLER
# ======================
async def handle_inline_query(event):
    """Main inline query handler with instant detection"""
    try:
        user_id = event.sender_id
        
        # Check cooldown
        if is_cooldown(user_id):
            await event.answer([])
            return
        
        query_text = event.text.strip() if event.text else ""
        
        # Get user's history
        user_history = history_manager.get_user_history(user_id)
        
        # Case 1: Empty query - Show ALL past recipients
        if not query_text:
            if user_history:
                # Create buttons for ALL past recipients
                buttons = []
                for recipient in user_history[:10]:  # Show first 10
                    name = recipient['name']
                    username = recipient.get('username')
                    
                    if username:
                        display_text = f"@{username}"
                        query_suffix = f" @{username}"
                    else:
                        display_text = name
                        query_suffix = f" {recipient['id']}"
                    
                    # Truncate if too long
                    if len(display_text) > 20:
                        display_text = display_text[:17] + "..."
                    
                    buttons.append([
                        Button.switch_inline(
                            display_text,
                            query=query_suffix,
                            same_peer=True
                        )
                    ])
                
                result_text = "📋 **Select from your past recipients or type a new message:**"
                
                result = event.builder.article(
                    title="🤫 Your Past Recipients",
                    description=f"{len(user_history)} recipients available",
                    text=result_text,
                    buttons=buttons
                )
                
            else:
                # New user - show basic help
                result_text = """
🤫 **Send a Secret Whisper**

💡 **How to send:**
1. Type your message
2. Add @username OR user ID
3. Send!

📱 **Examples:**
• `Hello! @username`
• `How are you 123456789`
• `Hi there @telegram_user`

🔒 **Only they can read your message!**
                """
                
                result = event.builder.article(
                    title="🤫 Send Secret Message",
                    description="Type: message @username",
                    text=result_text,
                    buttons=[[Button.switch_inline("🚀 Try Now", query="")]]
                )
            
            await event.answer([result])
            return
        
        # Case 2: Query has content - Detect recipient instantly
        detection_result = detector.extract_recipient_and_message(query_text)
        recipient, message_text, recipient_type = detection_result
        
        # If no recipient detected, show suggestions
        if not recipient:
            # Check if it's just a message (auto-suggest last recipient)
            if user_history and query_text:
                # Auto-suggest most recent recipient
                recent_recipient = user_history[0]
                return await create_whisper_result(
                    event, user_id, recent_recipient['id'], 
                    query_text, recent_recipient['name'], 
                    recent_recipient.get('username'), True
                )
            
            # Show history suggestions
            if user_history:
                suggestion_text = "💡 **Add a recipient:**\nType @username or user ID after your message"
                buttons = []
                
                for recipient in user_history[:5]:
                    name = recipient['name']
                    username = recipient.get('username')
                    
                    if username:
                        display = f"@{username}"
                        query = f"{query_text} @{username}"
                    else:
                        display = name
                        query = f"{query_text} {recipient['id']}"
                    
                    buttons.append([
                        Button.switch_inline(
                            f"✉️ {display}",
                            query=query,
                            same_peer=True
                        )
                    ])
                
                result = event.builder.article(
                    title="❌ Specify a recipient",
                    description="Add @username or user ID",
                    text=suggestion_text,
                    buttons=buttons
                )
                
                await event.answer([result])
                return
            
            # No history and no recipient
            result = event.builder.article(
                title="❌ Recipient required",
                description="Add @username or user ID",
                text="**Please specify a recipient!**\n\nExamples:\n• `Hello @username`\n• `Hi 123456789`",
                buttons=[[Button.switch_inline("🔄 Try Again", query=query_text)]]
            )
            
            await event.answer([result])
            return
        
        # Case 3: Recipient detected - Get user entity
        try:
            if recipient_type == 'userid':
                # Validate user ID
                user_id_int = int(''.join(filter(str.isdigit, recipient)))
                user_obj = await get_user_entity(bot, user_id_int)
                recipient_id = user_obj.id
                recipient_username = getattr(user_obj, 'username', None)
                recipient_name = getattr(user_obj, 'first_name', f'User {recipient_id}')
                
            else:  # username
                username = recipient.lstrip('@').lower()
                user_obj = await get_user_entity(bot, username)
                recipient_id = user_obj.id
                recipient_username = username
                recipient_name = getattr(user_obj, 'first_name', f'@{username}')
            
            # If no message text, use query as message
            if not message_text:
                message_text = query_text
            
            # Create whisper result
            return await create_whisper_result(
                event, user_id, recipient_id, message_text,
                recipient_name, recipient_username, False
            )
            
        except (UsernameNotOccupiedError, UsernameInvalidError) as e:
            logger.warning(f"User not found: {recipient}")
            
            error_text = f"""
❌ **User not found!**

**Tried:** `{recipient}`
**Type:** {'Username' if recipient_type == 'username' else 'User ID'}

💡 **Try:**
1. Check spelling
2. Use user ID instead
3. Make sure user exists
            """
            
            result = event.builder.article(
                title=f"❌ {recipient} not found",
                description="User doesn't exist",
                text=error_text,
                buttons=[[Button.switch_inline("🔄 Try Again", query=query_text)]]
            )
            
            await event.answer([result])
            return
            
        except Exception as e:
            logger.error(f"Error processing recipient {recipient}: {e}")
            
            result = event.builder.article(
                title="❌ Error",
                description="Something went wrong",
                text="❌ An error occurred. Please try again.",
                buttons=[[Button.switch_inline("🔄 Try Again", query=query_text)]]
            )
            
            await event.answer([result])
            return
    
    except Exception as e:
        logger.error(f"Inline query error: {e}")
        
        result = event.builder.article(
            title="❌ Error",
            description="Something went wrong",
            text="❌ An error occurred. Please try again.",
            buttons=[[Button.switch_inline("🔄 Try Again", query="")]]
        )
        
        await event.answer([result])

async def create_whisper_result(event, sender_id, recipient_id, message_text, 
                               recipient_name, recipient_username=None, auto_suggested=False):
    """Create and return a whisper result"""
    try:
        # Add to history
        history_manager.add_recipient(
            sender_id, recipient_id, recipient_name, recipient_username
        )
        
        # Cache user info
        if recipient_username:
            cache_manager.cache_user(
                f"@{recipient_username}", recipient_id,
                recipient_username, recipient_name, None
            )
        
        cache_manager.cache_user(
            str(recipient_id), recipient_id,
            recipient_username, recipient_name, None
        )
        
        # Create message ID
        message_id = f"msg_{sender_id}_{recipient_id}_{int(datetime.now().timestamp())}"
        
        # Save message
        message_manager.add_message(
            message_id, sender_id, recipient_id, message_text
        )
        
        # Create result text
        if auto_suggested:
            title = f"🤫 Auto to {recipient_name}"
            description = f"Auto-send to {recipient_name}"
            result_text = f"**✨ Auto-suggest active!**\n\n"
        else:
            title = f"🤫 To {recipient_name}"
            description = f"Send to {recipient_name}"
            result_text = f"**🔐 Secret message for {recipient_name}**\n\n"
        
        if recipient_username:
            result_text += f"**Recipient:** @{recipient_username}\n"
        else:
            result_text += f"**Recipient:** {recipient_name}\n"
        
        result_text += f"**Message:** {message_text[:100]}{'...' if len(message_text) > 100 else ''}\n\n"
        result_text += f"🔒 **Only {recipient_name} can read this!**"
        
        # Create result
        result = event.builder.article(
            title=title,
            description=description,
            text=result_text,
            buttons=[[Button.inline("🔓 Show Message", message_id)]]
        )
        
        await event.answer([result])
        
    except Exception as e:
        logger.error(f"Error creating whisper result: {e}")
        raise

# ======================
# CALLBACK QUERY HANDLER
# ======================
async def handle_callback_query(event):
    """Handle button clicks on whisper messages"""
    try:
        data = event.data.decode('utf-8')
        
        # Check if it's a message ID
        if data.startswith('msg_'):
            message_data = message_manager.get_message(data)
            
            if not message_data:
                await event.answer("❌ Message expired or not found!", alert=True)
                return
            
            sender_id = message_data['sender_id']
            recipient_id = message_data['recipient_id']
            message_text = message_data['message']
            
            # Check who is viewing
            viewer_id = event.sender_id
            
            if viewer_id == recipient_id:
                # Recipient viewing - show message with sender info
                try:
                    sender_info = await get_user_entity(bot, sender_id)
                    sender_name = getattr(sender_info, 'first_name', 'Someone')
                    sender_username = getattr(sender_info, 'username', None)
                    
                    sender_text = f"\n\n💌 **From:** {sender_name}"
                    if sender_username:
                        sender_text += f" (@{sender_username})"
                    
                    await event.answer(f"🔓 {message_text}{sender_text}", alert=True)
                    
                except Exception:
                    await event.answer(f"🔓 {message_text}\n\n💌 **From:** Anonymous", alert=True)
                    
            elif viewer_id == sender_id:
                # Sender viewing their own message
                try:
                    recipient_info = await get_user_entity(bot, recipient_id)
                    recipient_name = getattr(recipient_info, 'first_name', 'User')
                    
                    await event.answer(
                        f"📝 **Your message:** {message_text}\n\n"
                        f"👤 **To:** {recipient_name}",
                        alert=True
                    )
                    
                except Exception:
                    await event.answer(
                        f"📝 **Your message:** {message_text}\n\n"
                        f"👤 **To:** User {recipient_id}",
                        alert=True
                    )
                    
            else:
                # Someone else trying to view
                await event.answer("🔒 This message is not for you!", alert=True)
                
        else:
            await event.answer("❌ Invalid button!", alert=True)
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await event.answer("❌ An error occurred!", alert=True)

# ======================
# COMMAND HANDLERS
# ======================
async def handle_start_command(event):
    """Handle /start command"""
    try:
        user_id = event.sender_id
        
        # Get bot username FIRST with await
        bot_me = await bot.get_me()  # ✅ FIXED: await added
        bot_username = bot_me.username
        
        # Get user history stats
        user_history = history_manager.get_user_history(user_id)
        history_count = len(user_history)
        
        welcome_text = f"""
🤫 **Instant Whisper Bot**

🔒 Send anonymous secret messages
🚀 Only recipient can read
🎯 Instant user detection

📊 **Your stats:**
• Past recipients: {history_count}
• Last used: {datetime.now().strftime('%Y-%m-%d')}

💡 **How to use:**
Type `@{bot_username}` in any chat
        """
        
        buttons = [
            [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
            [Button.url("👥 Group", f"https://t.me/{SUPPORT_GROUP}")],
            [Button.switch_inline("🚀 Send Whisper", query="")],
        ]
        
        if user_id == ADMIN_ID:
            buttons.append([Button.inline("📊 Admin Stats", "admin_stats")])
        
        await event.reply(welcome_text, buttons=buttons)
        
    except Exception as e:
        logger.error(f"Start command error: {e}")
        await event.reply("❌ Error occurred!")

async def handle_history_command(event):
    """Handle /history command"""
    try:
        user_id = event.sender_id
        user_history = history_manager.get_user_history(user_id)
        
        if not user_history:
            await event.reply(
                "📭 **No whisper history yet!**\n\n"
                "Send your first whisper to build history.",
                buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
            )
            return
        
        history_text = "📚 **Your Past Recipients**\n\n"
        
        for i, recipient in enumerate(user_history[:15], 1):
            name = recipient['name']
            username = recipient.get('username')
            count = recipient.get('count', 1)
            
            if username:
                history_text += f"{i}. **{name}** (@{username}) - {count} whispers\n"
            else:
                history_text += f"{i}. **{name}** - {count} whispers\n"
        
        total_whispers = sum(r.get('count', 1) for r in user_history)
        history_text += f"\n📊 **Total:** {len(user_history)} recipients, {total_whispers} whispers"
        
        # Create quick buttons
        buttons = []
        for recipient in user_history[:6]:
            name = recipient['name']
            username = recipient.get('username')
            
            if username:
                display = f"🔤 @{username}"
                query = f" @{username}"
            else:
                display = f"👤 {name}"
                query = f" {recipient['id']}"
            
            buttons.append([
                Button.switch_inline(
                    display[:20],
                    query=query,
                    same_peer=True
                )
            ])
        
        buttons.append([Button.inline("🗑️ Clear History", "clear_history")])
        
        await event.reply(history_text, buttons=buttons)
        
    except Exception as e:
        logger.error(f"History command error: {e}")
        await event.reply("❌ Error loading history!")

async def handle_clear_command(event):
    """Handle /clear command"""
    try:
        user_id = event.sender_id
        
        if history_manager.clear_user_history(user_id):
            await event.reply(
                "✅ **History cleared!**\n\n"
                "All your past recipients have been removed.",
                buttons=[[Button.switch_inline("🚀 Send New Whisper", query="")]]
            )
        else:
            await event.reply("❌ Error clearing history!")
            
    except Exception as e:
        logger.error(f"Clear command error: {e}")
        await event.reply("❌ Error occurred!")

async def handle_stats_command(event):
    """Handle /stats command"""
    try:
        user_id = event.sender_id
        
        if user_id != ADMIN_ID:
            await event.reply("❌ Admin only command!")
            return
        
        # Get bot info
        bot_me = await bot.get_me()  # ✅ FIXED: await added
        
        # Get stats from database
        total_users = len(history_manager.get_all_user_ids())
        total_messages = message_manager.get_message_count()
        
        stats_text = f"""
📊 **Admin Statistics**

🤖 **Bot Info:**
• Username: @{bot_me.username}
• ID: {bot_me.id}
• Name: {bot_me.first_name}

📈 **Usage Stats:**
• Total Users: {total_users}
• Total Messages: {total_messages}
• Active Today: Calculating...

🕒 **Server:**
• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
• Status: ✅ Running
        """
        
        await event.reply(stats_text)
        
    except Exception as e:
        logger.error(f"Stats command error: {e}")
        await event.reply("❌ Error loading stats!")

# ======================
# SETUP HANDLERS
# ======================
def setup_handlers(bot_instance):
    """Setup all event handlers"""
    global bot
    bot = bot_instance
    
    # Inline query handler
    @bot.on(events.InlineQuery)
    async def inline_handler_wrapper(event):
        await handle_inline_query(event)
    
    # Callback query handler
    @bot.on(events.CallbackQuery)
    async def callback_handler_wrapper(event):
        await handle_callback_query(event)
    
    # Command handlers
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_handler_wrapper(event):
        await handle_start_command(event)
    
    @bot.on(events.NewMessage(pattern='/history'))
    async def history_handler_wrapper(event):
        await handle_history_command(event)
    
    @bot.on(events.NewMessage(pattern='/clear'))
    async def clear_handler_wrapper(event):
        await handle_clear_command(event)
    
    @bot.on(events.NewMessage(pattern='/stats'))
    async def stats_handler_wrapper(event):
        await handle_stats_command(event)
    
    logger.info("✅ Handlers setup complete")

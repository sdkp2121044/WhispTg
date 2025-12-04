# handlers.py
import logging
from datetime import datetime

from telethon import events, Button
from telethon.errors import UsernameNotOccupiedError, UsernameInvalidError

from config import WELCOME_TEXT, HELP_TEXT, SUPPORT_CHANNEL, SUPPORT_GROUP, ADMIN_ID
from database import (
    user_whisper_history, user_recent_recipients, messages_db,
    add_to_whisper_history, get_user_stats, clear_user_history, clear_user_recent_only
)
from utils import (
    is_cooldown, extract_target_from_text, get_user_entity,
    get_all_past_recipients_buttons
)

logger = logging.getLogger(__name__)

def setup_handlers(bot):
    """Setup all bot event handlers"""
    
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        try:
            user_id = event.sender_id
            logger.info(f"🚀 Start command from user: {user_id}")
            
            # Get user stats
            stats = get_user_stats(user_id)
            
            # Create personalized welcome message
            if stats['total_whispers'] > 0:
                stats_text = f"""
    📊 **Your Whisper Stats:**
    • Total Whispers: {stats['total_whispers']}
    • Unique Recipients: {stats['unique_recipients']}
    • Recent Whispers (7 days): {stats['recent_whispers']}
    • Recent Recipients: {stats['recent_recipients_count']}
                """
            else:
                stats_text = "📊 **No whispers yet!**\nSend your first whisper to see stats here."
            
            welcome_text = WELCOME_TEXT.format(stats=stats_text)
            
            buttons = [
                [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                [Button.url("👥 Group", f"https://t.me/{SUPPORT_GROUP}")],
                [Button.switch_inline("🚀 Send Whisper", query="")],
                [Button.inline("📖 Help", data="help"), Button.inline("📜 History", data="view_full_history")],
                [Button.inline("📊 My Stats", data="my_stats"), Button.inline("🕒 Recent", data="view_recent")]
            ]
            
            if user_id == ADMIN_ID:
                buttons.append([Button.inline("👑 Admin Stats", data="admin_stats")])
            
            await event.reply(welcome_text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Start error: {e}")
            await event.reply("❌ An error occurred. Please try again.")

    @bot.on(events.NewMessage(pattern='/help'))
    async def help_handler(event):
        try:
            bot_username = (await bot.get_me()).username
            help_text = HELP_TEXT.format(bot_username, bot_username, bot_username)
            
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

    @bot.on(events.NewMessage(pattern='/history'))
    async def history_handler(event):
        """Show user's complete whisper history"""
        try:
            user_id = event.sender_id
            
            if user_id not in user_recent_recipients or not user_recent_recipients[user_id]:
                await event.reply(
                    "📭 **No whisper history yet!**\n\n"
                    "Send your first whisper and bot will remember ALL recipients.",
                    buttons=[[Button.switch_inline("🚀 Send First Whisper", query="")]]
                )
                return
            
            # Get ALL unique recipients
            history_text = "📚 **ALL Your Past Recipients**\n\n"
            
            for i, recipient in enumerate(user_recent_recipients[user_id], 1):
                name = recipient.get('name', 'User')
                username = recipient.get('username')
                count = recipient.get('count', 1)
                last_time = datetime.fromisoformat(recipient['timestamp']).strftime("%d/%m %H:%M")
                
                if username:
                    history_text += f"{i}. **{name}** (@{username}) - {count} whispers, Last: {last_time}\n"
                else:
                    history_text += f"{i}. **{name}** - {count} whispers, Last: {last_time}\n"
            
            total = len(user_recent_recipients[user_id])
            total_whispers = sum(r.get('count', 1) for r in user_recent_recipients[user_id])
            
            history_text += f"\n📊 **Stats:** {total} unique recipients, {total_whispers} total whispers"
            
            # Create quick action buttons from ALL recipients
            buttons = []
            for recipient in user_recent_recipients[user_id][:6]:
                name = recipient.get('name', 'User')
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
            
            buttons.append([
                Button.inline("🔄 Refresh", data="view_full_history"),
                Button.inline("🗑️ Clear", data="clear_history_confirm")
            ])
            
            await event.reply(history_text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"History error: {e}")
            await event.reply("❌ Error loading history.")

    @bot.on(events.NewMessage(pattern='/recent'))
    async def recent_handler(event):
        """Show recent recipients"""
        try:
            user_id = event.sender_id
            
            if user_id not in user_recent_recipients or not user_recent_recipients[user_id]:
                await event.reply(
                    "🕒 **No recent recipients!**\n\n"
                    "Send a whisper first to build your recent list.",
                    buttons=[[Button.switch_inline("🚀 Send First Whisper", query="")]]
                )
                return
            
            recent_text = "🕒 **Your Recent Recipients**\n\n"
            
            for i, recipient in enumerate(user_recent_recipients[user_id][:15], 1):
                name = recipient.get('name', 'User')
                username = recipient.get('username')
                timestamp = datetime.fromisoformat(recipient['timestamp']).strftime("%d/%m %H:%M")
                
                if username:
                    recent_text += f"{i}. **{name}** (@{username}) - {timestamp}\n"
                else:
                    recent_text += f"{i}. **{name}** - {timestamp}\n"
            
            recent_text += f"\n📊 **Total Recent:** {len(user_recent_recipients[user_id])}"
            
            # Create quick selection buttons
            buttons = []
            for recipient in user_recent_recipients[user_id][:6]:
                name = recipient.get('name', 'User')
                username = recipient.get('username')
                
                if username:
                    display = f"🔤 @{username}"
                    query = f" @{username}"
                else:
                    display = f"👤 {name}"
                    query = f" {recipient['id']}"
                
                if len(display) > 20:
                    display = display[:17] + "..."
                
                buttons.append([
                    Button.switch_inline(
                        display,
                        query=query,
                        same_peer=True
                    )
                ])
            
            buttons.append([
                Button.inline("📚 Full History", data="view_full_history"),
                Button.inline("🔙 Back", data="back_start")
            ])
            
            await event.reply(recent_text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Recent error: {e}")
            await event.reply("❌ Error loading recent recipients.")

    @bot.on(events.NewMessage(pattern='/stats'))
    async def stats_handler(event):
        """Show user's personal statistics"""
        try:
            user_id = event.sender_id
            stats = get_user_stats(user_id)
            
            stats_text = f"""
    📊 **Your Personal Whisper Statistics**

    • **Total Whispers Sent:** {stats['total_whispers']}
    • **Unique Recipients:** {stats['unique_recipients']}
    • **Recent Whispers (7 days):** {stats['recent_whispers']}
    • **Recent Recipients Saved:** {stats['recent_recipients_count']}

    📅 **Account Created:** Not tracked
    🆔 **Your User ID:** `{user_id}`
    ⏰ **Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
            """
            
            buttons = [
                [Button.switch_inline("💌 Send Whisper", query="")],
                [Button.inline("📚 View History", data="view_full_history")],
                [Button.inline("🕒 Recent Recipients", data="view_recent")],
                [Button.inline("🔙 Back", data="back_start")]
            ]
            
            await event.reply(stats_text, buttons=buttons)
            
        except Exception as e:
            logger.error(f"Stats error: {e}")
            await event.reply("❌ Error loading statistics.")

    @bot.on(events.NewMessage(pattern='/clear'))
    async def clear_handler(event):
        """Clear user's history"""
        try:
            user_id = event.sender_id
            
            buttons = [
                [Button.inline("🗑️ Clear ALL History", data="clear_all_history")],
                [Button.inline("🕒 Clear Recent Only", data="clear_recent_only")],
                [Button.inline("❌ Cancel", data="back_start")]
            ]
            
            await event.reply(
                "⚠️ **Clear History**\n\n"
                "What would you like to clear?\n\n"
                "• **Clear ALL History:** Removes all whispers and recipients\n"
                "• **Clear Recent Only:** Keeps history but clears recent list\n\n"
                "⚠️ **Warning:** This action cannot be undone!",
                buttons=buttons
            )
            
        except Exception as e:
            logger.error(f"Clear error: {e}")
            await event.reply("❌ Error in clear command.")

    @bot.on(events.InlineQuery)
    async def inline_handler(event):
        """Handle inline queries with ALL past recipients"""
        try:
            if is_cooldown(event.sender_id):
                await event.answer([])
                return

            user_id = event.sender_id
            query_text = event.text.strip() if event.text else ""
            
            # सबसे पहले ALL past recipients के buttons get करें
            all_past_buttons = get_all_past_recipients_buttons(user_id, query_text)
            
            # Case 1: Empty query - Show ALL past recipients with stats
            if not query_text:
                if all_past_buttons:
                    # User has history - show ALL past recipients
                    result_text = f"""
    🤫 **Whisper Bot - Your Past Recipients**

    📚 **Bot remembers ALL users you've whispered to!**
    • Total unique recipients: {len(user_recent_recipients.get(user_id, []))}
    • Click any below to whisper again
    • Or type new message with @username/userID

    💡 **How to use:**
    1. Select from your past recipients below
    2. OR type: `message @username`
    3. OR type: `message 123456789`

    ✨ **All your past whispers are saved!**
                    """
                else:
                    # New user
                    result_text = """
    🤫 **Whisper Bot - Send Secret Messages**

    💡 **How to send:**
    1. Type your message below
    2. Add @username OR user ID
    3. Send!

    📚 **Bot will remember ALL your future recipients!**
                    """
                
                result = event.builder.article(
                    title="🤫 All Your Past Recipients",
                    description=f"{len(all_past_buttons)} past recipients",
                    text=result_text,
                    buttons=all_past_buttons or [[Button.switch_inline("🚀 Try Now", query="")]]
                )
                await event.answer([result])
                return
            
            # Case 2: Query has content - Try to detect target
            target_user, message_text, target_type = extract_target_from_text(query_text)
            
            # Case 2A: Target detected in query
            if target_user and target_type:
                try:
                    if target_type == 'userid':
                        if not target_user.isdigit() or len(target_user) < 8:
                            raise ValueError("Invalid user ID")
                        
                        user_obj = await get_user_entity(bot, int(target_user))
                        target_user_id = int(target_user)
                        target_username = getattr(user_obj, 'username', None)
                        target_name = getattr(user_obj, 'first_name', f'User {target_user}')
                        
                    else:
                        username = target_user.lower().replace('@', '')
                        
                        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', username):
                            raise UsernameInvalidError("Invalid username")
                        
                        user_obj = await get_user_entity(bot, username)
                        target_user_id = user_obj.id
                        target_username = username
                        target_name = getattr(user_obj, 'first_name', f'@{username}')
                    
                    # Validate message
                    if not message_text:
                        result = event.builder.article(
                            title="❌ Empty Message",
                            description="Please enter a message",
                            text="**Message is empty!**\n\nPlease type your secret message.\n\nSelect from your history below:",
                            buttons=all_past_buttons[:3]
                        )
                        await event.answer([result])
                        return
                    
                    # Add to whisper history
                    whisper_data = {
                        'recipient_id': target_user_id,
                        'recipient_name': target_name,
                        'recipient_username': target_username,
                        'message': message_text
                    }
                    add_to_whisper_history(user_id, whisper_data)
                    
                    # Create message entry
                    message_id = f'msg_{user_id}_{target_user_id}_{int(datetime.now().timestamp())}'
                    messages_db[message_id] = {
                        'user_id': target_user_id,
                        'msg': message_text,
                        'sender_id': user_id,
                        'timestamp': datetime.now().isoformat(),
                        'target_name': target_name,
                        'target_username': target_username,
                        'added_to_history': True
                    }
                    
                    # Create result
                    result_text = f"""
    **🔐 Secret message for {target_name}!**

    💬 **Message:** {message_text[:50]}{'...' if len(message_text) > 50 else ''}

    ✅ **Added to your whisper history!**
    📚 Bot will remember this recipient for future whispers.

    🔒 **Only {target_name} can open this message.**
                    """
                    
                    # Combine buttons
                    combined_buttons = [
                        [Button.inline("🔓 Send Secret Message", message_id)],
                        *all_past_buttons[:2]
                    ]
                    
                    result = event.builder.article(
                        title=f"🤫 To {target_name}",
                        description=f"Click to send to {target_name}",
                        text=result_text,
                        buttons=combined_buttons
                    )
                    
                    await event.answer([result])
                    return
                    
                except (UsernameNotOccupiedError, UsernameInvalidError):
                    error_text = f"""
    ❌ **User @{target_user} not found!**

    💡 **Try these:**
    1. Check username spelling
    2. Use user ID instead
    3. Select from your history below
                    """
                    result = event.builder.article(
                        title=f"❌ @{target_user} not found",
                        description="User doesn't exist",
                        text=error_text,
                        buttons=all_past_buttons[:3]
                    )
                    await event.answer([result])
                    return
                    
                except Exception as e:
                    logger.error(f"Error processing detected target: {e}")
            
            # Case 2B: Auto-suggest from recent
            if user_id in user_recent_recipients and user_recent_recipients[user_id]:
                recent_recipient = user_recent_recipients[user_id][0]
                target_user_id = recent_recipient['id']
                target_username = recent_recipient.get('username')
                target_name = recent_recipient.get('name', 'User')
                
                # Add to whisper history
                whisper_data = {
                    'recipient_id': target_user_id,
                    'recipient_name': target_name,
                    'recipient_username': target_username,
                    'message': query_text
                }
                add_to_whisper_history(user_id, whisper_data)
                
                # Create message entry
                message_id = f'msg_{user_id}_{target_user_id}_{int(datetime.now().timestamp())}'
                messages_db[message_id] = {
                    'user_id': target_user_id,
                    'msg': query_text,
                    'sender_id': user_id,
                    'timestamp': datetime.now().isoformat(),
                    'target_name': target_name,
                    'target_username': target_username,
                    'auto_suggested': True
                }
                
                # Create result
                result_text = f"""
    **✨ Auto-Suggest Active!**

    💬 **Message:** {query_text[:50]}{'...' if len(query_text) > 50 else ''}

    👤 **To:** {target_name} (Most Recent)

    ✅ **Added to your whisper history!**

    🔒 **Only {target_name} can open this message.**
                """
                
                combined_buttons = [
                    [Button.inline("🔓 Send Secret Message", message_id)],
                    *all_past_buttons[:2]
                ]
                
                result = event.builder.article(
                    title=f"🤫 Auto to {target_name}",
                    description=f"Auto-send to {target_name}",
                    text=result_text,
                    buttons=combined_buttons
                )
                
                await event.answer([result])
                return
            
            # Case 2C: No target detected - Show ALL history suggestions
            suggestion_text = """
    **💡 Need to specify a recipient!**

    Bot couldn't detect a username or user ID in your message.

    **Try these formats:**
    1. `your message @username`
    2. `your message 123456789`
    3. `to @username: your message`

    **Or select from your COMPLETE whisper history below:**
    📚 **All your past recipients will appear here!**
            """
            
            result = event.builder.article(
                title="❌ Specify a recipient",
                description="Add @username or user ID",
                text=suggestion_text,
                buttons=all_past_buttons[:5] or [
                    [Button.switch_inline("🔄 Try Again", query=query_text)]
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
        try:
            data = event.data.decode('utf-8')
            user_id = event.sender_id
            
            if data == "help":
                bot_username = (await bot.get_me()).username
                help_text = HELP_TEXT.format(bot_username, bot_username, bot_username)
                
                await event.edit(
                    help_text,
                    buttons=[
                        [Button.switch_inline("🚀 Try Now", query="")],
                        [Button.inline("🔙 Back", data="back_start")]
                    ]
                )
            
            elif data == "view_full_history":
                if user_id not in user_recent_recipients or not user_recent_recipients[user_id]:
                    await event.answer("No history!", alert=True)
                    await event.edit(
                        "📭 No whisper history yet!",
                        buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
                    )
                    return
                
                # Show ALL recipients with quick buttons
                history_text = f"""
    📚 **ALL Your Past Recipients**

    Total: {len(user_recent_recipients[user_id])} unique recipients

    💡 **Click any below to whisper again!**
    Bot remembers ALL users you've ever whispered to.
                """
                
                # Get buttons for ALL recipients
                all_buttons = get_all_past_recipients_buttons(user_id, "")
                
                if all_buttons:
                    await event.edit(history_text, buttons=all_buttons[:10])
                else:
                    await event.edit(history_text, buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]])
            
            elif data == "view_recent":
                if user_id not in user_recent_recipients or not user_recent_recipients[user_id]:
                    await event.answer("No recent recipients!", alert=True)
                    await event.edit(
                        "🕒 No recent recipients! Send a whisper first.",
                        buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
                    )
                    return
                
                recent_text = "🕒 **Your Recent Recipients**\n\n"
                for i, recipient in enumerate(user_recent_recipients[user_id][:10], 1):
                    name = recipient.get('name', 'User')
                    username = recipient.get('username')
                    if username:
                        recent_text += f"{i}. **{name}** (@{username})\n"
                    else:
                        recent_text += f"{i}. **{name}**\n"
                
                recent_text += f"\nTotal: {len(user_recent_recipients[user_id])} recent recipients"
                
                # Create quick selection buttons
                buttons = []
                for recipient in user_recent_recipients[user_id][:6]:
                    name = recipient.get('name', 'User')
                    username = recipient.get('username')
                    
                    if username:
                        display = f"🔤 @{username}"
                        query = f" @{username}"
                    else:
                        display = f"👤 {name}"
                        query = f" {recipient['id']}"
                    
                    if len(display) > 20:
                        display = display[:17] + "..."
                    
                    buttons.append([
                        Button.switch_inline(
                            display,
                            query=query,
                            same_peer=True
                        )
                    ])
                
                buttons.append([
                    Button.inline("📚 Full History", data="view_full_history"),
                    Button.inline("🔙 Back", data="back_start")
                ])
                
                await event.edit(recent_text, buttons=buttons)
            
            elif data == "my_stats":
                stats = get_user_stats(user_id)
                
                stats_text = f"""
    📊 **Your Personal Statistics**

    • **Total Whispers:** {stats['total_whispers']}
    • **Unique Recipients:** {stats['unique_recipients']}
    • **Recent Whispers (7 days):** {stats['recent_whispers']}
    • **Recent Recipients:** {stats['recent_recipients_count']}

    💡 **All your whispers are saved in history!**
    Every recipient you've ever whispered to is remembered.
                """
                
                await event.edit(
                    stats_text,
                    buttons=[
                        [Button.switch_inline("💌 Send Whisper", query="")],
                        [Button.inline("📚 View History", data="view_full_history")],
                        [Button.inline("🔙 Back", data="back_start")]
                    ]
                )
            
            elif data == "clear_history_confirm":
                await event.edit(
                    "⚠️ **Clear History Confirmation**\n\n"
                    "This will delete ALL your whisper history!\n"
                    "📚 **All past recipients will be forgotten.**\n"
                    "🕒 **Recent list will be cleared.**\n\n"
                    "⚠️ **This action cannot be undone!**\n\n"
                    "Are you sure you want to continue?",
                    buttons=[
                        [Button.inline("✅ Yes, Clear ALL", data="clear_all_history")],
                        [Button.inline("🕒 Clear Recent Only", data="clear_recent_only")],
                        [Button.inline("❌ Cancel", data="back_start")]
                    ]
                )
            
            elif data == "clear_all_history":
                total_whispers, total_recent = clear_user_history(user_id)
                
                await event.answer(f"✅ Cleared {total_whispers} whispers!", alert=True)
                await event.edit(
                    f"✅ **History Cleared!**\n\n"
                    f"• Deleted whispers: {total_whispers}\n"
                    f"• Cleared recipients: {total_recent}\n\n"
                    "📭 All your history has been removed.\n"
                    "Send a new whisper to start fresh!",
                    buttons=[[Button.switch_inline("🚀 Send New Whisper", query="")]]
                )
            
            elif data == "clear_recent_only":
                total_recent = clear_user_recent_only(user_id)
                if total_recent > 0:
                    await event.answer(f"✅ Cleared {total_recent} recent recipients!", alert=True)
                    await event.edit(
                        f"✅ **Recent List Cleared!**\n\n"
                        f"Cleared {total_recent} recent recipients.\n"
                        "📚 Your complete whisper history is still saved.\n"
                        "Recent list will rebuild as you send new whispers.",
                        buttons=[[Button.switch_inline("🚀 Send Whisper", query="")]]
                    )
                else:
                    await event.answer("No recent recipients to clear!", alert=True)
            
            elif data == "admin_stats":
                if user_id != ADMIN_ID:
                    await event.answer("❌ Admin only!", alert=True)
                    return
                    
                total_users = len(user_whisper_history)
                total_messages = len(messages_db)
                total_history_entries = sum(len(v) for v in user_whisper_history.values())
                
                from database import user_entity_cache
                
                stats_text = f"""
    👑 **Admin Statistics**

    👥 Total Users: {total_users}
    💬 Active Messages: {total_messages}
    📚 Total History Entries: {total_history_entries}
    🧠 Cached Users: {len(user_entity_cache)}

    🆔 Admin ID: {ADMIN_ID}
    🌐 Port: {PORT}
    🕒 Time: {datetime.now().strftime('%H:%M:%S')}

    **Status:** ✅ Running
                """
                
                await event.edit(
                    stats_text,
                    buttons=[[Button.inline("🔙 Back", data="back_start")]]
                )
            
            elif data == "back_start":
                # Get updated stats
                stats = get_user_stats(user_id)
                
                if stats['total_whispers'] > 0:
                    stats_text = f"""
    📊 **Your Stats:**
    • Total Whispers: {stats['total_whispers']}
    • Unique Recipients: {stats['unique_recipients']}
    • Recent Whispers: {stats['recent_whispers']}
                    """
                else:
                    stats_text = "📊 **No whispers yet!**"
                
                welcome_text = WELCOME_TEXT.format(stats=stats_text)
                
                buttons = [
                    [Button.url("📢 Channel", f"https://t.me/{SUPPORT_CHANNEL}")],
                    [Button.url("👥 Group", f"https://t.me/{SUPPORT_GROUP}")],
                    [Button.switch_inline("🚀 Send Whisper", query="")],
                    [Button.inline("📖 Help", data="help"), Button.inline("📜 History", data="view_full_history")],
                    [Button.inline("📊 My Stats", data="my_stats"), Button.inline("🕒 Recent", data="view_recent")]
                ]
                
                if user_id == ADMIN_ID:
                    buttons.append([Button.inline("👑 Admin Stats", data="admin_stats")])
                
                await event.edit(welcome_text, buttons=buttons)
            
            elif data in messages_db:
                msg_data = messages_db[data]
                
                if event.sender_id == msg_data['user_id']:
                    # Target user viewing
                    sender_info = ""
                    try:
                        sender_id = msg_data['sender_id']
                        from database import user_entity_cache
                        from utils import get_user_entity
                        
                        cache_key = str(sender_id)
                        if cache_key in user_entity_cache:
                            sender = user_entity_cache[cache_key]['entity']
                        else:
                            try:
                                sender = await bot.get_entity(sender_id)
                            except:
                                sender = type('obj', (object,), {
                                    'first_name': 'Someone',
                                    'username': None
                                })()
                        
                        sender_name = getattr(sender, 'first_name', 'Someone')
                        sender_info = f"\n\n💌 From: {sender_name}"
                        if hasattr(sender, 'username') and sender.username:
                            sender_info += f" (@{sender.username})"
                    except:
                        sender_info = f"\n\n💌 From: Anonymous"
                    
                    alert_text = f"🔓 {msg_data['msg']}{sender_info}"
                    if msg_data.get('added_to_history'):
                        alert_text += "\n\n📚 This whisper was added to sender's history!"
                    elif msg_data.get('auto_suggested'):
                        alert_text += "\n\n✨ Sent using auto-suggest from history!"
                    
                    await event.answer(alert_text, alert=True)
                
                elif event.sender_id == msg_data['sender_id']:
                    # Sender viewing
                    alert_text = f"📝 Your message: {msg_data['msg']}\n\n👤 To: {msg_data.get('target_name', 'User')}"
                    if msg_data.get('target_username'):
                        alert_text += f" (@{msg_data['target_username']})"
                    
                    alert_text += f"\n\n✅ Added to your whisper history!"
                    
                    await event.answer(alert_text, alert=True)
                
                else:
                    await event.answer("🔒 This message is not for you!", alert=True)
            
            else:
                await event.answer("❌ Invalid button!", alert=True)
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
            await event.answer("❌ An error occurred. Please try again.", alert=True)
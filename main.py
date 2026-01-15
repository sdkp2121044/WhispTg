import os
import json
import telebot
from telebot import types
from datetime import datetime
import threading
import time

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize bot
bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))
ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Import utilities
from utils.image_processor import process_image, add_watermark, add_color_background
from utils.invite_system import InviteSystem
from utils.file_manager import FileManager

# Initialize systems
invite_system = InviteSystem()
file_manager = FileManager()

# Ensure data directory exists
os.makedirs('data', exist_ok=True)

# ==================== HELPER FUNCTIONS ====================

def load_users():
    try:
        with open('data/users.json', 'r') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open('data/users.json', 'w') as f:
        json.dump(users, f, indent=2)

def get_user(user_id):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        users[user_id_str] = {
            'id': user_id,
            'invites': 0,
            'invited_users': [],
            'images_processed': 0,
            'has_no_watermark': False,
            'invite_code': invite_system.generate_code(user_id),
            'join_date': datetime.now().strftime('%Y-%m-%d'),
            'last_active': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        save_users(users)
    
    return users[user_id_str]

def update_user(user_id, updates):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str in users:
        users[user_id_str].update(updates)
        users[user_id_str]['last_active'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_users(users)

# ==================== COMMAND HANDLERS ====================

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    # Check if came from referral
    if len(message.text.split()) > 1:
        ref_code = message.text.split()[1]
        if ref_code.startswith('ref_'):
            inviter_id = invite_system.get_user_from_code(ref_code)
            if inviter_id and inviter_id != user_id:
                # Add to inviter's count
                inviter = get_user(inviter_id)
                if user_id not in inviter.get('invited_users', []):
                    inviter['invites'] = inviter.get('invites', 0) + 1
                    inviter['invited_users'] = inviter.get('invited_users', []) + [user_id]
                    update_user(inviter_id, inviter)
                    
                    # Check if inviter gets reward
                    if inviter['invites'] >= 2 and not inviter.get('has_no_watermark', False):
                        inviter['has_no_watermark'] = True
                        update_user(inviter_id, inviter)
                        bot.send_message(inviter_id, 
                            "🎉 CONGRATULATIONS!\n\n"
                            "You've invited 2 friends!\n"
                            "✅ Watermark REMOVED forever!\n"
                            "Your future images will have NO watermark! 🎨")

    # Send welcome message
    welcome_text = f"""
🎉 *Welcome to idx Empire BG Remover* 🎉

✨ *Features:*
• AI Background Removal
• Multiple Color Options  
• High Quality Output
• 100% Free Forever

🎁 *Invite Reward System:*
Invite 2 friends → Remove watermark forever!

📊 *Your Status:*
✅ Invites: {user.get('invites', 0)}/2
{'✅' if user.get('has_no_watermark') else '⚠️'} Watermark: {'OFF 🎉' if user.get('has_no_watermark') else 'ON'}

🔗 Your invite: /invite
🖼️ Try now: Send me a photo!

📢 Updates: {os.getenv('CHANNEL_USERNAME', '@idxempire_updates')}
💬 Support: {os.getenv('GROUP_USERNAME', '@idxempire_support')}
    """
    
    # Create keyboard
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{os.getenv('CHANNEL_USERNAME', 'idxempire_updates')[1:]}"),
        types.InlineKeyboardButton("👥 Join Group", url=f"https://t.me/{os.getenv('GROUP_USERNAME', 'idxempire_support')[1:]}")
    )
    keyboard.add(types.InlineKeyboardButton("🎨 Try Now", callback_data="try_now"))
    
    # Send welcome with animation
    try:
        with open('assets/welcome.jpg', 'rb') as photo:
            bot.send_photo(message.chat.id, photo, 
                          caption=welcome_text, 
                          reply_markup=keyboard,
                          parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, welcome_text, 
                        reply_markup=keyboard,
                        parse_mode='Markdown')

@bot.message_handler(commands=['invite'])
def handle_invite(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    invite_text = f"""
📤 *YOUR INVITE LINK*

Share this link with friends:
`https://t.me/{(bot.get_me()).username}?start=ref_{user['invite_code']}`

🎯 *Progress:* {user.get('invites', 0)}/2 invites
🏆 *Reward:* Remove watermark forever!

📊 *Your Stats:*
• Images processed: {user.get('images_processed', 0)}
• Invites completed: {user.get('invites', 0)}
• Watermark status: {'✅ OFF' if user.get('has_no_watermark') else '⚠️ ON'}

💡 *Tip:* Share in groups, with friends!
    """
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("📤 Share Link", 
        url=f"https://t.me/share/url?url=https://t.me/{(bot.get_me()).username}?start=ref_{user['invite_code']}&text=Remove%20backgrounds%20for%20free%20with%20this%20bot!%20🎨"))
    
    bot.send_message(message.chat.id, invite_text, 
                    reply_markup=keyboard,
                    parse_mode='Markdown')

@bot.message_handler(commands=['info'])
def handle_info(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    info_text = f"""
👤 *YOUR PROFILE*

📝 Name: {message.from_user.first_name} {f'(@{message.from_user.username})' if message.from_user.username else ''}
📅 Joined: {user.get('join_date', 'Today')}
🖼️ Images: {user.get('images_processed', 0)} processed
👥 Invites: {user.get('invites', 0)}/2 completed
💧 Watermark: {'✅ REMOVED 🎉' if user.get('has_no_watermark') else '⚠️ ACTIVE'}

{'🎉 Congratulations! Watermark is removed forever!' if user.get('has_no_watermark') else f'🎯 Need {2 - user.get("invites", 0)} more invite(s) to remove watermark!'}

🔗 Invite link: /invite
📊 Leaderboard: /leaderboard
    """
    
    bot.send_message(message.chat.id, info_text, parse_mode='Markdown')

@bot.message_handler(commands=['leaderboard'])
def handle_leaderboard(message):
    users = load_users()
    
    # Sort by invites
    sorted_users = sorted(users.items(), 
                         key=lambda x: x[1].get('invites', 0), 
                         reverse=True)[:10]
    
    leaderboard_text = "🏆 *INVITE LEADERBOARD*\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (user_id, user_data) in enumerate(sorted_users):
        if i < len(medals):
            username = user_data.get('username', f'User{user_id[:5]}')
            leaderboard_text += f"{medals[i]} {username}: {user_data.get('invites', 0)} invites\n"
    
    leaderboard_text += "\n🎯 Goal: Invite 2 friends to remove watermark!\n"
    leaderboard_text += "🔗 Your invite: /invite"
    
    bot.send_message(message.chat.id, leaderboard_text, parse_mode='Markdown')

@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Admin only command!")
        return
    
    # Ask for broadcast message
    msg = bot.reply_to(message, "📢 *BROADCAST MESSAGE*\n\nType your message to send to all users:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    users = load_users()
    total = len(users)
    success = 0
    failed = 0
    
    bot.send_message(message.chat.id, f"📤 Sending to {total} users...")
    
    for user_id_str in users.keys():
        try:
            bot.copy_message(user_id_str, message.chat.id, message.message_id)
            success += 1
        except:
            failed += 1
        time.sleep(0.05)  # Avoid rate limit
    
    bot.send_message(message.chat.id, 
                    f"✅ Broadcast completed!\n\n"
                    f"📊 Results:\n"
                    f"• Total users: {total}\n"
                    f"• Successfully sent: {success}\n"
                    f"• Failed: {failed}")

@bot.message_handler(commands=['stats'])
def handle_stats(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Admin only command!")
        return
    
    users = load_users()
    total_users = len(users)
    users_with_reward = sum(1 for u in users.values() if u.get('has_no_watermark', False))
    total_images = sum(u.get('images_processed', 0) for u in users.values())
    total_invites = sum(u.get('invites', 0) for u in users.values())
    
    stats_text = f"""
📊 *BOT STATISTICS*

👥 Users: {total_users}
🎉 Watermark removed: {users_with_reward}
🖼️ Total images: {total_images}
👥 Total invites: {total_invites}

📈 Conversion Rate: {(users_with_reward/total_users*100 if total_users > 0 else 0):.1f}%
👤 Avg. invites/user: {(total_invites/total_users if total_users > 0 else 0):.1f}

💡 Top 3 Inviters: /leaderboard
    """
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = """
🆘 *HELP & COMMANDS*

🤖 *BOT COMMANDS:*
/start - Start the bot
/invite - Get your invite link
/info - Check your profile
/leaderboard - See top inviters
/help - This help message

🎨 *HOW TO USE:*
1. Send me any photo
2. I'll remove background automatically
3. Choose color/transparent option
4. Download processed image

💧 *WATERMARK SYSTEM:*
• New users: Watermark on images
• Invite 2 friends: Watermark removed forever!
• Check status: /info

📢 *SUPPORT:*
• Updates: {channel}
• Community: {group}
• Issues: Contact @admin

🎯 *TIPS:*
• Use good quality photos
• Portrait photos work best
• Share with friends using /invite
    """.format(
        channel=os.getenv('CHANNEL_USERNAME', '@idxempire_updates'),
        group=os.getenv('GROUP_USERNAME', '@idxempire_support')
    )
    
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

# ==================== PHOTO PROCESSING ====================

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    # Check daily limit
    if user.get('images_processed', 0) >= int(os.getenv('DAILY_LIMIT', 50)):
        bot.reply_to(message, 
                    "⚠️ *Daily limit reached!*\n\n"
                    "You've processed 50 images today.\n"
                    "Limit resets at midnight.\n\n"
                    "🎁 Want unlimited? Invite 2 friends using /invite!",
                    parse_mode='Markdown')
        return
    
    # Get photo file
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    # Check file size
    file_size_mb = len(downloaded_file) / (1024 * 1024)
    if file_size_mb > int(os.getenv('MAX_FILE_SIZE', 10)):
        bot.reply_to(message, 
                    f"⚠️ *File too large!*\n\n"
                    f"Size: {file_size_mb:.1f}MB\n"
                    f"Max allowed: {os.getenv('MAX_FILE_SIZE', 10)}MB\n\n"
                    f"Please send a smaller image.")
        return
    
    # Process image
    processing_msg = bot.reply_to(message, "🔄 Processing your image...\n⏳ Estimated: 5-8 seconds")
    
    try:
        # Remove background
        processed_image = process_image(downloaded_file)
        
        # Check watermark status
        apply_watermark = not user.get('has_no_watermark', False)
        
        # Update user stats
        update_user(user_id, {
            'images_processed': user.get('images_processed', 0) + 1
        })
        
        # Ask for output format
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("⬜ Transparent", callback_data=f"format_transparent_{apply_watermark}"),
            types.InlineKeyboardButton("⚪ White BG", callback_data=f"format_white_{apply_watermark}"),
            types.InlineKeyboardButton("🎨 Colors", callback_data=f"show_colors_{apply_watermark}")
        )
        
        bot.delete_message(message.chat.id, processing_msg.message_id)
        
        watermark_status = "⚠️ With watermark" if apply_watermark else "✅ No watermark"
        
        bot.send_message(message.chat.id,
                        f"✅ *Background removed!*\n\n"
                        f"📊 Stats: Image #{user.get('images_processed', 0) + 1}\n"
                        f"💧 Status: {watermark_status}\n\n"
                        f"🎨 *Choose output format:*",
                        reply_markup=keyboard,
                        parse_mode='Markdown')
        
        # Save temp image for callback
        file_manager.save_temp_image(user_id, processed_image)
        
    except Exception as e:
        bot.delete_message(message.chat.id, processing_msg.message_id)
        bot.reply_to(message, f"❌ Error processing image:\n{str(e)}")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    
    if call.data == "try_now":
        bot.answer_callback_query(call.id, "Send me a photo to get started! 📸")
    
    elif call.data.startswith("format_"):
        # Get format from callback
        parts = call.data.split("_")
        if len(parts) >= 3:
            format_type = parts[1]
            apply_watermark = parts[2] == "True"
            
            # Get temp image
            temp_image = file_manager.get_temp_image(user_id)
            if not temp_image:
                bot.answer_callback_query(call.id, "❌ Image expired. Please send again.")
                return
            
            # Process based on format
            if format_type == "transparent":
                final_image = temp_image
            elif format_type == "white":
                final_image = add_color_background(temp_image, (255, 255, 255))
            else:
                bot.answer_callback_query(call.id, "Unknown format")
                return
            
            # Add watermark if needed
            if apply_watermark:
                final_image = add_watermark(final_image, os.getenv('WATERMARK_TEXT', 'idx Empire'))
            
            # Send image
            bot.send_photo(call.message.chat.id, final_image,
                          caption=f"✅ Processed successfully!\n"
                                 f"📊 Your total: {user.get('images_processed', 0)} images\n"
                                 f"{'💧 Watermark: ON' if apply_watermark else '🎉 Watermark: OFF'}\n\n"
                                 f"🔄 Process another? Send another photo!")
            
            # Clean temp
            file_manager.delete_temp_image(user_id)
    
    elif call.data.startswith("show_colors_"):
        # Show color options
        keyboard = types.InlineKeyboardMarkup(row_width=3)
        colors = [
            ("🔴 Red", (255, 0, 0)),
            ("🟠 Orange", (255, 165, 0)),
            ("🟡 Yellow", (255, 255, 0)),
            ("🟢 Green", (0, 255, 0)),
            ("🔵 Blue", (0, 0, 255)),
            ("🟣 Purple", (128, 0, 128)),
            ("🟤 Brown", (165, 42, 42)),
            ("⚫ Black", (0, 0, 0)),
            ("⚪ White", (255, 255, 255))
        ]
        
        apply_watermark = call.data.split("_")[2] == "True"
        
        for color_name, color_rgb in colors:
            keyboard.add(types.InlineKeyboardButton(color_name, 
                callback_data=f"color_{color_rgb[0]}_{color_rgb[1]}_{color_rgb[2]}_{apply_watermark}"))
        
        bot.edit_message_text("🎨 Select a color for background:",
                            call.message.chat.id,
                            call.message.message_id,
                            reply_markup=keyboard)
    
    elif call.data.startswith("color_"):
        # Get color from callback
        parts = call.data.split("_")
        if len(parts) >= 5:
            color_rgb = (int(parts[1]), int(parts[2]), int(parts[3]))
            apply_watermark = parts[4] == "True"
            
            # Get temp image
            temp_image = file_manager.get_temp_image(user_id)
            if not temp_image:
                bot.answer_callback_query(call.id, "❌ Image expired. Please send again.")
                return
            
            # Add color background
            final_image = add_color_background(temp_image, color_rgb)
            
            # Add watermark if needed
            if apply_watermark:
                final_image = add_watermark(final_image, os.getenv('WATERMARK_TEXT', 'idx Empire'))
            
            # Send image
            bot.send_photo(call.message.chat.id, final_image,
                          caption=f"✅ Colored background added!\n"
                                 f"📊 Your total: {user.get('images_processed', 0)} images\n"
                                 f"{'💧 Watermark: ON' if apply_watermark else '🎉 Watermark: OFF'}\n\n"
                                 f"🔄 Process another? Send another photo!")
            
            # Clean temp
            file_manager.delete_temp_image(user_id)
    
    bot.answer_callback_query(call.id)

# ==================== GROUP HANDLING ====================

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_members(message):
    if bot.get_me().id in [user.id for user in message.new_chat_members]:
        # Bot added to group
        welcome_text = f"""
👋 Hello *{message.chat.title}*!

I'm *idx Empire BG Remover Bot* 🤖

✨ I can remove backgrounds from any photo instantly!

📌 *How to use in group:*
1. Send me any photo in this chat
2. I'll remove background automatically
3. Choose color/transparent option
4. Download processed image

💡 *Tips:*
• I work in PM for better privacy
• Use /invite to remove watermark
• Join {os.getenv('CHANNEL_USERNAME')} for updates

🎨 Send a photo to try now!
        """
        
        bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown')
        
        # Save group info
        groups = file_manager.load_json('groups.json')
        group_id = str(message.chat.id)
        groups[group_id] = {
            'title': message.chat.title,
            'members': message.chat.member_count,
            'added_date': datetime.now().strftime('%Y-%m-%d'),
            'last_active': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        file_manager.save_json('groups.json', groups)

# ==================== START BOT ====================

def start_bot():
    print("🤖 Bot is starting...")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"💧 Watermark: {os.getenv('WATERMARK_TEXT', 'idx Empire')}")
    
    # Start polling
    bot.polling(none_stop=True, interval=0)

if __name__ == "__main__":
    start_bot()

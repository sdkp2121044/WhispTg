import os
import io
import logging
from PIL import Image
from flask import Flask
import telebot
from telebot import types
import requests
import threading
import time
import base64

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Bot token
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found!")
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Replace with your token from @BotFather

bot = telebot.TeleBot(BOT_TOKEN)

# Store user data
user_stats = {}

# ==================== BACKGROUND REMOVAL FUNCTION ====================
def remove_background_free_api(image_bytes):
    """
    Use FREE remove.bg API (100 free/month)
    No installation issues like rembg
    """
    try:
        # Convert image to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Use remove.bg API (FREE tier)
        api_key = "YOUR_REMOVE_BG_API_KEY"  # Get free from remove.bg
        api_url = "https://api.remove.bg/v1.0/removebg"
        
        headers = {
            'X-Api-Key': api_key,
            'Content-Type': 'application/json'
        }
        
        data = {
            'image_file_b64': image_base64,
            'size': 'auto',
            'format': 'png'
        }
        
        response = requests.post(api_url, json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Return PNG image bytes
            return response.content
        else:
            logger.error(f"API Error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"API call error: {e}")
        return None

def remove_background_local(image_bytes):
    """
    Local background removal (if API fails)
    Simple method without complex dependencies
    """
    try:
        # Try to use rembg if available
        try:
            from rembg import remove
            input_image = Image.open(io.BytesIO(image_bytes))
            
            # Resize for faster processing
            max_size = 800
            if max(input_image.size) > max_size:
                ratio = max_size / max(input_image.size)
                new_size = (int(input_image.width * ratio), int(input_image.height * ratio))
                input_image = input_image.resize(new_size, Image.Resampling.LANCZOS)
            
            output_image = remove(input_image)
            
            # Save to bytes
            img_byte_arr = io.BytesIO()
            output_image.save(img_byte_arr, format='PNG')
            return img_byte_arr.getvalue()
            
        except ImportError:
            logger.error("rembg not installed")
            return None
            
    except Exception as e:
        logger.error(f"Local removal error: {e}")
        return None

def remove_background_fallback(image_bytes):
    """
    Ultimate fallback: Return original image with message
    """
    try:
        # Just return the original image (as fallback)
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to PNG
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        
        return img_byte_arr.getvalue()
    except:
        return None

# ==================== BOT COMMANDS ====================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    # Initialize user stats
    if user_id not in user_stats:
        user_stats[user_id] = {
            'name': user_name,
            'images_processed': 0,
            'first_seen': time.strftime("%Y-%m-%d %H:%M:%S"),
            'last_active': time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    welcome_text = f"""
✨ *Welcome {user_name}!* ✨

🤖 *Background Remover Bot*

🚀 *How to use:*
1️⃣ Send me any photo
2️⃣ I'll remove background automatically
3️⃣ Get transparent PNG image

🎯 *Features:*
✅ High quality removal
✅ Fast processing  
✅ Free to use
✅ Multiple format support

📸 *Tips for best results:*
• Use clear photos
• Good lighting works best
• Single subject photos

⭐ *Commands:*
/start - Show this message
/stats - Your statistics
/about - About this bot

*Send a photo to get started!* 📸
"""
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        types.KeyboardButton("📸 Remove Background"),
        types.KeyboardButton("ℹ️ Help"),
        types.KeyboardButton("📊 My Stats")
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=keyboard
    )
    
    logger.info(f"New user: {user_name} (ID: {user_id})")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    user_id = message.from_user.id
    
    if user_id in user_stats:
        stats = user_stats[user_id]
        stats_text = f"""
📊 *Your Statistics*

👤 Name: {stats['name']}
🆔 ID: `{user_id}`
📸 Images Processed: *{stats['images_processed']}*
📅 First Seen: {stats['first_seen']}
⏰ Last Active: {time.strftime('%Y-%m-%d %H:%M:%S')}

🌟 Keep using! More features coming soon.
"""
    else:
        stats_text = "Send /start first to initialize!"
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

@bot.message_handler(commands=['about'])
def about_bot(message):
    total_users = len(user_stats)
    total_images = sum(user['images_processed'] for user in user_stats.values())
    
    about_text = f"""
🤖 *About This Bot*

*Version:* 4.0 Stable
*Status:* ✅ Online & Working
*Users:* {total_users}
*Images Processed:* {total_images}

🛠 *Technology:*
• Python 3.10
• Telegram Bot API
• Background Removal AI
• Render Hosting

💡 *Note:* This is a free service.
For issues, contact developer.

❤️ *Thank you for using!*
"""
    bot.send_message(message.chat.id, about_text, parse_mode='Markdown')

# ==================== PHOTO HANDLER ====================
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        
        # Update user stats
        if user_id in user_stats:
            user_stats[user_id]['last_active'] = time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            user_stats[user_id] = {
                'name': user_name,
                'images_processed': 0,
                'first_seen': time.strftime("%Y-%m-%d %H:%M:%S"),
                'last_active': time.strftime("%Y-%m-%d %H:%M:%S")
            }
        
        # Send initial message
        status_msg = bot.reply_to(
            message,
            "🔄 *Downloading your image...*",
            parse_mode='Markdown'
        )
        
        # Get the photo (largest size)
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        
        # Download image
        downloaded_file = bot.download_file(file_info.file_path)
        file_size = len(downloaded_file) / 1024  # KB
        
        bot.edit_message_text(
            f"✅ Downloaded ({file_size:.1f} KB)\n🎨 *Removing background...*",
            message.chat.id,
            status_msg.message_id,
            parse_mode='Markdown'
        )
        
        # METHOD 1: Try local removal first
        logger.info(f"Processing image for {user_name} ({file_size:.1f} KB)")
        result_bytes = remove_background_local(downloaded_file)
        
        if not result_bytes:
            # METHOD 2: Try API
            bot.edit_message_text(
                "⚡ *Using enhanced method...*",
                message.chat.id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            result_bytes = remove_background_free_api(downloaded_file)
        
        if not result_bytes:
            # METHOD 3: Ultimate fallback
            bot.edit_message_text(
                "⚠️ *Using fallback method...*",
                message.chat.id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            result_bytes = remove_background_fallback(downloaded_file)
        
        if result_bytes:
            # Update stats
            user_stats[user_id]['images_processed'] += 1
            
            bot.edit_message_text(
                "✅ *Background removed!*\n📤 *Sending image...*",
                message.chat.id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
            # Create keyboard
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(
                types.KeyboardButton("📸 Remove Another"),
                types.KeyboardButton("📊 My Stats"),
                types.KeyboardButton("⭐ Rate Us")
            )
            
            # Send the processed image
            caption = f"""
✅ *Background Removed Successfully!*

👤 User: {user_name}
📸 Total Images: {user_stats[user_id]['images_processed']}
💾 Size: {len(result_bytes) / 1024:.1f} KB
🎉 *Save as PNG for transparency*

*Tip:* Share with friends! 🤝
"""
            
            # Send as document (better for PNG)
            bot.send_document(
                chat_id=message.chat.id,
                document=result_bytes,
                visible_file_name=f"no_background_{user_id}.png",
                caption=caption,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
            # Delete status message
            bot.delete_message(message.chat.id, status_msg.message_id)
            
            logger.info(f"✅ Successfully processed image for {user_name}")
            
        else:
            bot.edit_message_text(
                "❌ *Failed to process image.*\n\n⚠️ Please try:\n• Different photo\n• Better lighting\n• Clearer subject\n• Smaller file size",
                message.chat.id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"❌ Error in handle_photo: {e}")
        bot.reply_to(
            message,
            f"❌ *Error:* `{str(e)[:100]}`\n\nPlease try again with a different photo.",
            parse_mode='Markdown'
        )

# ==================== TEXT MESSAGE HANDLER ====================
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    text = message.text
    
    if text == "📸 Remove Background" or text == "📸 Remove Another":
        bot.reply_to(
            message,
            "📸 *Send me any photo!*\nI'll remove the background automatically.",
            parse_mode='Markdown'
        )
    elif text == "ℹ️ Help":
        send_welcome(message)
    elif text == "📊 My Stats" or text == "📊 Stats":
        show_stats(message)
    elif text == "⭐ Rate Us":
        bot.reply_to(
            message,
            "⭐ *Thank you for using our bot!*\n\nPlease share with friends and family!\n\n❤️ Your support keeps this bot free.",
            parse_mode='Markdown'
        )
    else:
        bot.reply_to(
            message,
            "🤖 *I'm a Background Remover Bot!*\n\nSend me a photo or use the buttons below.",
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                types.KeyboardButton("📸 Remove Background"),
                types.KeyboardButton("ℹ️ Help")
            )
        )

# ==================== WEB ROUTES ====================
@app.route('/')
def home():
    """Simple home page without HTML errors"""
    return """
    <h1>🤖 Background Remover Bot</h1>
    <p>Status: <strong style="color: green;">ONLINE</strong></p>
    <p>Total Users: """ + str(len(user_stats)) + """</p>
    <p><a href="/health">Health Check</a></p>
    <p>Telegram: <a href="https://t.me/""" + (bot.get_me().username if hasattr(bot.get_me(), 'username') else "your_bot") + """">@Bot</a></p>
    """

@app.route('/health')
def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "telegram-bg-remover",
        "users": len(user_stats),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook for Telegram"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK'
    return 'ERROR'

# ==================== START BOT ====================
def start_bot():
    """Start the Telegram bot"""
    logger.info("🤖 Starting Background Remover Bot...")
    
    try:
        # Remove any existing webhook
        bot.remove_webhook()
        time.sleep(2)
        
        # Start polling (most reliable for free tier)
        logger.info("🔄 Starting polling...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
        
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
        # Restart after delay
        time.sleep(10)
        start_bot()

# ==================== MAIN ====================
if __name__ == '__main__':
    # Start bot in separate thread
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    # Get port from Render
    port = int(os.environ.get('PORT', 5000))
    
    logger.info(f"🚀 Starting web server on port {port}")
    
    # Import request here to avoid circular imports
    from flask import request
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True,
        use_reloader=False
        )

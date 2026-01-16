import os
import io
import logging
from PIL import Image
from flask import Flask, request
import telebot
from telebot import types
import requests
from rembg import remove
import threading
import time

# ========== SETUP ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Bot token
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not set!")
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

bot = telebot.TeleBot(BOT_TOKEN)
user_data = {}

# ========== BG REMOVAL ==========
def remove_background(image_bytes):
    try:
        input_image = Image.open(io.BytesIO(image_bytes))
        
        # Resize if too large
        max_size = 1500
        if max(input_image.size) > max_size:
            ratio = max_size / max(input_image.size)
            new_size = (int(input_image.width * ratio), int(input_image.height * ratio))
            input_image = input_image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Remove background
        output_image = remove(
            input_image,
            alpha_matting=True,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=10,
            post_process_mask=True
        )
        
        # Ensure transparency
        if output_image.mode != 'RGBA':
            output_image = output_image.convert('RGBA')
        
        return output_image
    except Exception as e:
        logger.error(f"BG removal error: {e}")
        return None

# ========== BOT HANDLERS ==========
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    welcome_text = f"""
🎉 *Welcome {user_name}!* 🎉

🤖 *Background Remover Bot*

📸 *Features:*
• High Quality Background Removal
• PNG with Transparency
• Fast Processing
• Free to Use

⚡ *How to Use:*
1. Send me any photo
2. I'll remove background
3. Get transparent PNG

📎 *Supported:*
• Photos (JPG, PNG, WEBP)
• Good lighting works best

🌟 *Send a photo to start!*"""
    
    if user_id not in user_data:
        user_data[user_id] = {
            'name': user_name,
            'processed': 0,
            'first_seen': time.time()
        }
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=create_keyboard()
    )

@bot.message_handler(commands=['about'])
def about_bot(message):
    total_users = len(user_data)
    total_images = sum(user['processed'] for user in user_data.values())
    
    about_text = f"""
🤖 *About This Bot*

*Version:* 3.0
*Engine:* AI-Powered
*Users:* {total_users}
*Images Processed:* {total_images}

*Hosted on:* Render.com
*Status:* ✅ Running
"""
    bot.reply_to(message, about_text, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def user_stats(message):
    user_id = message.from_user.id
    
    if user_id in user_data:
        stats = user_data[user_id]
        stats_text = f"""
📊 *Your Stats*

👤 Name: {stats['name']}
📸 Processed: {stats['processed']} images
⏰ Active: {time.strftime('%Y-%m-%d %H:%M', time.localtime(stats.get('last_active', stats['first_seen'])))}
"""
    else:
        stats_text = "Send /start first!"
    
    bot.reply_to(message, stats_text, parse_mode='Markdown')

def create_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    keyboard.add(
        types.KeyboardButton("📸 Remove BG"),
        types.KeyboardButton("ℹ️ Help"),
        types.KeyboardButton("📊 Stats"),
        types.KeyboardButton("🛠 About")
    )
    return keyboard

# ========== PHOTO PROCESSING ==========
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        user_id = message.from_user.id
        
        # Update stats
        if user_id in user_data:
            user_data[user_id]['last_active'] = time.time()
        else:
            user_data[user_id] = {
                'name': message.from_user.first_name,
                'processed': 0,
                'first_seen': time.time(),
                'last_active': time.time()
            }
        
        # Send initial processing message
        processing_msg = bot.reply_to(
            message, 
            "🔄 *Downloading image...*", 
            parse_mode='Markdown'
        )
        
        # Get photo
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Update message to processing
        try:
            bot.edit_message_text(
                "🎨 *Removing background...*", 
                message.chat.id, 
                processing_msg.message_id,
                parse_mode='Markdown'
            )
        except:
            pass  # Skip if edit fails
        
        # Process image
        result_image = remove_background(downloaded_file)
        
        if result_image:
            # Convert to bytes
            img_byte_arr = io.BytesIO()
            result_image.save(img_byte_arr, format='PNG', optimize=True)
            img_byte_arr.seek(0)
            
            # Update user stats
            user_data[user_id]['processed'] += 1
            
            # Update message to final
            try:
                bot.edit_message_text(
                    "✅ *Sending result...*", 
                    message.chat.id, 
                    processing_msg.message_id,
                    parse_mode='Markdown'
                )
            except:
                pass
            
            # Send result
            caption = f"""
✅ *Background Removed!*

👤 User: {message.from_user.first_name}
📸 Total: {user_data[user_id]['processed']} images
💾 Size: {len(img_byte_arr.getvalue()) // 1024} KB
🎉 *Save as PNG for transparency*"""
            
            bot.send_document(
                message.chat.id,
                document=img_byte_arr,
                visible_file_name=f"no_bg_{user_id}.png",
                caption=caption,
                parse_mode='Markdown',
                reply_markup=create_keyboard()
            )
            
            # Delete processing message
            try:
                bot.delete_message(message.chat.id, processing_msg.message_id)
            except:
                pass
            
        else:
            bot.edit_message_text(
                "❌ *Failed to process image*\nTry another photo.", 
                message.chat.id, 
                processing_msg.message_id,
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error: {e}")
        bot.reply_to(message, f"❌ Error: {str(e)[:200]}")

# ========== TEXT MESSAGES ==========
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    text = message.text
    
    if text == "📸 Remove BG":
        bot.reply_to(message, "📸 *Send me a photo!*", parse_mode='Markdown')
    elif text == "ℹ️ Help":
        send_welcome(message)
    elif text == "📊 Stats":
        user_stats(message)
    elif text == "🛠 About":
        about_bot(message)
    else:
        bot.reply_to(
            message, 
            "🤖 *Send a photo or use buttons below!*", 
            parse_mode='Markdown',
            reply_markup=create_keyboard()
        )

# ========== WEB ROUTES ==========
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>BG Remover Bot</title>
        <style>
            body { font-family: Arial; text-align: center; padding: 50px; }
            h1 { color: #0088cc; }
            .status { background: green; color: white; padding: 10px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>🤖 Background Remover Bot</h1>
        <p>Running on Render.com</p>
        <div class="status">🟢 STATUS: ONLINE</div>
        <p>Users: {}</p>
        <p><a href="/health">Health Check</a></p>
    </body>
    </html>
    """.format(len(user_data))

@app.route('/health')
def health():
    return {"status": "healthy", "users": len(user_data), "timestamp": time.time()}

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK'
    return 'ERROR'

# ========== START BOT ==========
def run_bot():
    """Run bot with polling"""
    logger.info("🤖 Starting bot...")
    
    # Remove webhook and use polling
    bot.remove_webhook()
    time.sleep(2)
    
    # Start polling
    logger.info("🔄 Starting polling...")
    bot.polling(none_stop=True, interval=3, timeout=30)
    
    logger.error("❌ Polling stopped!")

# ========== MAIN ==========
if __name__ == '__main__':
    # Start bot in thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Get port from Render
    port = int(os.environ.get('PORT', 5000))
    
    logger.info(f"🚀 Starting Flask on port {port}")
    
    # Run Flask
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True,
        use_reloader=False
          )

import os
import io
import logging
from PIL import Image
import asyncio
from flask import Flask, request
import telebot
from telebot import types
import requests
from rembg import remove
import cv2
import numpy as np
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app for Render port detection
app = Flask(__name__)

# Bot token (Render Environment Variable se)
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
bot = telebot.TeleBot(BOT_TOKEN)

# Store user data
user_data = {}

# Enhanced BG Removal with quality improvement
def enhance_bg_removal(image_bytes):
    try:
        # First pass with rembg
        input_image = Image.open(io.BytesIO(image_bytes))
        
        # Resize for better quality (max 2000px while maintaining aspect ratio)
        max_size = 2000
        ratio = min(max_size / input_image.width, max_size / input_image.height)
        if ratio < 1:
            new_size = (int(input_image.width * ratio), int(input_image.height * ratio))
            input_image = input_image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Remove background
        output_image = remove(
            input_image,
            alpha_matting=True,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=10,
            alpha_matting_erode_structure_size=10,
            alpha_matting_base_size=1000,
            post_process_mask=True
        )
        
        # Convert to RGBA for transparency
        if output_image.mode != 'RGBA':
            output_image = output_image.convert('RGBA')
        
        # Edge refinement using OpenCV
        cv_image = cv2.cvtColor(np.array(output_image), cv2.COLOR_RGBA2BGRA)
        
        # Apply Gaussian blur to alpha channel for smooth edges
        alpha = cv_image[:, :, 3]
        alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
        cv_image[:, :, 3] = alpha
        
        # Convert back to PIL
        enhanced_image = Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGRA2RGBA))
        
        return enhanced_image
        
    except Exception as e:
        logger.error(f"Error in bg removal: {e}")
        return None

# Welcome message handler
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    welcome_text = f"""
🎉 **Welcome {user_name}!** 🎉

🤖 **Background Remover Bot**

📸 **Meri Features:**
• High Quality Background Removal
• PNG Format with Transparency
• Fast Processing
• Support for Photos & Documents

⚡ **How to Use:**
1. Simply send me any photo
2. I'll remove the background automatically
3. You'll get transparent PNG image

📎 **You can send:**
• Photos (compressed/uncompressed)
• Document images (PNG, JPG, WEBP)
• Multiple photos at once

🛠 **Commands:**
/start - Show this welcome message
/help - Get help
/about - About this bot
/stats - Your usage statistics

🔧 **Tips for Best Results:**
• Good lighting photos work best
• Clear subject edges
• Avoid similar background colors

🌟 **Enjoy using the bot!**"""
    
    # Send welcome message with photo
    try:
        # Send welcome image
        welcome_img_url = "https://raw.githubusercontent.com/danielgatis/rembg/main/images/icon.png"
        img_data = requests.get(welcome_img_url).content
        
        bot.send_photo(
            message.chat.id,
            img_data,
            caption=welcome_text,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        
        # Initialize user stats
        if user_id not in user_data:
            user_data[user_id] = {
                'name': user_name,
                'images_processed': 0,
                'first_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'last_active': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        logger.info(f"New user: {user_name} (ID: {user_id})")
        
    except Exception as e:
        logger.error(f"Welcome error: {e}")
        bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['about'])
def about_bot(message):
    about_text = """
🤖 **About This Bot**

**Version:** 2.0 High Quality
**Engine:** U2-Net + OpenCV Enhancement
**Features:** 
• Advanced Alpha Matting
• Edge Refinement
• Smart Resizing
• Multi-format Support

🛠 **Technology Stack:**
• Python 3.10
• Rembg Library
• OpenCV for enhancement
• Flask server

📊 **Statistics:**
• Total Users: {}
• Images Processed: {}

❤️ **Open Source Project**
For feedback: Contact @YourUsername""".format(len(user_data), sum([u['images_processed'] for u in user_data.values()]))
    
    bot.reply_to(message, about_text, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def user_stats(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    if user_id in user_data:
        stats = user_data[user_id]
        stats_text = f"""
📊 **Your Statistics**

👤 **User:** {user_name}
🆔 **ID:** `{user_id}`
📸 **Images Processed:** {stats['images_processed']}
📅 **First Seen:** {stats['first_seen']}
⏰ **Last Active:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

🎯 **Rank:** {'⭐' * min(5, stats['images_processed'] // 10 + 1)}"""
    else:
        stats_text = "No statistics found. Send /start first!"
    
    bot.reply_to(message, stats_text, parse_mode='Markdown')

def create_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("📸 Remove BG")
    btn2 = types.KeyboardButton("ℹ️ Help")
    btn3 = types.KeyboardButton("📊 Stats")
    btn4 = types.KeyboardButton("🛠 About")
    keyboard.add(btn1, btn2, btn3, btn4)
    return keyboard

# Handle all photos and documents
@bot.message_handler(content_types=['photo', 'document'])
def handle_docs_photos(message):
    try:
        user_id = message.from_user.id
        
        # Update last active
        if user_id in user_data:
            user_data[user_id]['last_active'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Send processing message
        processing_msg = bot.reply_to(
            message, 
            "🔄 Processing your image...\n\n⚡ _High quality removal in progress_", 
            parse_mode='Markdown'
        )
        
        file_id = None
        
        # Get file based on content type
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
        elif message.content_type == 'document':
            if message.document.mime_type.startswith('image/'):
                file_id = message.document.file_id
            else:
                bot.reply_to(message, "❌ Please send only image files!")
                return
        
        if not file_id:
            bot.reply_to(message, "❌ Could not get image!")
            return
        
        # Download file
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Update processing message
        bot.edit_message_text(
            "🎨 Removing background with enhanced algorithm...", 
            message.chat.id, 
            processing_msg.message_id
        )
        
        # Process image
        result_image = enhance_bg_removal(downloaded_file)
        
        if result_image:
            # Save to bytes
            img_byte_arr = io.BytesIO()
            result_image.save(img_byte_arr, format='PNG', optimize=True)
            img_byte_arr.seek(0)
            
            # Update stats
            if user_id in user_data:
                user_data[user_id]['images_processed'] += 1
            
            # Send result
            bot.edit_message_text(
                "✅ Background removed successfully!\n📤 Sending image...", 
                message.chat.id, 
                processing_msg.message_id
            )
            
            # Send image with caption
            caption = f"""
✅ **Background Removed Successfully!**

👤 User: {message.from_user.first_name}
📊 Processed Images: {user_data.get(user_id, {}).get('images_processed', 1)}
🖼 Format: PNG with Transparency
💾 Size: {len(img_byte_arr.getvalue()) // 1024} KB

✨ _Tip: Save image for transparent background_"""
            
            bot.send_document(
                message.chat.id,
                (f"bg_removed_{message.message_id}.png", img_byte_arr),
                caption=caption,
                parse_mode='Markdown',
                reply_markup=create_main_keyboard()
            )
            
            # Delete processing message
            bot.delete_message(message.chat.id, processing_msg.message_id)
            
        else:
            bot.edit_message_text(
                "❌ Failed to process image. Please try with a different image.", 
                message.chat.id, 
                processing_msg.message_id
            )
            
    except Exception as e:
        logger.error(f"Processing error: {e}")
        bot.reply_to(message, f"❌ Error: {str(e)}")

# Text message handler
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if message.text == "📸 Remove BG":
        bot.reply_to(message, "📸 Please send me an image to remove background!")
    elif message.text == "ℹ️ Help":
        send_welcome(message)
    elif message.text == "📊 Stats":
        user_stats(message)
    elif message.text == "🛠 About":
        about_bot(message)
    else:
        bot.reply_to(
            message, 
            "🤖 Send me an image or use the buttons below!",
            reply_markup=create_main_keyboard()
        )

# Flask routes for Render
@app.route('/')
def home():
    return "🤖 Background Remover Bot is Running!"

@app.route('/health')
def health():
    return {"status": "healthy", "users": len(user_data)}

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Bad Request', 400

# Start bot with polling (for Render)
def run_bot():
    logger.info("Starting bot...")
    
    # Remove previous webhook
    bot.remove_webhook()
    
    # Get Render port
    port = int(os.environ.get("PORT", 5000))
    
    # Set webhook for Render
    render_domain = os.environ.get('RENDER_EXTERNAL_URL')
    if render_domain:
        webhook_url = f"{render_domain}/webhook"
        bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    else:
        # Use polling as fallback
        logger.info("Using polling method")
        bot.polling(none_stop=True, timeout=60)

if __name__ == '__main__':
    # Run Flask app
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting server on port {port}")
    
    # Run in thread
    from threading import Thread
    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Run Flask
    app.run(host='0.0.0.0', port=port, debug=False)

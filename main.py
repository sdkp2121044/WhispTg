import os
import io
import logging
from PIL import Image
from flask import Flask, request
import telebot
from telebot import types
import requests
import threading
import time
import base64
from io import BytesIO

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
REMOVE_BG_API_KEY = os.environ.get('REMOVE_BG_API_KEY')  # Your API key from remove.bg

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found!")
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

bot = telebot.TeleBot(BOT_TOKEN)

# Store user data and preferences
user_stats = {}
user_pending_images = {}  # Store temp image data for color selection

# Color options with emoji and hex codes
COLOR_OPTIONS = {
    "🔴 Red": "#FF0000",
    "🟠 Orange": "#FFA500", 
    "🟡 Yellow": "#FFFF00",
    "🟢 Green": "#00FF00",
    "🔵 Blue": "#0000FF",
    "🟣 Purple": "#800080",
    "🟤 Brown": "#A52A2A",
    "⚫ Black": "#000000",
    "⚪ White": "#FFFFFF",
    "💗 Pink": "#FFC0CB",
    "💙 Sky Blue": "#87CEEB",
    "💚 Light Green": "#90EE90",
    "🤎 Light Brown": "#D2691E",
    "💛 Light Yellow": "#FFFFE0",
    "🧡 Light Orange": "#FFD580",
    "💜 Light Purple": "#D8BFD8",
    "🩶 Gray": "#808080",
    "🌈 Gradient": "gradient",
    "✨ Transparent": "transparent"
}

# ==================== BACKGROUND REMOVAL FUNCTIONS ====================
def remove_background_api(image_bytes):
    """Use remove.bg API for high quality removal"""
    try:
        if not REMOVE_BG_API_KEY:
            logger.error("REMOVE_BG_API_KEY not set!")
            return None
            
        # Convert image to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Use remove.bg API
        api_url = "https://api.remove.bg/v1.0/removebg"
        
        headers = {
            'X-Api-Key': REMOVE_BG_API_KEY,
            'Content-Type': 'application/json'
        }
        
        data = {
            'image_file_b64': image_base64,
            'size': 'auto',
            'format': 'png',
            'type': 'auto'
        }
        
        response = requests.post(api_url, json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            logger.info("✅ Background removed via API successfully")
            return response.content
        else:
            logger.error(f"API Error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"API call error: {e}")
        return None

def apply_background_color(transparent_image_bytes, color_choice):
    """Apply selected background color to transparent image"""
    try:
        # Open transparent image
        transparent_img = Image.open(BytesIO(transparent_image_bytes)).convert('RGBA')
        
        if color_choice == "transparent":
            # Return as is for transparent
            output = BytesIO()
            transparent_img.save(output, format='PNG')
            return output.getvalue()
        
        elif color_choice == "gradient":
            # Create gradient background
            width, height = transparent_img.size
            gradient = Image.new('RGBA', (width, height))
            
            # Create gradient from left to right
            for x in range(width):
                # Color transition
                r = int((x / width) * 255)
                g = int(((width - x) / width) * 255)
                b = 128
                color = (r, g, b, 255)
                
                for y in range(height):
                    gradient.putpixel((x, y), color)
            
            # Composite image over gradient
            result = Image.alpha_composite(gradient, transparent_img)
            
        else:
            # Solid color background
            from PIL import ImageColor
            color_rgb = ImageColor.getrgb(color_choice)
            color_rgba = color_rgb + (255,)  # Add alpha channel
            
            # Create colored background
            background = Image.new('RGBA', transparent_img.size, color_rgba)
            
            # Composite image over colored background
            result = Image.alpha_composite(background, transparent_img)
        
        # Save to bytes
        output = BytesIO()
        result.save(output, format='PNG')
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"Color apply error: {e}")
        return transparent_image_bytes  # Return original if error

def remove_background_local(image_bytes):
    """Local fallback if API fails"""
    try:
        # Try to use rembg if available
        try:
            from rembg import remove
            input_image = Image.open(BytesIO(image_bytes))
            
            # Resize for faster processing
            max_size = 800
            if max(input_image.size) > max_size:
                ratio = max_size / max(input_image.size)
                new_size = (int(input_image.width * ratio), int(input_image.height * ratio))
                input_image = input_image.resize(new_size, Image.Resampling.LANCZOS)
            
            output_image = remove(input_image)
            
            # Save to bytes
            img_byte_arr = BytesIO()
            output_image.save(img_byte_arr, format='PNG')
            return img_byte_arr.getvalue()
            
        except ImportError:
            logger.warning("rembg not available")
            return None
            
    except Exception as e:
        logger.error(f"Local removal error: {e}")
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

🤖 *Background Remover Bot Pro*

🎨 *Now with Color Options!*
• Transparent PNG
• Solid Colors
• Gradient Backgrounds
• High Quality Removal

🚀 *How to use:*
1️⃣ Send me any photo
2️⃣ Choose background option
3️⃣ Get your customized image!

⚡ *Features:*
✅ 20+ Background Colors
✅ Gradient Effects
✅ Fast Processing
✅ Free Service

📸 *Tips:*
• Clear photos work best
• Good lighting
• Single subject

*Send a photo to begin!* 📸
"""
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        types.KeyboardButton("📸 Remove Background"),
        types.KeyboardButton("🎨 Color Options"),
        types.KeyboardButton("📊 My Stats"),
        types.KeyboardButton("ℹ️ Help")
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=keyboard
    )
    
    logger.info(f"New user: {user_name} (ID: {user_id})")

@bot.message_handler(commands=['colors'])
def show_colors(message):
    """Show all available color options"""
    colors_text = "🎨 *Available Background Colors:*\n\n"
    
    # Group colors in rows
    colors_list = list(COLOR_OPTIONS.keys())
    for i in range(0, len(colors_list), 3):
        row = colors_list[i:i+3]
        colors_text += " • " + "  ".join(row) + "\n"
    
    colors_text += "\n*How to use:*\n1. Send a photo\n2. Choose color\n3. Get result!"
    
    bot.send_message(message.chat.id, colors_text, parse_mode='Markdown')

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

🎨 *Favorite Features:*
• Transparent Backgrounds
• Color Options
• Gradient Effects

🌟 Keep exploring colors!
"""
    else:
        stats_text = "Send /start first to begin!"
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

@bot.message_handler(commands=['about'])
def about_bot(message):
    total_users = len(user_stats)
    total_images = sum(user['images_processed'] for user in user_stats.values())
    
    about_text = f"""
🤖 *About This Bot*

*Version:* 5.0 Color Edition
*Status:* ✅ Online
*Users:* {total_users}
*Images:* {total_images}
*Colors:* {len(COLOR_OPTIONS)} options

🎨 *Features:*
• Transparent Backgrounds
• Solid Color Fills
• Gradient Effects
• High Quality AI

💡 *Pro Tip:* Try the gradient option!

❤️ *Free Service - Enjoy!*
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
        
        # Remove background using API
        transparent_bytes = remove_background_api(downloaded_file)
        
        if not transparent_bytes:
            # Fallback to local method
            bot.edit_message_text(
                "⚡ *Trying alternative method...*",
                message.chat.id,
                status_msg.message_id,
                parse_mode='Markdown'
            )
            transparent_bytes = remove_background_local(downloaded_file)
        
        if transparent_bytes:
            # Store transparent image for this user
            user_pending_images[user_id] = transparent_bytes
            
            # Delete processing message
            bot.delete_message(message.chat.id, status_msg.message_id)
            
            # Ask for color choice
            ask_for_color(message.chat.id, user_id)
            
        else:
            bot.edit_message_text(
                "❌ *Failed to remove background.*\n\n⚠️ Please try:\n• Different photo\n• Better lighting\n• Clearer subject",
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

def ask_for_color(chat_id, user_id):
    """Ask user to choose background color"""
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    
    # Add color buttons in rows
    colors = list(COLOR_OPTIONS.keys())
    
    # First row: Popular options
    row1 = []
    for color in ["✨ Transparent", "🔴 Red", "🔵 Blue", "🟢 Green", "⚫ Black", "⚪ White"]:
        row1.append(types.InlineKeyboardButton(color, callback_data=f"color_{color}"))
    
    # Add rows
    keyboard.row(*row1[:3])
    keyboard.row(*row1[3:])
    
    # More colors
    row2 = []
    for color in ["🟠 Orange", "🟡 Yellow", "🟣 Purple", "🟤 Brown", "💗 Pink", "💙 Sky Blue"]:
        row2.append(types.InlineKeyboardButton(color, callback_data=f"color_{color}"))
    
    keyboard.row(*row2[:3])
    keyboard.row(*row2[3:])
    
    # Last row with gradient
    keyboard.row(
        types.InlineKeyboardButton("🌈 Gradient", callback_data="color_🌈 Gradient"),
        types.InlineKeyboardButton("🎨 More Colors", callback_data="more_colors")
    )
    
    bot.send_message(
        chat_id,
        "🎨 *Choose Background Color:*\n\n*Popular:* Transparent, Red, Blue, Green\n*Or try:* Gradient, Pink, Sky Blue!\n\nSelect one option below:",
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('color_'))
def handle_color_choice(call):
    """Handle color selection"""
    try:
        user_id = call.from_user.id
        color_name = call.data.replace('color_', '', 1)
        
        if color_name == "more_colors":
            # Show all colors
            show_all_colors(call.message.chat.id)
            bot.answer_callback_query(call.id, "Showing all colors...")
            return
        
        # Send processing message
        processing_msg = bot.send_message(
            call.message.chat.id,
            f"🔄 *Applying {color_name} background...*",
            parse_mode='Markdown'
        )
        
        # Get transparent image for this user
        if user_id in user_pending_images:
            transparent_bytes = user_pending_images[user_id]
            
            # Apply selected color
            color_hex = COLOR_OPTIONS.get(color_name, "#FFFFFF")
            final_image = apply_background_color(transparent_bytes, color_hex)
            
            if final_image:
                # Update user stats
                if user_id in user_stats:
                    user_stats[user_id]['images_processed'] += 1
                
                # Delete processing message
                bot.delete_message(call.message.chat.id, processing_msg.message_id)
                
                # Prepare result caption
                if color_name == "✨ Transparent":
                    bg_info = "Transparent Background"
                elif color_name == "🌈 Gradient":
                    bg_info = "Rainbow Gradient Background"
                else:
                    bg_info = f"{color_name} Background"
                
                caption = f"""
✅ *Background Applied Successfully!*

🎨 *Choice:* {bg_info}
👤 *User:* {call.from_user.first_name}
📸 *Total:* {user_stats.get(user_id, {}).get('images_processed', 1)} images
💾 *Format:* PNG

*Tip:* Save image and share! 📤
"""
                
                # Send the final image
                bot.send_document(
                    chat_id=call.message.chat.id,
                    document=final_image,
                    visible_file_name=f"{color_name.replace(' ', '_')}_background.png",
                    caption=caption,
                    parse_mode='Markdown'
                )
                
                # Send keyboard for next action
                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
                keyboard.add(
                    types.KeyboardButton("📸 Remove Another"),
                    types.KeyboardButton("🎨 Try Different Color"),
                    types.KeyboardButton("📊 My Stats"),
                    types.KeyboardButton("⭐ Rate Us")
                )
                
                bot.send_message(
                    call.message.chat.id,
                    "🌟 *What would you like to do next?*",
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
                
                # Clean up stored image
                if user_id in user_pending_images:
                    del user_pending_images[user_id]
                
                bot.answer_callback_query(call.id, f"Applied {color_name}!")
                
            else:
                bot.edit_message_text(
                    "❌ *Failed to apply color.*\nPlease try again.",
                    call.message.chat.id,
                    processing_msg.message_id,
                    parse_mode='Markdown'
                )
        else:
            bot.answer_callback_query(call.id, "❌ Image expired. Send a new photo.")
            
    except Exception as e:
        logger.error(f"Color choice error: {e}")
        bot.answer_callback_query(call.id, "❌ Error occurred!")

def show_all_colors(chat_id):
    """Show all color options in a message"""
    colors_text = "🎨 *All Available Colors:*\n\n"
    
    # Create color grid
    colors_grid = []
    current_row = []
    
    for i, (color_name, color_hex) in enumerate(COLOR_OPTIONS.items()):
        current_row.append(color_name)
        
        if (i + 1) % 3 == 0 or i == len(COLOR_OPTIONS) - 1:
            colors_grid.append(current_row)
            current_row = []
    
    # Format as text
    for row in colors_grid:
        colors_text += " • " + " | ".join(row) + "\n"
    
    colors_text += "\n*To use:* Send photo → Choose color → Get result!"
    
    bot.send_message(chat_id, colors_text, parse_mode='Markdown')

# ==================== TEXT MESSAGE HANDLER ====================
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    text = message.text
    
    if text == "📸 Remove Background" or text == "📸 Remove Another":
        bot.reply_to(
            message,
            "📸 *Send me any photo!*\nI'll remove background and let you choose color.",
            parse_mode='Markdown'
        )
    
    elif text == "🎨 Color Options" or text == "🎨 Try Different Color":
        show_colors(message)
    
    elif text == "📊 My Stats" or text == "📊 Stats":
        show_stats(message)
    
    elif text == "ℹ️ Help":
        send_welcome(message)
    
    elif text == "⭐ Rate Us":
        bot.reply_to(
            message,
            "⭐ *Thank you for using our bot!*\n\nIf you like it:\n1. Share with friends\n2. Rate on Telegram\n3. Keep using!\n\n❤️ Your support keeps this bot free.",
            parse_mode='Markdown'
        )
    
    else:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        keyboard.add(
            types.KeyboardButton("📸 Remove Background"),
            types.KeyboardButton("🎨 Color Options"),
            types.KeyboardButton("📊 My Stats"),
            types.KeyboardButton("ℹ️ Help")
        )
        
        bot.reply_to(
            message,
            "🤖 *I'm a Background Remover Bot with Color Options!*\n\n📸 Send a photo → 🎨 Choose color → ✅ Get result!\n\nUse buttons below:",
            parse_mode='Markdown',
            reply_markup=keyboard
        )

# ==================== WEB ROUTES ====================
@app.route('/')
def home():
    total_users = len(user_stats)
    total_images = sum(user['images_processed'] for user in user_stats.values())
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>BG Remover Bot Pro</title>
        <style>
            body {{ 
                font-family: Arial, sans-serif; 
                text-align: center; 
                padding: 50px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }}
            .container {{ 
                background: rgba(255,255,255,0.1); 
                padding: 30px; 
                border-radius: 15px; 
                backdrop-filter: blur(10px);
                max-width: 800px;
                margin: 0 auto;
            }}
            h1 {{ color: white; font-size: 2.5em; }}
            .status {{ 
                background: #4CAF50; 
                color: white; 
                padding: 10px 20px; 
                border-radius: 25px; 
                display: inline-block; 
                margin: 20px 0;
                font-size: 1.2em;
            }}
            .stats {{ 
                display: flex; 
                justify-content: center; 
                gap: 30px; 
                margin: 20px 0;
            }}
            .stat-box {{ 
                background: rgba(255,255,255,0.2); 
                padding: 15px; 
                border-radius: 10px;
                min-width: 150px;
            }}
            .color-grid {{
                display: grid;
                grid-template-columns: repeat(5, 1fr);
                gap: 10px;
                margin: 20px 0;
            }}
            .color-box {{
                padding: 10px;
                border-radius: 5px;
                font-size: 0.9em;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Background Remover Bot Pro</h1>
            <p>Advanced Telegram bot with color options</p>
            
            <div class="status">🟢 STATUS: ONLINE & RUNNING</div>
            
            <div class="stats">
                <div class="stat-box">
                    <h3>👥 Users</h3>
                    <p>{total_users}</p>
                </div>
                <div class="stat-box">
                    <h3>📸 Images</h3>
                    <p>{total_images}</p>
                </div>
                <div class="stat-box">
                    <h3>🎨 Colors</h3>
                    <p>{len(COLOR_OPTIONS)}</p>
                </div>
            </div>
            
            <h3>Available Colors:</h3>
            <div style="color: white; text-align: left; max-width: 600px; margin: 0 auto;">
                {', '.join(list(COLOR_OPTIONS.keys())[:15])}...
            </div>
            
            <p><strong>Features:</strong> Transparent • Solid Colors • Gradient • High Quality</p>
            
            <p><a href="/health" style="color: #FFD700; font-weight: bold;">Health Check</a></p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "telegram-bg-remover-pro",
        "users": len(user_stats),
        "images_processed": sum(user['images_processed'] for user in user_stats.values()),
        "colors_available": len(COLOR_OPTIONS),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

# ==================== START BOT ====================
def start_bot():
    """Start the Telegram bot"""
    logger.info("🤖 Starting Background Remover Bot Pro...")
    
    try:
        # Remove any existing webhook
        bot.remove_webhook()
        time.sleep(2)
        
        # Start polling (most reliable for free tier)
        logger.info("🔄 Starting polling with color options...")
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
    logger.info(f"🎨 Color options loaded: {len(COLOR_OPTIONS)}")
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True,
        use_reloader=False
    )
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot settings
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
    
    # Social
    CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '@idxempire_updates')
    GROUP_USERNAME = os.getenv('GROUP_USERNAME', '@idxempire_support')
    
    # Watermark
    WATERMARK_TEXT = os.getenv('WATERMARK_TEXT', 'idx Empire')
    WATERMARK_OPACITY = float(os.getenv('WATERMARK_OPACITY', 0.3))
    
    # Limits
    DAILY_LIMIT = int(os.getenv('DAILY_LIMIT', 50))
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 10))  # MB
    
    # Render
    PORT = int(os.getenv('PORT', 8080))

import os
import json
import logging
from datetime import datetime
from telethon import Button

logger = logging.getLogger(__name__)

class UserManager:
    def __init__(self):
        self.recent_users = {}
        self.DATA_DIR = "data"
        os.makedirs(self.DATA_DIR, exist_ok=True)
        self.RECENT_USERS_FILE = os.path.join(self.DATA_DIR, "recent_users.json")
    
    def load_data(self):
        """Load recent users from file"""
        try:
            if os.path.exists(self.RECENT_USERS_FILE):
                with open(self.RECENT_USERS_FILE, 'r', encoding='utf-8') as f:
                    self.recent_users = json.load(f)
                logger.info(f"✅ Loaded {len(self.recent_users)} recent users")
        except Exception as e:
            logger.error(f"❌ Error loading data: {e}")
            self.recent_users = {}
    
    def save_data(self):
        """Save recent users to file"""
        try:
            with open(self.RECENT_USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.recent_users, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ Error saving data: {e}")
    
    def add_to_recent_users(self, sender_id, target_user_id, target_username=None, target_first_name=None):
        """Add user to recent users list"""
        try:
            user_key = str(target_user_id)
            self.recent_users[user_key] = {
                'user_id': target_user_id,
                'username': target_username,
                'first_name': target_first_name,
                'last_used': datetime.now().isoformat()
            }
            
            # Keep only last 10 users
            if len(self.recent_users) > 10:
                # Remove oldest entry
                sorted_keys = sorted(
                    self.recent_users.keys(),
                    key=lambda k: self.recent_users[k].get('last_used', '')
                )
                for key in sorted_keys[:-10]:
                    del self.recent_users[key]
            
            self.save_data()
            logger.info(f"✅ Added user {target_user_id} to recent users")
        except Exception as e:
            logger.error(f"Error adding to recent users: {e}")
    
    def get_recent_users_buttons(self, user_id):
        """Get recent users buttons for inline suggestions"""
        try:
            if not self.recent_users:
                return []
            
            sorted_users = sorted(
                self.recent_users.items(),
                key=lambda x: x[1].get('last_used', ''),
                reverse=True
            )
            
            buttons = []
            for user_key, user_data in sorted_users[:5]:
                username = user_data.get('username')
                first_name = user_data.get('first_name', 'User')
                
                if username:
                    display_text = f"@{username}"
                    query_text = f"@{username}"
                else:
                    display_text = first_name
                    query_text = first_name
                
                if len(display_text) > 15:
                    display_text = display_text[:12] + "..."
                
                buttons.append([Button.switch_inline(
                    f"🔒 {display_text}",
                    query=query_text
                )])
            
            return buttons
        except Exception as e:
            logger.error(f"Error getting recent users buttons: {e}")
            return []

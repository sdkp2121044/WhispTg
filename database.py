# database.py
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# Import config
from config import DATA_DIR, WHISPER_HISTORY_FILE, RECENT_RECIPIENTS_FILE

# Global storage
user_whisper_history = defaultdict(list)  # Complete history
user_recent_recipients = {}               # Recent recipients
user_entity_cache = {}                    # User entity cache
user_cooldown = {}                        # Cooldown tracking
messages_db = {}                          # Active messages

def load_data():
    """Load all data from files"""
    global user_whisper_history, user_recent_recipients
    
    try:
        # Create data directory if not exists
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # Load complete whisper history
        if os.path.exists(WHISPER_HISTORY_FILE):
            with open(WHISPER_HISTORY_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                user_whisper_history = defaultdict(list)
                for user_id_str, history in loaded.items():
                    user_whisper_history[int(user_id_str)] = history
            logger.info(f"✅ Loaded complete history for {len(user_whisper_history)} users")
        
        # Load recent recipients
        if os.path.exists(RECENT_RECIPIENTS_FILE):
            with open(RECENT_RECIPIENTS_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                user_recent_recipients = {}
                for user_id_str, recipients in loaded.items():
                    user_recent_recipients[int(user_id_str)] = recipients
            logger.info(f"✅ Loaded recent recipients for {len(user_recent_recipients)} users")
            
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        user_whisper_history = defaultdict(list)
        user_recent_recipients = {}

def save_data():
    """Save all data to files"""
    try:
        # Save complete whisper history
        with open(WHISPER_HISTORY_FILE, 'w', encoding='utf-8') as f:
            save_dict = {str(k): v for k, v in user_whisper_history.items()}
            json.dump(save_dict, f, indent=2, ensure_ascii=False)
        
        # Save recent recipients
        with open(RECENT_RECIPIENTS_FILE, 'w', encoding='utf-8') as f:
            save_dict = {str(k): v for k, v in user_recent_recipients.items()}
            json.dump(save_dict, f, indent=2, ensure_ascii=False)
            
        logger.info("💾 Data saved successfully")
    except Exception as e:
        logger.error(f"❌ Error saving data: {e}")

def add_to_whisper_history(user_id, whisper_data):
    """Add a whisper to user's complete history"""
    try:
        # Add to complete history
        whisper_entry = {
            'timestamp': datetime.now().isoformat(),
            'recipient_id': whisper_data['recipient_id'],
            'recipient_name': whisper_data['recipient_name'],
            'recipient_username': whisper_data.get('recipient_username'),
            'message': whisper_data['message'],
            'message_preview': whisper_data['message'][:30] + ('...' if len(whisper_data['message']) > 30 else '')
        }
        
        user_whisper_history[user_id].insert(0, whisper_entry)
        
        # Keep last 50 whispers maximum
        if len(user_whisper_history[user_id]) > 50:
            user_whisper_history[user_id] = user_whisper_history[user_id][:50]
        
        # Update recent recipients
        if user_id not in user_recent_recipients:
            user_recent_recipients[user_id] = []
        
        recipient_id = whisper_data['recipient_id']
        recipient_name = whisper_data['recipient_name']
        recipient_username = whisper_data.get('recipient_username')
        
        # Check if recipient already exists
        recipient_found = False
        for i, recipient in enumerate(user_recent_recipients[user_id]):
            if recipient.get('id') == recipient_id:
                # Update existing recipient
                recipient['timestamp'] = datetime.now().isoformat()
                recipient['name'] = recipient_name
                recipient['username'] = recipient_username
                recipient['count'] = recipient.get('count', 0) + 1
                # Move to top
                user_recent_recipients[user_id].insert(0, user_recent_recipients[user_id].pop(i))
                recipient_found = True
                break
        
        if not recipient_found:
            # Add new recipient at the beginning
            new_recipient = {
                'id': recipient_id,
                'name': recipient_name,
                'username': recipient_username,
                'timestamp': datetime.now().isoformat(),
                'count': 1
            }
            user_recent_recipients[user_id].insert(0, new_recipient)
        
        # Keep only last 20 unique recipients
        if len(user_recent_recipients[user_id]) > 20:
            user_recent_recipients[user_id] = user_recent_recipients[user_id][:20]
        
        save_data()
        
    except Exception as e:
        logger.error(f"Error adding to whisper history: {e}")

def get_user_stats(user_id):
    """Get user's whisper statistics"""
    try:
        total_whispers = len(user_whisper_history.get(user_id, []))
        
        # Count unique recipients
        unique_recipients = set()
        for whisper in user_whisper_history.get(user_id, []):
            unique_recipients.add(whisper['recipient_id'])
        
        # Recent activity (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        recent_whispers = 0
        for whisper in user_whisper_history.get(user_id, []):
            whisper_time = datetime.fromisoformat(whisper['timestamp'])
            if whisper_time > week_ago:
                recent_whispers += 1
        
        return {
            'total_whispers': total_whispers,
            'unique_recipients': len(unique_recipients),
            'recent_whispers': recent_whispers,
            'recent_recipients_count': len(user_recent_recipients.get(user_id, []))
        }
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return {'total_whispers': 0, 'unique_recipients': 0, 'recent_whispers': 0, 'recent_recipients_count': 0}

def clear_user_history(user_id):
    """Clear user's complete history"""
    try:
        total_whispers = len(user_whisper_history.get(user_id, []))
        total_recent = len(user_recent_recipients.get(user_id, []))
        
        if user_id in user_whisper_history:
            del user_whisper_history[user_id]
        if user_id in user_recent_recipients:
            del user_recent_recipients[user_id]
        
        save_data()
        return total_whispers, total_recent
        
    except Exception as e:
        logger.error(f"Error clearing user history: {e}")
        return 0, 0

def clear_user_recent_only(user_id):
    """Clear only recent recipients"""
    try:
        total_recent = len(user_recent_recipients.get(user_id, []))
        if user_id in user_recent_recipients:
            del user_recent_recipients[user_id]
            save_data()
        return total_recent
    except Exception as e:
        logger.error(f"Error clearing recent recipients: {e}")
        return 0

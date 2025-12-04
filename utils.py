# utils.py
import re
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Import database
from database import user_entity_cache, user_recent_recipients

def is_cooldown(user_id):
    """Check if user is in cooldown"""
    from database import user_cooldown
    
    now = datetime.now().timestamp()
    user_id_str = str(user_id)
    
    if user_id_str in user_cooldown:
        if now - user_cooldown[user_id_str] < 1:
            return True
    
    user_cooldown[user_id_str] = now
    return False

def extract_target_from_text(text):
    """Smart extraction of target user from text"""
    text = text.strip()
    
    # Pattern 1: Username at end with @
    username_pattern = r'(.*?)\s*@([a-zA-Z][a-zA-Z0-9_]{3,30})\s*$'
    match = re.match(username_pattern, text, re.IGNORECASE)
    if match:
        message_text = match.group(1).strip()
        target_user = match.group(2)
        return target_user, message_text, 'username'
    
    # Pattern 2: User ID at end (8+ digits)
    userid_pattern = r'(.*?)\s*(\d{8,})\s*$'
    match = re.match(userid_pattern, text, re.IGNORECASE)
    if match:
        message_text = match.group(1).strip()
        target_user = match.group(2)
        return target_user, message_text, 'userid'
    
    # Pattern 3: Username anywhere in text with @
    username_anywhere = r'.*?@([a-zA-Z][a-zA-Z0-9_]{3,30}).*'
    match = re.match(username_anywhere, text, re.IGNORECASE)
    if match:
        target_user = match.group(1)
        message_text = re.sub(r'@' + re.escape(target_user), '', text, flags=re.IGNORECASE).strip()
        return target_user, message_text, 'username'
    
    # Pattern 4: User ID anywhere in text (8+ digits)
    userid_anywhere = r'.*?(\d{8,}).*'
    match = re.match(userid_anywhere, text, re.IGNORECASE)
    if match:
        target_user = match.group(1)
        message_text = re.sub(r'\b' + re.escape(target_user) + r'\b', '', text).strip()
        return target_user, message_text, 'userid'
    
    return None, text, None

async def get_user_entity(bot, user_identifier):
    """Get user entity with caching"""
    cache_key = str(user_identifier)
    
    if cache_key in user_entity_cache:
        cached_data = user_entity_cache[cache_key]
        cache_time = datetime.fromisoformat(cached_data['timestamp'])
        if datetime.now() - cache_time < timedelta(minutes=5):
            return cached_data['entity']
        else:
            del user_entity_cache[cache_key]
    
    try:
        if isinstance(user_identifier, int) or (isinstance(user_identifier, str) and user_identifier.isdigit()):
            user_id = int(user_identifier)
            try:
                entity = await bot.get_entity(user_id)
                if hasattr(entity, 'first_name'):
                    user_entity_cache[cache_key] = {
                        'entity': entity,
                        'timestamp': datetime.now().isoformat()
                    }
                    return entity
            except:
                entity = type('obj', (object,), {
                    'id': user_id,
                    'username': None,
                    'first_name': f'User {user_id}',
                    'last_name': None
                })()
                return entity
                
        else:
            username = user_identifier.lower().replace('@', '')
            
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{3,30}$', username):
                from telethon.errors import UsernameInvalidError
                raise UsernameInvalidError("Invalid username format")
            
            try:
                entity = await bot.get_entity(username)
                if hasattr(entity, 'first_name'):
                    user_entity_cache[cache_key] = {
                        'entity': entity,
                        'timestamp': datetime.now().isoformat()
                    }
                    return entity
                else:
                    raise ValueError("Not a user entity")
            except Exception as e:
                from telethon.errors import UsernameNotOccupiedError
                raise UsernameNotOccupiedError(f"User @{username} not found")
                
    except Exception as e:
        logger.error(f"Error getting user entity for {user_identifier}: {e}")
        raise

def get_all_past_recipients_buttons(user_id, current_query=""):
    """Get ALL past recipients as inline buttons"""
    try:
        if user_id not in user_recent_recipients or not user_recent_recipients[user_id]:
            return []
        
        from telethon import Button
        
        buttons = []
        # सभी recent recipients show करें
        for recipient in user_recent_recipients[user_id]:
            name = recipient.get('name', 'User')
            username = recipient.get('username')
            recipient_id = recipient.get('id')
            count = recipient.get('count', 1)
            
            # Create display text
            if username:
                display_text = f"@{username}"
                query_text = f"{current_query} @{username}"
                if count > 1:
                    display_text = f"🔢 {display_text} ({count}×)"
            else:
                display_text = f"{name}"
                query_text = f"{current_query} {recipient_id}"
                if count > 1:
                    display_text = f"👤 {display_text} ({count}×)"
            
            # Truncate if too long
            if len(display_text) > 25:
                display_text = display_text[:22] + "..."
            
            buttons.append([
                Button.switch_inline(
                    f"{display_text}",
                    query=query_text.strip(),
                    same_peer=True
                )
            ])
        
        return buttons[:15]  # Maximum 15 buttons
        
    except Exception as e:
        logger.error(f"Error getting all past recipients buttons: {e}")
        return []

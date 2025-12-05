# utils.py
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import hashlib
import pickle

from telethon.tl.types import User
from telethon.errors import (
    UsernameNotOccupiedError,
    UsernameInvalidError,
    FloodWaitError
)

from config import logger, COOLDOWN_SECONDS
from database import cache_manager

# ======================
# COOLDOWN MANAGEMENT
# ======================
class CooldownManager:
    def __init__(self):
        self.cooldowns = {}
    
    def check(self, user_id: int) -> bool:
        """Check if user is in cooldown"""
        now = datetime.now().timestamp()
        user_key = str(user_id)
        
        if user_key in self.cooldowns:
            last_time = self.cooldowns[user_key]
            if now - last_time < COOLDOWN_SECONDS:
                return True
        
        self.cooldowns[user_key] = now
        return False
    
    def clear_old(self):
        """Clear old cooldown entries"""
        now = datetime.now().timestamp()
        to_remove = []
        
        for user_key, last_time in self.cooldowns.items():
            if now - last_time > 3600:  # 1 hour
                to_remove.append(user_key)
        
        for user_key in to_remove:
            del self.cooldowns[user_key]

cooldown_manager = CooldownManager()

def is_cooldown(user_id: int) -> bool:
    """Check if user is in cooldown"""
    return cooldown_manager.check(user_id)

# ======================
# USER ENTITY RESOLVER
# ======================
class UserEntityResolver:
    def __init__(self, bot):
        self.bot = bot
        self.cache = {}
        self.lock = asyncio.Lock()
    
    async def get_entity(self, user_identifier) -> Optional[User]:
        """Get user entity with smart caching"""
        # Normalize identifier
        if isinstance(user_identifier, int):
            cache_key = str(user_identifier)
        else:
            cache_key = user_identifier.lower().replace('@', '')
        
        # Check memory cache first
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            if datetime.now() - cached_data['timestamp'] < timedelta(minutes=5):
                return cached_data['entity']
        
        # Check database cache
        cached_user = cache_manager.get_cached_user(cache_key)
        if cached_user:
            # Create user object from cache
            entity = type('obj', (object,), {
                'id': cached_user['id'],
                'username': cached_user['username'],
                'first_name': cached_user['first_name'],
                'last_name': cached_user['last_name']
            })()
            
            # Update memory cache
            self.cache[cache_key] = {
                'entity': entity,
                'timestamp': datetime.now()
            }
            
            return entity
        
        # Fetch from Telegram API
        try:
            async with self.lock:
                if isinstance(user_identifier, int) or user_identifier.isdigit():
                    user_id = int(''.join(filter(str.isdigit, str(user_identifier))))
                    entity = await self.bot.get_entity(user_id)
                else:
                    username = str(user_identifier).lower().replace('@', '')
                    entity = await self.bot.get_entity(username)
                
                if hasattr(entity, 'first_name'):
                    # Update caches
                    self.cache[cache_key] = {
                        'entity': entity,
                        'timestamp': datetime.now()
                    }
                    
                    cache_manager.cache_user(
                        cache_key, entity.id,
                        getattr(entity, 'username', None),
                        getattr(entity, 'first_name', ''),
                        getattr(entity, 'last_name', '')
                    )
                    
                    return entity
                else:
                    raise ValueError("Not a user entity")
                    
        except (UsernameNotOccupiedError, UsernameInvalidError):
            raise
        except FloodWaitError as e:
            logger.warning(f"Flood wait: {e.seconds} seconds")
            raise
        except Exception as e:
            logger.error(f"Error fetching user entity {user_identifier}: {e}")
            raise
    
    def clear_cache(self):
        """Clear memory cache"""
        self.cache.clear()

# Global resolver instance
resolver = None

def get_user_entity(bot, user_identifier):
    """Get user entity (wrapper for resolver)"""
    global resolver
    if resolver is None:
        resolver = UserEntityResolver(bot)
    return resolver.get_entity(user_identifier)

# ======================
# MESSAGE UTILITIES
# ======================
def create_message_id(sender_id: int, recipient_id: int) -> str:
    """Create unique message ID"""
    timestamp = int(datetime.now().timestamp())
    data = f"{sender_id}_{recipient_id}_{timestamp}"
    
    # Create hash for uniqueness
    hash_obj = hashlib.md5(data.encode())
    short_hash = hash_obj.hexdigest()[:8]
    
    return f"msg_{sender_id}_{recipient_id}_{timestamp}_{short_hash}"

def validate_message_text(text: str, max_length: int = 1000) -> bool:
    """Validate message text"""
    if not text or not text.strip():
        return False
    
    if len(text.strip()) > max_length:
        return False
    
    # Check for empty message after removing whitespace
    if not text.strip():
        return False
    
    return True

def format_display_name(user_data: Dict[str, Any]) -> str:
    """Format user name for display"""
    name = user_data.get('name', 'User')
    username = user_data.get('username')
    
    if username:
        return f"@{username}"
    else:
        return name

def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """Truncate text with ellipsis"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

# ======================
# PERFORMANCE UTILITIES
# ======================
async def run_in_thread(func, *args):
    """Run function in thread pool"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)

def measure_time(func):
    """Decorator to measure execution time"""
    async def wrapper(*args, **kwargs):
        start = datetime.now()
        result = await func(*args, **kwargs)
        end = datetime.now()
        logger.debug(f"{func.__name__} took {(end - start).total_seconds():.3f}s")
        return result
    return wrapper

# ======================
# ERROR HANDLING
# ======================
class WhisperError(Exception):
    """Base exception for whisper bot"""
    pass

class UserNotFoundError(WhisperError):
    """User not found error"""
    pass

class InvalidFormatError(WhisperError):
    """Invalid format error"""
    pass

class CooldownError(WhisperError):
    """Cooldown error"""
    pass

def handle_errors(func):
    """Decorator to handle common errors"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except UsernameNotOccupiedError as e:
            raise UserNotFoundError(f"User not found: {str(e)}")
        except UsernameInvalidError as e:
            raise InvalidFormatError(f"Invalid username: {str(e)}")
        except FloodWaitError as e:
            raise CooldownError(f"Please wait {e.seconds} seconds")
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise WhisperError(f"An error occurred: {str(e)}")
    return wrapper

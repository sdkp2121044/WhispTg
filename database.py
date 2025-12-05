# database.py
import json
import os
import sqlite3
from datetime import datetime, timedelta
import threading
import logging

from config import (
    logger, DATA_DIR, USER_HISTORY_FILE, 
    MAX_HISTORY_ENTRIES, MAX_CACHE_ENTRIES,
    MESSAGE_TTL_HOURS
)

# ======================
# SQLITE DATABASE SETUP
# ======================
DB_FILE = os.path.join(DATA_DIR, "whisper_bot.db")

def init_database():
    """Initialize SQLite database"""
    try:
        # Create data directory if it doesn't exist
        os.makedirs(DATA_DIR, exist_ok=True)
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # User history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_history (
                user_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                recipient_name TEXT NOT NULL,
                recipient_username TEXT,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, recipient_id)
            )
        ''')
        
        # Active messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                message_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        ''')
        
        # User cache table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_cache (
                user_identifier TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")

# ======================
# USER HISTORY MANAGEMENT
# ======================
class UserHistoryManager:
    def __init__(self):
        self.lock = threading.Lock()
        init_database()
    
    def add_recipient(self, user_id, recipient_id, recipient_name, recipient_username=None):
        """Add or update recipient in user's history"""
        try:
            with self.lock:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                
                # Check if recipient exists
                cursor.execute('''
                    SELECT usage_count FROM user_history 
                    WHERE user_id = ? AND recipient_id = ?
                ''', (user_id, recipient_id))
                
                result = cursor.fetchone()
                
                if result:
                    # Update existing entry
                    cursor.execute('''
                        UPDATE user_history 
                        SET last_used = CURRENT_TIMESTAMP, 
                            usage_count = usage_count + 1,
                            recipient_name = ?,
                            recipient_username = ?
                        WHERE user_id = ? AND recipient_id = ?
                    ''', (recipient_name, recipient_username, user_id, recipient_id))
                else:
                    # Insert new entry
                    cursor.execute('''
                        INSERT INTO user_history 
                        (user_id, recipient_id, recipient_name, recipient_username, usage_count)
                        VALUES (?, ?, ?, ?, 1)
                    ''', (user_id, recipient_id, recipient_name, recipient_username))
                
                # Clean old entries
                cursor.execute('''
                    DELETE FROM user_history 
                    WHERE user_id = ? AND recipient_id IN (
                        SELECT recipient_id FROM user_history 
                        WHERE user_id = ? 
                        ORDER BY last_used DESC 
                        LIMIT -1 OFFSET ?
                    )
                ''', (user_id, user_id, MAX_HISTORY_ENTRIES))
                
                conn.commit()
                conn.close()
                return True
                
        except Exception as e:
            logger.error(f"Error adding recipient: {e}")
            return False
    
    def get_user_history(self, user_id, limit=MAX_HISTORY_ENTRIES):
        """Get all recipients for a user"""
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT recipient_id, recipient_name, recipient_username, 
                       last_used, usage_count 
                FROM user_history 
                WHERE user_id = ? 
                ORDER BY last_used DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            results = cursor.fetchall()
            conn.close()
            
            history = []
            for row in results:
                history.append({
                    'id': row[0],
                    'name': row[1],
                    'username': row[2],
                    'last_used': row[3],
                    'count': row[4]
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting user history: {e}")
            return []
    
    def get_all_user_ids(self):
        """Get all user IDs in database"""
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            cursor.execute('SELECT DISTINCT user_id FROM user_history')
            results = cursor.fetchall()
            conn.close()
            
            return [row[0] for row in results]
            
        except Exception as e:
            logger.error(f"Error getting user IDs: {e}")
            return []
    
    def get_total_history_count(self):
        """Get total number of history entries"""
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM user_history')
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"Error getting history count: {e}")
            return 0
    
    def clear_user_history(self, user_id):
        """Clear all history for a user"""
        try:
            with self.lock:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                
                cursor.execute('''
                    DELETE FROM user_history WHERE user_id = ?
                ''', (user_id,))
                
                conn.commit()
                conn.close()
                return True
                
        except Exception as e:
            logger.error(f"Error clearing history: {e}")
            return False

# ======================
# MESSAGE MANAGEMENT
# ======================
class MessageManager:
    def __init__(self):
        self.lock = threading.Lock()
    
    def add_message(self, message_id, sender_id, recipient_id, message_text):
        """Add a new whisper message"""
        try:
            with self.lock:
                expires_at = datetime.now() + timedelta(hours=MESSAGE_TTL_HOURS)
                
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO messages 
                    (message_id, sender_id, recipient_id, message_text, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (message_id, sender_id, recipient_id, message_text, expires_at))
                
                conn.commit()
                conn.close()
                return True
                
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            return False
    
    def get_message(self, message_id):
        """Get message by ID"""
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT sender_id, recipient_id, message_text, created_at 
                FROM messages 
                WHERE message_id = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            ''', (message_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'sender_id': result[0],
                    'recipient_id': result[1],
                    'message': result[2],
                    'created_at': result[3]
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting message: {e}")
            return None
    
    def get_message_count(self):
        """Get total message count"""
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM messages')
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"Error getting message count: {e}")
            return 0
    
    def cleanup_expired(self):
        """Clean up expired messages"""
        try:
            with self.lock:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                
                cursor.execute('''
                    DELETE FROM messages 
                    WHERE expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP
                ''')
                
                deleted = cursor.rowcount
                conn.commit()
                conn.close()
                
                if deleted > 0:
                    logger.info(f"🧹 Cleaned up {deleted} expired messages")
                    
        except Exception as e:
            logger.error(f"Error cleaning up messages: {e}")

# ======================
# USER CACHE MANAGEMENT
# ======================
class UserCacheManager:
    def __init__(self):
        self.lock = threading.Lock()
    
    def cache_user(self, user_identifier, user_id, username=None, first_name=None, last_name=None):
        """Cache user information"""
        try:
            with self.lock:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO user_cache 
                    (user_identifier, user_id, username, first_name, last_name, cached_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (user_identifier, user_id, username, first_name, last_name))
                
                # Clean old cache entries
                cursor.execute('''
                    DELETE FROM user_cache 
                    WHERE user_identifier IN (
                        SELECT user_identifier FROM user_cache 
                        ORDER BY cached_at DESC 
                        LIMIT -1 OFFSET ?
                    )
                ''', (MAX_CACHE_ENTRIES,))
                
                conn.commit()
                conn.close()
                return True
                
        except Exception as e:
            logger.error(f"Error caching user: {e}")
            return False
    
    def get_cached_user(self, user_identifier):
        """Get cached user information"""
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT user_id, username, first_name, last_name 
                FROM user_cache 
                WHERE user_identifier = ? 
                AND cached_at >= datetime('now', '-5 minutes')
            ''', (user_identifier,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'id': result[0],
                    'username': result[1],
                    'first_name': result[2],
                    'last_name': result[3]
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached user: {e}")
            return None

# ======================
# GLOBAL MANAGERS
# ======================
history_manager = UserHistoryManager()
message_manager = MessageManager()
cache_manager = UserCacheManager()

# Initialize on import
init_database()

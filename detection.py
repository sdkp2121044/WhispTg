# detection.py
import re
import logging
from typing import Tuple, Optional, Dict, Any
from datetime import datetime

from config import (
    logger, USERNAME_MIN_LENGTH, USERNAME_MAX_LENGTH,
    USERID_MIN_LENGTH, USERID_MAX_LENGTH
)

# ======================
# PATTERN DEFINITIONS
# ======================
class DetectionPatterns:
    # Comprehensive user ID patterns
    USERID_PATTERNS = [
        # Pure numeric IDs (8-15 digits)
        r'\b(\d{8,15})\b',
        
        # IDs with prefixes
        r'(?:id|userid|uid|user)[:\s]*(\d{8,15})',
        r'(?:id|userid|uid|user)[:\s]*[@\s]*(\d{8,15})',
        
        # IDs in parentheses
        r'\((\d{8,15})\)',
        r'\[(\d{8,15})\]',
        
        # IDs after specific words
        r'(?:to|for|send|message)[:\s]+(\d{8,15})',
        
        # Telegram user ID format (negative for groups, positive for users)
        r'\b(-?\d{8,15})\b',
    ]
    
    # Username patterns
    USERNAME_PATTERNS = [
        # Standard @username
        r'@([a-zA-Z][a-zA-Z0-9_]{4,31})',
        
        # Username without @
        r'\b([a-zA-Z][a-zA-Z0-9_]{4,31})\b(?!\d)',
        
        # Username with prefixes
        r'(?:user|username|uname)[:\s]*@?([a-zA-Z][a-zA-Z0-9_]{4,31})',
        
        # Username after specific words
        r'(?:to|for|send|message)[:\s]+@?([a-zA-Z][a-zA-Z0-9_]{4,31})',
        
        # Username in various formats
        r't\.me/([a-zA-Z][a-zA-Z0-9_]{4,31})',
        r'telegram\.me/([a-zA-Z][a-zA-Z0-9_]{4,31})',
    ]
    
    # Message-target patterns
    MESSAGE_PATTERNS = [
        # Format: "message @username text"
        r'(?:.*?)\s+@([a-zA-Z][a-zA-Z0-9_]{4,31})\s+(.+)',
        
        # Format: "message 123456789 text"
        r'(?:.*?)\s+(\d{8,15})\s+(.+)',
        
        # Format: "to @username: text"
        r'to\s+@([a-zA-Z][a-zA-Z0-9_]{4,31})[:\s]*(.+)',
        
        # Format: "to 123456789: text"
        r'to\s+(\d{8,15})[:\s]*(.+)',
        
        # Format: "@username text"
        r'@([a-zA-Z][a-zA-Z0-9_]{4,31})\s+(.+)',
        
        # Format: "123456789 text"
        r'(\d{8,15})\s+(.+)',
    ]

# ======================
# DETECTION ENGINE
# ======================
class InstantDetector:
    def __init__(self):
        self.patterns = DetectionPatterns()
        self.compiled_patterns = {
            'userid': [re.compile(pattern, re.IGNORECASE) for pattern in self.patterns.USERID_PATTERNS],
            'username': [re.compile(pattern, re.IGNORECASE) for pattern in self.patterns.USERNAME_PATTERNS],
            'message': [re.compile(pattern, re.IGNORECASE) for pattern in self.patterns.MESSAGE_PATTERNS],
        }
    
    def detect_all(self, text: str) -> Dict[str, Any]:
        """
        Detect all possible user identifiers in text
        Returns: {'userids': [], 'usernames': [], 'messages': []}
        """
        text = text.strip()
        results = {
            'userids': [],
            'usernames': [],
            'messages': [],
            'raw_text': text
        }
        
        if not text:
            return results
        
        # Detect user IDs
        for pattern in self.compiled_patterns['userid']:
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if self._validate_userid(match):
                    results['userids'].append(match)
        
        # Detect usernames
        for pattern in self.compiled_patterns['username']:
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if self._validate_username(match):
                    results['usernames'].append(match)
        
        # Detect message patterns
        for pattern in self.compiled_patterns['message']:
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple) and len(match) == 2:
                    identifier, message = match
                    if self._validate_userid(identifier) or self._validate_username(identifier):
                        results['messages'].append({
                            'identifier': identifier,
                            'message': message.strip(),
                            'type': 'userid' if identifier.isdigit() else 'username'
                        })
        
        # Remove duplicates
        results['userids'] = list(dict.fromkeys(results['userids']))
        results['usernames'] = list(dict.fromkeys(results['usernames']))
        
        return results
    
    def extract_recipient_and_message(self, text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract recipient and message from text
        Returns: (recipient, message, recipient_type)
        """
        text = text.strip()
        
        # Try message patterns first
        for pattern in self.compiled_patterns['message']:
            match = pattern.match(text)
            if match:
                identifier, message = match.groups()
                if self._validate_userid(identifier):
                    return identifier, message, 'userid'
                elif self._validate_username(identifier):
                    return identifier, message, 'username'
        
        # If no message pattern matches, check if text contains only recipient
        if self._validate_userid(text):
            return text, None, 'userid'
        elif self._validate_username(text):
            return text, None, 'username'
        
        # Check if text ends with recipient
        words = text.split()
        if len(words) >= 2:
            last_word = words[-1]
            if self._validate_userid(last_word):
                message = ' '.join(words[:-1])
                return last_word, message, 'userid'
            elif self._validate_username(last_word):
                message = ' '.join(words[:-1])
                return last_word, message, 'username'
        
        return None, text, None
    
    def _validate_userid(self, userid: str) -> bool:
        """Validate user ID"""
        if not userid:
            return False
        
        # Remove any non-digit characters
        clean_id = ''.join(filter(str.isdigit, userid))
        
        if not clean_id:
            return False
        
        # Check length
        if not (USERID_MIN_LENGTH <= len(clean_id) <= USERID_MAX_LENGTH):
            return False
        
        # Check if it's a valid Telegram ID
        # Telegram IDs are usually 8-10 digits for users, can be negative for groups
        try:
            int_id = int(clean_id)
            # Valid user IDs are positive, group IDs are negative
            # But we accept both for flexibility
            return True
        except ValueError:
            return False
    
    def _validate_username(self, username: str) -> bool:
        """Validate username"""
        if not username:
            return False
        
        # Remove @ if present
        clean_username = username.lstrip('@')
        
        # Check length
        if not (USERNAME_MIN_LENGTH <= len(clean_username) <= USERNAME_MAX_LENGTH):
            return False
        
        # Check format (must start with letter, only letters, numbers, underscore)
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', clean_username):
            return False
        
        return True
    
    def is_valid_recipient(self, text: str) -> bool:
        """Check if text contains a valid recipient"""
        text = text.strip()
        
        # Check if it's a valid user ID
        if self._validate_userid(text):
            return True
        
        # Check if it's a valid username
        if self._validate_username(text):
            return True
        
        # Check if it contains a recipient in message format
        recipient, _, _ = self.extract_recipient_and_message(text)
        return recipient is not None

# ======================
# GLOBAL DETECTOR INSTANCE
# ======================
detector = InstantDetector()

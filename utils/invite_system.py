import hashlib
import random
import string
import json
import os

class InviteSystem:
    def __init__(self):
        self.invites_file = 'data/invites.json'
        os.makedirs('data', exist_ok=True)
    
    def generate_code(self, user_id):
        """Generate unique invite code for user"""
        base = f"{user_id}_{random_string(6)}"
        code_hash = hashlib.md5(base.encode()).hexdigest()[:8]
        return f"ref_{code_hash}"
    
    def get_user_from_code(self, code):
        """Get user_id from invite code"""
        if not code.startswith('ref_'):
            return None
        
        users = self.load_users()
        for user_id, user_data in users.items():
            if user_data.get('invite_code') == code:
                return int(user_id)
        return None
    
    def load_users(self):
        """Load users from JSON"""
        try:
            with open('data/users.json', 'r') as f:
                return json.load(f)
        except:
            return {}

def random_string(length=6):
    """Generate random string"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

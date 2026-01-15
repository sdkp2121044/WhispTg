import json
import os
from datetime import datetime

class FileManager:
    def __init__(self):
        self.temp_dir = 'temp'
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs('data', exist_ok=True)
    
    def save_temp_image(self, user_id, image_bytes):
        """Save temporary image for callback"""
        filename = f"{self.temp_dir}/{user_id}_{datetime.now().timestamp()}.png"
        with open(filename, 'wb') as f:
            f.write(image_bytes)
        return filename
    
    def get_temp_image(self, user_id):
        """Get latest temp image for user"""
        # Find latest file for user
        user_files = []
        for file in os.listdir(self.temp_dir):
            if file.startswith(f"{user_id}_"):
                user_files.append(file)
        
        if not user_files:
            return None
        
        # Get latest file
        latest = max(user_files)
        with open(f"{self.temp_dir}/{latest}", 'rb') as f:
            return f.read()
    
    def delete_temp_image(self, user_id):
        """Delete temp images for user"""
        for file in os.listdir(self.temp_dir):
            if file.startswith(f"{user_id}_"):
                os.remove(f"{self.temp_dir}/{file}")
    
    def load_json(self, filename):
        """Load JSON file"""
        try:
            with open(f'data/{filename}', 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def save_json(self, filename, data):
        """Save JSON file"""
        with open(f'data/{filename}', 'w') as f:
            json.dump(data, f, indent=2)

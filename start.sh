#!/bin/bash
echo "🚀 Starting ShriBots Whisper Bot on Render..."
echo "📝 Loading environment variables..."

# Create data directory if not exists
mkdir -p data

# Install requirements
pip install -r requirements.txt

# Start the bot
python bot.py

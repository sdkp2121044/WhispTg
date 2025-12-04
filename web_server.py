# web_server.py
from flask import Flask, render_template_string
import json
import threading
import logging
from datetime import datetime

from config import PORT, SUPPORT_CHANNEL, SUPPORT_GROUP
from database import user_whisper_history, messages_db, user_entity_cache

logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    bot_username = "whisper_bot"
    try:
        from main import bot
        if bot.is_connected():
            import asyncio
            bot_username = asyncio.run(bot.get_me()).username
    except:
        pass
    
    total_users = len(user_whisper_history)
    total_messages = len(messages_db)
    total_history_entries = sum(len(v) for v in user_whisper_history.values())
    
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ShriBots Whisper Bot</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
            body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
            .container { background: white; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); overflow: hidden; width: 100%; max-width: 900px; }
            .header { background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); color: white; padding: 30px; text-align: center; }
            .header h1 { font-size: 2.5rem; margin-bottom: 10px; display: flex; align-items: center; justify-content: center; gap: 15px; }
            .header p { font-size: 1.1rem; opacity: 0.9; }
            .content { padding: 40px; }
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 30px; }
            .stat-card { background: #f8fafc; border-radius: 15px; padding: 20px; text-align: center; border: 2px solid #e2e8f0; transition: transform 0.3s, border-color 0.3s; }
            .stat-card:hover { transform: translateY(-5px); border-color: #4f46e5; }
            .stat-value { font-size: 2.2rem; font-weight: bold; color: #4f46e5; margin-bottom: 8px; }
            .stat-label { font-size: 0.9rem; color: #64748b; font-weight: 500; }
            .feature-card { background: #f1f5f9; border-radius: 15px; padding: 25px; margin-bottom: 20px; border-left: 5px solid #4f46e5; }
            .feature-card h3 { color: #334155; margin-bottom: 15px; display: flex; align-items: center; gap: 10px; }
            .feature-card ul { list-style: none; padding-left: 0; }
            .feature-card li { padding: 8px 0; color: #475569; display: flex; align-items: center; gap: 10px; }
            .highlight { background: #e0e7ff; padding: 15px; border-radius: 10px; margin: 15px 0; border-left: 4px solid #4f46e5; }
            .bot-link { display: inline-block; background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); color: white; text-decoration: none; padding: 15px 30px; border-radius: 50px; font-weight: bold; font-size: 1.1rem; margin-top: 20px; transition: transform 0.3s, box-shadow 0.3s; }
            .bot-link:hover { transform: translateY(-3px); box-shadow: 0 10px 25px rgba(79, 70, 229, 0.4); }
            .status-badge { display: inline-block; padding: 8px 20px; background: #10b981; color: white; border-radius: 50px; font-weight: bold; margin-bottom: 20px; }
            @media (max-width: 768px) { .header h1 { font-size: 2rem; } .content { padding: 20px; } .stats-grid { grid-template-columns: 1fr; } }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤫 ShriBots Whisper Bot</h1>
                <p>Complete History Tracking + Smart Suggestions</p>
            </div>
            
            <div class="content">
                <div class="status-badge">✅ Bot is Running</div>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{{ total_users }}</div>
                        <div class="stat-label">👥 Total Users</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-value">{{ total_messages }}</div>
                        <div class="stat-label">💬 Active Messages</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-value">{{ total_history }}</div>
                        <div class="stat-label">📚 History Entries</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-value">{{ cached_users }}</div>
                        <div class="stat-label">🧠 Cached Users</div>
                    </div>
                </div>
                
                <div class="feature-card">
                    <h3>📚 Complete History Tracking</h3>
                    <ul>
                        <li>✅ Remembers <strong>ALL</strong> your past whispers</li>
                        <li>✅ Stores <strong>every username/userID</strong> you've ever used</li>
                        <li>✅ Shows <strong>ALL past recipients</strong> when you type @bot_username</li>
                        <li>✅ Auto-suggests from <strong>complete history</strong></li>
                        <li>✅ Personal statistics for each user</li>
                    </ul>
                    
                    <div class="highlight">
                        <strong>✨ Key Feature:</strong><br>
                        Every time you whisper to someone, bot remembers them forever!<br>
                        Next time you type @bot_username, ALL your past recipients will appear!
                    </div>
                </div>
                
                <div class="feature-card">
                    <h3>🚀 How to Use</h3>
                    <ul>
                        <li>1. Type <code>@{{ bot_username }}</code> in any Telegram chat</li>
                        <li>2. See <strong>ALL your past recipients</strong> appear automatically</li>
                        <li>3. Type message with @username or user ID</li>
                        <li>4. Bot remembers this recipient forever!</li>
                        <li>5. Next time: They appear in your history list</li>
                    </ul>
                </div>
                
                <center>
                    <a href="https://t.me/{{ bot_username }}" class="bot-link" target="_blank">
                        🚀 Try Complete History Feature
                    </a>
                </center>
            </div>
        </div>
    </body>
    </html>
    """
    
    return render_template_string(
        html_template,
        total_users=total_users,
        total_messages=total_messages,
        total_history=total_history_entries,
        cached_users=len(user_entity_cache),
        bot_username=bot_username
    )

@app.route('/health')
def health():
    total_history_entries = sum(len(v) for v in user_whisper_history.values())
    
    return json.dumps({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "total_users": len(user_whisper_history),
        "total_messages": len(messages_db),
        "total_history_entries": total_history_entries,
        "cached_users": len(user_entity_cache),
        "version": "4.0",
        "features": ["complete_history_tracking", "all_past_recipients", "personal_statistics", "smart_suggestions"]
    })

def run_flask():
    """Run Flask web server"""
    logger.info(f"🌐 Starting Flask server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

def start_web_server():
    """Start Flask server in a thread"""
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

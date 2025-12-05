# web_server.py
import logging
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, render_template_string

from config import logger, PORT, HOST, BOT_NAME
from database import history_manager, message_manager, cache_manager

# ======================
# FLASK APPLICATION
# ======================
app = Flask(__name__)

# Health status tracking
server_start_time = datetime.now()
last_health_check = datetime.now()

# ======================
# ROUTES
# ======================
@app.route('/')
def home():
    """Main homepage with bot status"""
    try:
        # Get basic stats
        total_users = len(history_manager.get_all_user_ids())
        total_messages = message_manager.get_message_count()
        total_history = history_manager.get_total_history_count()
        
        # Calculate uptime
        uptime = datetime.now() - server_start_time
        uptime_str = str(uptime).split('.')[0]  # Remove microseconds
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{BOT_NAME}</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f0f2f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .status {{ background: #4CAF50; color: white; padding: 10px; border-radius: 5px; text-align: center; margin: 20px 0; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 20px 0; }}
                .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; border: 1px solid #dee2e6; }}
                .stat-value {{ font-size: 24px; font-weight: bold; color: #333; }}
                .stat-label {{ color: #666; font-size: 14px; margin-top: 5px; }}
                .features {{ background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🤫 {BOT_NAME}</h1>
                    <p>Instant Secret Messages with Smart Detection</p>
                </div>
                
                <div class="status">
                    ✅ Bot Server is Running
                </div>
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-value">{total_users}</div>
                        <div class="stat-label">👥 Total Users</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-value">{total_messages}</div>
                        <div class="stat-label">💬 Messages</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-value">{total_history}</div>
                        <div class="stat-label">📚 History Entries</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-value">{uptime_str}</div>
                        <div class="stat-label">⏰ Uptime</div>
                    </div>
                </div>
                
                <div class="features">
                    <h3>✨ Active Features:</h3>
                    <ul>
                        <li>✅ Instant User Detection (Any format)</li>
                        <li>✅ Complete History Tracking</li>
                        <li>✅ All Past Recipients Shown</li>
                        <li>✅ Smart Auto-Suggest</li>
                        <li>✅ Real-time Processing</li>
                    </ul>
                </div>
                
                <p><strong>🔄 Last Updated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                <p><strong>🌐 Server:</strong> {HOST}:{PORT}</p>
            </div>
            
            <script>
                // Auto-refresh every 30 seconds
                setTimeout(() => location.reload(), 30000);
            </script>
        </body>
        </html>
        """
        
        return html
        
    except Exception as e:
        logger.error(f"Home route error: {e}")
        return f"<h1>{BOT_NAME}</h1><p>Status: Running (Stats temporarily unavailable)</p>"

@app.route('/health')
def health_check():
    """Health check endpoint"""
    global last_health_check
    last_health_check = datetime.now()
    
    try:
        # Basic health checks
        uptime = datetime.now() - server_start_time
        uptime_seconds = uptime.total_seconds()
        
        health_data = {
            "status": "healthy",
            "service": BOT_NAME,
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": uptime_seconds,
            "uptime_human": str(uptime).split('.')[0],
            "server_start": server_start_time.isoformat(),
            "last_health_check": last_health_check.isoformat(),
            "endpoints": {
                "home": "/",
                "health": "/health",
                "stats": "/stats",
                "api_health": "/api/health"
            }
        }
        
        # Add database health check
        try:
            # Try to query database
            test_users = len(history_manager.get_all_user_ids())
            health_data["database"] = {
                "status": "connected",
                "users_count": test_users
            }
        except Exception as db_error:
            health_data["database"] = {
                "status": "error",
                "error": str(db_error)
            }
            health_data["status"] = "degraded"
        
        return jsonify(health_data)
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/stats')
def stats():
    """Detailed statistics"""
    try:
        total_users = len(history_manager.get_all_user_ids())
        total_messages = message_manager.get_message_count()
        total_history = history_manager.get_total_history_count()
        
        # Get recent activity (last 24 hours would need timestamp tracking)
        stats_data = {
            "timestamp": datetime.now().isoformat(),
            "bot": {
                "name": BOT_NAME,
                "status": "running",
                "uptime": str(datetime.now() - server_start_time).split('.')[0]
            },
            "statistics": {
                "total_users": total_users,
                "total_messages": total_messages,
                "total_history_entries": total_history,
                "cached_users": 0,  # Would need cache manager method
                "active_sessions": 0  # Would need session tracking
            },
            "system": {
                "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "port": PORT,
                "host": HOST
            }
        }
        
        return jsonify(stats_data)
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/health')
def api_health():
    """Simple API health check"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    })

# ======================
# SERVER MANAGEMENT
# ======================
def run_server():
    """Run the Flask web server"""
    try:
        logger.info(f"🚀 Starting web server on {HOST}:{PORT}")
        
        # Try production server first
        try:
            from waitress import serve
            logger.info("✅ Using Waitress production server")
            serve(app, host=HOST, port=PORT, threads=4)
        except ImportError:
            # Fallback to Flask development server
            logger.info("⚠️ Using Flask development server (install waitress for production)")
            app.run(host=HOST, port=PORT, debug=False, threaded=True)
            
    except Exception as e:
        logger.error(f"❌ Web server failed to start: {e}")
        # Don't crash the whole bot, just log the error

def start_web_server_in_thread():
    """Start web server in a separate thread"""
    try:
        server_thread = threading.Thread(
            target=run_server,
            daemon=True,
            name="WebServer"
        )
        server_thread.start()
        
        # Give server time to start
        time.sleep(2)
        
        logger.info(f"✅ Web server started on port {PORT}")
        return server_thread
        
    except Exception as e:
        logger.error(f"❌ Failed to start web server thread: {e}")
        return None

# Background health monitor
def health_monitor():
    """Monitor server health in background"""
    while True:
        try:
            current_time = datetime.now()
            time_since_last_check = (current_time - last_health_check).total_seconds()
            
            if time_since_last_check > 300:  # 5 minutes
                logger.warning(f"⚠️ No health check for {int(time_since_last_check)} seconds")
            
            time.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Health monitor error: {e}")
            time.sleep(60)

# Start health monitor in background
monitor_thread = threading.Thread(target=health_monitor, daemon=True, name="HealthMonitor")
monitor_thread.start()
logger.info("✅ Health monitor started")

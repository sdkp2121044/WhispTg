# web_server.py
from flask import Flask, jsonify
import threading
import logging
from datetime import datetime

from config import logger, PORT, HOST

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "service": "Whisper Bot",
        "port": PORT,
        "time": datetime.now().isoformat()
    })

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

def run_server():
    """Run Flask web server - ये function main thread में call होना चाहिए"""
    try:
        # ✅ Production WSGI server use करें
        from waitress import serve
        logger.info(f"🌐 Starting production server on {HOST}:{PORT}")
        serve(app, host=HOST, port=PORT)
    except ImportError:
        # Fallback to development server
        logger.info(f"🌐 Starting development server on {HOST}:{PORT}")
        app.run(host=HOST, port=PORT, debug=False, threaded=True)

from flask import Flask, render_template_string
import os

app = Flask(__name__)

@app.route('/')
def home():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤫 Whisper Bot - Send Anonymous Messages</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                max-width: 800px;
                width: 100%;
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 15px;
            }
            
            .status {
                background: #10b981;
                color: white;
                padding: 12px;
                border-radius: 10px;
                margin: 20px 30px;
                text-align: center;
                font-weight: bold;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
            }
            
            .features {
                padding: 30px;
            }
            
            .feature-item {
                background: #f3f4f6;
                padding: 20px;
                border-radius: 12px;
                margin-bottom: 15px;
                border-left: 5px solid #4f46e5;
            }
            
            .feature-item h3 {
                color: #4f46e5;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .buttons {
                padding: 0 30px 30px;
                display: flex;
                gap: 15px;
                flex-wrap: wrap;
            }
            
            .btn {
                flex: 1;
                min-width: 200px;
                background: #4f46e5;
                color: white;
                padding: 15px;
                border-radius: 10px;
                text-decoration: none;
                text-align: center;
                font-weight: bold;
                transition: transform 0.3s, background 0.3s;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
            }
            
            .btn:hover {
                background: #3730a3;
                transform: translateY(-3px);
            }
            
            .btn-telegram {
                background: #0088cc;
            }
            
            .btn-telegram:hover {
                background: #006699;
            }
            
            .footer {
                text-align: center;
                padding: 20px;
                color: #6b7280;
                border-top: 1px solid #e5e7eb;
            }
            
            @media (max-width: 768px) {
                .header h1 {
                    font-size: 1.8rem;
                }
                
                .buttons {
                    flex-direction: column;
                }
                
                .btn {
                    width: 100%;
                }
            }
        </style>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>
                    <i class="fas fa-user-secret"></i>
                    Whisper Bot
                </h1>
                <p>Send anonymous secret messages with one click!</p>
            </div>
            
            <div class="status">
                <i class="fas fa-circle-check"></i>
                ✅ Bot is Running | @upspbot
            </div>
            
            <div class="features">
                <div class="feature-item">
                    <h3><i class="fas fa-bolt"></i> Instant Sending</h3>
                    <p>Username/ID लिखते ही send! Works with ANY username or ID.</p>
                </div>
                
                <div class="feature-item">
                    <h3><i class="fas fa-shield-alt"></i> Secure & Private</h3>
                    <p>Only intended recipient can read (except owner). गलत username/ID पर भी whisper.</p>
                </div>
                
                <div class="feature-item">
                    <h3><i class="fas fa-history"></i> Recent Users</h3>
                    <p>All recent users automatically show for quick sending.</p>
                </div>
                
                <div class="feature-item">
                    <h3><i class="fas fa-clone"></i> Clone System</h3>
                    <p>Create your own whisper bot in one click!</p>
                </div>
            </div>
            
            <div class="buttons">
                <a href="https://t.me/upspbot" class="btn btn-telegram">
                    <i class="fab fa-telegram"></i>
                    Open Main Bot
                </a>
                <a href="https://t.me/upspbot?start=help" class="btn">
                    <i class="fas fa-question-circle"></i>
                    How to Use
                </a>
                <a href="https://t.me/shribots" class="btn">
                    <i class="fas fa-bullhorn"></i>
                    Channel
                </a>
            </div>
            
            <div class="footer">
                <p>Powered by ShriBots • Hosted on Render • Owner: @upspbot</p>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/health')
def health():
    return {"status": "healthy", "service": "website"}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
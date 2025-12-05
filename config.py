# config.py
import os
import logging

# ======================
# LOGGING CONFIGURATION
# ======================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ======================
# TELEGRAM API CREDENTIALS
# ======================
API_ID = int(os.getenv('API_ID', ''))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_ID = int(os.getenv('ADMIN_ID', ''))

# ======================
# SERVER CONFIGURATION
# ======================
PORT = int(os.environ.get('PORT', 10000))
HOST = '0.0.0.0'

# ======================
# BOT SETTINGS
# ======================
BOT_NAME = "Instant Whisper Bot"
SUPPORT_CHANNEL = "shribots"
SUPPORT_GROUP = "idxhelp"

# ======================
# DATA MANAGEMENT
# ======================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
USER_HISTORY_FILE = os.path.join(DATA_DIR, "user_history.json")

# ======================
# LIMITS AND THROTTLING
# ======================
MAX_HISTORY_ENTRIES = 25
MAX_CACHE_ENTRIES = 100
COOLDOWN_SECONDS = 2
MESSAGE_TTL_HOURS = 24

# ======================
# DETECTION CONFIGURATION
# ======================
USERNAME_MIN_LENGTH = 5
USERNAME_MAX_LENGTH = 32
USERID_MIN_LENGTH = 8
USERID_MAX_LENGTH = 15

# ======================
# USER INTERFACE SETTINGS
# ======================
MAX_BUTTONS_PER_PAGE = 10
MAX_MESSAGE_LENGTH = 1000
PREVIEW_LENGTH = 50

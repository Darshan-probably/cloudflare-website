# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Loads variables from .env into os.environ

# Discord OAuth configuration
DISCORD_CLIENT_ID = os.getenv("CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("REDIRECT_URI")
DISCORD_OAUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_URL = "https://discord.com/api/users/@me"
MAIN_URL = os.getenv("main_url")
PORT = os.getenv("port")
# Add these to app/config.py

# Bot server configuration
BOT_SERVER_HOST = os.getenv("BOT_SERVER_HOST", "de3.bot-hosting.net")
BOT_SERVER_PORT = os.getenv("BOT_SERVER_PORT", "20058")
BOT_SERVER_URL = f"{BOT_SERVER_HOST}:{BOT_SERVER_PORT}"
# API secret used for internal authentication (e.g. WebSocket)
API_SECRET = os.getenv("API_SECRET")  # Replace default in production

# Session secret for SessionMiddleware; use a secure secret in production!
SESSION_SECRET = os.getenv("SESSION_SECRET")

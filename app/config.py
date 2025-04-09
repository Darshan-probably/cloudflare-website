# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Loads variables from .env into os.environ

# Discord OAuth configuration
DISCORD_CLIENT_ID = "1356319675717390507"
DISCORD_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
DISCORD_REDIRECT_URI = "http://127.0.0.1:8000/oauth-callback"
DISCORD_OAUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_URL = "https://discord.com/api/users/@me"

# API secret used for internal authentication (e.g. WebSocket)
API_SECRET = os.getenv("API_SECRET", "default-secret")  # Replace default in production

# Session secret for SessionMiddleware; use a secure secret in production!
SESSION_SECRET = os.getenv("SESSION_SECRET", "yes-i-am-dev")

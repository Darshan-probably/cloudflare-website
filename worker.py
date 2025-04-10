from fastapi import FastAPI, Request, WebSocket, Header, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware
import httpx
import json
import os
from typing import Optional, List
import base64
import hmac
import hashlib

app = FastAPI()

# CORS configuration
ALLOWED_ORIGINS = [
    "https://music.yourdomain.com",  # Your production domain
    "https://speechless.yourusername.workers.dev",  # Workers dev domain
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development - narrow this down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use the SESSION_SECRET environment variable for security
SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev_secret_change_this")
app.add_middleware(
    SessionMiddleware, 
    secret_key=SESSION_SECRET,
    https_only=True,
    same_site="lax"
)

# Config values
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI")
DISCORD_OAUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_URL = "https://discord.com/api/users/@me"
MAIN_SERVER_URL = os.environ.get("MAIN_SERVER_URL")
API_SECRET = os.environ.get("API_SECRET")

# Store WebSocket connections
bot_connection: WebSocket = None
frontend_clients: List[WebSocket] = []
last_now_playing: str = None

# Static files setup - will be manually handled since Workers don't support local file access
static_files = {
    # CSS files
    "/static/css/styles.css": {
        "content_type": "text/css",
        "content": """/* CSS content from your styles.css file */
:root {
    --primary-color: #7289da;
    --background-dark: #18191c;
    --background-light: #2f3136;
    --text-primary: #ffffff;
    --text-secondary: #b9bbbe;
}

/* Add the rest of your CSS content here */
""" 
    },
    # JavaScript files
    "/static/javascripts/script.js": {
        "content_type": "application/javascript",
        "content": """// WebSocket for now playing & queue updates
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;
const reconnectInterval = 3000; // 3 seconds

/* Add the rest of your JavaScript content here */
"""
    },
    # Image placeholders
    "/static/images/Speechless.png": {
        "content_type": "image/png",
        "content": "base64_encoded_image_data_here"  # Replace with actual base64 data
    },
    "/static/images/github-mark.png": {
        "content_type": "image/png",
        "content": "base64_encoded_image_data_here"  # Replace with actual base64 data
    }
}

# Helper function to serve static files
@app.get("/static/{path:path}")
async def serve_static(path: str):
    full_path = f"/static/{path}"
    if full_path in static_files:
        return Response(
            content=static_files[full_path]["content"],
            media_type=static_files[full_path]["content_type"]
        )
    return Response(status_code=404)

# Auth dependency for API token validation
async def get_token(x_api_token: Optional[str] = Header(None)):
    return x_api_token

# Session management utility
class SessionManager:
    def __init__(self, secret):
        self.secret = secret
    
    def create_signature(self, data):
        h = hmac.new(self.secret.encode(), data.encode(), hashlib.sha256)
        return base64.b64encode(h.digest()).decode()
    
    def create_session_cookie(self, data):
        json_data = json.dumps(data)
        b64_data = base64.b64encode(json_data.encode()).decode()
        signature = self.create_signature(b64_data)
        cookie_value = f"{b64_data}.{signature}"
        return f"session={cookie_value}; HttpOnly; Secure; SameSite=Lax; Path=/"
    
    def validate_session(self, cookie_value):
        if not cookie_value or "." not in cookie_value:
            return None
        
        b64_data, signature = cookie_value.split(".")
        expected_signature = self.create_signature(b64_data)
        
        if not hmac.compare_digest(signature, expected_signature):
            return None
        
        try:
            json_data = base64.b64decode(b64_data).decode()
            return json.loads(json_data)
        except:
            return None

    def get_session_from_request(self, request):
        cookies = request.cookies.get("session")
        if not cookies:
            return None
        return self.validate_session(cookies)

# WebSocket endpoint for now playing updates
@app.websocket("/ws/nowplaying")
async def now_playing_ws(websocket: WebSocket):
    global bot_connection, frontend_clients, last_now_playing
    
    await websocket.accept()
    
    # Retrieve token from header
    token = websocket.headers.get("x-api-token")
    
    # If token matches, this is the bot connection
    if token == API_SECRET:
        bot_connection = websocket
        print("Bot connected via WebSocket")
        try:
            while True:
                message = await websocket.receive_text()
                try:
                    data = json.loads(message)
                    
                    # Handle heartbeat messages
                    if data.get("type") == "heartbeat":
                        await websocket.send_text(json.dumps({"type": "heartbeat_ack"}))
                        continue
                    
                    print(f"[Bot] Message received: {message[:100]}...")
                    last_now_playing = message
                    
                    # Broadcast to all frontend clients
                    for client in frontend_clients:
                        try:
                            await client.send_text(message)
                        except Exception as e:
                            print(f"Failed to send to client: {e}")
                except Exception as e:
                    print(f"Error processing bot message: {e}")
        except Exception as e:
            print(f"Bot WebSocket error: {e}")
            bot_connection = None
    
    # Otherwise, this is a frontend client connection
    else:
        frontend_clients.append(websocket)
        client_id = id(websocket)
        print(f"Frontend client connected. ID: {client_id}")
        
        # Send the last now playing info if available
        if last_now_playing:
            try:
                await websocket.send_text(last_now_playing)
            except Exception as e:
                print(f"Error sending initial status: {e}")
        
        try:
            # Keep the connection open
            while True:
                data = await websocket.receive_text()
                try:
                    command = json.loads(data)
                    # Handle client commands
                    if command.get("action") == "status_request" and bot_connection:
                        await bot_connection.send_text(json.dumps({
                            "action": "status_request"
                        }))
                except Exception as e:
                    print(f"Error handling client message: {e}")
        except Exception as e:
            print(f"Frontend WebSocket error: {e}")
            if websocket in frontend_clients:
                frontend_clients.remove(websocket)

# Forward commands to the bot
@app.post("/forward_to_bot/{action}")
async def forward_to_bot(action: str, request: Request, token: str = Depends(get_token)):
    global bot_connection
    
    # Check authentication
    if token != API_SECRET:
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized", "status": "failed"}
        )
    
    if not bot_connection:
        return JSONResponse(
            status_code=503,
            content={"error": "Bot is not connected", "status": "failed"}
        )
    
    try:
        # Parse the request body
        payload = await request.json()
        
        # Create the command structure
        command = {
            "action": action,
            "payload": payload
        }
        
        # Send to the bot
        await bot_connection.send_text(json.dumps(command))
        return {"message": f"Command '{action}' sent to bot", "status": "success"}
    except Exception as e:
        print(f"Error forwarding command to bot: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "status": "failed"}
        )

# Control endpoints
@app.post("/control/{action}")
async def control_action(action: str, request: Request):
    try:
        payload = await request.json()
        
        # Forward the command to the bot API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MAIN_SERVER_URL}/forward_to_bot/{action}",
                json=payload,
                headers={"x-api-token": API_SECRET}
            )
            return response.json()
    except Exception as e:
        return {"error": str(e), "status": "failed"}

# Search suggestions endpoint
@app.get("/search/suggestions")
async def search_suggestions(query: str):
    # If it's a URL, offer simple suggestion
    if query.startswith("http"):
        return ["Play this URL"]
    
    # For non-URLs, offer generic suggestions
    suggestions = [
        f"{query} - Official Video",
        f"{query} - Audio",
        f"{query} - Live Performance"
    ]
    return suggestions

# Main page
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    # Get user from session
    session_manager = SessionManager(SESSION_SECRET)
    user = session_manager.get_session_from_request(request)
    
    # Render the appropriate HTML
    if user:
        # Logged in view
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Speechless - Discord Music Bot</title>
    <link rel="stylesheet" href="/static/css/styles.css">
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar">
        <div class="navbar-brand">Speechless</div>
        <div class="navbar-links">
            <a href="/docs" class="docs-button">Docs</a>
            <div class="dropdown">
                <button class="dropbtn">
                    <div class="user-info">
                        <img src="USER_AVATAR" alt="User Avatar" class="user-avatar">
                        <span>USER_NAME</span>
                    </div>
                </button>
                <div class="dropdown-content">
                    <a href="/logout">Logout</a>
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Container -->
    <div class="container">
        <!-- Search Section -->
        <section class="search-section">
            <form id="search-form" method="POST" onsubmit="return false;">
                <input type="text" id="search-input" placeholder="Search for a track..." required>
                <button type="submit" id="search-btn">Search</button>
            </form>
        </section>

        <section class="player-container">
            <!-- Now Playing Section -->
            <div class="now-playing">
                <h2>Now Playing</h2>
                <div class="track-info">
                    <img id="album-art" src="/static/images/Speechless.png" alt="Album Art">
                    <div class="track-details">
                        <h3 id="track-title">No track playing</h3>
                        <p id="track-artist"></p>
                        <div class="progress-bar">
                            <div id="progress" class="progress"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Queue Section -->
            <div class="queue-section">
                <h2>Queue</h2>
                <div id="queue">
                    <p>No songs in queue.</p>
                </div>
            </div>
            
            <!-- Controls Section -->
            <div class="controls">
                <button class="control-btn" onclick="handleControl('previous')">Previous</button>
                <button class="control-btn" onclick="handleControl('play_pause')">Play/Pause</button>
                <button class="control-btn" onclick="handleControl('skip')">Skip</button>
                <button class="control-btn" onclick="handleControl('loop')">Loop</button>
                <button class="control-btn" onclick="handleControl('shuffle')">Shuffle</button>
                <button class="control-btn" onclick="handleControl('stop')">Stop</button>
            </div>
        </section>
    </div>

    <!-- Footer -->
    <footer class="footer">
        <a href="https://github.com/Darshan-probably" target="_blank">
            <img src="/static/images/github-mark.png" alt="GitHub" class="github-logo">
        </a>
    </footer>

    <!-- JavaScript -->
    <script src="/static/javascripts/script.js"></script>
</body>
</html>
"""
        # Replace user info placeholders
        html_content = html_content.replace("USER_NAME", user["username"])
        html_content = html_content.replace("USER_AVATAR", user["avatar_url"])
    else:
        # Logged out view
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Speechless - Discord Music Bot</title>
    <link rel="stylesheet" href="/static/css/styles.css">
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar">
        <div class="navbar-brand">Speechless</div>
        <div class="navbar-links">
            <a href="/docs" class="docs-button">Docs</a>
            <a href="/login" class="login-button">Login</a>
        </div>
    </nav>

    <!-- Main Container -->
    <div class="container">
        <!-- About Section -->
        <section class="about">
            <img id="ok" src="/static/images/Speechless.png" alt="Speechless logo">
            <div class="about-text">
                <h2>Welcome to Speechless!</h2>
                <p>Speechless is a Discord music bot built on Hopes and Dreams.</p>
                <a href="/login" class="login-button hero-login">Login with Discord</a>
            </div>
        </section>
    </div>

    <!-- Footer -->
    <footer class="footer">
        <a href="https://github.com/Darshan-probably" target="_blank">
            <img src="/static/images/github-mark.png" alt="GitHub" class="github-logo">
        </a>
    </footer>
</body>
</html>
"""
    
    return HTMLResponse(content=html_content)

# Login route
@app.get("/login")
async def login():
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
    }
    url = httpx.URL(DISCORD_OAUTH_URL, params=params)
    return RedirectResponse(url=str(url))

# OAuth callback
@app.get("/oauth-callback")
async def oauth_callback(request: Request, code: str = None):
    if code is None:
        return JSONResponse(
            status_code=400,
            content={"error": "No code provided"}
        )
    
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "scope": "identify",
    }
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(DISCORD_TOKEN_URL, data=data, headers=headers)
        token_json = token_resp.json()
    
    access_token = token_json.get("access_token")
    if not access_token:
        return JSONResponse(
            status_code=400,
            content={"error": "Failed to get access token"}
        )
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(DISCORD_API_URL, headers=headers)
        user_json = user_resp.json()
    
    user = {
        "username": user_json.get("username"),
        "avatar": user_json.get("avatar"),
        "id": user_json.get("id"),
        "avatar_url": f"https://cdn.discordapp.com/avatars/{user_json.get('id')}/{user_json.get('avatar')}.png"
    }
    
    # Create session
    session_manager = SessionManager(SESSION_SECRET)
    response = RedirectResponse(url="/")
    response.headers["Set-Cookie"] = session_manager.create_session_cookie(user)
    
    return response

# Logout route
@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.headers["Set-Cookie"] = "session=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0"
    return response

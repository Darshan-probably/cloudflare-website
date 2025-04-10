# app/main.py - Updated with CORS for production

import uvicorn
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from starlette.routing import WebSocketRoute
import os
from app.config import DISCORD_API_URL, DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_OAUTH_URL, DISCORD_REDIRECT_URI, DISCORD_TOKEN_URL, SESSION_SECRET
from app.api import router as api_router
from app.control import router as control_router

# List of allowed origins
ALLOWED_ORIGINS = [
    "https://music.yourdomain.com",     # Your Cloudflare Worker subdomain
    "https://speechless-web-ui.yourusername.workers.dev",  # Workers dev domain
    "http://127.0.0.1:8000",            # Local development
]

app = FastAPI()

# Add middleware in the correct order.
app.add_middleware(ProxyHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware, 
    secret_key=SESSION_SECRET,
    # For production, use secure cookies
    https_only=True,
    same_site="lax"
)

# Include custom routers.
app.include_router(api_router)
app.include_router(control_router)

# Mount static files and initialize templates.
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# The rest of your code remains the same...

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n🔌 WebSocket Routes Initialized:")
    for route in app.routes:
        from starlette.routing import WebSocketRoute
        if isinstance(route, WebSocketRoute):
            print(f"📡 {route.path}")
    yield

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = request.session.get("user")
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/login")
async def login():
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
    }
    url = httpx.URL(DISCORD_OAUTH_URL, params=params)
    return RedirectResponse(url)

@app.get("/oauth-callback")
async def oauth_callback(request: Request, code: str = None):
    if code is None:
        raise HTTPException(status_code=400, detail="No code provided")
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
        raise HTTPException(status_code=400, detail="Failed to get access token")
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(DISCORD_API_URL, headers=headers)
        user_json = user_resp.json()
    request.session["user"] = {
        "username": user_json.get("username"),
        "avatar": user_json.get("avatar"),
        "id": user_json.get("id"),
        # Optionally, include avatar_url directly.
        "avatar_url": f"https://cdn.discordapp.com/avatars/{user_json.get('id')}/{user_json.get('avatar')}.png"
    }
    return RedirectResponse(url="/")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

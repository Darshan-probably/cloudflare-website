from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse
import json
from typing import List
import os
from app.config import API_SECRET

router = APIRouter()

# Store the bot connection and frontend client list.
bot_connection: WebSocket = None
frontend_clients: List[WebSocket] = []

# Global variable to store last now playing message.
last_now_playing: str = None

@router.websocket("/ws/nowplaying")
async def now_playing_ws(websocket: WebSocket):
    global bot_connection, last_now_playing

    # Retrieve token from header.
    token = websocket.headers.get("x-api-token")
    await websocket.accept()

    # If token matches, this connection is from the bot.
    if token == API_SECRET:
        bot_connection = websocket
        print("Bot connected to backend via WebSocket.")
        try:
            while True:
                message = await websocket.receive_text()
                print(f"[Bot] Now Playing: {message}")
                last_now_playing = message
                # Broadcast to all connected frontend clients.
                for client in frontend_clients:
                    try:
                        await client.send_text(message)
                    except Exception as e:
                        print(f"Failed to send to client: {e}")
        except WebSocketDisconnect:
            print("Bot disconnected.")
            bot_connection = None

    # Otherwise, treat this as a frontend connection.
    else:
        frontend_clients.append(websocket)
        print("Frontend user connected via WebSocket.")
        # Immediately send last now playing if available.
        if last_now_playing:
            await websocket.send_text(last_now_playing)
        try:
            while True:
                # Optionally wait for messages (if needed).
                await websocket.receive_text()
        except WebSocketDisconnect:
            print("Frontend user disconnected.")
            frontend_clients.remove(websocket)

@router.post("/forward_to_bot/{action}")
async def forward_to_bot(action: str, request: Request):
    """
    Forwards a command to the connected bot via WebSocket
    """
    global bot_connection
    
    if not bot_connection:
        return JSONResponse(status_code=503, content={"error": "Bot is not connected", "status": "failed"})
    
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
        return JSONResponse(status_code=500, content={"error": str(e), "status": "failed"})
    
# In app/api.py - Update the search/suggestions endpoint:
@router.get("/search/suggestions")
async def search_suggestions(query: str):
    """
    Returns suggestions based on query.
    """
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
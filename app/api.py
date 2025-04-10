# app/api.py - Updated for Cloudflare Worker support
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, Header, Depends
from fastapi.responses import JSONResponse
import json
from typing import List, Optional
import os
from app.config import API_SECRET

router = APIRouter()

# Store the bot connection and frontend client list.
bot_connection: WebSocket = None
frontend_clients: List[WebSocket] = []

# Global variable to store last now playing message.
last_now_playing: str = None

async def get_token(x_api_token: Optional[str] = Header(None)):
    return x_api_token

@router.websocket("/ws/nowplaying")
async def now_playing_ws(websocket: WebSocket):
    global bot_connection, last_now_playing

    await websocket.accept()
    
    # Retrieve token from header.
    token = websocket.headers.get("x-api-token")

    # If token matches, this connection is from the bot.
    if token == API_SECRET:
        bot_connection = websocket
        print("Bot connected to backend via WebSocket.")
        try:
            while True:
                message = await websocket.receive_text()
                try:
                    data = json.loads(message)
                    
                    # Handle heartbeat messages
                    if data.get("type") == "heartbeat":
                        # Just respond with acknowledgment
                        await websocket.send_text(json.dumps({"type": "heartbeat_ack"}))
                        continue
                        
                    # Process other messages as before
                    print(f"[Bot] Message received: {message[:100]}...")
                    last_now_playing = message
                    # Broadcast to all connected frontend clients.
                    for client in frontend_clients:
                        try:
                            await client.send_text(message)
                        except Exception as e:
                            print(f"Failed to send to client: {e}")
                except json.JSONDecodeError:
                    print(f"Received invalid JSON: {message[:100]}...")
                except Exception as e:
                    print(f"Error processing message: {e}")
        except WebSocketDisconnect:
            print("Bot disconnected.")
            bot_connection = None
        except Exception as e:
            print(f"Error in bot websocket: {e}")
            bot_connection = None

    # Otherwise, treat this as a frontend connection.
    else:
        frontend_clients.append(websocket)
        client_id = id(websocket)
        print(f"Frontend user connected via WebSocket. Client ID: {client_id}")
        
        # Immediately send last now playing if available.
        if last_now_playing:
            try:
                await websocket.send_text(last_now_playing)
            except Exception as e:
                print(f"Error sending initial status: {e}")
        
        try:
            # Keep connection open and handle incoming messages
            while True:
                data = await websocket.receive_text()
                try:
                    command = json.loads(data)
                    # Handle command if needed (e.g., status request)
                    if command.get("action") == "status_request" and bot_connection:
                        await bot_connection.send_text(json.dumps({
                            "action": "status_request"
                        }))
                except Exception as e:
                    print(f"Error handling client message: {e}")
        except WebSocketDisconnect:
            print(f"Frontend user disconnected. Client ID: {client_id}")
            if websocket in frontend_clients:
                frontend_clients.remove(websocket)
        except Exception as e:
            print(f"Error in frontend websocket: {e}")
            if websocket in frontend_clients:
                frontend_clients.remove(websocket)

@router.post("/forward_to_bot/{action}")
async def forward_to_bot(action: str, request: Request, token: str = Depends(get_token)):
    """
    Forwards a command to the connected bot via WebSocket
    """
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
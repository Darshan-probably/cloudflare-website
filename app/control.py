# app/control.py
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse
import httpx
from app.config import API_SECRET, BOT_SERVER_HOST, BOT_SERVER_PORT

router = APIRouter(prefix="/control", tags=["control"])

@router.post("/{action}")
async def control_action(action: str, payload: dict = Body({})):
    """
    Handles control commands. Action can be 'previous', 'play_pause', 'skip', 'loop', 'shuffle', 'stop'.
    """
    print(f"Control command received: {action} with payload: {payload}")
    
    # Forward the command to the bot via the bot server
    async with httpx.AsyncClient() as client:
        try:
            # Add API_SECRET to the headers
            headers = {"x-api-token": API_SECRET}
            response = await client.post(
                f"http://{BOT_SERVER_HOST}:{BOT_SERVER_PORT}/bot/{action}", 
                json=payload,
                headers=headers
            )
            return response.json()
        except Exception as e:
            print(f"Error forwarding command to bot server: {e}")
            return {"error": str(e), "status": "failed"}
        

@router.post("/search")
async def control_search(payload: dict = Body(...)):    
    """
    Handles search requests. Expects a 'query' in the payload.
    """
    query = payload.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Missing query in payload.")
    print(f"Search query received: {query}")
    
    # Forward the search request to the bot server
    async with httpx.AsyncClient() as client:
        try:
            headers = {"x-api-token": API_SECRET}
            response = await client.post(
                f"http://{BOT_SERVER_HOST}:{BOT_SERVER_PORT}/bot/search", 
                json=payload,
                headers=headers
            )
            return response.json()
        except Exception as e:
            print(f"Error forwarding search to bot server: {e}")
            return {"error": str(e), "status": "failed"}

@router.get("/search/suggestions")
async def search_suggestions(query: str):
    """
    Returns suggestions based on query by fetching from bot server.
    """
    # Forward suggestion request to bot server
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"http://{BOT_SERVER_HOST}:{BOT_SERVER_PORT}/search/suggestions?query={query}"
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error fetching suggestions from bot server: {e}")
    
    # Fallback suggestions if bot server is unreachable
    if query.startswith("http"):
        return ["Add this URL to queue"]
    
    suggestions = [
        f"{query} - Song",
        f"{query} - Official Video",
        f"{query} - Audio"
    ]
    return suggestions

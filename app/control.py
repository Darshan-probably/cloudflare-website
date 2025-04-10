# app/control.py
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse
import httpx
from app.config import API_SECRET, MAIN_URL, PORT


router = APIRouter(prefix="/control", tags=["control"])

@router.post("/{action}")
async def control_action(action: str, payload: dict = Body({})):
    """
    Handles control commands. Action can be 'previous', 'play_pause', 'skip', 'loop', 'shuffle', 'stop'.
    """
    print(f"Control command received: {action} with payload: {payload}")
    
    # Forward the command to the bot via our API endpoint
    async with httpx.AsyncClient() as client:
        try:
            # Add API_SECRET to the headers
            headers = {"x-api-token": API_SECRET}
            response = await client.post(
                f"http://{MAIN_URL}:{PORT}/forward_to_bot/{action}", 
                json=payload,
                headers=headers  # Add this line
            )
            return response.json()
        except Exception as e:
            print(f"Error forwarding command: {e}")
            return {"error": str(e), "status": "failed"}
        

# Keep your other functions unchanged...
@router.post("/search")
async def control_search(payload: dict = Body(...)):    
    """
    Handles search requests. Expects a 'query' in the payload.
    """
    query = payload.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Missing query in payload.")
    print(f"Search query received: {query}")
    
    # Forward the search request with the API token
    async with httpx.AsyncClient() as client:
        try:
            headers = {"x-api-token": API_SECRET}
            response = await client.post(
                f"http://{MAIN_URL}:{PORT}/forward_to_bot/search", 
                json=payload,
                headers=headers
            )
            return response.json()
        except Exception as e:
            print(f"Error forwarding search: {e}")
            return {"error": str(e), "status": "failed"}
    
    # Keep your fallback code or remove it if you only want to use the forwarded response


# In app/control.py
@router.get("/search/suggestions")
async def search_suggestions(query: str):
    """
    Returns suggestions based on query.
    """
    # If it's a URL, treat it differently (for YouTube, Spotify, etc.)
    if query.startswith("http"):
        return ["Add this URL to queue"]
    
    # Otherwise, provide normal search suggestions
    # Replace with your actual suggestion logic
    suggestions = [
        f"{query} - Song 1",
        f"{query} - Song 2",
        f"{query} - Song 3"
    ]
    return suggestions  
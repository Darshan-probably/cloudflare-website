# app/control.py
from fastapi import APIRouter, Body, HTTPException
from app.config import API_SECRET

router = APIRouter(prefix="/control", tags=["control"])

@router.post("/{action}")
async def control_action(action: str, payload: dict = Body({})):
    """
    Handles control commands. Action can be 'previous', 'play_pause', 'skip', 'loop', 'shuffle', 'stop'.
    """
    print(f"Control command received: {action} with payload: {payload}")
    # Here, add logic to forward the command to your Discord bot or process it accordingly.
    return {"message": f"Action '{action}' received", "payload": payload}

@router.post("/search")
async def control_search(payload: dict = Body(...)):
    """
    Handles search requests. Expects a 'query' in the payload.
    """
    query = payload.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Missing query in payload.")
    print(f"Search query received: {query}")
    # Simulated search result; integrate with your actual search logic.
    result = {
        "title": "Sample Track Title",
        "artist": "Sample Artist",
        "thumbnail": "https://via.placeholder.com/150",
        "position": 0,
        "duration": 300
    }
    return result

@router.get("/search/suggestions")
async def search_suggestions(query: str):
    """
    Returns suggestions based on query.
    """
    # Simulated suggestion list; replace with your search engine logic.
    suggestions = [
        "Sample Track 1",
        "Sample Track 2",
        "Sample Track 3"
    ]
    return suggestions

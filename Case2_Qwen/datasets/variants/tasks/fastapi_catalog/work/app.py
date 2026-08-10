import json

from fastapi import FastAPI, HTTPException, Query

app = FastAPI(title="Item Catalog API")

# Load data at startup
with open("data.json", "r") as f:
    items = [dict(item) for item in json.load(f)]


@app.get("/items")
def get_all_items():
    """Get all items."""
    return {"items": items}


@app.get("/items/search")
def search_items(q: str = Query(..., description="Search query (required)")):
    """Search items by name with case-insensitive substring match."""
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    q_lower = q.lower()
    matches = [item for item in items if q_lower in item["name"].lower()]
    return {"items": matches}


@app.get("/items/{id}")
def get_item(id: int):
    """Get a single item by ID. Returns 404 if not found."""
    item = next((i for i in items if i["id"] == id), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item with id {id} not found")
    return {"item": item}

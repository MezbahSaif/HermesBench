from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


app = FastAPI(title="Item Catalog API")

# In-memory data store initialized from data.json
import json

with open("data.json", "r") as f:
    initial_data = json.load(f)

items = {
    item["id"]: {
        "id": item["id"],
        "name": item["name"],
        "price": float(item["price"]),
    }
    for item in initial_data
}
next_id = max(items.keys()) + 1 if items else 1


class ItemCreate(BaseModel):
    name: str
    price: float


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float


@app.get("/items", response_model=List[ItemResponse])
def list_items():
    """Return all items in the catalog."""
    return list(items.values())


@app.get("/items/search")
def search_items(q: str):
    """Search items by name (case-insensitive substring match)."""
    query_lower = q.lower()
    matches = [item for item in items.values() if query_lower in item["name"].lower()]
    return matches


@app.get("/items/{item_id}", response_model=ItemResponse)
def get_item(item_id: int):
    """Get a single item by ID. Returns 404 if not found."""
    if item_id not in items:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    return items[item_id]


@app.post("/items", response_model=ItemResponse, status_code=201)
def create_item(item: ItemCreate):
    """Create a new item with auto-incremented ID."""
    global next_id
    items[next_id] = {
        "id": next_id,
        "name": item.name,
        "price": item.price
    }
    result = items[next_id]
    next_id += 1
    return result

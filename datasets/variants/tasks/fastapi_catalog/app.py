"""FastAPI item catalog API."""

from dataclasses import asdict, dataclass
from typing import List, Optional
import json


@dataclass
class Item:
    """Item model matching data.json structure."""
    id: int
    name: str
    price: float


class CatalogService:
    """In-memory catalog service loading data from JSON file."""

    def __init__(self, data_file: str):
        self.data_file = data_file
        self._load_items()

    def _load_items(self) -> None:
        with open(self.data_file, "r") as f:
            raw = json.load(f)
        self.items: dict[int, Item] = {item["id"]: Item(**item) for item in raw}
    
    def get_all(self) -> List[Item]:
        return list(self.items.values())
    
    def get_by_id(self, item_id: int) -> Item | None:
        return self.items.get(item_id)
    
    def search(self, query: str) -> List[Item]:
        q_lower = query.lower()
        return [item for item in self.items.values() if q_lower in item.name.lower()]


def load_catalog(data_file: str) -> CatalogService:
    return CatalogService(data_file)


# Global catalog instance loaded at module level
catalog: CatalogService | None = None


class ItemResponse:
    """Single item response."""
    def __init__(self, id: int, name: str, price: float):
        self.id = id
        self.name = name
        self.price = price
    
    def dict(self) -> dict:
        return {"id": self.id, "name": self.name, "price": self.price}


class ItemsResponse:
    """List of items response."""
    def __init__(self, items):
        self.items = items

    def dict(self) -> dict:
        return {"items": [item.dict() for item in self.items]}


def get_catalog() -> CatalogService:
    global catalog
    if catalog is None:
        catalog = load_catalog("data.json")
    return catalog


from fastapi import FastAPI, HTTPException, Query

app = FastAPI(title="Item Catalog API", version="0.1.0")


@app.get("/items", status_code=200)
async def list_items():
    """List all items in the catalog."""
    items = get_catalog().get_all()
    return ItemsResponse(items=[ItemResponse(**item.__dict__) for item in items]).dict()


@app.get("/items/search", status_code=200)
async def search_items(q: Optional[str] = Query(None, description="Search query string")):
    """Search items by name.

    Returns list of matching items.
    """
    if q is None or len(q.strip()) == 0:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")
    items = get_catalog().search(q)
    return ItemsResponse(items=[ItemResponse(**item.__dict__) for item in items]).dict()


@app.get("/items/{item_id}", status_code=200)
async def get_item(item_id: int):
    """Get a single item by ID.

    Returns 404 if item not found.
    """
    item = get_catalog().get_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item with id {item_id} not found")
    return ItemResponse(**item.__dict__).dict()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Catalog API

Build a FastAPI app in `app.py` for a small item catalog. Load `data.json`
at startup into an in-memory list.

Endpoints:
- GET /items           -> all items
- GET /items/{id}      -> one item; 404 if missing
- GET /items/search    -> query param `q` (str, required): case-insensitive
                          substring match on item name; returns matching items

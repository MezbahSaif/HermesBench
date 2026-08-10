# Orders API

Build a FastAPI app in `app.py` for a small ordering system. Load `data.json`
(products with `price`) at startup.

Endpoints:
- GET /orders                 -> all orders
- GET /orders/{id}            -> one order; 404 if missing
- POST /orders                -> body {"items": [{"product_id": 1, "qty": 2}]};
                                 returns 201 with the order including
                                 "total" (sum of price * qty, rounded to 2),
                                 and a generated "id" (max id + 1)

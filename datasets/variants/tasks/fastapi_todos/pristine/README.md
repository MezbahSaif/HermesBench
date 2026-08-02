# Todo API

Build a FastAPI app in `app.py` for a small todo list. Data is stored
in-memory (a Python list); the id counter starts at 1.

Endpoints:
- GET /todos          -> list of all todos
- GET /todos/{id}     -> one todo; 404 JSON {"detail": "not found"} if missing
- POST /todos         -> body {"task": "..."}; creates todo with {"id": 2, "task": "...", "done": false}, returns 201
- DELETE /todos/{id}  -> deletes the todo; 204 on success, 404 if missing

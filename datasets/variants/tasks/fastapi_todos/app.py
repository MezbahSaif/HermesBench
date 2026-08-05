from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

app = FastAPI(title="Todo API")

# In-memory storage
todos: List[dict] = []
next_id = 1


class Todo(BaseModel):
    title: str
    completed: bool = False


class TodoResponse(Todo):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


def get_todo_or_404(todo_id: int) -> dict:
    """Get a todo by ID or return 404 error."""
    global todos
    for todo in todos:
        if todo['id'] == todo_id:
            return todo
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Todo with id {todo_id} not found"
    )


@app.get("/", response_model=dict)
def root():
    """Root endpoint returning API info."""
    return {
        "name": "Todo API",
        "version": "1.0.0",
        "endpoints": [
            "/todos (GET)",
            "/todos (POST)",
            "/todos/{todo_id} (GET)",
            "/todos/{todo_id} (PUT)",
            "/todos/{todo_id} (DELETE)"
        ]
    }


@app.get("/todos", response_model=List[TodoResponse])
def list_todos():
    """Get all todos."""
    global todos
    return [TodoResponse(**todo) for todo in todos]


@app.post("/todos", status_code=status.HTTP_201_CREATED, response_model=TodoResponse)
def create_todo(todo: Todo):
    """Create a new todo."""
    global next_id, todos
    
    new_todo = {
        "id": next_id,
        "title": todo.title,
        "completed": todo.completed,
        "created_at": datetime.now()
    }
    todos.append(new_todo)
    return TodoResponse(**new_todo)


@app.get("/todos/{todo_id}", response_model=TodoResponse)
def get_todo(todo_id: int):
    """Get a specific todo by ID."""
    global todos
    
    for todo in todos:
        if todo['id'] == todo_id:
            return TodoResponse(**todo)
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Todo with id {todo_id} not found"
    )


@app.put("/todos/{todo_id}", response_model=TodoResponse)
def update_todo(todo_id: int, todo_data: Todo):
    """Update an existing todo."""
    global todos
    
    for i, todo in enumerate(todos):
        if todo['id'] == todo_id:
            todos[i]['title'] = todo_data.title
            todos[i]['completed'] = todo_data.completed
            return TodoResponse(**todos[i])
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Todo with id {todo_id} not found"
    )


@app.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int):
    """Delete a todo by ID."""
    global todos
    
    for i, todo in enumerate(todos):
        if todo['id'] == todo_id:
            del todos[i]
            return None  # Return nothing for 204 status
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Todo with id {todo_id} not found"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import List

app = FastAPI()

# In-memory storage
todos: List[dict] = []
id_counter = 1


class TodoCreate(BaseModel):
    task: str


@app.get("/todos")
def list_todos() -> List[dict]:
    return todos


@app.get("/todos/{todo_id}")
def get_todo(todo_id: int) -> dict:
    global id_counter
    for todo in todos:
        if todo["id"] == todo_id:
            return todo
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")


@app.post("/todos", status_code=status.HTTP_201_CREATED)
def create_todo(todo: TodoCreate) -> dict:
    global id_counter
    new_todo = {
        "id": id_counter,
        "task": todo.task,
        "done": False,
    }
    todos.append(new_todo)
    id_counter += 1
    return new_todo


@app.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int) -> None:
    global id_counter
    for i, todo in enumerate(todos):
        if todo["id"] == todo_id:
            todos.pop(i)
            return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")

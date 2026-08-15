from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json

app = FastAPI()


# Load initial data from data.json at startup
with open("data.json", "r") as f:
    todos = json.load(f)
next_id = max((t["id"] for t in todos), default=0) + 1


class TodoCreate(BaseModel):
    task: str


@app.get("/todos")
def list_todos():
    return todos


@app.get("/todos/{todo_id}")
def get_todo(todo_id: int):
    for todo in todos:
        if todo["id"] == todo_id:
            return todo
    raise HTTPException(status_code=404, detail="not found")


@app.post("/todos", status_code=201)
def create_todo(todo_data: TodoCreate):
    new_todo = {"id": next_id, "task": todo_data.task, "done": False}
    todos.append(new_todo)
    next_id += 1
    return new_todo


@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int):
    for i, todo in enumerate(todos):
        if todo["id"] == todo_id:
            del todos[i]
            return None
    raise HTTPException(status_code=404, detail="not found")

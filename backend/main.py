from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

expenses = []
next_id = 1

class Expense(BaseModel):
    description: str
    amount: float
    category: str
    date: str

@app.get("/api/expenses")
def get_expenses():
    return expenses

@app.post("/api/expenses", status_code=201)
def add_expense(expense: Expense):
    global next_id
    entry = {"id": next_id, **expense.dict()}
    next_id += 1
    expenses.append(entry)
    return entry


@app.get("/api/expenses/summary")
def summary():
    totals = {}
    for e in expenses:
        cat = e["category"]
        if cat not in totals:
            totals[cat] = {"total": 0, "count": 0}
        totals[cat]["total"] += e["amount"]
        totals[cat]["count"] += 1
    return totals

@app.get("/api/expenses/total")
def total():
    return {"total": sum(e["amount"] for e in expenses)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)


@app.put("/api/expenses/{id}")
def update_expense(id: int, expense: Expense):
    for i, e in enumerate(expenses):
        if e["id"] == id:
            expenses[i] = {
                "id": id,
                "description": expense.description,
                "amount": expense.amount,
                "category": expense.category,
                "date": expense.date
            }
            return {"message": f"Updated expense #{id}", "expense": expenses[i]}
    raise HTTPException(status_code=404, detail="Expense not found")

@app.delete("/api/expenses/{id}")
def delete_expense(id: int):
    for i, e in enumerate(expenses):
        if e["id"] == id:
            expenses.pop(i)
            return {"message": f"Deleted expense #{id}"}
    raise HTTPException(status_code=404, detail="Expense not found")

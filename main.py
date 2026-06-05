from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import sqlite3
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
import uuid

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_db():
    conn = sqlite3.connect("pastes.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pastes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL UNIQUE,
            text TEXT NOT NULL,
            creation_time TEXT NOT NULL,
            author TEXT NOT NULL,
            views INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

class Paste(BaseModel):
    text: str = Field(max_length=50_000)
    #expiry: int
    author: str = Field("Guest", max_length=100)

@app.post("/create")
@limiter.limit("5/minute")
async def create(request: Request, paste: Paste):
    conn = sqlite3.connect("pastes.db")
    cursor = conn.cursor()
    paste_uuid = str(uuid.uuid4())
    creation_time = datetime.now(timezone.utc).isoformat()

    if paste.text.strip() == '':
        raise HTTPException(status_code=400, detail="Paste cannot be empty")

    cursor.execute("INSERT INTO pastes (uuid, text, creation_time, author) VALUES (?, ?, ?, ?)", (paste_uuid, paste.text, creation_time, paste.author))
    conn.commit()
    conn.close()
    return {"id": paste_uuid, "message": "Paste created successfully"}

@app.get("/get")
@limiter.limit("15/minute")
async def get_paste(request: Request, id: str):
    conn = sqlite3.connect("pastes.db")
    cursor = conn.cursor()

    cursor.execute("UPDATE pastes SET views = views + 1 WHERE uuid = ?", (id,))
    conn.commit()

    paste = cursor.execute("SELECT * FROM pastes WHERE uuid = ?", (id,)).fetchone()
    conn.close()
    if paste == None:
        raise HTTPException(status_code=404, detail="Paste not found")
    return {"id": paste[1], "text": paste[2], "creation_time": paste[3], "author": paste[4], "views": paste[5]}
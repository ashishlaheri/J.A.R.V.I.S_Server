"""REST API routes."""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from api.auth import verify_token, create_token
from skills import reminders, memory, weather, news
from skills.time_date import get_time, get_date

router = APIRouter(prefix="/api")


# ── Auth dependency ─────────────────────────────────
def require_auth(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(401, "Missing token")
    token = authorization.replace("Bearer ", "")
    if not verify_token(token):
        raise HTTPException(401, "Invalid token")


# ── Models ──────────────────────────────────────────
class LoginRequest(BaseModel):
    password: str

class ReminderRequest(BaseModel):
    text: str
    due_at: str = None

class DeleteReminderRequest(BaseModel):
    id: int = None
    text: str = None

class MemoryRequest(BaseModel):
    key: str
    value: str = None


# ── Auth ────────────────────────────────────────────
@router.post("/login")
async def login(req: LoginRequest):
    token = create_token(req.password)
    if not token:
        raise HTTPException(401, "Wrong password, Sir.")
    return {"token": token}


# ── Briefing ────────────────────────────────────────
@router.get("/briefing", dependencies=[Depends(require_auth)])
async def briefing():
    w = await weather.get_weather()
    n = await news.get_headlines(3)
    r = await reminders.get_reminders()
    return {"weather": w, "news": n, "reminders": r, "time": get_time(), "date": get_date()}


# ── Reminders ───────────────────────────────────────
@router.get("/reminders", dependencies=[Depends(require_auth)])
async def list_reminders():
    return {"message": await reminders.get_reminders()}

@router.post("/reminders", dependencies=[Depends(require_auth)])
async def add_reminder(req: ReminderRequest):
    return {"message": await reminders.add_reminder(req.text, req.due_at)}

@router.delete("/reminders", dependencies=[Depends(require_auth)])
async def delete_reminder(req: DeleteReminderRequest):
    if req.id:
        return {"message": await reminders.delete_reminder(reminder_id=req.id)}
    elif req.text:
        return {"message": await reminders.delete_reminder(text_search=req.text)}
    else:
        return {"message": await reminders.clear_all_reminders()}

@router.delete("/reminders/all", dependencies=[Depends(require_auth)])
async def clear_all_reminders():
    return {"message": await reminders.clear_all_reminders()}


# ── Memory ──────────────────────────────────────────
@router.get("/memory", dependencies=[Depends(require_auth)])
async def list_memories():
    return {"message": await memory.get_all_memories()}

@router.post("/memory", dependencies=[Depends(require_auth)])
async def store_memory(req: MemoryRequest):
    return {"message": await memory.remember(req.key, req.value)}


# ── Health ──────────────────────────────────────────
@router.get("/health")
async def health():
    return {"status": "operational", "system": "J.A.R.V.I.S. v3.1"}

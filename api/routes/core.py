from fastapi import APIRouter, Depends
from db.models import UserRecord
from utils.auth import get_current_user

router = APIRouter(tags=["core"])

@router.get("/")
def root(user: UserRecord = Depends(get_current_user)):
    return {"ok": True, "message": "Chatbox API is running", "version": "0.1.0", "user_name": user.email}


@router.get("/healthz")
def healthz():
    return {"ok": True, "service": "chatbox-api", "version": "0.1.0"}
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models_db import User
from app.schemas import AssistantRequest, AssistantResponse
from app.services.assistant import answer

router = APIRouter()


@router.post("/chat", response_model=AssistantResponse)
def chat(req: AssistantRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Answer read-only FoodBridge questions using the authenticated user's data."""
    return answer(db, user, req.message, req.language)
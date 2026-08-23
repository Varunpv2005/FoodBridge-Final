from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models_db import User
from app.schemas_v2 import RegisterRequest, LoginRequest, TokenResponse
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter()


def _user_public(user: User) -> dict:
    return {
        "id": user.id, "email": user.email, "name": user.name, "role": user.role,
        "phone": user.phone, "lat": user.lat, "lng": user.lng,
        "trust_score": user.trust_score,
        "ngo_capacity_total": user.ngo_capacity_total,
        "ngo_capacity_available": user.ngo_capacity_available,
        "ngo_tier": user.ngo_tier, "ngo_has_cold_storage": user.ngo_has_cold_storage,
        "ngo_sentiment_score": user.ngo_sentiment_score,
        "volunteer_capacity_plates": user.volunteer_capacity_plates,
        "volunteer_is_available": user.volunteer_is_available,
        "volunteer_rating": user.volunteer_rating,
    }


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(400, "Email already registered.")

    user = User(
        email=req.email, hashed_password=hash_password(req.password),
        name=req.name, role=req.role, phone=req.phone, lat=req.lat, lng=req.lng,
        ngo_capacity_total=req.ngo_capacity_total or 100,
        ngo_capacity_available=req.ngo_capacity_total or 100,
        ngo_has_cold_storage=bool(req.ngo_has_cold_storage),
        ngo_tier=req.ngo_tier or 1,
        volunteer_capacity_plates=req.volunteer_capacity_plates or 60,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id, "role": user.role})
    return TokenResponse(access_token=token, user=_user_public(user))


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password.")
    token = create_access_token({"sub": user.id, "role": user.role})
    return TokenResponse(access_token=token, user=_user_public(user))


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _user_public(user)

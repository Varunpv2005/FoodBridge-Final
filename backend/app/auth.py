import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db import get_db
from app.models_db import User

SECRET_KEY = os.getenv("FOODBRIDGE_SECRET", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week, convenient for demos

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, session_id: str) -> str:
    to_encode = data.copy()
    to_encode["session_id"] = session_id
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def new_session_id() -> str:
    return secrets.token_urlsafe(32)


def get_user_from_token(token: str, db: Session) -> User:
    cred_exc = HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        session_id: Optional[str] = payload.get("session_id")
        if user_id is None or session_id is None:
            raise cred_exc
    except JWTError:
        raise cred_exc
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.current_session_id != session_id:
        raise cred_exc
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    return get_user_from_token(token, db)


def require_role(*roles: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {roles}")
        return user
    return _dep

import hashlib
import base64
import bcrypt
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.core.config import settings
from app.core.database import get_db


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _prepare_password(password: str) -> bytes:
    """SHA256 orqali parolni 72 bayt chegarasidan xalos qiladi."""
    password_bytes = password.encode("utf-8")
    sha256_hash = hashlib.sha256(password_bytes).digest()
    return base64.b64encode(sha256_hash)


def hash_password(password: str) -> str:
    prepared = _prepare_password(password)
    hashed = bcrypt.hashpw(prepared, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    prepared = _prepare_password(plain)
    return bcrypt.checkpw(prepared, hashed.encode("utf-8"))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def register_user(db: Session, email: str, password: str, role: str):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return None
    user = User(email=email, password=hash_password(password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password):
        return None
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token yaroqsiz yoki muddati o'tgan",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user


def require_role(*allowed_roles: UserRole):
    """
    Faqat ko'rsatilgan rol(lar)ga ruxsat beruvchi dependency generator.
    Masalan: Depends(require_role(UserRole.admin))
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu amal uchun ruxsatingiz yo'q",
            )
        return current_user

    return role_checker
import hashlib
from datetime import datetime, timezone, timedelta
import jwt
from dotenv import load_dotenv
from api.models import UserResponse
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from db.database import get_db
from db.schema import UserRecord
from sqlalchemy.orm import Session
from jwt.exceptions import PyJWTError
from config.settings import settings

load_dotenv()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

security = HTTPBearer(auto_error=False)

# hash a given password
def hash_password(password: str):
    hashed_password = hashlib.sha256(password.encode())
    hashed_password = hashed_password.hexdigest()
    return hashed_password

# verify if given hashed pw == user hashed pw
def verify_password(plain: str, hashed: str) -> bool:
    plain_hashed = hashlib.sha256(plain.encode()).hexdigest()
    return plain_hashed == hashed

# create user JWT acces token
def create_access_token(user: UserResponse):
    payload = {
        "sub": str(user.id),
    }

    expire = datetime.now(timezone.utc) + timedelta(minutes = ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expire})
    
    return jwt.encode(payload = payload, key = settings.secret_key, algorithm = ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security), db: Session = Depends(get_db)) -> UserRecord:
    if not credentials or credentials.scheme != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization",
        )

    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user_id = int(user_id)
    except (PyJWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(UserRecord).filter(UserRecord.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user
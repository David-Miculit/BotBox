from fastapi import APIRouter
from fastapi import Depends
from db.models import UserRecord
from db.database import get_db
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from utils.hashing import hash_password
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone, timedelta
import jwt
from dotenv import load_dotenv
import os

load_dotenv()
jwt_key = os.getenv("SECRET_KEY")

router = APIRouter(prefix="/auth", tags=["auth"])

class UserSignup(BaseModel):
    email: EmailStr
    name: str = Field(min_length=3, max_length=20)
    phone: str = Field(default="")
    avatar_url: str = Field(default="")
    password: str = Field(min_length=8, max_length=20)

class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str
    phone: str
    avatar_url: str
    # password_hash: str

class TokenResponse():
    user: User
    access_token = str
    token_type: str

    def __init__(self, user, access_token, token_type = "bearer"):
        self.user = user
        self.access_token = access_token
        token_type = token_type

def create_access_token(user: User):
    payload = {
        "sub": str(user.id),
        "email": user.email
    }

    expire = datetime.now(timezone.utc) + timedelta(minutes = 30)
    payload.update({"exp": expire})
    
    encoded_jwt = jwt.encode(payload = payload, key = jwt_key, algorithm = "HS256")
    return encoded_jwt

@router.post("/login")
def login():
    """Login endpoint. Implement later."""
    pass

@router.post("/signup")
def signup(user_signup: UserSignup, db = Depends(get_db)):
    hashed_password = hash_password(user_signup.password)
    new_user = UserRecord(
        email = user_signup.email,
        name = user_signup.name,
        phone = user_signup.phone,
        avatar_url = user_signup.avatar_url,
        password_hash = hashed_password
    )

    try:
        db.add(new_user)
        db.commit()
    except IntegrityError:
        return "User already exists"

    user = User.model_validate(new_user)
    access_token = create_access_token(user)

    return TokenResponse(user=user, access_token=access_token)
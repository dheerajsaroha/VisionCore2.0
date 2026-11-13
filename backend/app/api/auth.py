from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.security import (
    create_access_token,
    get_password_hash,
    verify_password,
    get_current_user,
)

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse, name="auth:login")
async def login(payload: LoginRequest):
    """
    Very simple demo login – replace with DB lookup.
    """
    if payload.email != "admin@example.com":
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    # Simulated stored hash (in production fetch from DB)
    stored_hash = get_password_hash("admin123")
    if not verify_password(payload.password, stored_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = create_access_token({"sub": payload.email})
    return TokenResponse(access_token=access_token)


@router.get("/me", name="auth:me")
async def read_current_user(current_user: dict = Depends(get_current_user)):
    """Echo back the user identifier from the JWT."""
    return {"email": current_user["sub"]}
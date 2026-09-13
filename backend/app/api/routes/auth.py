from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
auth = AuthService()


class Credentials(BaseModel):
    email: str
    password: str


@router.post("/signup", status_code=201)
def signup(credentials: Credentials):
    try:
        user = auth.create_user(credentials.email, credentials.password)
        token, _ = auth.sign_in(credentials.email, credentials.password)
        return {"token": token, "user": user}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/signin")
def signin(credentials: Credentials):
    try:
        token, user = auth.sign_in(credentials.email, credentials.password)
        return {"token": token, "user": user}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/signout", status_code=204)
def signout(authorization: str | None = Header(None)):
    auth.sign_out(_bearer(authorization))


@router.get("/me")
def me(authorization: str | None = Header(None)):
    user = auth.user_for_token(_bearer(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="A valid session is required")
    return user


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None
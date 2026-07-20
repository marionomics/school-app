from typing import Optional

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    username: Optional[str]
    bio: str
    avatar_url: Optional[str]
    role: str
    grade_is_private: bool


class GoogleLoginRequest(BaseModel):
    credential: str


class AuthResponse(BaseModel):
    token: str
    user: UserOut
    needs_onboarding: bool

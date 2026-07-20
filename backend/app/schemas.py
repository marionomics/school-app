from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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


class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, pattern=r"^[a-z0-9_]{3,20}$")
    bio: Optional[str] = Field(default=None, max_length=500)


class GoogleLoginRequest(BaseModel):
    credential: str


class AuthResponse(BaseModel):
    token: str
    user: UserOut
    needs_onboarding: bool

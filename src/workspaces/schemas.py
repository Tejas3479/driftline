from pydantic import BaseModel, EmailStr
from typing import Optional

class WorkspaceUserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "member"

class UserUpdate(BaseModel):
    role: str


from pydantic import BaseModel, EmailStr


class WorkspaceUserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "member"

class UserUpdate(BaseModel):
    role: str

from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr | None = None
    password_string: str
    first_name: str
    middle_name: str
    last_name: str | None = None

class Token(BaseModel):
    access_token: str
    token_type: str

class UserFull(BaseModel):
    email: EmailStr | None = None
    first_name: str
    middle_name: str
    last_name: str | None = None
    id: int
    isu_number: int | None = None
    tg_nickname: str | None = None

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    isu_number: int | None = None
    tg_nickname: str | None = None

class UserResponse(BaseModel):
    id: int
    email: EmailStr

    class Config:
        from_attributes = True

class DeleteResponse(BaseModel):
    message: str


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from schemas import *
from db.models import User

from auth import bcrypt_context

router = APIRouter()

@router.get("/users/{user_id}", response_model=UserFull)
def fetch_user(
    user_id: int, 
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="There is no user with that id!")
    
    return db_user

@router.patch("/users/{user_id}", response_model=UserFull)
def update_user(
    user_id: int, 
    user: UserUpdate,
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="There is no user with that id!")
    
    update_data = user.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)

    return db_user

@router.delete("/users/{user_id}", response_model=DeleteResponse)
def delete_user(
    user_id: int, 
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="There is no user with that id!")
        
    db.delete(db_user)
    db.commit()

    return {"message": "User Deleted"}

@router.post("/users", response_model=UserResponse)
def create_user(
    user: UserCreate, 
    db: Session = Depends(get_db)
):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=404, detail="User with this email alread exists!")

    pwd = user.password_string
    print("pwdpwd:::::::::::::::::", pwd)
    data = user.model_dump(exclude={"password_string"})
    data["password_hashed"] = bcrypt_context.hash(pwd)
    db_user = User(**data)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


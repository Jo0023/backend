from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import User
# passlib has an issue, that is a fix I found. consider using alternatives:
import bcrypt
bcrypt.__about__ = bcrypt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from core.config import settings
from schemas import UserCreate, Token


# router = APIRouter(prefix='/auth', tags=['auth'])

# TODO learn what this is:
bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

oauth2_bearer = OAuth2PasswordBearer(tokenUrl='/auth/token')


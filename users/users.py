import collections
import contextlib
import logging.config
import sqlite3
import datetime
import typing
from typing import Optional
from fastapi import FastAPI, Depends, Response, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import base64
import hashlib
import secrets
import json
import datetime
import jwt

# ------------- Constants -------------
DATABASE='users/var/users.db'
LOGGING_CONFIG='users/etc/logging.ini'
ALGORITHM = "pbkdf2_sha256"

def get_logger():
    return logging.getLogger(__name__)

def get_db(logger: logging.Logger = Depends(get_logger)):
    with contextlib.closing(sqlite3.connect(DATABASE)) as db:
        db.row_factory = sqlite3.Row
        db.set_trace_callback(logger.debug)
        yield db

app = FastAPI()

# logging.config.fileConfig(LOGGING_CONFIG, disable_existing_loggers=False)

# Pydantic model for user registration
class UserRegistration(BaseModel):
    username: str
    password: str
    fullname: str
    roles: str

# Pydantic model for user login
class UserLogin(BaseModel):
    username: str
    password: str

"""
Helper Functions
"""

# Function to hash a password
def hash_password(password, salt=None, iterations=260000):
    if salt is None:
        salt = secrets.token_hex(16)
    assert salt and isinstance(salt, str) and "$" not in salt
    assert isinstance(password, str)
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    b64_hash = base64.b64encode(pw_hash).decode("ascii").strip()
    return "{}${}${}${}".format(ALGORITHM, iterations, salt, b64_hash)

# Function to verify a hash_password
def verify_password(password, password_hash):
    if (password_hash or "").count("$") != 3:
        return False
    algorithm, iterations, salt, b64_hash = password_hash.split("$", 3)
    iterations = int(iterations)
    assert algorithm == ALGORITHM
    compare_hash = hash_password(password, salt, iterations)
    return secrets.compare_digest(password_hash, compare_hash)

# Function to create a new user
def create_user(user: UserRegistration):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password, fullname, roles) VALUES (?, ?, ?, ?)", (user.username, hash_password(user.password),user.fullname, user.roles))
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
    
def expiration_in(minutes):
    creation = datetime.datetime.now(tz=datetime.timezone.utc)
    expiration = creation + datetime.timedelta(minutes=minutes)
    return creation, expiration

# Function to generate JWT claims (Token)
def generate_claims(username, user_id, fullName, roles):
    _, exp = expiration_in(20)

    claims = {
        "aud": "krakend.local.gd",
        "iss": "auth.local.gd",
        "sub": username,
        "jti": str(user_id),
        "roles": roles,
        "name" : fullName,
        "exp": int(exp.timestamp()),
    }

    token = {
        "access_token": claims,
        "refresh_token": claims,
        "exp": int(exp.timestamp()),
    }

    return token

# Authentication using JWT
def authenticate_user(user: UserLogin):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT userid, username, password, fullName, roles FROM users WHERE username=?", [user.username])
    user_data = cursor.fetchone()
    if user_data and verify_password(user.password, user_data[2]): # hashed_password = user_data[2]
        return generate_claims(user.username,user_data[0],user_data[3],user_data[4])
    raise HTTPException(status_code=401, detail="Authentication failed")


"""
Endpoints
"""

@app.get("/",status_code=status.HTTP_200_OK)
def default():
    hidden_paths = ["/openapi.json", "/docs/oauth2-redirect", "/redoc", "/openapi.json", "/docs", "/"]
    url_list = list(filter(lambda x: x["path"] not in hidden_paths, [{"path" : route.path, "name": route.name} for route in app.routes]))
    return {"routes" : url_list, "message" : f'{len(url_list)} routes found'}

# Endpoint for user registration
@app.post("/register")
async def register_user(user: UserRegistration):
    create_user(user)
    return {"message": "User registered successfully"}

# Endpoint for user authentication
@app.post("/login")
async def login_user(user: UserLogin):
    claims = authenticate_user(user)
    return claims
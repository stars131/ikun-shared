import hashlib
import hmac
import os
import time
from typing import Optional

import bcrypt
from fastapi import Request
from sqlalchemy.orm import Session

from .models import User

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required.")

SESSION_COOKIE = "ikun_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
try:
    BCRYPT_ROUNDS = max(4, int(os.getenv("BCRYPT_ROUNDS", "12")))
except ValueError:
    BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def _verify_legacy_password(password: str, password_hash: str) -> bool:
    if "$" not in password_hash:
        return False
    salt, stored_hash = password_hash.split("$", 1)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return hmac.compare_digest(h, stored_hash)


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("$2"):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False
    return _verify_legacy_password(password, password_hash)


def needs_password_rehash(password_hash: str) -> bool:
    return not password_hash.startswith("$2")


def _sign(payload: str) -> str:
    return hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_session_cookie(user_id: int) -> str:
    payload = f"{user_id}:{int(time.time())}"
    signature = _sign(payload)
    return f"{payload}:{signature}"


def parse_session_cookie(token: str) -> Optional[int]:
    parts = token.split(":")
    if len(parts) != 3:
        return None
    user_id_str, timestamp_str, signature = parts
    payload = f"{user_id_str}:{timestamp_str}"
    expected = _sign(payload)
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        ts = int(timestamp_str)
    except ValueError:
        return None
    if time.time() - ts > SESSION_MAX_AGE:
        return None
    try:
        return int(user_id_str)
    except ValueError:
        return None


def get_current_user(request: Request, db: Session) -> Optional[User]:
    token = request.cookies.get(SESSION_COOKIE, "").strip()
    if not token:
        return None
    user_id = parse_session_cookie(token)
    if user_id is None:
        return None
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()

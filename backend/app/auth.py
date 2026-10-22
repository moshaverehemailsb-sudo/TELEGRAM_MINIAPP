"""Telegram Mini App authentication.

The frontend sends the raw `initData` string in the X-Telegram-Init-Data header.
The server verifies its HMAC signature with the bot token. The numeric user id
inside the signed data is the only identity used for authorization.
"""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import Student


@dataclass(frozen=True)
class Identity:
    telegram_user_id: int
    is_advisor: bool


def _unauthorized(detail: str = "احراز هویت انجام نشد. لطفا از داخل تلگرام وارد شوید.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def verify_init_data(init_data: str, bot_token: str, max_age: int) -> int:
    """Return the verified Telegram user id or raise 401."""
    if not init_data or not bot_token:
        raise _unauthorized()

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise _unauthorized()

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise _unauthorized()

    try:
        auth_date = int(pairs.get("auth_date", "0"))
        user_id = int(json.loads(pairs.get("user", ""))["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise _unauthorized()

    if time.time() - auth_date > max_age:
        raise _unauthorized("نشست شما منقضی شده است. Mini App را دوباره باز کنید.")
    return user_id


def get_identity(
    x_telegram_init_data: str | None = Header(default=None),
    x_dev_telegram_id: str | None = Header(default=None),
) -> Identity:
    settings = get_settings()

    if x_telegram_init_data:
        user_id = verify_init_data(
            x_telegram_init_data,
            settings.telegram_bot_token,
            settings.telegram_init_data_max_age,
        )
    elif settings.allow_dev_auth and not settings.is_production and x_dev_telegram_id:
        try:
            user_id = int(x_dev_telegram_id)
        except ValueError:
            raise _unauthorized()
    else:
        raise _unauthorized()

    return Identity(telegram_user_id=user_id, is_advisor=user_id in settings.advisor_ids)


def get_current_student(
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
) -> Student:
    student = db.scalar(select(Student).where(Student.telegram_user_id == identity.telegram_user_id))
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="برای این حساب تلگرام پرونده‌ای ثبت نشده است.",
        )
    return student
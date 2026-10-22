"""Build a SIGNED Telegram initData string for offline testing (synthetic users only).

Run from the backend folder:
  python -m scripts.make_test_init_data 900000001

The printed value is what the Mini App sends in the X-Telegram-Init-Data header.
"""

import hashlib
import hmac
import json
import sys
import time
from urllib.parse import urlencode

from app.config import get_settings


def build_init_data(user_id: int, bot_token: str, first_name: str = "Test") -> str:
    user = json.dumps({"id": user_id, "first_name": first_name}, ensure_ascii=False, separators=(",", ":"))
    fields = {"auth_date": str(int(time.time())), "user": user}

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    return urlencode(fields)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m scripts.make_test_init_data <telegram_user_id>")

    token = get_settings().telegram_bot_token
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is empty in .env")

    print(build_init_data(int(sys.argv[1]), token))
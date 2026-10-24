"""Invite code generation. Codes are shown to the advisor once; only a hash is stored."""

import hashlib
import secrets

from .form_import import normalize_digits

# Without 0, O, 1 and I, so codes are easy to read aloud
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8


def generate_code() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
    return f"{raw[:4]}-{raw[4:]}"


def _clean(value: str) -> str | None:
    text = normalize_digits(value).upper().replace("-", "").replace(" ", "")
    if len(text) != CODE_LENGTH or any(ch not in ALPHABET for ch in text):
        return None
    return text


def hash_code(value: str) -> str | None:
    """Return the storage hash for a code typed by a user, or None if the format is wrong."""
    cleaned = _clean(value)
    if cleaned is None:
        return None
    return hashlib.sha256(cleaned.encode()).hexdigest()
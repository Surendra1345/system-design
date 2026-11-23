from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import defaultdict
from typing import Dict, Tuple


def hash_password(password: str, salt: str | None = None) -> Tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=2**14, r=8, p=1, dklen=64)
    return salt, digest.hex()


def verify_password(password: str, salt: str, expected: str) -> bool:
    _, digest = hash_password(password, salt)
    return hmac.compare_digest(digest, expected)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class TokenBucket:
    """Per-key token bucket. Used to slow down password guessing and cap AI spend."""

    def __init__(self, capacity: float, per_second: float, clock=time.monotonic):
        self.capacity, self.per_second, self.clock = capacity, per_second, clock
        self._state: Dict[str, Tuple[float, float]] = defaultdict(lambda: (capacity, clock()))

    def allow(self, key: str) -> bool:
        tokens, last = self._state[key]
        now = self.clock()
        tokens = min(self.capacity, tokens + (now - last) * self.per_second)
        if tokens < 1:
            self._state[key] = (tokens, now)
            return False
        self._state[key] = (tokens - 1, now)
        return True

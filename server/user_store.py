"""Persisted user accounts: username, salted/hashed password, ELO rating.

Zero knowledge of WebSocket connections, the EventBus, or GameEngine -
this is a plain persistence layer, analogous to how board/rules know
nothing about the server. server/rating_update_handler.py is the only
thing that connects this to game outcomes.

Password hashing uses the stdlib's hashlib.pbkdf2_hmac with a random
per-user salt - never bcrypt/argon2, since adding a third-party
dependency isn't warranted for this project's scope, but plaintext
storage is never acceptable either.

Blocking I/O note: every method here does a synchronous sqlite3 call
directly on the caller's (async) event loop, with no asyncio.to_thread
wrapping. This is a deliberate tradeoff, not an oversight: sqlite3 always
blocks regardless of wrapping, but these are single-row lookups/writes
against an indexed PRIMARY KEY in one local file, called only once per
login (not from the per-tick hot path in server/game_server.py's
_tick_loop) - the resulting stall is on the order of a millisecond, which
this project's scope (a presentation-grade single-process server, not a
production service under real concurrent load) doesn't need to hide
behind a thread handoff.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from dataclasses import dataclass
from enum import Enum, auto

# 200_000 rounds of PBKDF2-HMAC-SHA256 is comfortably above OWASP's current
# minimum recommendation for this algorithm - a stdlib-only choice, since
# adding bcrypt/argon2 isn't warranted here.
PBKDF2_ITERATIONS = 200_000
STARTING_RATING = 1200


class AuthOutcome(Enum):
    NEW_ACCOUNT_CREATED = auto()
    AUTHENTICATED = auto()
    WRONG_PASSWORD = auto()


@dataclass(frozen=True)
class AuthResult:
    outcome: AuthOutcome
    rating: int | None = None


class UserStore:
    def __init__(self, db_path):
        self._connection = sqlite3.connect(db_path)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                rating INTEGER NOT NULL DEFAULT 1200
            )
            """
        )
        self._connection.commit()

    def register_or_authenticate(self, username: str, password: str) -> AuthResult:
        """First login for `username` creates a new account (rating 1200)
        and returns NEW_ACCOUNT_CREATED. An existing username checks
        `password` against the stored hash: AUTHENTICATED if it matches,
        WRONG_PASSWORD (no rating) if it doesn't."""
        row = self._connection.execute(
            "SELECT password_salt, password_hash, rating FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if row is None:
            salt = os.urandom(16)
            password_hash = self._hash(password, salt)
            self._connection.execute(
                "INSERT INTO users (username, password_salt, password_hash, rating) VALUES (?, ?, ?, ?)",
                (username, salt.hex(), password_hash.hex(), STARTING_RATING),
            )
            self._connection.commit()
            return AuthResult(AuthOutcome.NEW_ACCOUNT_CREATED, STARTING_RATING)

        salt_hex, stored_hash_hex, rating = row
        computed_hash = self._hash(password, bytes.fromhex(salt_hex))
        if not hmac.compare_digest(computed_hash.hex(), stored_hash_hex):
            return AuthResult(AuthOutcome.WRONG_PASSWORD)
        return AuthResult(AuthOutcome.AUTHENTICATED, rating)

    def rating_for(self, username: str) -> int | None:
        row = self._connection.execute(
            "SELECT rating FROM users WHERE username = ?", (username,),
        ).fetchone()
        return row[0] if row is not None else None

    def update_rating(self, username: str, new_rating: int) -> None:
        self._connection.execute(
            "UPDATE users SET rating = ? WHERE username = ?", (new_rating, username),
        )
        self._connection.commit()

    def _hash(self, password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)

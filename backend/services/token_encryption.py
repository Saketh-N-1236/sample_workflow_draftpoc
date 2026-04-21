"""
Token encryption helpers for per-repository Personal Access Tokens.

Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
The encryption key is read from TOKEN_ENCRYPTION_KEY in the environment.

If TOKEN_ENCRYPTION_KEY is not set, tokens are stored as plain text with a
warning — suitable only for local development.

Generate a key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import os
import logging

logger = logging.getLogger(__name__)

_PLAIN_PREFIX = "plain:"
_ENC_PREFIX   = "enc:"

_fernet = None
_key_checked = False


def _get_fernet():
    """Lazy-load and cache the Fernet instance."""
    global _fernet, _key_checked
    if _key_checked:
        return _fernet

    _key_checked = True
    raw_key = os.getenv("TOKEN_ENCRYPTION_KEY", "").strip()
    if not raw_key:
        logger.warning(
            "[TOKEN] TOKEN_ENCRYPTION_KEY is not set — PATs will be stored as plain text. "
            "Set this variable in .env for production use."
        )
        return None

    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(raw_key.encode())
        logger.info("[TOKEN] Fernet token encryption active.")
    except Exception as e:
        logger.error("[TOKEN] Invalid TOKEN_ENCRYPTION_KEY (%s) — falling back to plain text.", e)
        _fernet = None

    return _fernet


def encrypt_token(token: str) -> str:
    """
    Encrypt a PAT for storage in the database.

    Returns a string prefixed with "enc:" (encrypted) or "plain:" (no key set).
    The prefix lets decrypt_token handle both cases transparently.
    """
    if not token or not token.strip():
        return ""

    fernet = _get_fernet()
    if fernet is None:
        return f"{_PLAIN_PREFIX}{token}"

    encrypted = fernet.encrypt(token.encode()).decode()
    return f"{_ENC_PREFIX}{encrypted}"


def decrypt_token(stored: str) -> str:
    """
    Decrypt a stored token value.

    Handles:
    - "enc:<fernet_token>"  → decrypt with Fernet
    - "plain:<raw_token>"   → return as-is
    - Legacy (no prefix)    → return as-is (backward compatibility)
    """
    if not stored:
        return ""

    if stored.startswith(_ENC_PREFIX):
        payload = stored[len(_ENC_PREFIX):]
        fernet = _get_fernet()
        if fernet is None:
            logger.error(
                "[TOKEN] Encrypted token found in DB but TOKEN_ENCRYPTION_KEY is not set. "
                "Cannot decrypt — set the key to match the one used during storage."
            )
            return ""
        try:
            return fernet.decrypt(payload.encode()).decode()
        except Exception as e:
            logger.error("[TOKEN] Decryption failed: %s", e)
            return ""

    if stored.startswith(_PLAIN_PREFIX):
        return stored[len(_PLAIN_PREFIX):]

    # Legacy value stored before this module existed (raw token, no prefix)
    return stored

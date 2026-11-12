from __future__ import annotations

import io

import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_NONCE_BYTES = 12


class BiometricCipher:
    """AES-256-GCM encryption for face embeddings.

    The key comes from BIOMETRIC_ENCRYPTION_KEY (32 random bytes, URL-safe
    base64). In development only, a key is derived from SECRET_KEY so the app
    can boot; production validation requires an explicit key.
    """

    def __init__(self, key: bytes | None = None) -> None:
        self._aes = AESGCM(key or settings.biometric_key)

    def encrypt_embedding(self, embedding: np.ndarray) -> bytes:
        buffer = io.BytesIO()
        np.save(buffer, np.asarray(embedding, dtype=np.float32), allow_pickle=False)
        nonce = np.random.bytes(_NONCE_BYTES)
        ciphertext = self._aes.encrypt(nonce, buffer.getvalue(), b"face-embedding-v1")
        return nonce + ciphertext

    def decrypt_embedding(self, payload: bytes | None) -> np.ndarray | None:
        if payload is None:
            return None
        if len(payload) <= _NONCE_BYTES:
            raise ValueError("Invalid encrypted embedding payload")
        nonce, ciphertext = payload[:_NONCE_BYTES], payload[_NONCE_BYTES:]
        plaintext = self._aes.decrypt(nonce, ciphertext, b"face-embedding-v1")
        return np.load(io.BytesIO(plaintext), allow_pickle=False)

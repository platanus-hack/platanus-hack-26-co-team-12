"""AEAD. Sustituye al XOR con keystream reutilizado (C4: two-time pad)."""
from __future__ import annotations

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

__all__ = ["seal", "open_", "InvalidTag"]


def seal(k_cipher: bytes, nonce12: bytes, plaintext: bytes, aad: bytes) -> bytes:
    return ChaCha20Poly1305(k_cipher).encrypt(nonce12, plaintext, aad)


def open_(k_cipher: bytes, nonce12: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    return ChaCha20Poly1305(k_cipher).decrypt(nonce12, ciphertext, aad)

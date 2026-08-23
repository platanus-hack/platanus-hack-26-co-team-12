"""Derivacion de llaves. Sustituye a ChaosMod como fuente de secreto (C3)."""
from __future__ import annotations

from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# El extractor ciego no puede leer nada del medio antes de derivar k_chaos,
# asi que el salt es constante por necesidad. Eso exige passphrases fuertes.
APP_SALT = b"stego-v1-app-salt-2026-0000000000"


@dataclass(frozen=True)
class KeyMaterial:
    k_cipher: bytes
    k_chaos: bytes


def derive(passphrase: str, tenant: bytes = b"") -> KeyMaterial:
    """passphrase -> Argon2id -> HKDF -> (k_cipher, k_chaos).

    `tenant` permite que varios clientes compartan el layout (y por tanto una
    sola busqueda de sincronia) mientras cada uno conserva su propia llave de
    cifrado: sin esto, verificar con N clientes cuesta N sincronias completas.
    """
    master = Argon2id(
        salt=APP_SALT, length=32, iterations=3, lanes=1, memory_cost=64 * 1024
    ).derive(passphrase.encode("utf-8"))

    def sub(info: bytes) -> bytes:
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(master)

    return KeyMaterial(k_cipher=sub(b"cipher|" + tenant), k_chaos=sub(b"chaos"))

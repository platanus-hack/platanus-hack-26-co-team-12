"""Trama de payload: cabecera + nonce + AEAD. Reemplaza ord()/chr() y el
sidecar de metadatos: la trama se describe a si misma (C8)."""
from __future__ import annotations

import os
import zlib
from dataclasses import dataclass

from . import cipher

VERSION = 1
FLAG_ZLIB = 0x01
HEADER_LEN = 4
NONCE_LEN = 8
TAG_LEN = 16
OVERHEAD = HEADER_LEN + NONCE_LEN + TAG_LEN  # 28 bytes


class BadFrame(Exception):
    """Trama ilegible: llave incorrecta o dano irrecuperable."""


@dataclass(frozen=True)
class Frame:
    data: bytes


def _nonce12(nonce8: bytes, header: bytes) -> bytes:
    return nonce8 + header


def pack(k_cipher: bytes, data: bytes, *, compress: bool = True) -> bytes:
    body = data
    flags = 0
    if compress:
        z = zlib.compress(data, 9)
        if len(z) < len(data):  # zlib real, sin perdida, en microsegundos (C9)
            body, flags = z, FLAG_ZLIB
    if len(body) > 0xFFFF:
        raise ValueError("payload demasiado grande")
    header = bytes([VERSION, flags]) + len(body).to_bytes(2, "big")
    nonce8 = os.urandom(NONCE_LEN)
    ct = cipher.seal(k_cipher, _nonce12(nonce8, header), body, header)
    return header + nonce8 + ct


def unpack(k_cipher: bytes, frame: bytes) -> bytes:
    if len(frame) < OVERHEAD:
        raise BadFrame("trama truncada")
    header, nonce8, ct = frame[:4], frame[4:12], frame[12:]
    if header[0] != VERSION:
        raise BadFrame(f"version {header[0]} no soportada")
    body_len = int.from_bytes(header[2:4], "big")
    if len(ct) != body_len + TAG_LEN:
        raise BadFrame("longitud inconsistente")
    try:
        body = cipher.open_(k_cipher, _nonce12(nonce8, header), ct, header)
    except cipher.InvalidTag as exc:
        raise BadFrame("llave incorrecta o imagen demasiado danada") from exc
    return zlib.decompress(body) if header[1] & FLAG_ZLIB else body


def frame_len(payload_len: int) -> int:
    return OVERHEAD + payload_len

"""Reed-Solomon con borrados. Un recorte es un canal de borrados *conocidos*,
que RS corrige al doble de eficiencia que los errores (s <= n-k vs 2e <= n-k)."""
from __future__ import annotations

import numpy as np
from reedsolo import ReedSolomonError, RSCodec


class DecodeFailed(Exception):
    pass


def encode(frame: bytes, codeword_len: int) -> bytes:
    nsym = codeword_len - len(frame)
    if nsym < 2:
        raise ValueError(f"capacidad insuficiente: {codeword_len} B para trama de {len(frame)} B")
    return bytes(RSCodec(nsym).encode(frame))


def decode(codeword: bytes, frame_len_: int, erasures: list[int] | None = None) -> bytes:
    nsym = len(codeword) - frame_len_
    try:
        out = RSCodec(nsym).decode(bytes(codeword), erase_pos=erasures or [])[0]
    except (ReedSolomonError, ZeroDivisionError) as exc:
        raise DecodeFailed(str(exc)) from exc
    return bytes(out)


def bits_to_bytes(bits: np.ndarray) -> bytes:
    return np.packbits(np.asarray(bits, dtype=np.uint8)).tobytes()


def bytes_to_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))

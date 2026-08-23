import numpy as np
import pytest

from stego import ecc, payload
from tests.conftest import IDENT


def test_roundtrip(km):
    f = payload.pack(km.k_cipher, IDENT)
    assert payload.unpack(km.k_cipher, f) == IDENT


def test_llave_incorrecta_rechaza(km, km_otro):
    f = payload.pack(km.k_cipher, IDENT)
    with pytest.raises(payload.BadFrame):
        payload.unpack(km_otro.k_cipher, f)


def test_nonce_distinto_por_llamada(km):
    assert payload.pack(km.k_cipher, IDENT) != payload.pack(km.k_cipher, IDENT)


def test_manipulacion_detectada(km):
    f = bytearray(payload.pack(km.k_cipher, IDENT))
    f[20] ^= 0x01
    with pytest.raises(payload.BadFrame):
        payload.unpack(km.k_cipher, bytes(f))


def test_utf8_fuera_de_latin1(km):
    txt = "€ — … 😀 acentuación".encode()
    f = payload.pack(km.k_cipher, txt)
    assert payload.unpack(km.k_cipher, f) == txt


@pytest.mark.parametrize("n_borrados", [0, 10, 25, 40])
def test_rs_con_borrados(km, n_borrados):
    f = payload.pack(km.k_cipher, IDENT)
    cw = bytearray(ecc.encode(f, 84))
    er = sorted(np.random.default_rng(n_borrados).choice(84, n_borrados, replace=False).tolist())
    for i in er:
        cw[i] = 0
    assert payload.unpack(km.k_cipher, ecc.decode(bytes(cw), len(f), er)) == IDENT


def test_rs_falla_por_encima_de_su_capacidad(km):
    f = payload.pack(km.k_cipher, IDENT)
    cw = bytearray(ecc.encode(f, 84))
    er = list(range(45))
    for i in er:
        cw[i] = 0
    with pytest.raises((ecc.DecodeFailed, payload.BadFrame)):
        payload.unpack(km.k_cipher, ecc.decode(bytes(cw), len(f), er))

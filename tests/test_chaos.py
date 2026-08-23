import numpy as np

from stego.chaos import LogisticFP64, chaos_permutation


def test_determinista_entre_instancias(km):
    a = LogisticFP64(km.k_chaos).bits(2048)
    b = LogisticFP64(km.k_chaos).bits(2048)
    assert np.array_equal(a, b)


def test_llaves_distintas_dan_secuencias_distintas(km, km_otro):
    a = LogisticFP64(km.k_chaos).bits(4096)
    b = LogisticFP64(km_otro.k_chaos).bits(4096)
    assert (a != b).mean() > 0.4


def test_monobit_sin_sesgo(km):
    """Con r = 4 exacto el sesgo desaparece; con el r = 3.999952 original el
    test monobit fallaba con z = +10.5."""
    bits = LogisticFP64(km.k_chaos).bits(200_000)
    z = abs(bits.mean() - 0.5) * 2 * np.sqrt(len(bits))
    assert z < 4.0, f"z monobit = {z:.2f}"


def test_permutacion_grande_termina_y_es_valida(km):
    """El muestreo con rechazo original no terminaba para n >= 20834."""
    n = 50_000
    p = chaos_permutation(n, LogisticFP64(km.k_chaos))
    assert np.array_equal(np.sort(p), np.arange(n))
    assert (p != np.arange(n)).mean() > 0.9

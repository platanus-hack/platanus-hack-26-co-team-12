import pytest

from stego.attacks import image as atk
from stego.covers import image_dct_qim as codec
from tests.conftest import IDENT, make_image

PERFIL_ROBUSTO = 42.0


@pytest.mark.parametrize("q", [90, 75, 50, 40])
@pytest.mark.parametrize("kind", ["natural", "texturizado"])
def test_recompresion_jpeg_perfil_estandar(km, q, kind):
    """Sobre declarado del perfil por defecto (delta=26): Q >= 40.

    La cota es delta >= 2*q_k(Q) + 4; a Q30 el paso de cuantizacion de los
    portadores sube a 18 y haria falta delta >= 40.
    """
    marked = codec.embed(make_image(kind), IDENT, km)
    out, d = codec.extract(atk.jpeg(marked, q), km)
    assert out == IDENT, f"Q{q} {kind}: {d}"


@pytest.mark.parametrize("q", [30])
def test_q_bajo_necesita_perfil_robusto(km, q):
    img = make_image("natural")
    estandar = codec.extract(atk.jpeg(codec.embed(img, IDENT, km), q), km)[0]
    robusto = codec.extract(
        atk.jpeg(codec.embed(img, IDENT, km, delta=PERFIL_ROBUSTO), q), km, delta=PERFIL_ROBUSTO)[0]
    assert robusto == IDENT, f"el perfil robusto deberia aguantar Q{q}"
    if estandar is not None:
        assert estandar == IDENT  # nunca un id inventado


def test_q20_esta_fuera_de_alcance_y_no_miente(km):
    """Q20 no lo aguanta ningun perfil probado. Lo que importa es que falle
    diciendo 'sin marca', nunca devolviendo un identificador inventado."""
    marked = codec.embed(make_image("natural"), IDENT, km, delta=PERFIL_ROBUSTO)
    out, d = codec.extract(atk.jpeg(marked, 20), km, delta=PERFIL_ROBUSTO)
    assert out in (None, IDENT)
    if out is None:
        assert d.reason


def test_submuestreo_de_croma_no_afecta(km, natural):
    """La marca vive solo en luminancia."""
    marked = codec.embed(natural, IDENT, km)
    assert codec.extract(atk.jpeg(marked, 75, subsampling=2), km)[0] == IDENT


def test_reescalado_a_la_mitad_requiere_perfil_robusto(km):
    """El QIM es fragil a la ganancia: reducir a x0.5 y volver a ampliar atenua
    los portadores (~0.75). La compensacion de ganancia lo corrige, pero el
    margen de ruido del ciclo solo alcanza con delta alto."""
    img = make_image("natural")
    m = codec.embed(img, IDENT, km, delta=PERFIL_ROBUSTO)
    atacada = atk.jpeg(atk.rescale(m, max(m.shape[:2]) // 2), 75)
    out, d = codec.extract(atacada, km, delta=PERFIL_ROBUSTO)
    assert out == IDENT, d
    assert d.gain != 1.0 or d.pilot_ber == 0.0

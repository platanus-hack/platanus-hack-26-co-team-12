"""Servidor de la demo: registra una imagen a nombre de un emisor, verifica una
imagen recibida sin pedir contrasena, y corre la bateria de ataques de canal.

Cada numero que la interfaz muestra lo calcula el codec en el momento. No hay
resultados escritos a mano: si aqui no se computa, en pantalla no aparece.

    .venv/bin/python -m uvicorn web.server:app --port 8000

Los endpoints son sincronos a proposito. FastAPI los corre en su threadpool, asi
que una verificacion lenta no bloquea el event loop; ese era uno de los defectos
de la API vieja (docs/auditoria.md, pendientes).
"""
from __future__ import annotations

import base64
import io
import json
import os
import secrets
import sys
import time
from dataclasses import asdict
from datetime import datetime

import numpy as np
from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from stego.attacks import image as atk  # noqa: E402
from stego.covers import image_dct_qim as codec  # noqa: E402
from stego.image import loading  # noqa: E402
from stego.image.layout import build  # noqa: E402
from stego.integrity import analyse  # noqa: E402
from scipy import ndimage  # noqa: E402
from stego.keys import KeyMaterial, derive  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
RUTA_REGISTRO = os.path.join(HERE, "registro.json")
BASE_LONG = 1024  # docs/operacion.md: normalizar antes de marcar es mas fiable

# Amplitud de la plantilla de sincronia: el parametro que hace que esta demo
# funcione sobre fotografias.
#
# El default del codec (2.0) esta calibrado sobre imagenes sinteticas, donde la
# plantilla periodica no compite con nada. Sobre una fotografia el espectro del
# contenido la tapa: la z de sincronia cae de ~5.7 a ~3.4 y los recortes chicos
# dejan de recuperar. Medido sobre 3 fotografias reales, 5 firmas cada una:
#
#   amp   PSNR      recorte 400   recorte 256   reescalado x0.75
#   2.0   42.3 dB      26 %           0 %            60 %
#   4.0   40.3 dB     100 %          67 %           100 %
#   6.0   38.1 dB     100 %         100 %           100 %
#
# 6.0 fue el perfil de la demo hasta que se reporto lo evidente: la plantilla se
# VE. A esa amplitud inyecta un RMS de 2.29 niveles con picos de +-6.9, en un
# patron periodico exacto de 64 px, y como se sumaba con amplitud constante a
# todos los pixeles, en cielos, paredes y piel salia un moteado. Reparto medido
# de la energia de error a delta=26: plantilla 66 %, QIM 34 %.
#
# La respuesta fue bajar a 4.0 Y modular la plantilla por enmascaramiento
# perceptual (stego.image.masking): baja en zonas planas, sube donde hay textura
# que la esconde. Eso ataca justamente donde se veia, sin tocar la periodicidad,
# que es lo unico que el sincronizador necesita conservar.
#
# Pero se cambiaron las dos cosas a la vez y no se volvio a medir. Separadas
# sobre las mismas 3 fotografias, 3 firmas, la culpa no estaba repartida:
#
#   perfil                  PSNR      recorte 400   recorte 256
#   6.0 sin mascara        38.21 dB      100 %         100 %
#   4.0 sin mascara        40.46 dB      100 %          66 %
#   6.0 CON mascara        38.21 dB      100 %         100 %   <- la mascara es gratis
#   4.0 con mascara        40.43 dB       66 %          66 %   <- tumba tambien el de 400
#
# La mascara no cuesta robustez: a igual amplitud da la misma tasa y el mismo
# PSNR. Lo que se llevo los recortes fue bajar la amplitud, y la mascara solo
# amplifica ese coste cuando ya no queda margen.
#
# Pero subir la amplitud le devuelve nube, y el PSNR no lo ve. Medido con el
# error de escala gruesa en zona plana —pasa-bajos, que es lo que el ojo integra—
# y tomando como 100 % el perfil que produjo el moteado:
#
#   6.0 sin mascara ........ 100 %   <- el problema reportado
#   4.0 con mascara ........  49 %   <- el arreglo original
#   5.0 con mascara ........  58 %   <- devolvia ~1/5 del arreglo
#
# Por eso el perfil no es solo la amplitud: va con `masking.DEFAULTS["floor"]`
# bajado de 0.35 a 0.12, que saca plantilla de las zonas planas sin tocar la
# textura, de donde sale la sincronia. Con las dos cosas: nube al 45 % —mejor que
# el arreglo original— y los 8/8 de vuelta.
#
# Verificado con 3 fotografias x 10 firmas = 30 intentos por ataque: seis ataques
# al 100 %, los dos recortes chicos (400x300 y 256x256) al 97 %. PSNR 39.27 dB,
# 0 falsos positivos con passphrase incorrecta.
#
# Ese 97 % NO es un coste del floor: a floor 0.35 los mismos recortes tampoco dan
# 100 % reproducible. Estan en el margen y lo decide el nonce de payload.pack --
# 30/30 en una tanda, 29/30 en la siguiente, mismo perfil. Barrido dedicado de 30
# firmas: floor .35 30/30, .25 30/30, .18 30/30, .12 30/30, con la z de sincronia
# cayendo apenas de 3.71 a 3.64.
#
# Por eso el rail muestra 97 % y no se redondea: una tasa medida que en tarima
# falla una vez de treinta tiene que estar declarada de antemano.
#
# Reproducir con:
#   .venv/bin/python web/tasas.py <fotos> --firmas 5 --template-amp <valor>
TEMPLATE_AMP = 5.0

# Mediana del BER por celda a partir de la cual la malla del cotejo por region se
# considera desalineada y su mapa deja de significar nada. Con la malla correcta
# la mediana es 0.000; con un pixel de corrimiento se va a 0.33.
MEDIANA_LIMPIA = 0.05

# Celdas contiguas a partir de las cuales el cotejo por region declara alteracion.
# Una edicion es local y compacta; el ruido de fondo y lo que deja el canal es
# disperso. Medido sobre una lamina de 736 celdas (grupo contiguo mas grande):
#
#   lamina intacta ......  1      recuadro de  96 px .. 15
#   JPEG Q75 ............  5      recuadro de 128 px .. 21
#   canal WhatsApp ......  5      recuadro de 160 px .. 33
#   +12 de brillo global . 17     recuadro de 200 px .. 49
#
# 24 deja el canal a 4.8x de margen y no marca el cambio global de brillo, que el
# metodo declara como no distinguible. **Piso declarado**: una edicion menor a
# ~160 px de lado puede pasar sin detectarse.
GRUPO_MINIMO = 24

# ── La llave del registro ────────────────────────────────────────────────
# Vive en el servidor y no sale nunca. Es lo que permite que verificar NO pida
# contrasena: ChaCha20-Poly1305 es simetrico, asi que entregarle la passphrase
# al ciudadano para que verifique seria entregarle tambien la capacidad de
# falsificar marcas de esa entidad. La verificacion es un servicio, no una
# operacion local.
#
PASSPHRASE_REGISTRO = os.environ.get(
    "STEGO_REGISTRO", "passphrase-del-registro-2026-larga-y-solo-para-demo"
)

# UNA llave para todo el registro, y el nombre de quien marca es un campo del
# asiento, igual que el titulo.
#
# Antes habia tres emisores fijos, cada uno un tenant con su propia k_cipher.
# Eso demostraba la separacion multi-tenant del codec, pero ataba la identidad a
# la criptografia: para saber QUIEN marco, `_identificar` probaba la llave de
# cada emisor por turno. Con nombres libres eso no escala — cada nombre nuevo
# seria una llave mas que probar, y el caso "sin marca" ya cuesta segundos.
#
# Asi que la identidad se resuelve donde corresponde: los 16 bytes son el codigo,
# el codigo resuelve una fila del registro, y la fila dice el nombre. Es ademas
# como funciona un sistema real —cuentas, no llaves por cliente— y de paso el
# caso "sin marca" baja a una sola busqueda en vez de tres.
#
# La separacion multi-tenant sigue existiendo en el codec (`keys.derive` acepta
# `tenant`); lo que ya no hace es esta demo.
LLAVE_REGISTRO: KeyMaterial = derive(PASSPHRASE_REGISTRO)

#: Tope del nombre. No es seguridad —no hay autenticacion de ninguna clase— sino
#: higiene: que no entre un texto de kilobytes al registro ni a la pantalla.
NOMBRE_MAX = 60

app = FastAPI(title="Registro de Procedencia")

# Las laminas firmadas viven en memoria solo para alimentar la pestana Pruebas.
# ponytail: un operador, una demo; se pierde al reiniciar y esta bien.
SESIONES: dict[str, dict] = {}


# ── registro: disco en local, S3 cuando corre en Lambda ──────────────────
#
# En Lambda el sistema de ficheros es de solo lectura salvo /tmp, y /tmp se
# borra entre invocaciones: escribir registro.json ahi hacia fallar /api/firmar
# con Internal Server Error. Si ESTADO_BUCKET esta definida, el registro vive en
# S3; si no, se comporta exactamente como antes.

ESTADO_BUCKET = os.environ.get("ESTADO_BUCKET", "")
CLAVE_REGISTRO = "registro.json"


def _s3():
    import boto3  # import perezoso: en local no hace falta

    return boto3.client("s3")


def _leer_registro() -> dict:
    if ESTADO_BUCKET:
        try:
            obj = _s3().get_object(Bucket=ESTADO_BUCKET, Key=CLAVE_REGISTRO)
            return json.loads(obj["Body"].read())
        except Exception:
            # Aun no existe (primer arranque) o S3 no responde: registro vacio,
            # que es el mismo comportamiento que tenia el fichero ausente.
            return {}
    try:
        with open(RUTA_REGISTRO, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _guardar_sesion(token: str, ses: dict) -> None:
    """La sesion guarda la imagen marcada para poder atacarla despues. En
    memoria se perdia entre invocaciones de Lambda: el cotejo fallaba con
    "esa firma ya no esta en memoria" si el contenedor se reciclaba."""
    if not ESTADO_BUCKET:
        SESIONES[token] = ses
        for viejo in list(SESIONES)[:-12]:
            SESIONES.pop(viejo, None)
        return

    buf = io.BytesIO()
    np.save(buf, ses["marcada"], allow_pickle=False)
    cli = _s3()
    cli.put_object(
        Bucket=ESTADO_BUCKET,
        Key=f"sesiones/{token}.npy",
        Body=buf.getvalue(),
    )
    meta = {k: v for k, v in ses.items() if k != "marcada"}
    meta["ident"] = ses["ident"].hex()
    cli.put_object(
        Bucket=ESTADO_BUCKET,
        Key=f"sesiones/{token}.json",
        Body=json.dumps(meta).encode("utf-8"),
        ContentType="application/json",
    )


def _cargar_sesion(token: str) -> dict | None:
    if not ESTADO_BUCKET:
        return SESIONES.get(token)
    try:
        cli = _s3()
        meta = json.loads(
            cli.get_object(Bucket=ESTADO_BUCKET, Key=f"sesiones/{token}.json")["Body"].read()
        )
        crudo = cli.get_object(Bucket=ESTADO_BUCKET, Key=f"sesiones/{token}.npy")["Body"].read()
    except Exception:
        return None
    meta["ident"] = bytes.fromhex(meta["ident"])
    meta["marcada"] = np.load(io.BytesIO(crudo), allow_pickle=False)
    return meta


def _asentar(ident_hex: str, entrada: dict) -> None:
    reg = _leer_registro()
    reg[ident_hex] = entrada
    cuerpo = json.dumps(reg, ensure_ascii=False, indent=2)
    if ESTADO_BUCKET:
        _s3().put_object(
            Bucket=ESTADO_BUCKET,
            Key=CLAVE_REGISTRO,
            Body=cuerpo.encode("utf-8"),
            ContentType="application/json",
        )
        return
    with open(RUTA_REGISTRO, "w", encoding="utf-8") as fh:
        fh.write(cuerpo)


# ── utilidades ───────────────────────────────────────────────────────────

def _psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = ((a.astype(np.float64) - b.astype(np.float64)) ** 2).mean()
    return float("inf") if mse == 0 else 10 * np.log10(255.0**2 / mse)


def _png(rgb: np.ndarray) -> str:
    """PNG sin perdida y con el perfil sRGB declarado.

    Lo segundo importa tanto como lo primero: sin perfil, un navegador con
    gestion de color supone un espacio y vuelve a desplazar los colores, que es
    justo lo que loading.open_rgb acaba de normalizar.
    """
    return ("data:image/png;base64,"
            + base64.b64encode(loading.encode_png(rgb)).decode())


def _redimensionar(rgb: np.ndarray, s: float) -> np.ndarray:
    h, w = rgb.shape[:2]
    return np.asarray(Image.fromarray(rgb).resize(
        (max(1, int(round(w * s))), max(1, int(round(h * s)))), Image.Resampling.LANCZOS))


def _normalizar(rgb: np.ndarray, long_side: int = BASE_LONG) -> np.ndarray:
    m = max(rgb.shape[:2])
    return rgb if m <= long_side else _redimensionar(rgb, long_side / m)


def _recorte(m: np.ndarray, w: int, h: int, x: int, y: int) -> np.ndarray:
    """Recorte con desplazamiento arbitrario, encajado dentro de la imagen real."""
    ih, iw = m.shape[:2]
    w, h = min(w, iw), min(h, ih)
    x, y = min(x, iw - w), min(y, ih - h)
    return atk.crop(m, x, y, w, h)


# ── bateria de ataques ───────────────────────────────────────────────────

ATAQUES: list[dict] = [
    {
        "clave": "limpia", "titulo": "Sin ataque", "cadena": "—",
        "nota": "La línea base. Sale de la firma y entra al cotejo sin tocarse.",
        "fn": lambda m: m,
    },
    {
        "clave": "jpeg75", "titulo": "Recompresión JPEG Q75", "cadena": "JPEG calidad 75",
        "nota": "La calidad a la que recomprime cualquier red social al republicar.",
        "fn": lambda m: atk.jpeg(m, 75),
    },
    {
        "clave": "crop800", "titulo": "Recorte 800 × 600",
        "cadena": "recorte @(13,37) → JPEG Q75",
        "nota": "Desplazamiento arbitrario: el receptor no sabe dónde empezaba la imagen.",
        "fn": lambda m: atk.jpeg(_recorte(m, 800, 600, 13, 37), 75),
    },
    {
        "clave": "crop400", "titulo": "Recorte 400 × 300",
        "cadena": "recorte @(71,53) → JPEG Q75",
        "nota": "Queda menos de un quinto del área original.",
        "fn": lambda m: atk.jpeg(_recorte(m, 400, 300, 71, 53), 75),
    },
    {
        "clave": "crop256", "titulo": "Recorte 256 × 256",
        "cadena": "recorte @(91,17) → JPEG Q75",
        "nota": "El piso declarado: 256 px marcando a 1024. Justo dos teselas de lado.",
        "fn": lambda m: atk.jpeg(_recorte(m, 256, 256, 91, 17), 75),
    },
    {
        "clave": "escala075", "titulo": "Reescalado × 0.75",
        "cadena": "Lanczos ×0.75 → JPEG Q75",
        "nota": "El paso de la tesela cambia: la sincronía tiene que recuperar la escala.",
        "fn": lambda m: atk.jpeg(atk.rescale(m, int(max(m.shape[:2]) * 0.75)), 75),
    },
    {
        "clave": "whatsapp", "titulo": "Canal WhatsApp",
        "cadena": "reescalado a 1600 px → JPEG Q75 4:2:0 → metadatos borrados",
        "nota": "Aquí muere una Content Credential. El identificador no vive en los metadatos.",
        "fn": lambda m: atk.whatsapp(m),
    },
    {
        "clave": "crop_whatsapp", "titulo": "Recorte grande + canal",
        "cadena": "recorte → 1600 px → JPEG Q75 4:2:0",
        "nota": "Los dos ataques encadenados, que es como llega una imagen en la vida real.",
        "fn": lambda m: atk.whatsapp(
            _recorte(m, int(m.shape[1] * 0.86), int(m.shape[0] * 0.86), 13, 37)
        ),
    },
]
POR_CLAVE = {a["clave"]: a for a in ATAQUES}


# ── verificacion ─────────────────────────────────────────────────────────

def _extraer(rgb: np.ndarray, km: KeyMaterial, delta: float, amp: float, buscar: bool):
    return codec.extract(rgb, km, delta=delta, template_amp=amp, search_scale=buscar)


def _verificar(rgb: np.ndarray, km: KeyMaterial, delta: float, template_amp: float = TEMPLATE_AMP):
    """Un solo emisor conocido: escala nativa primero, busqueda solo si el AEAD
    no valida. El criterio de reintento es que la trama no autentique, nunca una
    comparacion contra el identificador esperado: un verificador no lo conoce."""
    salida, diag = _extraer(rgb, km, delta, template_amp, False)
    if salida is not None:
        return salida, diag, "escala nativa"
    salida, diag = _extraer(rgb, km, delta, template_amp, True)
    return salida, diag, "búsqueda de escala"


def _cotejo(diag, delta: float = codec.DEFAULT_DELTA,
            amp: float = TEMPLATE_AMP) -> dict | None:
    """Cotejo por region: que celdas no llevan los bits que deberian.

    La misma marca sirve para procedencia e integridad segun como se lea. En
    global sobrevive a lo que degrada la imagen entera de forma leve y uniforme
    -- un canal --; por celda delata lo que destruye una zona localizada -- una
    edicion --. Ver docs/arquitectura.md, seccion 9.
    """
    if diag.frame is None or diag.view is None or diag.sync is None:
        return None
    lay = build(LLAVE_REGISTRO.k_chaos, delta, amp)

    # La vista que deja el extractor puede quedar hasta un pixel corrida respecto
    # de la alineacion con la que decodifico de verdad: la sincronia por plantilla
    # tiene periodo 64 px y el refinamiento subpixel trabaja sobre una copia
    # desplazada que no vuelve al diagnostico. Medido sobre una lamina intacta:
    # sin corregir, la mediana del BER por celda es 0.33 y el umbral MAD se va por
    # encima de 1.0, con lo cual el mapa NO PUEDE marcar nada nunca -- una edicion
    # visible sale como "0 celdas alteradas". Corrida -1 px, la mediana cae a 0.000
    # y la misma edicion aparece con 62 de 736 celdas.
    #
    # Se elige la alineacion de mediana mas baja, no la de mas celdas marcadas: la
    # mediana es una propiedad global de la malla, asi que minimizarla encuentra el
    # encuadre y deja intacto lo local, que es justo lo que hay que detectar.
    rep = analyse(diag.view, lay, diag.sync, diag.gain, diag.frame)
    if rep.ok and rep.median_ber > MEDIANA_LIMPIA:
        for dy in (-1.0, 1.0, -0.5, 0.5):
            for dx in (0.0, -0.5, 0.5):
                v = ndimage.shift(diag.view, (dy, dx), order=3, mode="nearest")
                cand = analyse(v, lay, diag.sync, diag.gain, diag.frame)
                if cand.ok and cand.median_ber < rep.median_ber:
                    rep = cand
                    if rep.median_ber <= MEDIANA_LIMPIA:
                        break
            if rep.median_ber <= MEDIANA_LIMPIA:
                break

    if not rep.ok:
        return None
    if rep.median_ber > MEDIANA_LIMPIA:
        # Sin una malla limpia el mapa no significa nada; mejor no mostrarlo que
        # afirmar que no hubo edicion.
        return None

    # Alteracion = un grupo contiguo grande, no celdas sueltas. Con "cualquier
    # celda marcada" una lamina intacta salia como editada: siempre quedan 1 a 6
    # celdas de ruido.
    etiquetas, n = ndimage.label(rep.tampered)
    grupo = int(np.bincount(etiquetas.ravel())[1:].max()) if n else 0
    umbral = max(GRUPO_MINIMO, round(0.03 * rep.tampered.size))
    return {
        "celda_px": rep.cell_px,
        "filas": int(rep.tampered.shape[0]),
        "columnas": int(rep.tampered.shape[1]),
        "celdas": int(rep.tampered.size),
        "marcadas": int(rep.tampered.sum()),
        "grupo_mayor": grupo,
        "umbral_celdas": umbral,
        "alterada": grupo >= umbral,
        # una cadena de 0/1 por fila: el mapa entero pesa menos que un JSON anidado
        "mapa": ["".join("1" if v else "0" for v in fila) for fila in rep.tampered],
    }


def _diag_publico(diag) -> dict:
    d = asdict(diag)
    return {
        "z": round(d["z"], 2), "escala": round(d["scale"], 4),
        "pilot_ber": round(d["pilot_ber"], 3), "borrados": d["erasures"],
        "teselas": round(d["tiles_seen"]),
    }


# ── endpoints ────────────────────────────────────────────────────────────

def _medicion() -> dict:
    """Tasas medidas por `web/tasas.py`. Si el archivo no esta, la interfaz no
    inventa ningun porcentaje: simplemente no muestra ninguno.

    Y si las tasas se midieron con un perfil distinto del que este servidor usa
    para firmar, tampoco se muestran. Ya paso una vez: los porcentajes en
    pantalla venian de `template_amp = 6.0` sin enmascaramiento mientras el
    codigo firmaba de otra manera. Un numero medido con otra configuracion no es
    un numero conservador, es un numero falso."""
    try:
        with open(os.path.join(HERE, "tasas.json"), encoding="utf-8") as fh:
            med = json.load(fh)
    except (OSError, ValueError):
        return {}

    desfase = [
        f"template_amp medido {med.get('template_amp')!r} != {TEMPLATE_AMP!r} en uso"
        if med.get("template_amp") != TEMPLATE_AMP else "",
        f"delta medido {med.get('delta')!r} != {codec.DEFAULT_DELTA!r} en uso"
        if med.get("delta") != codec.DEFAULT_DELTA else "",
        "medido sin enmascaramiento perceptual"
        if not med.get("template_mask") else "",
    ]
    desfase = [d for d in desfase if d]
    if desfase:
        return {"desactualizada": desfase}
    return med


@app.get("/api/ataques")
def ataques() -> dict:
    med = _medicion()
    tasas = med.get("tasas", {})
    return {
        "desactualizada": med.get("desactualizada"),
        "medicion": {k: med[k] for k in
                     ("imagenes", "firmas_por_imagen", "intentos_por_ataque",
                      "delta", "template_amp", "template_mask", "psnr_medio") if k in med},
        "ataques": [
            {**{k: a[k] for k in ("clave", "titulo", "cadena", "nota")},
             "tasa": tasas.get(a["clave"])}
            for a in ATAQUES
        ],
    }


@app.post("/api/firmar")
def firmar(
    imagen: UploadFile,
    emisor: str = Form(...),
    titulo: str = Form(""),
    enlace: str = Form(""),
    delta: float = Form(codec.DEFAULT_DELTA),
    template_amp: float = Form(TEMPLATE_AMP),
    template_mask: bool = Form(True),
) -> dict:
    # Nombre libre: lo escribe quien marca y queda en el asiento. No se valida
    # contra ninguna lista porque no hay ninguna — y tampoco se autentica, que
    # es la limitacion real de esta demo y esta declarada en el README.
    nombre = " ".join(emisor.split())[:NOMBRE_MAX]
    if not nombre:
        raise HTTPException(400, "Falta el nombre de quien marca la imagen.")
    try:
        # loading.open_rgb y no convert("RGB"): aplica la orientacion EXIF,
        # convierte a sRGB con el perfil incrustado y compone el canal alfa sobre
        # blanco. Sin esto una foto de celular (Display P3 + EXIF) salia
        # sobresaturada y, si era vertical, acostada -- un cambio que el usuario
        # atribuia a la marca y que la marca no habia hecho.
        subida = loading.open_rgb(imagen.file)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"No pude leer la imagen: {exc}") from exc

    alto_subido, ancho_subido = subida.shape[:2]
    original = _normalizar(subida)
    if min(original.shape[:2]) < 256:
        raise HTTPException(400, "La imagen es menor de 256 px: no cabe una tesela.")

    ident = secrets.token_bytes(16)
    t0 = time.perf_counter()
    marcada = codec.embed(original, ident, LLAVE_REGISTRO,
                          delta=delta, template_amp=template_amp,
                          template_mask=template_mask)
    ms = round((time.perf_counter() - t0) * 1000)

    h, w = marcada.shape[:2]
    entrada = {
        "nombre": nombre,
        "titulo": titulo.strip() or "Sin título",
        "enlace": enlace.strip(),
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ancho": w,
        "alto": h,
        # Este PSNR mide SOLO lo que anade la marca. Antes se comparaba contra el
        # original ya reescalado sin decirlo, asi que el numero ocultaba el
        # reescalado a 1024 px: el usuario leia "38 dB" creyendo que era la
        # diferencia respecto de lo que subio. Ahora el reescalado se declara
        # aparte en vez de esconderse dentro de una metrica.
        "psnr": round(_psnr(original, marcada), 2),
        "redimensionada": (ancho_subido, alto_subido) != (w, h),
        "subida": f"{ancho_subido}×{alto_subido}",
    }
    _asentar(ident.hex(), entrada)

    token = secrets.token_hex(8)
    _guardar_sesion(token, {"marcada": marcada, "ident": ident, "nombre": nombre,
                            "delta": delta, "template_amp": template_amp,
                            "template_mask": template_mask})

    return {"token": token, "identificador": ident.hex(), "ms": ms,
            "delta": delta, "template_amp": template_amp,
            "template_mask": template_mask,
            "entrada": entrada, "lamina": _png(marcada),
            # El original YA normalizado, para que el A/B de la interfaz aisle
            # la marca en vez de mezclarla con el reescalado y el perfil de color.
            "antes": _png(original)}


@app.post("/api/verificar")
def verificar(imagen: UploadFile) -> dict:
    """Verifica una imagen cualquiera. **Sin contrasena**: la llave del registro
    no sale del servidor. No sabe que identificador esperar ni de quien."""
    try:
        rgb = loading.open_rgb(imagen.file)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"No pude leer la imagen: {exc}") from exc
    # El registro marca a 1024 px de lado largo, asi que el verificador trabaja a
    # esa resolucion. Medido: en una imagen sin marca de 1280 px, decir que no hay
    # nada baja de 17.3 s a 9.4 s, y ningun caso positivo cambia.
    rgb = _normalizar(rgb)
    if min(rgb.shape[:2]) < 128:
        raise HTTPException(400, "La imagen es menor de 128 px: no cabe una tesela.")

    t0 = time.perf_counter()
    ident, diag, via = _verificar(rgb, LLAVE_REGISTRO, codec.DEFAULT_DELTA)
    ms = round((time.perf_counter() - t0) * 1000)
    h, w = rgb.shape[:2]
    base = {"via": via, "ms": ms, "dimensiones": f"{w}×{h}",
            "diagnostico": _diag_publico(diag)}

    if ident is None:
        # Nunca acusamos: la ausencia de marca no prueba que el archivo sea ajeno.
        return {**base, "estado": "sin_marca", "veredicto": "sin marca legible",
                "motivo": diag.reason or "el tag AEAD no validó",
                "identificador": None, "entrada": None, "cotejo": None}

    entrada = _leer_registro().get(ident.hex())
    if entrada is None:
        # El codigo es autentico —el tag AEAD lo garantiza— pero no hay fila.
        # Pasa si el registro se borro, o si se marco en otra instancia.
        return {**base, "estado": "sin_asiento",
                "veredicto": "código válido, sin registro",
                "motivo": "el código es auténtico, pero no figura en este registro",
                "identificador": ident.hex(), "entrada": None,
                "cotejo": _cotejo(diag)}

    return {**base, "estado": "verificado", "veredicto": "procedencia verificada",
            "motivo": "", "identificador": ident.hex(), "entrada": entrada,
            "cotejo": _cotejo(diag)}


@app.post("/api/cotejar")
def cotejar(token: str = Form(...), clave: str = Form(...)) -> dict:
    ses = _cargar_sesion(token)
    if ses is None:
        raise HTTPException(404, "Esa firma ya no está en memoria. Volvé a firmar.")
    ataque = POR_CLAVE.get(clave)
    if ataque is None:
        raise HTTPException(404, f"Ataque desconocido: {clave}")

    atacada = ataque["fn"](ses["marcada"])
    t0 = time.perf_counter()
    salida, diag, via = _verificar(atacada, LLAVE_REGISTRO,
                                   ses["delta"], ses["template_amp"])
    ms = round((time.perf_counter() - t0) * 1000)

    h, w = atacada.shape[:2]
    mh, mw = ses["marcada"].shape[:2]
    exacto = salida is not None and salida == ses["ident"]
    return {
        "clave": clave, "exacto": exacto,
        "veredicto": "identificador recuperado" if exacto else "sin marca legible",
        "motivo": "" if exacto else (diag.reason or "el tag AEAD no validó"),
        "recuperado": salida.hex() if salida is not None else None,
        "esperado": ses["ident"].hex(), "via": via, "ms": ms,
        "entrada": f"{mw}×{mh}", "salida": f"{w}×{h}",
        "pixeles_restantes": round(100 * (w * h) / (mw * mh)),
        "diagnostico": _diag_publico(diag),
        "lamina": _png(atacada),
    }


# ── errores de validacion ────────────────────────────────────────────────
#
# FastAPI devuelve las validaciones automaticas como {"detail": [ {...} ]}, una
# lista de objetos, mientras que un HTTPException devuelve {"detail": "texto"}.
# El front hacia new Error(d.detail) para los dos y en el primer caso pintaba
# "[object Object]". Aqui se traduce la lista a una frase, de modo que el front
# recibe siempre una cadena.

CAMPOS = {
    "imagen": "la imagen",
    "emisor": "el nombre de quien marca",
    "titulo": "el titulo",
    "enlace": "el enlace",
    "delta": "el delta",
    "template_amp": "la amplitud de plantilla",
    "token": "la firma de referencia",
    "clave": "el ataque",
}


def _frase(err: dict) -> str:
    campo = err["loc"][-1]
    nombre = CAMPOS.get(campo, f"el campo {campo}")
    tipo = err.get("type", "")
    if tipo == "missing":
        return f"falta {nombre}"
    if tipo.startswith(("float", "int", "decimal")):
        return f"{nombre} tiene que ser un numero"
    if tipo.startswith("bool"):
        return f"{nombre} tiene que ser si o no"
    return f"{nombre} no es valido"


@app.exception_handler(RequestValidationError)
async def validacion(_request, exc: RequestValidationError) -> JSONResponse:
    fallos = [_frase(e) for e in exc.errors()]
    # Sin duplicados y en orden: un mismo campo puede generar varios errores.
    vistos: list[str] = []
    for f in fallos:
        if f not in vistos:
            vistos.append(f)
    detalle = "Revisa el formulario: " + ", ".join(vistos) + "."
    return JSONResponse(status_code=422, content={"detail": detalle})


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC, "index.html"))


# ── entrada en AWS Lambda ─────────────────────────────────────────────────
# El runtime invoca web.server.handler. mangum traduce el evento de Lambda a
# ASGI, asi que la app es la misma en local y desplegada. El import va
# protegido porque mangum solo se instala en la imagen del despliegue: en
# local (docker compose, uvicorn) no esta y la app tiene que arrancar igual.
try:
    from mangum import Mangum
except ImportError:  # pragma: no cover - solo ocurre fuera de Lambda
    handler = None
else:
    handler = Mangum(app)

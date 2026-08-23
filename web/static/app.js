/* Registro de Procedencia — tres actos: firmar, verificar, y el banco de ataques.
   Ningún número de la pantalla se calcula acá: todos vienen del códec. */

const $ = (id) => document.getElementById(id);

const V = {
  veredicto: $('veredicto'),
  texto: $('veredicto-texto'),
  cola: $('veredicto-cola'),
};

function veredicto(estado, texto, cola = '') {
  V.veredicto.dataset.estado = estado;
  V.texto.textContent = texto;
  V.cola.textContent = cola;
}

const grupos = (hex) => hex.replace(/(.{4})/g, '$1 ').trim();

/* La cartulina toma la proporción real de la lámina: cada recorte cambia la
   forma del papel, así el daño se ve en el objeto y no solo en la foto. */
function ajustar(caja, img) {
  const w = img.naturalWidth, h = img.naturalHeight;
  if (w && h) caja.style.setProperty('--ar', `${w} / ${h}`);
}

function estampar(sello) {
  sello.removeAttribute('data-estampando');
  void sello.offsetWidth;
  sello.setAttribute('data-estampando', '');
}

/* ─── pestañas ──────────────────────────────────────────────────── */

// El servidor manda {detail: "texto"} para los errores propios y, si algo se
// escapa de la validacion de FastAPI, podria mandar una lista de objetos. Sin
// esto, new Error(d.detail) pintaba "[object Object]" en la cara del usuario.
function motivo(d, porDefecto) {
  const x = d && d.detail;
  if (typeof x === 'string' && x.trim()) return x;
  if (Array.isArray(x) && x.length) {
    const partes = x.map((e) => (e && (e.msg || e.message)) || '').filter(Boolean);
    if (partes.length) return partes.join(', ');
  }
  return porDefecto;
}

const VISTAS = ['firmar', 'verificar', 'pruebas'];
const REPOSO = {
  firmar: 'Listo para registrar',
  verificar: 'Listo para verificar',
};

function mostrar(vista) {
  for (const v of VISTAS) $(`v-${v}`).hidden = v !== vista;
  for (const b of $('pestanas').children) {
    b.setAttribute('aria-selected', String(b.dataset.vista === vista));
  }
  if (vista === 'pruebas') banco.abrir();
  else veredicto('reposo', REPOSO[vista]);
}

$('pestanas').addEventListener('click', (ev) => {
  const b = ev.target.closest('button');
  if (b) mostrar(b.dataset.vista);
});

/* ─── zona de soltar ────────────────────────────────────────────── */

function zona(sufijo, alSoltar) {
  const caja = $(`s-${sufijo}`);
  const input = $(`a-${sufijo}`);
  const img = $(`l-${sufijo}`);
  const texto = $(`t-${sufijo}`);

  const poner = (file) => {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      veredicto('no', 'Eso no es una imagen', file.type || 'tipo desconocido');
      return;
    }
    const url = URL.createObjectURL(file);
    img.onload = () => { ajustar(caja, img); URL.revokeObjectURL(url); };
    img.src = url;
    img.alt = file.name;
    img.hidden = false;
    texto.hidden = true;
    alSoltar?.(file);
  };

  input.addEventListener('change', () => poner(input.files[0]));

  for (const ev of ['dragenter', 'dragover']) {
    caja.addEventListener(ev, (e) => { e.preventDefault(); caja.setAttribute('data-encima', ''); });
  }
  for (const ev of ['dragleave', 'drop']) {
    caja.addEventListener(ev, () => caja.removeAttribute('data-encima'));
  }
  caja.addEventListener('drop', (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) { input.files = e.dataTransfer.files; poner(file); }
  });

  return {
    archivo: () => input.files[0],
    mostrarLamina(src, alt) {
      img.onload = () => ajustar(caja, img);
      img.src = src; img.alt = alt; img.hidden = false; texto.hidden = true;
    },
    /* A/B honesto: mantener pulsado muestra el original ya normalizado, soltar
       vuelve a la marcada. Las dos pasan por el mismo camino de codificación,
       así que lo único que cambia entre ellas es la marca. */
    comparar(antes, despues) {
      img.onload = () => ajustar(caja, img);
      img.src = despues; img.alt = 'Imagen marcada';
      img.hidden = false; texto.hidden = true;
      if (!antes) return;
      const ver = (src) => { img.src = src; };
      const on = () => ver(antes), off = () => ver(despues);
      caja.title = 'Mantené pulsado para ver el original sin marcar';
      caja.onpointerdown = on;
      for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) caja[`on${ev}`] = off;
    },
  };
}

function ocupar(boton, v, etiqueta, cola = 'el códec está trabajando') {
  boton.disabled = v;
  boton.textContent = v ? `${etiqueta}…` : boton.dataset.reposo;
  if (v) veredicto('corriendo', `${etiqueta}…`, cola);
}

/* ─── firmar ────────────────────────────────────────────────────── */

const zFirmar = zona('firmar');
const bFirmar = $('b-firmar');
bFirmar.dataset.reposo = bFirmar.textContent;

$('f-firmar').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const f = zFirmar.archivo();
  if (!f) { veredicto('no', 'Falta la imagen', 'soltala en la cartulina'); return; }

  const cuerpo = new FormData();
  cuerpo.append('imagen', f);
  cuerpo.append('emisor', $('emisor').value);
  cuerpo.append('titulo', $('titulo').value);
  cuerpo.append('enlace', $('enlace').value);
  cuerpo.append('delta', $('delta-firmar').value);
  cuerpo.append('template_amp', $('amp-firmar').value);
  cuerpo.append('template_mask', $('mask-firmar').checked ? '1' : '0');

  ocupar(bFirmar, true, 'Marcando');
  try {
    const r = await fetch('/api/firmar', { method: 'POST', body: cuerpo });
    const d = await r.json();
    if (!r.ok) throw new Error(motivo(d, 'no pude firmar'));

    // Comparación justa. Antes el "antes" era el archivo crudo que pinta el
    // navegador (con su perfil de color, su rotación EXIF y su resolución
    // completa) y el "después" era el PNG del servidor a 1024 px. El usuario
    // comparaba todo eso a la vez y se lo atribuía a la marca. Ahora el "antes"
    // es el mismo original ya normalizado, así que la única diferencia visible
    // entre las dos imágenes es la marca.
    zFirmar.comparar(d.antes, d.lamina);
    $('id-firmar').textContent = grupos(d.identificador);
    $('sello-firmar').hidden = false;
    estampar($('sello-firmar'));

    const a = $('bajar');
    a.href = d.lamina;
    a.download = `marcada-${d.identificador.slice(0, 8)}.png`;
    a.hidden = false;

    banco.cargar(d);
    const e = d.entrada;
    veredicto('ok', `Registrada por ${e.nombre}`,
      `${e.ancho}×${e.alto} · PSNR ${e.psnr} dB · marcada en ${d.ms} ms`);
  } catch (err) {
    veredicto('no', 'No se pudo firmar', String(err.message || err));
  } finally {
    ocupar(bFirmar, false);
  }
});

/* ─── verificar ─────────────────────────────────────────────────── */

const zVerificar = zona('verificar', () => {
  $('sello-verificar').hidden = true;
  $('constancia').hidden = true;
  veredicto('reposo', REPOSO.verificar);
});
const bVerificar = $('b-verificar');
bVerificar.dataset.reposo = bVerificar.textContent;

$('f-verificar').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const f = zVerificar.archivo();
  if (!f) { veredicto('no', 'Falta la imagen', 'soltala en la cartulina'); return; }

  // Sin contraseña: la llave del registro no sale del servidor.
  const cuerpo = new FormData();
  cuerpo.append('imagen', f);

  // Decir que no cuesta más que decir que sí: hay que agotar la búsqueda de
  // escala antes de concluir que no hay marca. Que se vea por qué tarda.
  ocupar(bVerificar, true, 'Verificando', 'primero a escala nativa, después la búsqueda completa');
  try {
    const r = await fetch('/api/verificar', { method: 'POST', body: cuerpo });
    const d = await r.json();
    if (!r.ok) throw new Error(motivo(d, 'no pude verificar'));

    mostrarConstancia(d);
  } catch (err) {
    veredicto('no', 'No se pudo verificar', String(err.message || err));
  } finally {
    ocupar(bVerificar, false);
  }
});

/* La constancia: quién firmó, cuándo, qué pieza. Los 16 bytes son el radicado
   que la resuelve, no el mensaje. */
const FECHA = new Intl.DateTimeFormat('es-CO', {
  dateStyle: 'long', timeStyle: 'short',
});

/* El cotejo por región. La misma marca leída por celdas: un canal degrada la
   imagen entera de forma leve y no marca nada; una edición local se delata sola.
   Se dibuja sobre la lámina porque la degradación se ve, no se lee. */
function pintarCotejo(c) {
  const capa = $('cotejo-verificar');
  const nota = $('nota-cotejo');
  capa.hidden = true;
  capa.replaceChildren();
  nota.hidden = c === null || c === undefined;
  if (!c) return;

  const { filas, columnas, mapa, celda_px, marcadas, celdas, alterada, grupo_mayor } = c;
  // Los límites se declaran con el mismo peso que el hallazgo: qué se detecta,
  // desde qué tamaño, y qué no se distingue del canal.
  const limites = `Detecta ediciones desde unos 160 px de lado; por debajo pueden pasar. `
    + `Un cambio uniforme sobre toda la imagen no se distingue del canal.`;
  nota.dataset.alterada = alterada ? 'si' : 'no';
  nota.textContent = alterada
    ? `Cotejo por región: la marca no coincide en ${marcadas} de ${celdas} celdas de ${celda_px} px, `
      + `y ${grupo_mayor} de ellas son contiguas. ${limites}`
    : `Cotejo por región: sin alteración local. ${marcadas} de ${celdas} celdas de ${celda_px} px `
      + `no coinciden, dispersas —el ruido de fondo y el canal dejan esa cantidad—. ${limites}`;
  if (!alterada) return;

  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${columnas} ${filas}`);
  svg.setAttribute('preserveAspectRatio', 'none');

  const fondos = document.createElementNS(NS, 'g');
  // El trazo va a dos tonos y en dos pasadas: primero todas las bases claras,
  // después todas las de óxido. Una sola pasada dejaría la base de una celda
  // tapando el trazo de su vecina. Sin la base, el rayado se camufla cuando lo
  // que se editó es de un color parecido al óxido -- probado con un bloque rojo
  // pegado: sólo se leía en los bordes.
  const base = document.createElementNS(NS, 'g');
  const encima = document.createElementNS(NS, 'g');
  for (let f = 0; f < filas; f++) {
    for (let col = 0; col < columnas; col++) {
      if (mapa[f][col] !== '1') continue;
      const r = document.createElementNS(NS, 'rect');
      r.setAttribute('x', col); r.setAttribute('y', f);
      r.setAttribute('width', 1); r.setAttribute('height', 1);
      r.setAttribute('class', 'cotejo__celda');
      fondos.append(r);
      for (const [g, clase] of [[base, 'cotejo__raya cotejo__raya--base'],
                                [encima, 'cotejo__raya']]) {
        const l = document.createElementNS(NS, 'line');
        l.setAttribute('x1', col); l.setAttribute('y1', f + 1);
        l.setAttribute('x2', col + 1); l.setAttribute('y2', f);
        l.setAttribute('class', clase);
        g.append(l);
      }
    }
  }
  svg.append(fondos, base, encima);
  capa.append(svg);
  capa.hidden = false;
}

function mostrarConstancia(d) {
  const legible = d.identificador !== null;
  const sello = $('sello-verificar');
  $('id-verificar').textContent = legible ? grupos(d.identificador) : 'no hay marca que leer';
  sello.dataset.legible = legible ? 'si' : 'no';
  sello.hidden = false;
  if (legible) estampar(sello);

  pintarCotejo(d.cotejo);

  const e = d.entrada;
  $('constancia').hidden = d.estado !== 'verificado';
  if (d.estado === 'verificado') {
    $('c-emisor').textContent = e.nombre;
    $('c-fecha').textContent = FECHA.format(new Date(e.fecha));
    $('c-titulo').textContent = e.titulo;
    const hay = Boolean(e.enlace);
    $('fila-enlace').hidden = !hay;
    if (hay) { $('c-enlace').href = e.enlace; $('c-enlace').textContent = e.enlace; }
  }

  // El veredicto nunca acusa: dice de quién es, qué le pasó, o que no pudo leer
  // una marca. «Alterada» es una medición —estas celdas no llevan los bits que
  // deberían—, no una imputación.
  if (d.estado === 'verificado' && d.cotejo?.alterada) {
    veredicto('alterada', 'Alterada después de emitida',
      `${e.nombre} · ${d.cotejo.marcadas} de ${d.cotejo.celdas} celdas · ${d.ms} ms`);
  } else if (d.estado === 'verificado') {
    veredicto('ok', `Emitida por ${e.nombre}`,
      `${FECHA.format(new Date(e.fecha))} · ${d.via} · ${d.ms} ms`);
  } else if (d.estado === 'sin_asiento') {
    veredicto('ok', d.veredicto, `${d.motivo} · ${d.ms} ms`);
  } else {
    veredicto('no', d.veredicto, `${d.motivo} · ${d.dimensiones} · ${d.ms} ms`);
  }
}

/* ─── banco de ataques ──────────────────────────────────────────── */

const MARCAS = {
  ok: '<svg viewBox="0 0 16 16" class="marca" aria-hidden="true"><path d="M2.5 8.6 6.2 12.3 13.5 4"/></svg>',
  no: '<svg viewBox="0 0 16 16" class="marca" aria-hidden="true"><path d="M3.6 3.6 12.4 12.4M12.4 3.6 3.6 12.4"/></svg>',
  corriendo: '<svg viewBox="0 0 16 16" class="marca" aria-hidden="true"><circle cx="8" cy="8" r="5.2"/></svg>',
};

const banco = {
  ataques: [], medicion: {}, desactualizada: null, token: null,
  activo: 0, ocupado: false, res: new Map(),

  cargar(firma) {
    this.token = firma.token;
    this.res.clear();
    this.activo = 0;
    this.pintar();
  },

  abrir() {
    if (!this.token) {
      veredicto('reposo', 'Banco cerrado', 'firmá una imagen primero');
      $('caso').textContent = 'Firmá una imagen para abrir el banco.';
    } else {
      this.elegir(this.activo);
    }
  },

  pintar() {
    const pasos = this.ataques.map((a, i) => {
      const li = document.createElement('li');
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'paso';
      b.disabled = !this.token;
      b.setAttribute('aria-current', String(i === this.activo));
      b.dataset.estado = this.res.get(a.clave)?.estado ?? '';
      b.innerHTML = '<span class="paso__t"></span><span class="paso__tasa"></span><span class="paso__e"></span>';
      b.querySelector('.paso__t').textContent = a.titulo;
      // La tasa medida se muestra siempre: un fallo en tarima tiene que leerse
      // como resultado declarado, no como sorpresa.
      if (a.tasa) b.querySelector('.paso__tasa').textContent = `${a.tasa.pct} %`;
      b.querySelector('.paso__e').innerHTML = MARCAS[this.res.get(a.clave)?.estado] ?? '';
      b.addEventListener('click', () => this.elegir(i, true));
      li.append(b);
      return li;
    });

    /* El servidor se niega a mostrar tasas medidas con otro perfil del que firma,
       y hace bien. Pero sin esto los ocho porcentajes desaparecían y nada decía
       por qué: en tarima eso se lee como que la pantalla se rompió, no como la
       decisión deliberada que es. El aviso dice qué no coincide y cómo rehacerlo. */
    if (this.desactualizada?.length) {
      const li = document.createElement('li');
      li.className = 'rail__aviso';
      li.textContent = `Sin porcentajes medidos: ${this.desactualizada.join('; ')}. `
        + 'Rehacelos con web/tasas.py y el perfil en uso.';
      pasos.push(li);
    }
    $('rail').replaceChildren(...pasos);
  },

  elegir(i, correr = false) {
    this.activo = i;
    const a = this.ataques[i];
    this.pintar();
    const n = this.medicion.imagenes?.length;
    const tasa = a.tasa && n ? ` · recupera ${a.tasa.ok} de ${a.tasa.n} sobre ${n} fotografías` : '';
    $('caso').textContent = (a.cadena === '—' ? 'Sin operaciones' : a.cadena) + tasa;

    const previo = this.res.get(a.clave);
    if (previo?.datos) { this.mostrar(previo.datos); return; }
    veredicto('reposo', a.titulo, 'clic de nuevo para cotejar');
    $('medidas').textContent = '';
    if (correr) this.correr();
  },

  async correr() {
    if (!this.token || this.ocupado) return;
    const a = this.ataques[this.activo];
    this.res.set(a.clave, { estado: 'corriendo' });
    this.pintar();
    this.ocupado = true;
    veredicto('corriendo', 'Cotejando…', a.titulo);

    const cuerpo = new FormData();
    cuerpo.append('token', this.token);
    cuerpo.append('clave', a.clave);
    try {
      const r = await fetch('/api/cotejar', { method: 'POST', body: cuerpo });
      const d = await r.json();
      if (!r.ok) throw new Error(motivo(d, 'no pude cotejar'));
      this.res.set(a.clave, { estado: d.exacto ? 'ok' : 'no', datos: d });
      this.mostrar(d);
    } catch (err) {
      this.res.set(a.clave, { estado: 'no' });
      veredicto('no', 'Cotejo interrumpido', String(err.message || err));
    } finally {
      this.ocupado = false;
      this.pintar();
    }
  },

  mostrar(d) {
    const img = $('l-pruebas');
    img.onload = () => ajustar($('montaje-caja'), img);
    img.src = d.lamina;
    img.alt = `Lámina después de: ${this.ataques[this.activo].titulo}`;
    img.hidden = false;
    $('t-pruebas').hidden = true;

    const g = d.diagnostico;
    $('medidas').textContent =
      `${d.entrada} → ${d.salida} · ${d.pixeles_restantes} % de los píxeles · ` +
      `z ${g.z} · escala ${g.escala} · ${g.teselas} teselas · ${d.ms} ms`;

    veredicto(d.exacto ? 'ok' : 'no', d.veredicto,
      d.exacto ? `exacto, 16 de 16 bytes · ${d.via}` : d.motivo);
  },
};

/* ─── teclado ───────────────────────────────────────────────────── */

/* Sin barra visible: en tarima el operador ya los sabe y la pantalla no tiene
   por qué cargar con la chuleta. Están en web/README.md. */
document.addEventListener('keydown', (ev) => {
  if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
    if (ev.key === 'Escape') document.activeElement.blur();
    return;
  }
  const i = '123'.indexOf(ev.key);
  if (i >= 0) { ev.preventDefault(); mostrar(VISTAS[i]); return; }

  if ($('v-pruebas').hidden || !banco.token) return;
  if (ev.key === 'ArrowRight' || ev.key === ' ') {
    ev.preventDefault();
    banco.elegir(Math.min(banco.activo + 1, banco.ataques.length - 1), true);
  } else if (ev.key === 'ArrowLeft') {
    ev.preventDefault();
    banco.elegir(Math.max(banco.activo - 1, 0));
  } else if (ev.key === 'Enter') {
    ev.preventDefault();
    banco.correr();
  }
});

/* ─── arranque ──────────────────────────────────────────────────── */

(async () => {
  try {
    const d = await (await fetch('/api/ataques')).json();
    banco.ataques = d.ataques;
    banco.medicion = d.medicion || {};
    banco.desactualizada = d.desactualizada || null;
    banco.pintar();

  } catch {
    veredicto('no', 'Servidor sin respuesta', 'levantá uvicorn y recargá');
  }
})();

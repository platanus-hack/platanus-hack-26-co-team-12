/* Deck — navegación y cronómetro.
 *
 * IIFE: comparte documento con nadie hoy, pero la regla de la casa es que
 * ningún script clásico exponga nombres al ámbito global. `app.js` declara
 * `$`, `banco`, `mostrar`... con `const`, y una colisión mata el script entero
 * antes de ejecutar su primera línea.
 *
 * El cronómetro no es un adorno: la restricción de la presentación es que la
 * introducción no pase de un minuto, y un minuto no se estima, se mide. Arranca
 * al primer avance y se pone en negativo al pasarse.
 */
(() => {
  'use strict';

  const laminas = [...document.querySelectorAll('.lamina')];
  const hud = document.getElementById('hud');
  const avance = document.getElementById('avance');
  const barra = document.getElementById('avance-barra');
  const reloj = document.getElementById('reloj');
  const meta = document.getElementById('meta');
  const actual = document.getElementById('actual');

  /* La lámina de la demo corta la introducción: hasta ahí corre el minuto. */
  const CORTE = laminas.findIndex((l) => l.classList.contains('lamina--demo'));
  const TOPE = 60;

  let i = 0;
  let t0 = null;

  document.getElementById('total').textContent = laminas.length;

  function pintar() {
    laminas.forEach((l, n) => l.toggleAttribute('data-activa', n === i));
    actual.textContent = i + 1;
    barra.style.transform = `scaleX(${(i + 1) / laminas.length})`;
    meta.textContent = i <= CORTE ? 'intro · 1:00' : 'demo hecha';
    /* La firma se retira en la lámina de marca, donde el nombre ya está grande. */
    document.body.toggleAttribute('data-marca',
      laminas[i].classList.contains('lamina--marca'));
    /* Precargar la siguiente no aplica —no hay medios—, pero sí conviene que el
       navegador tenga el layout resuelto antes de mostrarla. */
  }

  function ir(n) {
    const destino = Math.max(0, Math.min(laminas.length - 1, n));
    if (destino === i) return;
    if (t0 === null) t0 = performance.now();
    i = destino;
    pintar();
  }

  function tic() {
    if (t0 !== null) {
      const s = Math.floor((performance.now() - t0) / 1000);
      reloj.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
      /* Sólo avisa mientras la introducción está en curso: pasada la demo, el
         reloj deja de ser una restricción y no tiene por qué gritar. */
      reloj.toggleAttribute('data-pasado', s > TOPE && i <= CORTE);
    }
    requestAnimationFrame(tic);
  }

  const TECLAS = {
    ArrowRight: () => ir(i + 1),
    ArrowDown: () => ir(i + 1),
    PageDown: () => ir(i + 1),
    ' ': () => ir(i + 1),
    ArrowLeft: () => ir(i - 1),
    ArrowUp: () => ir(i - 1),
    PageUp: () => ir(i - 1),
    Home: () => ir(0),
    End: () => ir(laminas.length - 1),
    f: () => (document.fullscreenElement
      ? document.exitFullscreen()
      : document.documentElement.requestFullscreen()),
    i: () => { hud.hidden = !hud.hidden; avance.hidden = hud.hidden; },
    r: () => { t0 = null; reloj.textContent = '0:00'; reloj.removeAttribute('data-pasado'); },
  };

  document.addEventListener('keydown', (ev) => {
    const fn = TECLAS[ev.key];
    if (!fn) return;
    ev.preventDefault();
    fn();
  });

  /* Clic para avanzar, salvo sobre un enlace: el botón de la demo tiene que
     poder abrirse sin saltar de lámina. */
  document.addEventListener('click', (ev) => {
    if (!ev.target.closest('a')) ir(i + 1);
  });

  pintar();
  requestAnimationFrame(tic);
})();

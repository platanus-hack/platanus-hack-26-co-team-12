/* Landing — lo único que necesita JS: que un CTA abra la pestaña correcta.
 *
 * IIFE OBLIGATORIO, y no es una preferencia de estilo. `app.js` declara con
 * `const` en el ámbito léxico global: $, V, VISTAS, REPOSO, MARCAS, banco,
 * FECHA, veredicto, mostrar, zona, ocupar, ajustar, estampar, grupos,
 * pintarCotejo. Un segundo script clásico que redeclare CUALQUIERA de esos
 * nombres lanza `SyntaxError: Identifier has already been declared` y mata
 * `app.js` entero antes de ejecutar su primera línea — la herramienta quedaría
 * muerta y la página se vería perfecta.
 *
 * El salto lo hace `href="#probalo"` de forma nativa. Acá sólo se conmuta la
 * pestaña, y se hace disparando un click sobre el botón real en vez de llamar
 * a `mostrar()`: `app.js` ya tiene un listener delegado en `#pestanas`, así que
 * esto usa la puerta de entrada pública y no se acopla a nada interno.
 */
(() => {
  'use strict';

  const irA = (vista) => {
    const boton = document.querySelector(
      `#pestanas button[data-vista="${vista}"]`);
    if (boton) boton.click();
  };

  for (const enlace of document.querySelectorAll('a[data-ir]')) {
    enlace.addEventListener('click', () => irA(enlace.dataset.ir));
  }
})();

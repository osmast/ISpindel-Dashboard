/* The pointer is a single static beer glass, drawn by the CSS cursor in assets/input.pcss
 * (`cursor-beer.svg` / `cursor-beer.png`). The animated DOM cursor and its "full on hover" SVG twin
 * were removed: one cursor image everywhere, no mousemove handler, no hover swap, nothing that can
 * jitter or lag behind the pointer.
 *
 * This file intentionally does nothing. It stays in the repository (and in the Dockerfile COPY
 * list) so an old deployment that still references it does not 404; it never sets the
 * `data-beer-cursor` attribute, so the browser's native pointer - the beer glass - is kept.
 */

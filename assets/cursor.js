/* The pointer: a glass of beer that follows the mouse and fills up to the brim - frothy head
 * included - while it is over something clickable.
 *
 * Why a DOM cursor and not `cursor: url(...)`: a cursor image can only be swapped on hover, it
 * cannot be animated. The smooth "the beer rises" needs an element that can be transitioned, so the
 * glass is drawn here and styled in assets/input.pcss as plain CSS (Tailwind only scans main.py and
 * components/*.py - `@source` in input.pcss).
 *
 * The geometry is the 48 x 48 glass of the design this was taken from, kept 1:1 including the clip
 * path of the interior; only the colours are the project ones (its white outline would vanish on the
 * white panels). The static twins are assets/cursor-beer.svg (empty) and
 * assets/cursor-beer-hover.svg (full) - they are the CSS cursors of input.pcss.
 *
 * Our system, not a side car:
 *  - a normal Dash asset: assets/ is linked automatically, and the Dockerfile COPY list carries the
 *    file into the image (a file that is only committed works on the host and 404s in the container);
 *  - the class that hides the native pointer is added **by this script, as its last step**: if
 *    anything above fails the browser keeps its own cursor, and without JavaScript or with reduced
 *    motion the static glass cursors of input.pcss are still in place - the same glass;
 *  - NFR-06: only for a real pointer (`pointer: fine`) - a touch device has no cursor to draw;
 *  - `pointer-events: none`, so clicks reach the page, and the glass is offset by its own rim, so
 *    the rim - not the middle of the glass - is the point that clicks.
 */
(function () {
    "use strict";

    var fine = window.matchMedia("(pointer: fine)").matches;
    var calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!fine || calm) {
        return;
    }

    // the same set of elements as the hover cursor rule of input.pcss and the fizz of bubbles.js
    var CLICKABLE = "a, button, summary, label, select, [role='button'], [role='tab'], " +
                    "[role='radio'], [role='checkbox'], [role='switch'], .cursor-pointer";

    // the rendered glass in px - keep in sync with `.beer-cursor` in assets/input.pcss. The rim of
    // the glass is at 11,10 of the 48 x 48 viewBox, so the glass hangs below-right of the pointer.
    var SIZE = 34;
    var OFFSET_X = 11 / 48 * SIZE;
    var OFFSET_Y = 10 / 48 * SIZE;

    var GLASS =
        '<svg class="beer-cursor-glass" viewBox="0 0 48 48" width="100%" height="100%" fill="none">' +
          '<defs>' +
            '<clipPath id="beer-cursor-inner">' +
              '<path d="M12 12 H28 L26 38 C26 39.1 25.1 40 24 40 H16 C14.9 40 14 39.1 14 38' +
                    ' L12 12 Z"/>' +
            '</clipPath>' +
            '<linearGradient id="beer-cursor-beer" x1="0" y1="0" x2="1" y2="0">' +
              '<stop offset="0%" stop-color="#E67E22"/>' +
              '<stop offset="60%" stop-color="#F39C12"/>' +
              '<stop offset="100%" stop-color="#F1C40F"/>' +
            '</linearGradient>' +
          '</defs>' +
          '<path d="M27 16 H33 C35.2 16 37 17.8 37 20 V28 C37 30.2 35.2 32 33 32 H26"' +
                ' stroke="#0057B7" stroke-width="3" stroke-linecap="round"/>' +
          '<path d="M11 10 H29 L26.8 38.2 C26.7 39.8 25.3 41 23.7 41 H16.3 C14.7 41 13.3 39.8' +
                ' 13.2 38.2 L11 10 Z" fill="#FFFFFF" fill-opacity="0.85"/>' +
          '<g clip-path="url(#beer-cursor-inner)">' +
            '<rect class="beer-liquid" x="10" y="11" width="20" height="29"' +
                  ' fill="url(#beer-cursor-beer)"/>' +
            '<circle class="beer-cursor-bubble" cx="16" cy="30" r="1" fill="#FFFFFF"' +
                    ' opacity="0.6"/>' +
            '<circle class="beer-cursor-bubble" cx="23" cy="24" r="1.2" fill="#FFFFFF"' +
                    ' opacity="0.6"/>' +
            '<circle class="beer-cursor-bubble" cx="18" cy="18" r="0.8" fill="#FFFFFF"' +
                    ' opacity="0.6"/>' +
          '</g>' +
          '<path d="M11 10 H29 L26.8 38.2 C26.7 39.8 25.3 41 23.7 41 H16.3 C14.7 41 13.3 39.8' +
                ' 13.2 38.2 L11 10 Z" stroke="#0057B7" stroke-width="2.5" stroke-linejoin="round"/>' +
          '<line x1="14.5" y1="14" x2="15.5" y2="36" stroke="#0057B7" stroke-width="1.5"' +
                ' stroke-linecap="round" opacity="0.4"/>' +
          '<g class="beer-foam">' +
            '<path d="M10 11 C9 11 8 9.5 9 8 C9.8 6.8 11.5 7 12 8 C12.8 6 15 6 16 7.5 C17 6' +
                  ' 19.5 6 20.5 7.5 C21.5 6 24 6 25 7.5 C26 6.5 28 7 28.5 8 C29.5 9.5 28.5 11' +
                  ' 27.5 11 Z" fill="#FFFFFF" stroke="#0057B7" stroke-width="1"/>' +
          '</g>' +
          '<circle cx="11" cy="10" r="2.2" fill="#0057B7" stroke="#FFFFFF" stroke-width="1"/>' +
        '</svg>';


    var glass = document.createElement("div");
    glass.className = "beer-cursor";
    glass.innerHTML = GLASS;
    document.body.appendChild(glass);

    var x = 0;
    var y = 0;
    var queued = false;

    function place() {
        queued = false;
        glass.style.transform =
            "translate3d(" + (x - OFFSET_X) + "px, " + (y - OFFSET_Y) + "px, 0)";
    }

    function over(event) {
        return !!(event.target && event.target.closest && event.target.closest(CLICKABLE));
    }

    document.addEventListener("mousemove", function (event) {
        x = event.clientX;
        y = event.clientY;
        glass.classList.add("is-visible");       // no glass in the corner before the first move
        glass.classList.toggle("is-hovering", over(event));
        if (!queued) {                           // one position update per animation frame
            queued = true;
            requestAnimationFrame(place);
        }
    }, { passive: true });

    // safety net: the element under the pointer can change without a movement (a refreshed table, a
    // dialog that opens under the glass) - and when the pointer leaves the window, nothing should be
    // left hanging at the old position
    document.addEventListener("mouseover", function (event) {
        glass.classList.toggle("is-hovering", over(event));
    });
    document.addEventListener("mouseout", function (event) {
        if (!event.relatedTarget) {
            glass.classList.remove("is-visible", "is-hovering");
        }
    });

    // the last step, once everything above is wired: from here on the native pointer is hidden. If
    // an earlier line threw, this class is never added and the browser keeps its own cursor.
    document.documentElement.classList.add("beer-cursor");
})();

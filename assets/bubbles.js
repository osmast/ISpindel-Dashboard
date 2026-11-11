/* A short CO2 bubble burst, only on click - the fermentation bubbles of the beer theme.
 *
 * It used to follow the pointer on every mousemove, which made the page feel jittery. It now does
 * nothing while the mouse moves and releases a small puff only when the user clicks. That is one
 * event per intent instead of one per pixel, so the animation never competes with the pointer.
 *
 * Dash links every .js under assets/ automatically (like card_state.js), so no import in main.py
 * is needed - but the file has to be listed in the Dockerfile COPY list, or it works on the host
 * and 404s in the container.
 *
 * The bubbles are created here, styled in assets/input.pcss as **plain CSS** (`.beer-bubbles` /
 * `.beer-bubble`): Tailwind only scans main.py and components/*.py (`@source` in input.pcss), so a
 * utility class invented in JavaScript would never reach tailwind.css and the bubbles would stay
 * invisible.
 *
 * Deliberately a visual extra, so it stays out of the way:
 *  - NFR-06: only for a real pointer (`pointer: fine`);
 *  - no motion for users who asked for reduced motion;
 *  - a hard cap on the bubbles in the air, so a double click does not flood the DOM - and none of
 *    this touches a Dash callback (the page's 15 s refresh is unaffected).
 */
(function () {
    "use strict";

    var fine = window.matchMedia("(pointer: fine)").matches;
    var calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!fine || calm) {
        return;
    }

    var MAX_LIVE = 32;          // hard cap on the bubbles in the air at once

    var layer = null;
    var live = 0;

    function overlay() {
        if (!layer || !layer.isConnected) {     // a hot reload can drop the node
            layer = document.createElement("div");
            layer.className = "beer-bubbles";
            document.body.appendChild(layer);
        }
        return layer;
    }

    // one bubble of `size` px, centered on the pointer, with its own rise, drift, wobble and pop
    function bubble(px, py, size) {
        var el = document.createElement("span");
        el.className = "beer-bubble";
        el.style.left = px + "px";
        el.style.top = py + "px";
        el.style.width = size + "px";
        el.style.height = size + "px";
        // distance and speed follow the size: a fat bubble travels further and is quicker
        el.style.setProperty("--rise", (-30 - size * 2.2 - Math.random() * 60).toFixed(0) + "px");
        el.style.setProperty("--drift", (Math.random() * 44 - 22).toFixed(0) + "px");
        el.style.animationDuration = (900 + size * 16 + Math.random() * 600).toFixed(0) + "ms";

        var skin = document.createElement("span");
        skin.className = Math.random() < 0.28 ? "beer-bubble-skin is-foam" : "beer-bubble-skin";
        if (Math.random() < 0.35) {         // a few are not quite round - that is the bubbly look
            skin.style.borderRadius = "58% 42% 52% 48% / 46% 55% 45% 54%";
        }
        skin.style.animationDuration = (360 + Math.random() * 560).toFixed(0) + "ms";
        skin.style.animationDelay = (-Math.random() * 500).toFixed(0) + "ms";
        el.appendChild(skin);

        live += 1;
        el.addEventListener("animationend", function (event) {
            if (event.target !== el || event.animationName !== "bubble-rise") {
                return;                      // the wobble of the skin ends here as well
            }
            live -= 1;
            el.remove();
        });
        overlay().appendChild(el);
    }

    // one burst at the click point: a handful of bubbles, capped by MAX_LIVE
    document.addEventListener("click", function (event) {
        var count = 3 + Math.floor(Math.random() * 4);
        for (var i = 0; i < count && live < MAX_LIVE; i++) {
            var size = 5 + Math.random() * 20;
            var spread = size * 0.8;
            bubble(event.clientX + (Math.random() * spread - spread / 2),
                   event.clientY + (Math.random() * spread - spread / 2), size);
        }
    }, { passive: true });
})();

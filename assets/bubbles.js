/* A CO2 bubble trail that follows the pointer - the fermentation bubbles of the beer theme.
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
 *  - NFR-06: only for a real pointer (`pointer: fine`) - a phone has no cursor to trail, and the
 *    effect would just cost battery.
 *  - no motion for users who asked for reduced motion (the same courtesy as
 *    `motion-reduce:animate-none` on the panels and the accordion's media query).
 *  - a hard cap on the bubbles in the air and a minimum gap between two puffs, so a fast mouse does
 *    not flood the DOM - and none of this touches a Dash callback (the page's 15 s refresh is
 *    unaffected).
 *
 * The trail is bubblier over something clickable (the same set of elements the hover pointer of
 * input.pcss covers): there a puff is up to three bubbles and they go up to ~30 px, while a plain
 * move leaves one small bubble or none - fermentation that starts to work when you touch it.
 */
(function () {
    "use strict";

    var fine = window.matchMedia("(pointer: fine)").matches;
    var calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!fine || calm) {
        return;
    }

    // everything the pointer turns into a hand over - the same set the hover pointer of
    // input.pcss covers. Over one of these the trail fizzes harder.
    var CLICKABLE = "a, button, summary, label, select, [role='button'], [role='tab'], " +
                    "[role='radio'], [role='checkbox'], [role='switch'], .cursor-pointer";

    var MAX_LIVE = 44;          // hard cap on the bubbles in the air at once
    var GAP_MOVE_MS = 40;       // minimum gap between two puffs while the pointer just moves
    var GAP_HOVER_MS = 14;      // ... and while it is over something clickable (a real fizz)

    var layer = null;
    var live = 0;
    var lastPuff = 0;
    var queued = false;
    var x = 0;
    var y = 0;
    var hot = false;

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

    // one puff at the pointer: a single small bubble while it just moves, up to three fat ones
    // while it is over something clickable
    function puff() {
        var count = hot ? 1 + Math.floor(Math.random() * 3) : (Math.random() < 0.35 ? 0 : 1);
        for (var i = 0; i < count && live < MAX_LIVE; i++) {
            var size = hot ? 6 + Math.random() * 24 : 4 + Math.random() * 18;
            var spread = size * 0.7;
            bubble(x + (Math.random() * spread - spread / 2),
                   y + (Math.random() * spread - spread / 2), size);
        }
    }

    document.addEventListener("mousemove", function (event) {
        x = event.clientX;
        y = event.clientY;
        hot = !!(event.target && event.target.closest && event.target.closest(CLICKABLE));
        var now = Date.now();
        if (queued || now - lastPuff < (hot ? GAP_HOVER_MS : GAP_MOVE_MS)) {
            return;
        }
        queued = true;
        requestAnimationFrame(function () {
            queued = false;
            lastPuff = Date.now();
            puff();
        });
    }, { passive: true });
})();

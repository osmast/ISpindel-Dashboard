/* Remembers which accordion cards are open.
 *
 * The cards are plain <details> elements, so the browser toggles them itself - instant, no
 * round trip. But update_dashboard() rebuilds the whole card tree every refresh, and Dash
 * gives a component a React key of its `id`, or else its index path (see createContainer in
 * dash_renderer). A <details> whose key shifts is unmounted and mounted again, which throws
 * away its `open` attribute - that is why the cards kept closing.
 *
 * So on every toggle we push the current open set into the `open_cards` store; main.py
 * renders `open` from it again, and the state survives any remount.
 */
(function () {
    "use strict";

    function publish() {
        var open = {};
        var cards = document.querySelectorAll("details[data-card]");
        for (var i = 0; i < cards.length; i++) {
            open[cards[i].dataset.card] = cards[i].open;
        }
        if (window.dash_clientside && window.dash_clientside.set_props) {
            window.dash_clientside.set_props("open_cards", {data: open});
        }
    }

    // `toggle` does not bubble, so listen in the capture phase
    document.addEventListener("toggle", function (event) {
        var target = event.target;
        if (target && target.dataset && target.dataset.card !== undefined) {
            publish();
        }
    }, true);
})();
